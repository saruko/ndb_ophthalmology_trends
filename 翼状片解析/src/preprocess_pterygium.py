import os
import glob
import re
import pandas as pd
import numpy as np

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
]

TARGET_DENSEN_CODE = 150080210  # K224 翼状片手術（弁の移植を要するもの）

def clean_count_value(val, imputation_strategy="zero"):
    """
    マスクされた値（10件未満, 例: '-'）のクレンジングと補完
    imputation_strategy: 'zero' (0で補完), 'five' (5で補完), 'random' (1-9の乱数)
    """
    if pd.isna(val) or val == "" or str(val).strip() in ["-", "—", "－", ""]:
        if imputation_strategy == "zero":
            return 0.0
        elif imputation_strategy == "five":
            return 5.0
        elif imputation_strategy == "random":
            return float(np.random.randint(1, 10))
        else:
            return 0.0
    try:
        val_str = str(val).replace(",", "").strip()
        return float(val_str)
    except ValueError:
        return 0.0

def process_sheet(file_path, sheet_name, year, imputation_strategy="zero"):
    """
    Excelの1つのシートから K224 データを抽出する
    """
    print(f"  Reading sheet: {sheet_name}")
    df_sheet = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    
    # 1. 都道府県が並んでいるヘッダー行を検出する
    pref_row_idx = None
    pref_cols = {} # col_idx -> pref_name
    
    for r_idx in range(min(15, len(df_sheet))):
        row_vals = [str(x).strip() for x in df_sheet.iloc[r_idx] if pd.notna(x)]
        if any(p in row_vals for p in ["北海道", "青森県", "東京都", "大阪府"]):
            pref_row_idx = r_idx
            break
            
    if pref_row_idx is None:
        print(f"    Warning: Prefecture row not found in sheet '{sheet_name}' of {os.path.basename(file_path)}")
        return pd.DataFrame()
        
    for c in range(df_sheet.shape[1]):
        val = str(df_sheet.iloc[pref_row_idx, c]).strip()
        for p in PREFECTURES:
            if p in val:
                pref_cols[c] = p
                break
                
    # 2. 分類コード、診療行為名、電算コードの列インデックスを特定
    # 通常、手術ファイルは 1: 区分番号, 3: 電算コード, 4: 診療行為名
    # 実データをスキャンして電算コード 150080210 が一致する行を探す
    densen_col_idx = 3
    target_row_idx = None
    for r_idx in range(pref_row_idx + 1, len(df_sheet)):
        densen_val = df_sheet.iloc[r_idx, densen_col_idx]
        if pd.isna(densen_val):
            continue
        try:
            densen_code = int(float(str(densen_val).strip().replace(",", "")))
            if densen_code == TARGET_DENSEN_CODE:
                target_row_idx = r_idx
                break
        except ValueError:
            continue
            
    if target_row_idx is None:
        print(f"    Warning: Target code {TARGET_DENSEN_CODE} not found in sheet '{sheet_name}'")
        return pd.DataFrame()
        
    # 全都道府県が秘匿（例: 2017年入院）の場合は補完せず欠測として扱う
    raw_vals = [df_sheet.iloc[target_row_idx, c] for c in pref_cols]
    def is_masked(v):
        return pd.isna(v) or str(v).strip() in ["-", "—", "－", ""]
    if all(is_masked(v) for v in raw_vals):
        print(f"    Note: All prefecture values masked in sheet '{sheet_name}' ({year}). Treating as missing.")
        return pd.DataFrame()

    records = []
    for col_idx, pref_name in pref_cols.items():
        if col_idx >= df_sheet.shape[1]:
            continue
        count_raw = df_sheet.iloc[target_row_idx, col_idx]
        count_val = clean_count_value(count_raw, imputation_strategy)
        records.append({
            "prefecture": pref_name,
            "count": count_val
        })

    df_res = pd.DataFrame(records)
    return df_res

def preprocess_pterygium(raw_dir, output_dir, imputation_strategy="zero"):
    """
    生ExcelからK224を抽出し、processed/pterygium_long.csv を生成する
    """
    print(f"Starting preprocess_pterygium with strategy: {imputation_strategy}")
    
    shujutsu_files = glob.glob(os.path.join(raw_dir, "ndb_shujutsu_*.*"))
    years_map = {}
    for f in shujutsu_files:
        m = re.search(r"ndb_shujutsu_(\d{4})\.(xlsx|xls)", os.path.basename(f))
        if m:
            years_map[int(m.group(1))] = f
            
    if not years_map:
        raise FileNotFoundError(f"No ndb_shujutsu_*.xlsx files found in {raw_dir}")
        
    all_records = []
    
    for year, file_path in sorted(years_map.items()):
        print(f"Processing year {year} from {os.path.basename(file_path)}...")
        
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        
        np.random.seed(year)  # random補完用のシード固定
        
        if year == 2014:
            # 2014年は「全体」シートのみ
            sheet = "全体" if "全体" in sheet_names else sheet_names[0]
            df_sheet = process_sheet(file_path, sheet, year, imputation_strategy)
            if not df_sheet.empty:
                df_sheet["year"] = year
                df_sheet["setting"] = "total"
                all_records.append(df_sheet)
        else:
            # 2015年以降は「外来」「入院」
            df_out = pd.DataFrame()
            df_in = pd.DataFrame()
            
            if "外来" in sheet_names:
                df_out = process_sheet(file_path, "外来", year, imputation_strategy)
                if not df_out.empty:
                    df_out["year"] = year
                    df_out["setting"] = "outpatient"
                    all_records.append(df_out)
                    
            if "入院" in sheet_names:
                df_in = process_sheet(file_path, "入院", year, imputation_strategy)
                if not df_in.empty:
                    df_in["year"] = year
                    df_in["setting"] = "inpatient"
                    all_records.append(df_in)
            
            # total (外来 + 入院) の算出
            # 入院が欠測の年（2017年）は total も欠測とする（外来のみの値で代用しない）
            if not df_out.empty and not df_in.empty:
                df_total = pd.merge(df_out, df_in, on="prefecture", suffixes=("_out", "_in"))
                df_total["count"] = df_total["count_out"] + df_total["count_in"]
                df_total["year"] = year
                df_total["setting"] = "total"
                all_records.append(df_total[["year", "prefecture", "setting", "count"]])
            elif not df_out.empty:
                print(f"    Note: inpatient missing for {year}; 'total' is treated as missing for this year.")
                
    if not all_records:
        raise ValueError("No records were successfully parsed from the excel files.")
        
    df_long = pd.concat(all_records, ignore_index=True)
    
    # prefectureの空白等をクレンジング
    df_long["prefecture"] = df_long["prefecture"].str.strip()
    
    # 並び替え
    df_long = df_long.sort_values(by=["year", "setting", "prefecture"]).reset_index(drop=True)
    
    # 保存
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "pterygium_long.csv")
    df_long.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"Successfully saved {out_file} (shape: {df_long.shape})")
    return df_long

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--imputation", type=str, default="zero", choices=["zero", "five", "random"])
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raw_dir = os.path.join(base_dir, "../data/raw")
    output_dir = os.path.join(base_dir, "processed")
    
    preprocess_pterygium(raw_dir, output_dir, args.imputation)
