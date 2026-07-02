import pdfplumber
import sys

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = "tmp/hanako_data_2021.pdf"

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        # Let's search all pages for tables or specific keywords like "表2" or "総数"
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and ("月別" in text or "総飛散" in text or "平均スギ" in text or "スギ花粉" in text):
                print(f"\n--- Page {i+1} matches ---")
                print(text[:1000]) # first 1000 chars
                tables = page.extract_tables()
                print(f"Tables on Page {i+1}: {len(tables)}")
                for t_idx, table in enumerate(tables):
                    print(f"  Table {t_idx+1} shape: {len(table)} x {len(table[0]) if table else 0}")
                    for row in table[:5]:
                        print("    ", row)
except Exception as e:
    print(f"Error: {e}")
