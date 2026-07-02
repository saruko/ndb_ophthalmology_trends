import urllib.request
import pandas as pd
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

os.makedirs("tmp", exist_ok=True)

# Let's inspect multiple files from the Hanako list to see where the actual pollen data is.
# For example, 000072400.xlsx is 2021 Kanto? Let's check sheet names.
urls = [
    "https://www.env.go.jp/content/000072400.xlsx",
    "https://www.env.go.jp/content/000072407.xlsx",
    "https://www.env.go.jp/content/000072415.xlsx",
    "https://www.env.go.jp/content/000072424.xlsx"
]

for url in urls:
    filename = url.split("/")[-1]
    dest = f"tmp/{filename}"
    if not os.path.exists(dest):
        print(f"Downloading {url}...")
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            continue
            
    try:
        xl = pd.ExcelFile(dest)
        print(f"\nFile: {filename}")
        print("Sheets:", xl.sheet_names)
    except Exception as e:
        print(f"Error reading {filename}: {e}")
