import os
import urllib.request
import pandas as pd
import argparse
from utils import clean_prefecture_name

def download_npo_file(year, pollen_type):
    """
    NPO法人花粉情報協会から指定された年度と花粉種のExcelファイルをダウンロードする。
    """
    os.makedirs("tmp", exist_ok=True)
    
    # 2019〜2022年はWayback Machineからダウンロード
    if year in [2019, 2020, 2021, 2022]:
        timestamp_map = {
            2022: "20230601000000",
            2021: "20220601000000",
            2020: "20210601000000",
            2019: "20200601000000"
        }
        ts = timestamp_map[year]
        url = f"https://web.archive.org/web/{ts}id_/https://pollen-net.com/zennkoku24/{pollen_type}{year}.xls"
        dest = f"tmp/npo_{pollen_type}{year}.xls"
        
        if os.path.exists(dest):
            return dest
            
        print(f"Downloading {year} {pollen_type} from Wayback: {url}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(dest, 'wb') as f:
                    f.write(response.read())
            return dest
        except Exception as e:
            if os.path.exists(dest):
                os.remove(dest)
            raise Exception(f"Failed to download NPO pollen data from Wayback for {year} ({pollen_type}): {e}")
            
    # 2023年以降（またはその他）は通常ダウンロード
    exts = [".xlsx", ".xls"]
    base_folder = "zennkoku26" if year >= 2023 else "zennkoku24"
    downloaded_path = None
    last_error = None
    
    for ext in exts:
        url = f"https://pollen-net.com/{base_folder}/{pollen_type}{year}{ext}"
        dest = f"tmp/npo_{pollen_type}{year}{ext}"
        
        if os.path.exists(dest):
            return dest
            
        print(f"Downloading {url} to {dest}...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(dest, 'wb') as f:
                    f.write(response.read())
            downloaded_path = dest
            break
        except Exception as e:
            last_error = e
            if os.path.exists(dest):
                os.remove(dest)
                
    if downloaded_path:
        return downloaded_path
    else:
        raise Exception(f"Failed to download NPO pollen data for {year} ({pollen_type}): {last_error}")


def parse_npo_excel(file_path, year, pollen_type):
    """
    NPO法人のExcelファイルをパースして、標準フォーマットのリストを取得する。
    """
    # Excelファイルを読み込む。最初のシート。
    # エンジンはxlsの場合は xlrd, xlsxの場合は openpyxl が使われる
    xl = pd.ExcelFile(file_path)
    sheet_name = xl.sheet_names[0]
    df = xl.parse(sheet_name, header=None)
    
    # 文字列に変換して検索しやすくする
    df_str = df.astype(str)
    
    # "都道府県" というセルを探す
    pref_cells = []
    for r in range(df_str.shape[0]):
        for c in range(df_str.shape[1]):
            val = df_str.iloc[r, c].strip()
            if "都道府県" in val:
                pref_cells.append((r, c))
                
    if not pref_cells:
        raise Exception(f"Could not find '都道府県' cell in {file_path}")
        
    # "期間中合計", "累計" または "合計" が含まれる行を探す
    total_rows = []
    priority_keywords = ["期間中合計", "期間合計", "総合計", "総計", "累計"]
    
    # 優先キーワードで検索
    for r in range(df_str.shape[0]):
        row_vals = df_str.iloc[r, :].values
        if any(any(kw in str(val) for kw in priority_keywords) for val in row_vals if pd.notna(val)):
            total_rows.append(r)
            
    if not total_rows:
        # フォールバック: 単に「合計」が含まれるが、月合計や小計ではないものを探す
        for r in range(df_str.shape[0]):
            row_vals = df_str.iloc[r, :].values
            for val in row_vals:
                val_str = str(val)
                if "合計" in val_str and not any(m in val_str for m in ["月", "小計", "平均", "比"]):
                    total_rows.append(r)
                    break
                    
    if not total_rows:
        raise Exception(f"Could not find total row in {file_path}")
    
    # 最初の合計行を使用する（複数ある場合は通常同一内容）
    total_row_idx = total_rows[0]
    print(f"Found '都道府県' cells at {pref_cells}, total row at index {total_row_idx}")
    
    results = []
    
    for r_pref, c_pref in pref_cells:
        # 都道府県セルの行において、右方向にスキャン
        # 通常、都道府県名はその行の右側の列にある
        for col_idx in range(c_pref + 1, df.shape[1]):
            val = df.iloc[r_pref, col_idx]
            if pd.isna(val):
                continue
            
            pref_name = clean_prefecture_name(str(val))
            if not pref_name:
                continue
                
            # 地点名は1行下にある
            station_name = df.iloc[r_pref + 1, col_idx]
            if pd.isna(station_name):
                station_name = "不明"
            else:
                station_name = str(station_name).strip().replace("\n", "").replace("　", "")
                
            # 合計値を取得
            total_val = df.iloc[total_row_idx, col_idx]
            try:
                # カンマなどを除外してfloatに変換
                if isinstance(total_val, str):
                    total_val = total_val.replace(",", "")
                total_float = float(total_val)
            except Exception:
                total_float = 0.0
                
            results.append({
                "year": year,
                "source": "NPO",
                "prefecture": pref_name,
                "station": station_name,
                "pollen_type": "スギ" if pollen_type == "sugi" else "ヒノキ",
                "total_scattering": total_float
            })
            
    return results

def get_npo_pollen(year, pollen_type):
    file_path = download_npo_file(year, pollen_type)
    return parse_npo_excel(file_path, year, pollen_type)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NPO Pollen Net Data Gatherer")
    parser.add_argument("--year", type=int, default=2024, help="Target year")
    parser.add_argument("--type", type=str, default="sugi", choices=["sugi", "hinoki"], help="Pollen type")
    args = parser.parse_args()
    
    try:
        data = get_npo_pollen(args.year, args.type)
        df = pd.DataFrame(data)
        out_path = f"tmp/npo_{args.type}_{args.year}.csv"
        df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"Successfully processed NPO data. Output saved to {out_path}")
        print(df.head(5))
    except Exception as e:
        print(f"Error processing NPO data: {e}")
