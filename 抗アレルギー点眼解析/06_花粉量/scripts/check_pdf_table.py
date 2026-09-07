import pdfplumber
import sys

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = "tmp/env_sugi2024.pdf"

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            print(f"\n--- Page {i+1} ---")
            text = page.extract_text()
            print("--- Text Preview (first 300 chars) ---")
            if text:
                print(text[:300])
            
            tables = page.extract_tables()
            print(f"--- Tables found: {len(tables)} ---")
            for t_idx, table in enumerate(tables):
                print(f"Table {t_idx+1} shape: {len(table)} rows x {len(table[0]) if table else 0} cols")
                print("First 5 rows:")
                for row in table[:5]:
                    print(row)
except Exception as e:
    print(f"Error: {e}")
