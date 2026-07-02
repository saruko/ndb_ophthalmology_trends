import urllib.request
import pandas as pd
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

os.makedirs("tmp", exist_ok=True)

# Let's test the Excel at 000377138.xlsx (likely Sugi 2024)
url = "https://www.env.go.jp/content/000377138.xlsx"
dest = "tmp/env_sugi2024.xlsx"

if not os.path.exists(dest):
    print(f"Downloading {url} to {dest}...")
    urllib.request.urlretrieve(url, dest)

try:
    xl = pd.ExcelFile(dest)
    print("Sheets in Env Excel:")
    print(xl.sheet_names)
    
    # Read the first sheet
    df = xl.parse(xl.sheet_names[0])
    csv_path = "tmp/env_sugi2024_preview.csv"
    df.to_csv(csv_path, encoding='utf-8', index=False)
    print(f"Saved preview to {csv_path}. Shape: {df.shape}")
except Exception as e:
    print(f"Error: {e}")
