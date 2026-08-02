import os
import glob
import re
import pandas as pd
import numpy as np

from paths import raw_file

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
# 薬効分類=131（眼科用剤）かつ医薬品名に「点眼」を含む行を対象に、薬剤名で分類。
# 配合剤を先に判定する（「ミケルナ」を「ミケラン」と誤判定しない等、部分一致の取り違えを避ける）。
DRUG_CATEGORIES = [
    # 配合剤（FDC）
    ("FDC_PG_BETA",   "PG関連薬・β遮断薬配合点眼（ザラカム等）",  ["ザラカム", "デュオトラバ", "タプコム", "ミケルナ"]),
    ("FDC_CAI_BETA",  "CAI・β遮断薬配合点眼（コソプト等）",       ["コソプト", "アゾルガ"]),
    ("FDC_A2_BETA",   "α2作動薬・β遮断薬配合点眼（アイベータ）",  ["アイベータ"]),
    ("FDC_A2_CAI",    "α2作動薬・CAI配合点眼（アイラミド）",       ["アイラミド"]),
    ("FDC_ROCK_A2",   "ROCK阻害薬・α2作動薬配合点眼（グラアルファ）", ["グラアルファ"]),
    # 単剤A: プロスタグランジン関連薬（現在の第一選択）
    ("LATANOPROST",   "ラタノプロスト点眼（キサラタン系）",       ["ラタノプロスト", "キサラタン"]),
    ("TRAVOPROST",    "トラボプロスト点眼（トラバタンズ系）",     ["トラボプロスト", "トラバタンズ"]),
    ("TAFLUPROST",    "タフルプロスト点眼（タプロス系）",         ["タフルプロスト", "タプロス"]),
    ("BIMATOPROST",   "ビマトプロスト点眼（ルミガン系）",         ["ビマトプロスト", "ルミガン"]),
    ("OMIDENEPAG",    "オミデネパグ点眼（エイベリス）",           ["オミデネパグ", "エイベリス"]),
    ("UNOPROSTONE",   "ウノプロストン点眼（レスキュラ系）",       ["イソプロピルウノプロストン", "レスキュラ"]),
    # 単剤B: β遮断薬・αβ遮断薬
    ("TIMOLOL",       "チモロール点眼（チモプトール系）",         ["チモロール", "チモプトール", "リズモン"]),
    ("CARTEOLOL",     "カルテオロール点眼（ミケラン系）",         ["カルテオロール", "ミケラン"]),
    ("BETAXOLOL",     "ベタキソロール点眼（ベトプティック系）",   ["ベタキソロール", "ベトプティック"]),
    ("LEVOBUNOLOL",   "レボブノロール点眼（ミロル系）",           ["レボブノロール", "ミロル"]),
    ("NIPRADILOL",    "ニプラジロール点眼（ハイパジール系）",     ["ニプラジロール", "ハイパジール", "ニプラノール"]),
    # 単剤C: 炭酸脱水酵素阻害薬（CAI）
    ("DORZOLAMIDE",   "ドルゾラミド点眼（トルソプト系）",         ["ドルゾラミド", "トルソプト"]),
    ("BRINZOLAMIDE",  "ブリンゾラミド点眼（エイゾプト系）",       ["ブリンゾラミド", "エイゾプト"]),
    # 単剤D: α2作動薬
    ("BRIMONIDINE",   "ブリモニジン点眼（アイファガン系）",       ["ブリモニジン", "アイファガン"]),
    # 単剤E: ROCK阻害薬
    ("RIPASUDIL",     "リパスジル点眼（グラナテック）",           ["リパスジル", "グラナテック"]),
    # 単剤F: その他（α1遮断・副交感神経刺激・交感神経作動）
    ("BUNAZOSIN",     "ブナゾシン点眼（デタントール）",           ["ブナゾシン", "デタントール"]),
    ("PILOCARPINE",   "ピロカルピン点眼（サンピロ）",             ["ピロカルピン", "サンピロ"]),
    ("DIPIVEFRINE",   "ジピベフリン点眼（ピバレフリン）",         ["ジピベフリン", "ピバレフリン"]),
    # ジスチグミン点眼は緑内障・調節性内斜視が適応。NDBには2022年度以降のみ収録され数量も僅少
    ("DISTIGMINE",    "ジスチグミン点眼（ウブレチド）",           ["ジスチグミン", "ウブレチド"]),
    # 別掲: アプラクロニジン（レーザー後等の一過性眼圧上昇に対する短期使用。慢性治療でないため合計から除外）
    ("APRACLONIDINE", "アプラクロニジン点眼（アイオピジンUD・別掲）", ["アプラクロニジン", "アイオピジン"]),
]

# ─────────────────────────────────────────────
# 薬効群の分類（緑内障診療ガイドライン第5版・日本緑内障学会 に準拠）
#
# ガイドラインの「眼圧下降薬（点眼薬）」の分類をそのまま集計単位にする。
#   プロスタグランジン関連薬（FP受容体作動薬／EP2受容体作動薬／イオンチャネル開口薬）
#   交感神経β遮断薬（非選択性／β1選択性）
#   交感神経α1β遮断薬
#   交感神経α1遮断薬
#   交感神経α2刺激薬
#   交感神経非選択性刺激薬
#   副交感神経刺激薬（直接型／間接型）
#   炭酸脱水酵素阻害薬
#   Rhoキナーゼ（ROCK）阻害薬
#   配合点眼薬
# 配合剤は複数の薬効群にまたがるため、単剤の薬効群とは重複させず独立群として扱う。
# ─────────────────────────────────────────────

# プロスタグランジン関連薬の下位分類
PGA_FP_CODES  = {"LATANOPROST", "TRAVOPROST", "TAFLUPROST", "BIMATOPROST"}
PGA_EP2_CODES = {"OMIDENEPAG"}
PGA_ION_CODES = {"UNOPROSTONE"}
PGA_CODES     = PGA_FP_CODES | PGA_EP2_CODES | PGA_ION_CODES

# 交感神経β遮断薬（ニプラジロールはα1β遮断薬でありβ遮断薬には含めない）
BETA_NONSEL_CODES = {"TIMOLOL", "CARTEOLOL", "LEVOBUNOLOL"}
BETA_B1SEL_CODES  = {"BETAXOLOL"}
BETA_CODES        = BETA_NONSEL_CODES | BETA_B1SEL_CODES

ALPHA1BETA_CODES = {"NIPRADILOL"}          # 交感神経α1β遮断薬
ALPHA1_CODES     = {"BUNAZOSIN"}           # 交感神経α1遮断薬
ALPHA2_CODES     = {"BRIMONIDINE"}         # 交感神経α2刺激薬
SYMPATHO_CODES   = {"DIPIVEFRINE"}         # 交感神経非選択性刺激薬
PARASYMPATHO_DIRECT_CODES   = {"PILOCARPINE"}   # 副交感神経刺激薬（直接型）
PARASYMPATHO_INDIRECT_CODES = {"DISTIGMINE"}    # 副交感神経刺激薬（間接型・ChE阻害）
PARASYMPATHO_CODES = PARASYMPATHO_DIRECT_CODES | PARASYMPATHO_INDIRECT_CODES
CAI_CODES   = {"DORZOLAMIDE", "BRINZOLAMIDE"}   # 炭酸脱水酵素阻害薬
ROCK_CODES  = {"RIPASUDIL"}                     # Rhoキナーゼ阻害薬
FDC_CODES   = {"FDC_PG_BETA", "FDC_CAI_BETA", "FDC_A2_BETA",
               "FDC_A2_CAI", "FDC_ROCK_A2"}     # 配合点眼薬

# 慢性緑内障治療の総量。アプラクロニジンは短期使用のため含めない。
TOTAL_CODES = (PGA_CODES | BETA_CODES | ALPHA1BETA_CODES | ALPHA1_CODES
               | ALPHA2_CODES | SYMPATHO_CODES | PARASYMPATHO_CODES
               | CAI_CODES | ROCK_CODES | FDC_CODES)

# 成分別曝露量の集計（配合剤を成分に分解する）。カテゴリ間で重複するため、
# シェア・HHI・総量の計算には使わず、別ファイルに出力する。
INGREDIENT_MAP = {
    "ING_PGA":    ("PG関連薬（成分ベース：配合剤を含む）",
                   PGA_CODES | {"FDC_PG_BETA"}),
    # ニプラジロールはα1β遮断薬でありβ遮断作用を持つため成分ベースでは含める
    "ING_BETA":   ("β遮断薬（成分ベース：配合剤・α1β遮断薬を含む）",
                   BETA_CODES | ALPHA1BETA_CODES
                   | {"FDC_PG_BETA", "FDC_CAI_BETA", "FDC_A2_BETA"}),
    "ING_CAI":    ("炭酸脱水酵素阻害薬（成分ベース：配合剤を含む）",
                   CAI_CODES | {"FDC_CAI_BETA", "FDC_A2_CAI"}),
    "ING_ALPHA2": ("α2作動薬（成分ベース：配合剤を含む）",
                   ALPHA2_CODES | {"FDC_A2_BETA", "FDC_A2_CAI", "FDC_ROCK_A2"}),
    "ING_ROCK":   ("ROCK阻害薬（成分ベース：配合剤を含む）",
                   ROCK_CODES | {"FDC_ROCK_A2"}),
}

# 薬効群の集計（ガイドライン第5版の分類。互いに重複せず、合計＝GLAUCOMA_EYE_TOTAL）
GROUP_DEFS = [
    ("PGA",          "プロスタグランジン関連薬",       PGA_CODES),
    ("BETA",         "交感神経β遮断薬",               BETA_CODES),
    ("ALPHA1BETA",   "交感神経α1β遮断薬",             ALPHA1BETA_CODES),
    ("ALPHA1",       "交感神経α1遮断薬",              ALPHA1_CODES),
    ("ALPHA2",       "交感神経α2刺激薬",              ALPHA2_CODES),
    ("SYMPATHO",     "交感神経非選択性刺激薬",         SYMPATHO_CODES),
    ("PARASYMPATHO", "副交感神経刺激薬",               PARASYMPATHO_CODES),
    ("CAI",          "炭酸脱水酵素阻害薬",             CAI_CODES),
    ("ROCK",         "Rhoキナーゼ阻害薬",              ROCK_CODES),
    ("FDC_TOTAL",    "配合点眼薬",                     FDC_CODES),
]
# 下位分類（上位群と重複するためシェア・HHIの計算には使わない）
SUBGROUP_DEFS = [
    ("PGA_FP",       "PG関連薬：FP受容体作動薬",       PGA_FP_CODES),
    ("PGA_EP2",      "PG関連薬：EP2受容体作動薬",      PGA_EP2_CODES),
    ("PGA_ION",      "PG関連薬：イオンチャネル開口薬", PGA_ION_CODES),
    ("BETA_NONSEL",  "β遮断薬：非選択性",              BETA_NONSEL_CODES),
    ("BETA_B1SEL",   "β遮断薬：β1選択性",             BETA_B1SEL_CODES),
    ("PARASYM_DIR",  "副交感神経刺激薬：直接型",       PARASYMPATHO_DIRECT_CODES),
    ("PARASYM_IND",  "副交感神経刺激薬：間接型",       PARASYMPATHO_INDIRECT_CODES),
]
GROUP_CODES = {code for code, _, _ in GROUP_DEFS}
SUBGROUP_CODES = {code for code, _, _ in SUBGROUP_DEFS}

AGGREGATE_DEFS = GROUP_DEFS + SUBGROUP_DEFS + [
    ("GLAUCOMA_EYE_TOTAL", "緑内障点眼薬（全体合計）", TOTAL_CODES),
]

# 全角数字→半角
_ZEN2HAN = str.maketrans("０１２３４５６７８９．", "0123456789.")
# 「コソプトミニ配合点眼液　０．４ｍＬ」のように、品名末尾に容量が明記されている品目を拾う
_VOLUME_RE = re.compile(r"[　\s]([０-９．]+)ｍＬ")


def base_name(drug_name: str) -> str:
    """「（選）」を除いた品名を返す（品目の同一性を判定するための正規化）。

    2024年10月開始の長期収載品の選定療養により、同一銘柄が「通常分」と「（選）」の
    2行に分割収載されるようになった。品目数を数えるとき・品目単位で数量を追うときは
    名寄せしないと2024年度だけ品目数が増え数量が分散するため、品名を正規化する。
    """
    return drug_name.replace("（選）", "")


def classify_drug(drug_name: str) -> tuple[str, str] | None:
    """医薬品名から薬剤カテゴリコードと名称を返す。該当なしはNone。"""
    for code, name, patterns in DRUG_CATEGORIES:
        if any(p in drug_name for p in patterns):
            return code, name
    return None


def ml_per_unit(drug_name: str) -> float:
    """医薬品名から「1数量あたりのmL数」を返す。

    NDBオープンデータの処方数量は品目ごとに単位（ｍＬ / 瓶 / 個）が異なる。
    緑内障点眼薬では、単位が容器（瓶・個）である品目はすべて品名の末尾に容量が
    明記されている（サンピロ点眼液…５ｍＬ＝瓶、コソプトミニ…０．４ｍＬ＝個、
    タプロスミニ／エイベリスミニ…０．３ｍＬ＝個、アイオピジンUD…０．１ｍＬ＝個）。
    逆に単位が ｍＬ の品目は品名に容量を含まない。

    この対応は2016〜2024年度（単位列が存在する年度）の外用薬・年齢性別ファイル
    全シートで検証済みであり、3,138行すべてで一致・不一致0件だった
    （単位列のない2014・2015年度も同一品目・同一品名で整合する）。
    したがって品名から単位を判定し、すべての品目をmLに換算できる。
    """
    m = _VOLUME_RE.search(drug_name)
    if m is None:
        return 1.0
    return float(m.group(1).translate(_ZEN2HAN))


def clean_count_value(val, imputation_strategy: str = "zero") -> float:
    """秘匿値（'-' 等）を補完処理する

    外用薬（処方薬）の秘匿閾値は数量1,000未満であり、全年度・全シート共通である。
    したがって秘匿セルの真値は区間 [0, 1000) にあり、zero が識別区間の下限、
    upper (999) が上限に対応する。five / random は閾値10を前提とした旧仕様。
    """
    if pd.isna(val) or str(val).strip() in ["-", "—", "－", ""]:
        if imputation_strategy == "upper":
            return 999.0
        elif imputation_strategy == "five":
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
    外用薬Excelの1シートから、緑内障点眼薬データを抽出して縦持ち形式で返す。

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

        # 「点眼」を含まない剤形（眼軟膏, 原末等）は除外
        if "点眼" not in drug_name:
            continue

        result = classify_drug(drug_name)
        if result is None:
            continue
        category_code, category_name = result
        factor = ml_per_unit(drug_name)

        for col_idx, pref_name in pref_col_map.items():
            raw_val = df.iloc[r_idx, col_idx]
            count = clean_count_value(raw_val, imputation_strategy)
            records.append({
                "year":           year,
                "prefecture":     pref_name,
                "code":           category_code,
                "procedure_name": category_name,
                "count":          count,
                "count_ml":       count * factor,
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
    )[["count", "count_ml"]].sum()
    return df_agg


def _merge_covariates(df: pd.DataFrame, covariate_path: str) -> pd.DataFrame:
    """都道府県共変量をマージし、人口10万対などの派生列を付ける。"""
    df_cov = pd.read_csv(covariate_path)
    df_cov["prefecture"] = df_cov["prefecture"].str.strip()
    df = df.copy()
    df["prefecture"] = df["prefecture"].str.strip()

    m = pd.merge(df, df_cov, on=["year", "prefecture"], how="left")
    m["count_per_100k"]        = (m["count_ml"] / m["population_total"]) * 100000
    m["count_per_100k_65plus"] = (m["count_ml"] / m["population_65plus"]) * 100000
    m["aging_rate"]            = m["population_65plus"] / m["population_total"]
    m["docs_per_100k"]         = (m["ophthalmologists"] / m["population_total"]) * 100000
    m["facilities_per_100k"]   = (m["facilities"] / m["population_total"]) * 100000
    return m


def preprocess_glaucoma(raw_dir: str, covariate_path: str,
                        output_dir: str, imputation_strategy: str = "zero",
                        nokouhi: bool = True) -> pd.DataFrame:
    """
    緑内障点眼薬解析用のデータ前処理。
    外用薬ファイル (ndb_gaiyo_YYYY.xlsx) を読み込み、共変量とマージして保存する。

    処方数量は品目単位（ｍＬ / 瓶 / 個）が混在するため mL に統一した count_ml を
    作り、人口10万対などの指標はすべて count_ml から計算する。count は公表値の
    素の合算（単位混在）であり、公表値との突合用に残している。

    nokouhi=True（主解析）のとき、2024年度だけ公費レセプトを含まない集計表に
    差し替える。2014〜2023年度はもともと公費含まない集計のみが公表されている。
    """
    print(f"Starting preprocess_glaucoma (eye drops) with strategy: {imputation_strategy}"
          f", kouhi={'含まない' if nokouhi else '含む'}...")

    gaiyo_files = glob.glob(os.path.join(raw_dir, "ndb_gaiyo_*.*"))
    years_map: dict[int, str] = {}
    for f in gaiyo_files:
        m = re.search(r"ndb_gaiyo_(\d{4})\.(xlsx|xls)", os.path.basename(f))
        if m:
            years_map[int(m.group(1))] = f

    if not years_map:
        raise FileNotFoundError(f"No ndb_gaiyo_*.xlsx files found in {raw_dir}")

    if nokouhi:
        for year in list(years_map):
            sub = raw_file("ndb_gaiyo", year, nokouhi=True)
            if sub != years_map[year]:
                print(f"  {year}年度は公費含まない版に差し替え: {os.path.basename(sub)}")
                years_map[year] = sub

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
        sub = df_raw[df_raw["code"].isin(src_codes)]
        if sub.empty:
            return pd.DataFrame()
        agg = sub.groupby(["year", "prefecture"], as_index=False)[["count", "count_ml"]].sum()
        agg["code"] = agg_code
        agg["procedure_name"] = agg_name
        return agg

    aggregates = [_make_aggregate(codes, code, name)
                  for code, name, codes in AGGREGATE_DEFS]
    df_combined = pd.concat([df_raw] + [a for a in aggregates if not a.empty],
                            ignore_index=True)

    print(f"Loading covariates from {covariate_path}...")
    df_merged = _merge_covariates(df_combined, covariate_path)

    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"ndb_processed_glaucoma_{imputation_strategy}.csv")
    df_merged.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"Eye drop dataset saved to {out_file} (shape: {df_merged.shape})")

    # --- 成分別曝露量（配合剤を成分に分解。カテゴリ間で重複するため別ファイル）---
    ing = []
    for ing_code, (ing_name, codes) in INGREDIENT_MAP.items():
        a = _make_aggregate(codes, ing_code, ing_name)
        if not a.empty:
            ing.append(a)
    if ing:
        df_ing = _merge_covariates(pd.concat(ing, ignore_index=True), covariate_path)
        ing_file = os.path.join(output_dir, f"ingredient_exposure_glaucoma_{imputation_strategy}.csv")
        df_ing.to_csv(ing_file, index=False, encoding="utf-8-sig")
        print(f"Ingredient-level exposure saved to {ing_file} (shape: {df_ing.shape})")

    return df_merged


if __name__ == "__main__":
    preprocess_glaucoma(
        raw_dir="data/raw",
        covariate_path="data/covariates/prefecture_covariates.csv",
        output_dir="緑内障点眼/processed_nokouhi",
        imputation_strategy="zero"
    )
