import os
import urllib.request
import zipfile
import pandas as pd
import argparse
from utils import clean_prefecture_name

def download_tokyo_zip(year, pollen_type):
    """
    東京都アレルギー情報naviから指定された年度・花粉種別のZIPファイルをダウンロードし、解凍する。
    """
    os.makedirs("tmp", exist_ok=True)
    
    # 年度を和暦（令和）に変換 (令和1年 = 2019年, 令和6年 = 2024年, 令和7年 = 2025年)
    reiwa_year = year - 2018
    if reiwa_year <= 0:
        raise Exception(f"Unsupported year for Tokyo pollen data: {year} (Pre-Reiwa years are not mapped)")
        
    pollen_map = {
        "sugi": "cedar",
        "hinoki": "japanese_cypress",
        "total": "total"
    }
    p_name = pollen_map.get(pollen_type)
    if not p_name:
        raise Exception(f"Unsupported pollen type for Tokyo data: {pollen_type}")
        
    url = f"https://www.hokeniryo1.metro.tokyo.lg.jp/allergy/pollen/archive/csv/r{reiwa_year}_{p_name}_archive.csv.zip"
    dest_zip = f"tmp/tokyo_r{reiwa_year}_{p_name}.zip"
    dest_dir = f"tmp/tokyo_r{reiwa_year}_{p_name}_extracted"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    if not os.path.exists(dest_zip):
        print(f"Downloading Tokyo data from {url}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response, open(dest_zip, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            raise Exception(f"Failed to download Tokyo data from {url}: {e}")
            
    # 解凍
    print(f"Extracting ZIP to {dest_dir}...")
    with zipfile.ZipFile(dest_zip, 'r') as zip_ref:
        zip_ref.extractall(dest_dir)
        # 解凍されたCSVファイルパスを見つける
        csv_files = [f for f in zip_ref.namelist() if f.endswith(".csv") and not f.startswith("__MACOSX")]
        if not csv_files:
            raise Exception(f"No CSV file found in ZIP {dest_zip}")
        return os.path.join(dest_dir, csv_files[0])

def parse_tokyo_csv(csv_path, year, pollen_type):
    """
    東京都のCSVファイルを読み込み、各観測地点の総飛散量を集計する。
    """
    # 東京都のCSVは通常 UTF-8-sig (BOM付き)
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except Exception as e:
        print(f"Warning: Failed to read CSV with utf-8-sig ({e}). Trying cp932.")
        df = pd.read_csv(csv_path, encoding='cp932')
        
    print(f"Parsing Tokyo CSV: {csv_path}. Columns: {df.columns.tolist()[:5]}...")
    
    # 各列の合計を計算
    results = []
    
    # 日付列を除外した観測地点の列リストを作成
    station_cols = [col for col in df.columns if col not in ['日付', 'Unnamed: 13', '（単位：個/cm2）'] and not col.startswith('Unnamed')]
    
    for col in station_cols:
        # 数値に変換可能なものを抽出して合計
        # カラム内の各セルをfloatに変換
        col_data = df[col]
        numeric_vals = []
        for val in col_data:
            if pd.isna(val):
                continue
            try:
                # カンマなどを除去してfloatキャスト
                val_clean = str(val).replace(",", "").strip()
                numeric_vals.append(float(val_clean))
            except ValueError:
                pass
                
        total_scattering = sum(numeric_vals)
        
        results.append({
            "year": year,
            "source": "Tokyo",
            "prefecture": "東京都",
            "station": col.strip(),
            "pollen_type": "スギ" if pollen_type == "sugi" else "ヒノキ",
            "total_scattering": total_scattering
        })
        
    return results

def get_tokyo_pollen(year, pollen_type):
    csv_path = download_tokyo_zip(year, pollen_type)
    return parse_tokyo_csv(csv_path, year, pollen_type)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tokyo Pollen Data Gatherer")
    parser.add_argument("--year", type=int, default=2024, help="Target year")
    parser.add_argument("--type", type=str, default="sugi", choices=["sugi", "hinoki"], help="Pollen type")
    args = parser.parse_args()
    
    try:
        data = get_tokyo_pollen(args.year, args.type)
        df = pd.DataFrame(data)
        out_path = f"tmp/local_tokyo_{args.type}_{args.year}.csv"
        df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"Successfully processed Tokyo data. Output saved to {out_path}")
        print(df)
    except Exception as e:
        print(f"Error processing Tokyo data: {e}")
