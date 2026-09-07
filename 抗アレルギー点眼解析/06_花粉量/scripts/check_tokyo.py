import zipfile
import os
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

csv_file = "tmp/tokyo_r6/r6_cedar_archive.csv"

# Try UTF-8-sig
try:
    df = pd.read_csv(csv_file, encoding='utf-8-sig')
    print("Read successfully with utf-8-sig!")
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    print("First 5 rows:")
    print(df.head(5))
    print("Last 5 rows:")
    print(df.tail(5))
except Exception as e:
    print(f"Error reading: {e}")
