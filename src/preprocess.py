import os
import glob
import json
import re
import pandas as pd
import numpy as np

# 都道府県リスト
PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
]

# レセプト電算処理システム用コードと解析用内部コードのマッピング
DENSEN_CODE_MAP = {
    # 水晶体再建術（K282）
    150253010: "K282_ro", # 水晶体再建術（眼内レンズを挿入する場合）（その他のもの）
    190179210: "K282_ro", # 短手３（水晶体再建術・眼内レンズ挿入・その他のもの）
    190179310: "K282_ro", # 短手３（水晶体再建術・眼内レンズ挿入・その他のもの）（生活療養）
    150356210: "K282_i",  # 水晶体再建術（眼内レンズを挿入する場合）（縫着レンズを挿入するもの）
    150380950: "K282_ring_y", # 水晶体再建術（水晶体嚢拡張リング・縫着を行ったもの）
    150381050: "K282_ring_n", # 水晶体再建術（水晶体嚢拡張リング・縫着を行っていないもの）
    150315610: "K282_no_lens", # 水晶体再建術（眼内レンズを挿入しない場合）
    190179410: "K282_no_lens", # 短手３（水晶体再建術（眼内レンズ挿入しない場合））
    190179510: "K282_no_lens", # 短手３（水晶体再建術（眼内レンズ挿入しない場合））（生活療養）
    150356310: "K282_capsule", # 水晶体再建術（計画的後嚢切開を伴う場合）

    # 硝子体茎顕微鏡下離断術（K280）
    150274010: "K280_1",  # 硝子体茎顕微鏡下離断術（網膜付着組織を含むもの）
    150090610: "K280_2",  # 硝子体茎顕微鏡下離断術（その他のもの）
    
    # 網膜付着組織を含む硝子体切除術（眼内内視鏡を用いるもの）（K280-2）
    150356110: "K280-2",
    
    # 増殖性硝子体網膜症手術（K281）
    150252810: "K281",
    150373110: "K281-2", # 網膜再建術

    # 緑内障手術（K268）
    # ── 濾過手術グループ ──
    150335910: "K268_filtration",   # 緑内障手術（濾過手術）
    150427310: "K268_bleb",        # 緑内障手術（濾過胞再建術）（needle法）
    # ── 虹彩切除グループ（その他に分類）──
    150087510: "K268_iridectomy",  # 緑内障手術（虹彩切除術）
    # ── デバイス（インプラント）グループ ──
    150356010: "K268_device_noplate", # 緑内障手術（緑内障治療用インプラント挿入術）（プレートのないもの）
    150373010: "K268_device_plate",   # 緑内障手術（緑内障治療用インプラント挿入術）（プレートのあるもの）
    # ── 流出路再建術グループ ──
    150427210: "K268_trabec_other",   # 緑内障手術（流出路再建術）（その他のもの）
    150435810: "K268_trabec_endo",    # 緑内障手術（流出路再建術）（眼内法）
    # ── 水晶体再建術併用眼内ドレーン ──
    150395150: "K268_istent",        # 緑内障手術（水晶体再建術併用眼内ドレーン挿入術）

    # 角膜移植術（K259）
    150086210: "K259",  # 角膜移植術（K259-2 の自家培養・口腔粘膜系は除外）
}

def load_mapping_config(config_path):
    """マッピング設定ファイルをロードする"""
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

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
        # カンマなどを除去して数値変換
        val_str = str(val).replace(",", "").strip()
        return float(val_str)
    except ValueError:
        return 0.0

def load_ndb_year(year, file_path, config, imputation_strategy="zero"):
    """
    1年分のNDB Excelファイルからデータを抽出し、縦持ち変換を行う。
    『外来』および『入院』のシートから、都道府県別の件数をパースする。
    """
    print(f"Processing year {year} from {file_path}...")
    
    # 対象となる大まかな区分コード（前方補完後にチェックする）
    target_prefixes = ["K282", "K280", "K281", "K280-2", "K268", "K259"]
    
    # 全シート名を読み込む
    excel_file = pd.ExcelFile(file_path)
    sheet_names = excel_file.sheet_names
    
    dfs = []
    
    # 解析対象シートは '外来' または '入院' (加算シートは除く)
    target_sheets = [s for s in sheet_names if s in ['外来', '入院']]
    if not target_sheets:
        # 万が一シート名が異なる場合は最初と3番目のシートを候補にするなどのフォールバック
        target_sheets = [sheet_names[0]]
        if len(sheet_names) >= 3:
            target_sheets.append(sheet_names[2])
            
    for sheet in target_sheets:
        df_sheet = pd.read_excel(file_path, sheet_name=sheet, header=None)
        
        # 1. 都道府県が並んでいるヘッダー行を検出する
        pref_row_idx = None
        pref_cols = {} # col_idx -> pref_name
        
        for r_idx in range(min(15, len(df_sheet))):
            row_vals = [str(x).strip() for x in df_sheet.iloc[r_idx] if pd.notna(x)]
            # 行の中に「北海道」などの主要な都道府県名が含まれるかチェック
            if any(p in row_vals for p in ["北海道", "青森県", "東京都", "大阪府"]):
                pref_row_idx = r_idx
                break
                
        if pref_row_idx is None:
            # 都道府県行が見つからない場合はスキップ
            continue
            
        # 都道府県名列とインデックスのマッピング
        for c in range(df_sheet.shape[1]):
            val = str(df_sheet.iloc[pref_row_idx, c]).strip()
            # 都道府県名が含まれている列を特定
            for p in PREFECTURES:
                if p in val:
                    pref_cols[c] = p
                    break
                    
        # 2. 分類コード（K282等）と診療行為名の列を特定する
        # 都道府県行の1〜2行上をスキャンする
        code_col_idx = None
        name_col_idx = None
        
        # 手術・処置のデフォルト（フォールバック用）
        if 'shujutsu' in file_path.lower():
            code_col_idx = 1
            name_col_idx = 4
        else: # shochi
            code_col_idx = 0
            name_col_idx = 3
            
        for offset in [1, 2]:
            r_check = pref_row_idx - offset
            if r_check >= 0:
                for c in range(min(10, df_sheet.shape[1])):
                    val = str(df_sheet.iloc[r_check, c]).strip()
                    if '分類' in val or 'コード' in val:
                        if code_col_idx is None or c < code_col_idx:
                            code_col_idx = c
                    if '診療行為' in val and 'コード' not in val:
                        name_col_idx = c
                        
        # 3. データをスキャンして対象コードの行を抽出
        if code_col_idx is not None and code_col_idx < df_sheet.shape[1]:
            df_sheet[code_col_idx] = df_sheet[code_col_idx].ffill()
        if name_col_idx is not None and name_col_idx < df_sheet.shape[1]:
            df_sheet[name_col_idx] = df_sheet[name_col_idx].ffill()
            
        np.random.seed(year)
        
        # 電算コード列は通常3
        densen_col_idx = 3
        
        for r_idx in range(pref_row_idx + 1, len(df_sheet)):
            # 区分コードの取得
            if code_col_idx >= df_sheet.shape[1]:
                continue
            code_raw = str(df_sheet.iloc[r_idx, code_col_idx]).strip()
            
            # 前方補完された区分番号が解析対象のいずれかに該当するかチェック
            is_target_proc = False
            for tc in target_prefixes:
                if code_raw == tc or code_raw.startswith(tc + "-"):
                    is_target_proc = True
                    break
                    
            if not is_target_proc:
                continue
                
            # 電算コードの取得と識別
            if densen_col_idx >= df_sheet.shape[1]:
                continue
            densen_val = df_sheet.iloc[r_idx, densen_col_idx]
            try:
                densen_code = int(float(str(densen_val).strip().replace(",", "")))
            except ValueError:
                continue
                
            # マッピングが存在しない電算コードはスキップ
            if densen_code not in DENSEN_CODE_MAP:
                continue
                
            code_clean = DENSEN_CODE_MAP[densen_code]
            
            # 診療行為名の取得
            proc_name = ""
            if name_col_idx < df_sheet.shape[1]:
                proc_name = str(df_sheet.iloc[r_idx, name_col_idx]).strip().replace('\n', '')
                
            # 都道府県ごとにデータレコードを作成
            for col_idx, pref_name in pref_cols.items():
                if col_idx >= df_sheet.shape[1]:
                    continue
                count_raw = df_sheet.iloc[r_idx, col_idx]
                count_val = clean_count_value(count_raw, imputation_strategy)
                
                dfs.append(pd.DataFrame([{
                    "year": year,
                    "prefecture": pref_name,
                    "code": code_clean,
                    "procedure_name": proc_name,
                    "age_group": "All",   # 総計シートのため年齢はAllで代用
                    "sex": "All",         # 性別もAll
                    "count_raw": str(count_raw),
                    "count": count_val
                }]))
                
    if not dfs:
        return pd.DataFrame()
        
    df_all = pd.concat(dfs, ignore_index=True)
    return df_all

def load_a400_k282(a400_dir, imputation_strategy="zero"):
    """
    A400（短期滞在手術等基本料）ファイルからK282短手3データを抽出する。
    2016-2023年のA400ファイルに含まれるK282関連の短手3コードを
    都道府県別に抽出してK282_roとして返す。
    第1回(2014)・第2回(2015)は手術ファイル内に短手3が含まれるためA400ファイル不要。
    """
    A400_K282_RO_CODES = {"190179210", "190179310", "190195910", "190196010"}

    dfs = []
    for year in range(2016, 2024):
        fpath = os.path.join(a400_dir, f"a400_pref_{year}.xlsx")
        if not os.path.exists(fpath):
            continue

        print(f"Processing A400 year {year} from {fpath}...")
        df_sheet = pd.read_excel(fpath, sheet_name=0, header=None)

        pref_row_idx = None
        pref_cols = {}
        for r_idx in range(min(10, len(df_sheet))):
            for c in range(df_sheet.shape[1]):
                val = str(df_sheet.iloc[r_idx, c]).strip()
                if val == "北海道":
                    pref_row_idx = r_idx

        if pref_row_idx is None:
            continue

        for c in range(df_sheet.shape[1]):
            val = str(df_sheet.iloc[pref_row_idx, c]).strip()
            for p in PREFECTURES:
                if p == val:
                    pref_cols[c] = p
                    break

        densen_col = 2
        for r_idx in range(pref_row_idx + 1, len(df_sheet)):
            code_raw = str(df_sheet.iloc[r_idx, densen_col]).strip().split(".")[0] if pd.notna(df_sheet.iloc[r_idx, densen_col]) else ""
            if code_raw not in A400_K282_RO_CODES:
                continue

            proc_name = str(df_sheet.iloc[r_idx, 3]).strip().replace("\n", "") if df_sheet.shape[1] > 3 else ""

            for col_idx, pref_name in pref_cols.items():
                if col_idx >= df_sheet.shape[1]:
                    continue
                count_val = clean_count_value(df_sheet.iloc[r_idx, col_idx], imputation_strategy)
                dfs.append({
                    "year": year,
                    "prefecture": pref_name,
                    "code": "K282_ro",
                    "procedure_name": "水晶体再建術（短手3・A400）",
                    "age_group": "All",
                    "sex": "All",
                    "count_raw": str(df_sheet.iloc[r_idx, col_idx]),
                    "count": count_val,
                })

    if not dfs:
        return pd.DataFrame()
    df = pd.DataFrame(dfs)
    totals = df.groupby("year")["count"].sum()
    for y, t in totals.items():
        print(f"  A400 K282_ro {int(y)}: {int(t):,} 件")
    return df


def load_ndb_chusha_year(year, file_path, imputation_strategy="zero"):
    """
    1年分の注射薬Excelファイルから抗VEGF薬のデータを抽出し、縦持ち変換を行う。
    """
    print(f"Processing chusha year {year} from {file_path}...")
    
    # 対象薬コード (NDBオープンデータに実在するコードおよび代表的なコード)
    vegf_codes = [
        "620009103", "621894901", "622199401", "622352001",
        "629906401", "629916701", "629918901",
        "622744301", "622927201"
    ]
    
    excel_file = pd.ExcelFile(file_path)
    sheet_names = excel_file.sheet_names
    
    dfs = []
    target_sheets = [s for s in sheet_names if '注射薬' in s]
    
    for sheet in target_sheets:
        df_sheet = pd.read_excel(file_path, sheet_name=sheet, header=None)
        
        # 1. 都道府県が並んでいるヘッダー行を検出する
        pref_row_idx = None
        pref_cols = {} # col_idx -> pref_name
        
        for r_idx in range(min(15, len(df_sheet))):
            row_vals = [str(x).strip() for x in df_sheet.iloc[r_idx] if pd.notna(x)]
            if any(p in row_vals for p in ["北海道", "青森県", "東京都", "大阪府"]):
                pref_row_idx = r_idx
                break
                
        if pref_row_idx is None:
            continue
            
        # 都道府県名列とインデックスのマッピング
        for c in range(df_sheet.shape[1]):
            val = str(df_sheet.iloc[pref_row_idx, c]).strip()
            for p in PREFECTURES:
                if p in val:
                    pref_cols[c] = p
                    break
                    
        # 2. 医薬品コードの列（通常はインデックス 2）を特定
        code_col_idx = None
        for offset in range(pref_row_idx + 1):
            r_check = pref_row_idx - offset
            for c in range(min(10, df_sheet.shape[1])):
                val = str(df_sheet.iloc[r_check, c]).strip()
                if '医薬品コード' in val or 'コード' in val:
                    if '薬価基準' not in val:
                        code_col_idx = c
                        break
            if code_col_idx is not None:
                break
                
        if code_col_idx is None:
            code_col_idx = 2
            
        name_col_idx = 3 # 医薬品名の列 (通常はインデックス 3)
        
        # 3. データ行を走査して抗VEGF薬的コードの行を抽出
        for r_idx in range(pref_row_idx + 1, len(df_sheet)):
            if code_col_idx >= df_sheet.shape[1]:
                continue
            code_val_raw = df_sheet.iloc[r_idx, code_col_idx]
            if pd.isna(code_val_raw):
                continue
                
            code_str = str(code_val_raw).split('.')[0].strip()
            if code_str not in vegf_codes:
                continue
                
            proc_name = str(df_sheet.iloc[r_idx, name_col_idx]).strip().replace('\n', '') if name_col_idx < df_sheet.shape[1] else ""
            
            # 都道府県ごとにデータレコードを作成
            for col_idx, pref_name in pref_cols.items():
                if col_idx >= df_sheet.shape[1]:
                    continue
                count_raw = df_sheet.iloc[r_idx, col_idx]
                count_val = clean_count_value(count_raw, imputation_strategy)
                
                dfs.append(pd.DataFrame([{
                    "year": year,
                    "prefecture": pref_name,
                    "code": "J039-2",
                    "procedure_name": "抗VEGF薬注射（薬剤数量代替）",
                    "age_group": "All",
                    "sex": "All",
                    "count_raw": str(count_raw),
                    "count": count_val
                }]))
                
    if not dfs:
        return pd.DataFrame()
        
    return pd.concat(dfs, ignore_index=True)

def preprocess_all(raw_dir, covariate_path, mapping_path, output_dir, imputation_strategy="zero"):
    """
    全年度の前処理を行い、共変量データとマージして保存する
    """
    config = load_mapping_config(mapping_path)
    
    # NDBファイルの検索
    shujutsu_files = glob.glob(os.path.join(raw_dir, "ndb_shujutsu_*.*"))
    shochi_files = glob.glob(os.path.join(raw_dir, "ndb_shochi_*.*"))
    chusha_files = glob.glob(os.path.join(raw_dir, "ndb_chusha_*.*"))
    
    # 年度ごとにファイルをマッピング
    years_files = {}
    for f in shujutsu_files + shochi_files:
        match = re.search(r"ndb_(shujutsu|shochi)_(\d{4})\.(xlsx|xls)", os.path.basename(f))
        if not match:
            continue
        file_type = match.group(1)
        year = int(match.group(2))
        if year not in years_files:
            years_files[year] = []
        years_files[year].append(f)
        
    # 注射ファイルの年度マッピング
    years_chusha = {}
    for f in chusha_files:
        match = re.search(r"ndb_chusha_(\d{4})\.(xlsx|xls)", os.path.basename(f))
        if not match:
            continue
        year = int(match.group(1))
        years_chusha[year] = f
        
    if not years_files and not years_chusha:
        raise FileNotFoundError(f"No NDB raw files found in {raw_dir}")
        
    all_years_dfs = []
    
    # 手術・処置のパース
    for year, files in sorted(years_files.items()):
        for file_path in files:
            df_file = load_ndb_year(year, file_path, config, imputation_strategy)
            if not df_file.empty:
                all_years_dfs.append(df_file)
                
    # 注射（抗VEGF薬）のパースと統合
    for year, file_path in sorted(years_chusha.items()):
        df_chusha = load_ndb_chusha_year(year, file_path, imputation_strategy)
        if not df_chusha.empty:
            all_years_dfs.append(df_chusha)

    # A400（短期滞在手術等基本料）からK282短手3データを追加
    a400_dir = os.path.join(raw_dir, "a400")
    if os.path.isdir(a400_dir):
        df_a400 = load_a400_k282(a400_dir, imputation_strategy)
        if not df_a400.empty:
            all_years_dfs.append(df_a400)

    if not all_years_dfs:
        raise ValueError("No data was parsed from the raw files.")

    df_ndb = pd.concat(all_years_dfs, ignore_index=True)
    
    # 都道府県名の表記統一（「都道府県」の表記ゆれ、スペース除去など）
    df_ndb["prefecture"] = df_ndb["prefecture"].str.strip()

    # 診療行為名の正規化（内部コードベースで統一）
    code_name_map = {
        "K282_ro":     "水晶体再建術（眼内レンズを挿入する場合）（その他のもの）",
        "K282_i":      "水晶体再建術（眼内レンズを挿入する場合）（縫着レンズを挿入するもの）",
        "K282_total":  "水晶体再建術（眼内レンズ挿入合算）",
        "K280_1":      "硝子体茎顕微鏡下離断術（網膜付着組織を含むもの）",
        "K280_2":      "硝子体茎顕微鏡下離断術（その他のもの）",
        "K280":        "硝子体茎顕微鏡下離断術（K280合算）",
        "K280-2":      "網膜付着組織を含む硝子体切除術（眼内内視鏡を用いるもの）",
        "K281":        "増殖性硝子体網膜症手術",
        "J039-2":      "抗VEGF薬注射（薬剤数量代替）",
        # 緑内障手術 個別サブグループコード
        "K268_filtration":  "緑内障手術（濾過手術）",
        "K268_bleb":        "緑内障手術（濾過胞再建術）（needle法）",
        "K268_iridectomy":  "緑内障手術（虹彩切除術）",
        "K268_device_noplate": "緑内障手術（インプラント：プレートなし）",
        "K268_device_plate":   "緑内障手術（インプラント：プレートあり）",
        "K268_trabec_other":   "緑内障手術（流出路再建術：その他）",
        "K268_trabec_endo":    "緑内障手術（流出路再建術：眼内法）",
        "K268_istent":         "緑内障手術（水晶体再建術併用眼内ドレーン）",
        # 緑内障手術 サブグループ合算コード
        "K268_grp_filtration": "緑内障手術（濾過手術系合算）",
        "K268_grp_device":     "緑内障手術（デバイス系合算）",
        "K268_grp_trabec":     "緑内障手術（流出路再建術系合算）",
        "K268_grp_combo":      "緑内障手術（水晶体再建術併用ドレーン）",
        # 緑内障手術 全体合算
        "K268":  "緑内障手術（K268合算）",
        # 角膜移植術
        "K259":  "角膜移植術",
    }

    # ── 合算データの作成 ───────────────────────────────────────────
    # 1. K282_total: K282_ro と K282_i の合算
    df_k282_src = df_ndb[df_ndb["code"].isin(["K282_ro", "K282_i"])].copy()
    if not df_k282_src.empty:
        df_k282_total = df_k282_src.groupby(["year", "prefecture", "age_group", "sex"], as_index=False)["count"].sum()
        df_k282_total["code"] = "K282_total"
        df_k282_total["procedure_name"] = code_name_map["K282_total"]
        df_k282_total["count_raw"] = "Aggregated"
        df_ndb = pd.concat([df_ndb, df_k282_total], ignore_index=True)

    # 2. K280: K280_1 と K280_2 の合算
    df_k280_src = df_ndb[df_ndb["code"].isin(["K280_1", "K280_2"])].copy()
    if not df_k280_src.empty:
        df_k280_total = df_k280_src.groupby(["year", "prefecture", "age_group", "sex"], as_index=False)["count"].sum()
        df_k280_total["code"] = "K280"
        df_k280_total["procedure_name"] = code_name_map["K280"]
        df_k280_total["count_raw"] = "Aggregated"
        df_ndb = pd.concat([df_ndb, df_k280_total], ignore_index=True)

    # 3. K268 サブグループ合算
    #    濾過手術系: 濾過手術 + 濾過胞再建術
    _k268_filt_codes = ["K268_filtration", "K268_bleb"]
    df_k268_filt_src = df_ndb[df_ndb["code"].isin(_k268_filt_codes)].copy()
    if not df_k268_filt_src.empty:
        df_tmp = df_k268_filt_src.groupby(["year", "prefecture", "age_group", "sex"], as_index=False)["count"].sum()
        df_tmp["code"] = "K268_grp_filtration"
        df_tmp["procedure_name"] = code_name_map["K268_grp_filtration"]
        df_tmp["count_raw"] = "Aggregated"
        df_ndb = pd.concat([df_ndb, df_tmp], ignore_index=True)

    #    デバイス系: インプラント（プレートなし + プレートあり）
    _k268_dev_codes = ["K268_device_noplate", "K268_device_plate"]
    df_k268_dev_src = df_ndb[df_ndb["code"].isin(_k268_dev_codes)].copy()
    if not df_k268_dev_src.empty:
        df_tmp = df_k268_dev_src.groupby(["year", "prefecture", "age_group", "sex"], as_index=False)["count"].sum()
        df_tmp["code"] = "K268_grp_device"
        df_tmp["procedure_name"] = code_name_map["K268_grp_device"]
        df_tmp["count_raw"] = "Aggregated"
        df_ndb = pd.concat([df_ndb, df_tmp], ignore_index=True)

    #    流出路再建術系: その他 + 眼内法
    _k268_trab_codes = ["K268_trabec_other", "K268_trabec_endo"]
    df_k268_trab_src = df_ndb[df_ndb["code"].isin(_k268_trab_codes)].copy()
    if not df_k268_trab_src.empty:
        df_tmp = df_k268_trab_src.groupby(["year", "prefecture", "age_group", "sex"], as_index=False)["count"].sum()
        df_tmp["code"] = "K268_grp_trabec"
        df_tmp["procedure_name"] = code_name_map["K268_grp_trabec"]
        df_tmp["count_raw"] = "Aggregated"
        df_ndb = pd.concat([df_ndb, df_tmp], ignore_index=True)

    #    水晶体再建術併用ドレーン系: K268_istent のみ（alias）
    _k268_combo_codes = ["K268_istent"]
    df_k268_combo_src = df_ndb[df_ndb["code"].isin(_k268_combo_codes)].copy()
    if not df_k268_combo_src.empty:
        df_tmp = df_k268_combo_src.groupby(["year", "prefecture", "age_group", "sex"], as_index=False)["count"].sum()
        df_tmp["code"] = "K268_grp_combo"
        df_tmp["procedure_name"] = code_name_map["K268_grp_combo"]
        df_tmp["count_raw"] = "Aggregated"
        df_ndb = pd.concat([df_ndb, df_tmp], ignore_index=True)

    # 4. K268 全体合算（全8電算コードを合算）
    _k268_all_codes = [
        "K268_filtration", "K268_bleb", "K268_iridectomy",
        "K268_device_noplate", "K268_device_plate",
        "K268_trabec_other", "K268_trabec_endo",
        "K268_istent"
    ]
    df_k268_all_src = df_ndb[df_ndb["code"].isin(_k268_all_codes)].copy()
    if not df_k268_all_src.empty:
        df_tmp = df_k268_all_src.groupby(["year", "prefecture", "age_group", "sex"], as_index=False)["count"].sum()
        df_tmp["code"] = "K268"
        df_tmp["procedure_name"] = code_name_map["K268"]
        df_tmp["count_raw"] = "Aggregated"
        df_ndb = pd.concat([df_ndb, df_tmp], ignore_index=True)

    # 既存データの procedure_name をマッピングで更新
    df_ndb["procedure_name"] = df_ndb["code"].map(code_name_map).fillna(df_ndb["procedure_name"])

    # 共変量データの読み込み
    print(f"Loading covariates from {covariate_path}...")
    df_cov = pd.read_csv(covariate_path)
    df_cov["prefecture"] = df_cov["prefecture"].str.strip()

    def _merge_and_calc(df_src, df_cov_src):
        """集計・共変量マージ・指標算出の共通処理"""
        df_agg = df_src.groupby(["year", "prefecture", "code", "procedure_name"], as_index=False)["count"].sum()
        df_m = pd.merge(df_agg, df_cov_src, on=["year", "prefecture"], how="left")
        df_m["count_per_100k"]       = (df_m["count"] / df_m["population_total"]) * 100000
        df_m["count_per_100k_65plus"] = (df_m["count"] / df_m["population_65plus"]) * 100000
        df_m["aging_rate"]            = df_m["population_65plus"] / df_m["population_total"]
        df_m["docs_per_100k"]         = (df_m["ophthalmologists"] / df_m["population_total"]) * 100000
        df_m["facilities_per_100k"]   = (df_m["facilities"] / df_m["population_total"]) * 100000
        return df_m

    os.makedirs(output_dir, exist_ok=True)

    # ── サブ解析用: すべての個別コードおよび合算コードを保持 ──────────────────────
    df_sub = _merge_and_calc(df_ndb, df_cov)
    out_sub = os.path.join(output_dir, f"ndb_processed_k280_sub_{imputation_strategy}.csv")
    df_sub.to_csv(out_sub, index=False, encoding="utf-8-sig")
    print(f"Sub-analysis dataset saved to {out_sub} (shape: {df_sub.shape})")

    # ── メイン解析用 ─────────────────────────────────────────
    # K281は大半の都道府県で秘匿閾値（10件未満非公開）に該当し安定した解析が困難なため除外
    # K268（緑内障手術合算）, K259（角膜移植術）を追加
    df_ndb_main = df_ndb[df_ndb["code"].isin(
        ["K282_ro", "K282_total", "K280", "J039-2", "K268", "K259"]
    )].copy()
    df_ndb_main.loc[df_ndb_main["code"] == "K282_ro", "code"] = "K282"
    df_ndb_main["procedure_name"] = df_ndb_main["code"].map({
        "K282":       "水晶体再建術（眼内レンズを挿入する場合）（その他のもの）",
        "K282_total": "水晶体再建術（眼内レンズ挿入合算）",
        "K280":       "硝子体茎顕微鏡下離断術（K280合算）",
        "J039-2":     "抗VEGF薬注射（薬剤数量代替）",
        "K268":       "緑内障手術（K268合算）",
        "K259":       "角膜移植術",
    })

    df_merged = _merge_and_calc(df_ndb_main, df_cov)
    out_file = os.path.join(output_dir, f"ndb_processed_{imputation_strategy}.csv")
    df_merged.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"Processed dataset saved to {out_file} (shape: {df_merged.shape})")

    # 年齢階級別の詳細データ（メイン合算ベース）
    df_age_detail = pd.merge(df_ndb_main, df_cov, on=["year", "prefecture"], how="left")
    df_age_detail["count_per_100k"] = (df_age_detail["count"] / df_age_detail["population_total"]) * 100000
    df_age_detail["aging_rate"]     = df_age_detail["population_65plus"] / df_age_detail["population_total"]
    out_age_file = os.path.join(output_dir, f"ndb_processed_age_detail_{imputation_strategy}.csv")
    df_age_detail.to_csv(out_age_file, index=False, encoding="utf-8-sig")
    print(f"Processed age-detail dataset saved to {out_age_file} (shape: {df_age_detail.shape})")
    
    return df_merged

if __name__ == "__main__":
    # 注意: 必ず本番用共変量データ（prefecture_covariates.csv）を使用すること。
    # 開発用途のCSVを使用すると data/processed/ の出力が汚染される。
    preprocess_all(
        raw_dir="data/raw",
        covariate_path="data/covariates/prefecture_covariates.csv",
        mapping_path="configs/ndb_mapping.json",
        output_dir="data/processed",
        imputation_strategy="zero"
    )
