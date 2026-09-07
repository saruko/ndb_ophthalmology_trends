import urllib.request
import pandas as pd
import os
import sys

# Ensure output is utf-8
sys.stdout.reconfigure(encoding='utf-8')

os.makedirs("tmp", exist_ok=True)

urls = {
    "sugi2025": "https://pollen-net.com/zennkoku26/sugi2025.xlsx",
    "sugi2024": "https://pollen-net.com/zennkoku26/sugi2024.xlsx",
    "sugi2023": "https://pollen-net.com/zennkoku26/sugi2023.xls"
}

for name, url in urls.items():
    ext = os.path.splitext(url)[1]
    dest = f"tmp/{name}{ext}"
    
    try:
        xl = pd.ExcelFile(dest)
        print(f"\n--- {name} sheets ---")
        for s in xl.sheet_names:
            print(f"  Sheet: {s}")
        df = xl.parse(xl.sheet_names[0])
        csv_path = f"tmp/{name}_preview.csv"
        df.to_csv(csv_path, encoding='utf-8', index=False)
        print(f"Saved preview to {csv_path}. Shape: {df.shape}")
    except Exception as e:
        print(f"Failed to read/save {dest}: {e}")
