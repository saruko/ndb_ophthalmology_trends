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

# 都道府県コード（01-47）→都道府県名のマッピング
PREF_CODE_TO_NAME = {f"{i+1:02d}": name for i, name in enumerate(PREFECTURES)}

# 薬剤カテゴリ定義: (カテゴリコード, カテゴリ名, [マッチする薬剤名キーワード])
# 薬効分類=131（眼科用剤）かつ医薬品名に「点眼」を含む行を対象に、薬剤名で分類
DRUG_CATEGORIES = [
    # カテゴリA: 抗ヒスタミン点眼薬（第二世代, 現在の第一選択）
    ("OLOPATADINE",   "オロパタジン点眼（パタノール系）",        ["オロパタジン", "パタノール"]),
    ("EPINASTINE",    "エピナスチン点眼（アレジオン系）",        ["エピナスチン", "アレジオン"]),
    ("KETOTIFEN",     "ケトチフェン点眼（ザジテン系）",          ["ケトチフェン", "ザジテン"]),
    ("LEVOCASTINE",   "レボカバスチン点眼（リボスチン系）",      ["レボカバスチン", "リボスチン"]),
    # カテゴリB: メディエーター遊離抑制点眼薬（予防的投与, 旧世代）
    ("CROMOGLICATE",  "クロモグリク酸点眼（インタール系）",      ["クロモグリク酸", "インタール"]),
    ("TRANILAST",     "トラニラスト点眼（リザベン系）",          ["トラニラスト", "リザベン"]),
    ("PEMIROLAST",    "ペミロラスト点眼（アレギサール系）",      ["ペミロラスト", "アレギサール"]),
    ("IBUDILAST",     "イブジラスト点眼（ケタス）",             ["イブジラスト", "ケタス"]),
    ("ACITAZANOLAST", "アシタザノラスト点眼（ゼペリン）",        ["アシタザノラスト", "ゼペリン"]),
    # カテゴリC: 免疫抑制点眼薬（春季カタル等の重症アレルギー性結膜疾患）
    ("CYCLOSPORINE",  "シクロスポリン点眼（パピロック）",        ["シクロスポリン", "パピロック"]),
    ("TACROLIMUS",    "タクロリムス点眼（タリムス）",            ["タクロリムス", "タリムス"]),
]

ANTI_HIST_CODES   = {"OLOPATADINE", "EPINASTINE", "KETOTIFEN", "LEVOCASTINE"}
MED_RELEASE_CODES = {"CROMOGLICATE", "TRANILAST", "PEMIROLAST", "IBUDILAST", "ACITAZANOLAST"}
IMMUNO_CODES      = {"CYCLOSPORINE", "TACROLIMUS"}

# 全身性アレルギー治療薬（注射薬）: 注射薬ファイルから抽出
INJECTION_DRUG_CATEGORIES = [
    ("ZOLEAIR",   "ゾレア（オマリズマブ）",     ["ゾレア"]),
    ("DUPIXENT",  "デュピクセント（デュピルマブ）", ["デュピクセント"]),
]


def classify_drug(drug_name: str) -> tuple[str, str] | None:
    """医薬品名から薬剤カテゴリコードと名称を返す。該当なしはNone。"""
    for code, name, patterns in DRUG_CATEGORIES:
        if any(p in drug_name for p in patterns):
            return code, name
    return None


def clean_count_value(val, imputation_strategy: str = "zero") -> float:
    """秘匿値（'-' 等）を補完処理する"""
    if pd.isna(val) or str(val).strip() in ["-", "—", "－", ""]:
        if imputation_strategy == "five":
            return 5.0
        elif imputation_strategy == "random":
            return float(np.random.randint(1, 10))
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return 0.0


def load_gaiyo_sheet(year: int, file_path: str, sheet_name: str,
                     imputation_strategy: str = "zero") -> pd.DataFrame:
    """
    外用薬Excelの1シートから、眼科系抗アレルギー点眼薬データを抽出して縦持ち形式で返す。

    列構成の年度差異:
    - 2014: 総計=col7, 都道府県=col8-54 (単位列なし)
    - 2015+: 総計=col8, 都道府県=col9-55 (単位列あり)
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    # Row2からヘッダー情報取得
    row2 = [str(x) for x in df.iloc[2]]

    # 総計列を動的に特定
    total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
    if total_col is None:
        print(f"  Warning: 総計列が見つかりません: {file_path} [{sheet_name}]")
        return pd.DataFrame()

    # 薬効分類コード列 (col0) をffillで補完
    df[0] = df[0].ffill()

    # 都道府県コード (01-47) → 都道府県名のマッピングをRow3から構築
    row3 = [str(x).strip() for x in df.iloc[3]]
    pref_col_map: dict[int, str] = {}
    for col_idx in range(total_col + 1, min(total_col + 48, df.shape[1])):
        pref_name_candidate = row3[col_idx]
        if pref_name_candidate in PREFECTURES:
            pref_col_map[col_idx] = pref_name_candidate

    if not pref_col_map:
        # Row3に都道府県名がない場合、数値コードから生成
        for i, pref in enumerate(PREFECTURES):
            col_idx = total_col + 1 + i
            if col_idx < df.shape[1]:
                pref_col_map[col_idx] = pref

    np.random.seed(year)

    records = []
    for r_idx in range(4, len(df)):
        # 薬効分類が131（眼科用剤）でない行はスキップ
        if str(df.iloc[r_idx, 0]).strip() != "131":
            continue

        drug_name = str(df.iloc[r_idx, 3]).strip()

        # 「点眼」を含まない剤形（眼軟膏, 眼耳鼻科用液等）は除外
        if "点眼" not in drug_name:
            continue

        result = classify_drug(drug_name)
        if result is None:
            continue
        category_code, category_name = result

        for col_idx, pref_name in pref_col_map.items():
            raw_val = df.iloc[r_idx, col_idx]
            count = clean_count_value(raw_val, imputation_strategy)
            records.append({
                "year":           year,
                "prefecture":     pref_name,
                "code":           category_code,
                "procedure_name": category_name,
                "count":          count,
            })

    return pd.DataFrame(records)


def load_gaiyo_year(year: int, file_path: str,
                    imputation_strategy: str = "zero") -> pd.DataFrame:
    """
    1年分の外用薬ファイルから全シート（院内・院外・入院）を読み込み、
    都道府県×薬剤カテゴリごとに合算して返す。
    """
    print(f"Processing gaiyo year {year} from {file_path}...")
    xl = pd.ExcelFile(file_path)
    target_sheets = [s for s in xl.sheet_names if "外用薬" in s]

    dfs = []
    for sheet in target_sheets:
        df_sheet = load_gaiyo_sheet(year, file_path, sheet, imputation_strategy)
        if not df_sheet.empty:
            dfs.append(df_sheet)

    if not dfs:
        return pd.DataFrame()

    df_all = pd.concat(dfs, ignore_index=True)
    # シート間（院内・院外・入院）を合算
    df_agg = df_all.groupby(
        ["year", "prefecture", "code", "procedure_name"], as_index=False
    )["count"].sum()
    return df_agg


def preprocess_allergy(raw_dir: str, covariate_path: str,
                       output_dir: str, imputation_strategy: str = "zero") -> pd.DataFrame:
    """
    抗アレルギー点眼薬解析用のデータ前処理。
    外用薬ファイル (ndb_gaiyo_YYYY.xlsx) を読み込み、共変量とマージして保存する。
    """
    print(f"Starting preprocess_allergy (eye drops) with strategy: {imputation_strategy}...")

    gaiyo_files = glob.glob(os.path.join(raw_dir, "ndb_gaiyo_*.*"))
    years_map: dict[int, str] = {}
    for f in gaiyo_files:
        m = re.search(r"ndb_gaiyo_(\d{4})\.(xlsx|xls)", os.path.basename(f))
        if m:
            years_map[int(m.group(1))] = f

    if not years_map:
        raise FileNotFoundError(f"No ndb_gaiyo_*.xlsx files found in {raw_dir}")

    all_dfs = []
    for year, file_path in sorted(years_map.items()):
        df_year = load_gaiyo_year(year, file_path, imputation_strategy)
        if not df_year.empty:
            all_dfs.append(df_year)

    if not all_dfs:
        raise ValueError("No target eye drop data parsed from the raw files.")

    df_raw = pd.concat(all_dfs, ignore_index=True)

    # --- 集計カテゴリの追加 ---
    def _make_aggregate(src_codes: set, agg_code: str, agg_name: str) -> pd.DataFrame:
        sub = df_raw[df_raw["code"].isin(src_codes)].copy()
        if sub.empty:
            return pd.DataFrame()
        agg = sub.groupby(["year", "prefecture"], as_index=False)["count"].sum()
        agg["code"] = agg_code
        agg["procedure_name"] = agg_name
        return agg

    df_anti_hist = _make_aggregate(
        ANTI_HIST_CODES, "ANTI_HIST", "抗ヒスタミン点眼薬（合計）")
    df_med_release = _make_aggregate(
        MED_RELEASE_CODES, "MED_RELEASE", "メディエーター遊離抑制点眼薬（合計）")
    df_immuno = _make_aggregate(
        IMMUNO_CODES, "IMMUNO", "免疫抑制点眼薬（合計）")
    df_total = _make_aggregate(
        ANTI_HIST_CODES | MED_RELEASE_CODES | IMMUNO_CODES,
        "ALLERGY_EYE_TOTAL", "抗アレルギー点眼薬（全体合計）")

    df_combined = pd.concat(
        [df_raw, df_anti_hist, df_med_release, df_immuno, df_total],
        ignore_index=True
    )

    # --- 共変量マージ ---
    print(f"Loading covariates from {covariate_path}...")
    df_cov = pd.read_csv(covariate_path)
    df_cov["prefecture"] = df_cov["prefecture"].str.strip()
    df_combined["prefecture"] = df_combined["prefecture"].str.strip()

    df_merged = pd.merge(df_combined, df_cov, on=["year", "prefecture"], how="left")

    df_merged["count_per_100k"]        = (df_merged["count"] / df_merged["population_total"]) * 100000
    df_merged["count_per_100k_65plus"] = (df_merged["count"] / df_merged["population_65plus"]) * 100000
    df_merged["aging_rate"]            = df_merged["population_65plus"] / df_merged["population_total"]
    df_merged["docs_per_100k"]         = (df_merged["ophthalmologists"] / df_merged["population_total"]) * 100000
    df_merged["facilities_per_100k"]   = (df_merged["facilities"] / df_merged["population_total"]) * 100000

    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"ndb_processed_allergy_{imputation_strategy}.csv")
    df_merged.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"Eye drop dataset saved to {out_file} (shape: {df_merged.shape})")

    return df_merged


def classify_injection_drug(drug_name: str) -> tuple[str, str] | None:
    """注射薬の医薬品名からカテゴリコードと名称を返す。"""
    for code, name, patterns in INJECTION_DRUG_CATEGORIES:
        if any(p in drug_name for p in patterns):
            return code, name
    return None


def load_chusha_sheet(year: int, file_path: str, sheet_name: str,
                      imputation_strategy: str = "zero") -> pd.DataFrame:
    """注射薬Excelの1シートから、DUPIXENT/ZOLEAIRデータを抽出する。"""
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

    row2 = [str(x) for x in df.iloc[2]]
    total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
    if total_col is None:
        return pd.DataFrame()

    df[0] = df[0].ffill()

    row3 = [str(x).strip() for x in df.iloc[3]]
    pref_col_map: dict[int, str] = {}
    for col_idx in range(total_col + 1, min(total_col + 48, df.shape[1])):
        if col_idx < len(row3) and row3[col_idx] in PREFECTURES:
            pref_col_map[col_idx] = row3[col_idx]
    if not pref_col_map:
        for i, pref in enumerate(PREFECTURES):
            col_idx = total_col + 1 + i
            if col_idx < df.shape[1]:
                pref_col_map[col_idx] = pref

    np.random.seed(year)
    records = []
    for r_idx in range(4, len(df)):
        drug_name = str(df.iloc[r_idx, 3]).strip()
        result = classify_injection_drug(drug_name)
        if result is None:
            continue
        category_code, category_name = result
        for col_idx, pref_name in pref_col_map.items():
            raw_val = df.iloc[r_idx, col_idx]
            count = clean_count_value(raw_val, imputation_strategy)
            records.append({
                "year": year, "prefecture": pref_name,
                "code": category_code, "procedure_name": category_name,
                "count": count,
            })
    return pd.DataFrame(records)


def load_chusha_year(year: int, file_path: str,
                     imputation_strategy: str = "zero") -> pd.DataFrame:
    """1年分の注射薬ファイルからDUPIXENT/ZOLEAIRを抽出・合算する。"""
    print(f"Processing chusha year {year} from {file_path}...")
    xl = pd.ExcelFile(file_path)
    target_sheets = [s for s in xl.sheet_names if "注射" in s]
    dfs = []
    for sheet in target_sheets:
        df_sheet = load_chusha_sheet(year, file_path, sheet, imputation_strategy)
        if not df_sheet.empty:
            dfs.append(df_sheet)
    if not dfs:
        return pd.DataFrame()
    df_all = pd.concat(dfs, ignore_index=True)
    return df_all.groupby(
        ["year", "prefecture", "code", "procedure_name"], as_index=False
    )["count"].sum()


def preprocess_injection_drugs(raw_dir: str, covariate_path: str,
                               output_dir: str,
                               imputation_strategy: str = "zero") -> pd.DataFrame:
    """DUPIXENT/ZOLEAIRの前処理。注射薬ファイルから抽出し共変量とマージする。"""
    print(f"Starting preprocess_injection_drugs with strategy: {imputation_strategy}...")

    chusha_files = glob.glob(os.path.join(raw_dir, "ndb_chusha_*.*"))
    drug_file_2024 = os.path.join(raw_dir, "ndb_chusha_drug_2024.xlsx")
    if os.path.exists(drug_file_2024):
        chusha_files.append(drug_file_2024)

    years_map: dict[int, str] = {}
    for f in chusha_files:
        m = re.search(r"ndb_chusha(?:_drug)?_(\d{4})\.(xlsx|xls)", os.path.basename(f))
        if m:
            year = int(m.group(1))
            xl = pd.ExcelFile(f)
            if any("注射" in s for s in xl.sheet_names):
                years_map[year] = f

    if not years_map:
        print("No chusha files with injection sheets found. Skipping injection drugs.")
        return pd.DataFrame()

    all_dfs = []
    for year, file_path in sorted(years_map.items()):
        df_year = load_chusha_year(year, file_path, imputation_strategy)
        if not df_year.empty:
            all_dfs.append(df_year)

    if not all_dfs:
        print("No DUPIXENT/ZOLEAIR data found.")
        return pd.DataFrame()

    df_raw = pd.concat(all_dfs, ignore_index=True)

    df_cov = pd.read_csv(covariate_path)
    df_cov["prefecture"] = df_cov["prefecture"].str.strip()
    df_raw["prefecture"] = df_raw["prefecture"].str.strip()
    df_merged = pd.merge(df_raw, df_cov, on=["year", "prefecture"], how="left")

    df_merged["count_per_100k"]        = (df_merged["count"] / df_merged["population_total"]) * 100000
    df_merged["count_per_100k_65plus"] = (df_merged["count"] / df_merged["population_65plus"]) * 100000
    df_merged["aging_rate"]            = df_merged["population_65plus"] / df_merged["population_total"]
    df_merged["docs_per_100k"]         = (df_merged["ophthalmologists"] / df_merged["population_total"]) * 100000
    df_merged["facilities_per_100k"]   = (df_merged["facilities"] / df_merged["population_total"]) * 100000

    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"ndb_processed_injection_allergy_{imputation_strategy}.csv")
    df_merged.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"Injection drug dataset saved to {out_file} (shape: {df_merged.shape})")
    return df_merged


if __name__ == "__main__":
    preprocess_allergy(
        raw_dir="data/raw",
        covariate_path="data/covariates/prefecture_covariates.csv",
        output_dir="allergy解析/processed",
        imputation_strategy="zero"
    )
