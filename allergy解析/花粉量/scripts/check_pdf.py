import urllib.request
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.env.go.jp/content/000377136.pdf"
dest = "tmp/env_sugi2024.pdf"

os.makedirs("tmp", exist_ok=True)
if not os.path.exists(dest):
    print(f"Downloading {url} to {dest}...")
    urllib.request.urlretrieve(url, dest)

# Try pypdf or pdfplumber to extract text
try:
    import pypdf
    print("pypdf is installed.")
    reader = pypdf.PdfReader(dest)
    print(f"Total pages: {len(reader.pages)}")
    for i, page in enumerate(reader.pages):
        print(f"--- Page {i+1} ---")
        text = page.extract_text()
        print(text[:1000]) # print first 1000 chars of each page
except ImportError:
    print("pypdf is not installed.")

try:
    import pdfplumber
    print("pdfplumber is installed.")
    with pdfplumber.open(dest) as pdf:
        print(f"Total pages in pdfplumber: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            print(f"--- Page {i+1} Table ---")
            table = page.extract_table()
            if table:
                print(f"Found table with {len(table)} rows. First 3 rows:")
                for r in table[:3]:
                    print(r)
            else:
                print("No table found on this page.")
except ImportError:
    print("pdfplumber is not installed.")
