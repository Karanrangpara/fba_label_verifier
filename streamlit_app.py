
import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
from datetime import datetime

def count_field_occurrences(field_values, lines):
    result = {}
    for val in field_values:
        result[val] = sum(1 for line in lines if val in line)
    return result

st.title("📦 Amazon FBA Label Verifier")

amazon_file = st.file_uploader("Upload Amazon FBA Excel File", type=["xlsx"])
label_file = st.file_uploader("Upload Excel File Used for Label Generation", type=["xlsx"])
pdf_file = st.file_uploader("Upload Generated Label PDF", type=["pdf"])

if amazon_file and label_file and pdf_file:
    amazon_df = pd.read_excel(amazon_file)
    label_df = pd.read_excel(label_file)
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")

    amazon_skus = amazon_df.iloc[:, 10].dropna().astype(str).str.strip()
    barcode_skus = label_df['sku_identifier'].astype(str).str.strip()
    barcode_qtys = label_df.set_index('sku_identifier')['print_qty']
    fnsku_list = label_df['fnsku_barcode'].astype(str).str.strip().tolist()
    mrp_list = label_df['mrp'].astype(str).str.strip().unique().tolist()
    mfg_list = label_df['mfg'].astype(str).str.strip().unique().tolist()
    exp_list = label_df['exp'].astype(str).str.strip().unique().tolist()
    valid_skus_set = set(barcode_skus)

    lines = [line.strip() for page in doc for line in page.get_text().split('\n') if line.strip()]
    sku_line_counts = {sku: 0 for sku in valid_skus_set}
    for line in lines:
        if line in sku_line_counts:
            sku_line_counts[line] += 1

    fnsku_counts = count_field_occurrences(fnsku_list, lines)
    mrp_counts = count_field_occurrences(mrp_list, lines)
    mfg_counts = count_field_occurrences(mfg_list, lines)
    exp_counts = count_field_occurrences(exp_list, lines)

    output_rows = []
    for _, row in label_df.iterrows():
        sku = str(row['sku_identifier']).strip()
        fnsku = str(row['fnsku_barcode']).strip()
        mrp = str(row['mrp']).strip()
        mfg = str(row['mfg']).strip()
        exp = str(row['exp']).strip()
        title = str(row['title']).strip()
        print_qty = int(row['print_qty'])
        amazon_qty = amazon_df[amazon_df.iloc[:, 10].astype(str).str.strip() == sku].iloc[0, 9] if sku in amazon_skus.values else None
        pdf_count = sku_line_counts.get(sku, 0)

        verified = (
            print_qty == pdf_count == amazon_qty and
            fnsku_counts.get(fnsku, 0) >= print_qty and
            mrp_counts.get(mrp, 0) >= print_qty and
            mfg_counts.get(mfg, 0) >= print_qty and
            exp_counts.get(exp, 0) >= print_qty
        )

        remarks = []
        if print_qty != amazon_qty:
            remarks.append("Mismatch in Amazon qty")
        if print_qty != pdf_count:
            remarks.append("Mismatch in label count")
        if fnsku_counts.get(fnsku, 0) < print_qty:
            remarks.append("FNSKU missing")
        if mrp_counts.get(mrp, 0) < print_qty:
            remarks.append("MRP missing")
        if mfg_counts.get(mfg, 0) < print_qty:
            remarks.append("MFG date missing")
        if exp_counts.get(exp, 0) < print_qty:
            remarks.append("EXP date missing")

        output_rows.append({
            "print_qty": print_qty,
            "fnsku_barcode": fnsku,
            "sku_identifier": sku,
            "mrp": mrp,
            "mfg": mfg,
            "exp": exp,
            "title": title,
            "pdf_label_count": pdf_count,
            "amazon_shipped_qty": amazon_qty,
            "verified": verified,
            "remarks": "; ".join(remarks) if remarks else ""
        })

    out_df = pd.DataFrame(output_rows)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_filename = f"Verified_Label_Output_{timestamp}.xlsx"
    out_df.to_excel(output_filename, index=False)

    with open(output_filename, "rb") as f:
        st.download_button("📥 Download Verified Excel", f, file_name=output_filename)

    st.success("Verification complete!")
