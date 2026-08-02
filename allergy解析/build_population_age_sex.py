#!/usr/bin/env python3
"""
build_population_age_sex.py
人口推計（各年10月1日現在）から年齢×性別の人口分母CSVを構築する。

データソース:
  総務省統計局「人口推計」各年10月1日現在 全国：年齢（各歳），男女別人口
  e-Statからの直接ダウンロード（APIキー不要）

出力:
  allergy解析/processed/population_age_sex.csv
  列: year, sex, age_group, population

NDB年度（4月〜翌3月）に対して、その年度内の10月1日時点人口を分母に対応させる
（例: 2014年度 → 2014年10月1日人口）。
"""
import csv
import os
import sys
import re
import time
import urllib.request
import pandas as pd

# ── 設定 ──

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import BASE_DIR, nokouhi_from_argv, output_dir  # noqa: E402

RAW_DIR = os.path.join(BASE_DIR, "data", "population_raw")
# 人口は公費の有無に依らないが、出力先は解析側と揃える
OUT_DIR = output_dir(nokouhi_from_argv())

# statInfId一覧（全てe-Stat: https://www.e-stat.go.jp/ ）
# 人口推計 → 全国：年齢（各歳），男女別人口（各年10月1日現在）
POP_AGE_SEX_IDS = {
    2014: ("000029025950", "pop_age_sex_2014.xlsx", 0),  # 平成26年
    2015: ("000031495530", "pop_age_sex_2015.xlsx", 0),  # 平成27年（国勢調査）
    2016: ("000031560310", "pop_age_sex_2016.xlsx", 0),  # 平成28年
    2017: ("000031690314", "pop_age_sex_2017.xlsx", 0),  # 平成29年
    2018: ("000031807138", "pop_age_sex_2018.xlsx", 0),  # 平成30年
    2019: ("000031921670", "pop_age_sex_2019.xlsx", 0),  # 令和元年
    2020: ("000032153669", "pop_age_sex_2020.xlsx", 4),  # 令和2年（国勢調査, fileKind=4）
    2021: ("000032191042", "pop_age_sex_2021.xlsx", 0),  # 令和3年
    2022: ("000040045487", "pop_age_sex_2022.xlsx", 0),  # 令和4年
    2023: ("000040166025", "pop_age_sex_2023.xlsx", 0),  # 令和5年
    2024: ("000040268910", "pop_age_sex_2024.xlsx", 0),  # 令和6年
}

# NDB年齢区分
# 2016年以降: 21区分（100歳以上まで）
AGE_GROUPS_21 = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80-84", "85-89", "90-94", "95-99", "100+",
]

# 2014-2015: 19区分（90+まで）
AGE_GROUPS_19 = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80-84", "85-89", "90+",
]


# ── ダウンロード ──

def _download(stat_inf_id, filename, file_kind=0):
    """e-Statからファイルをダウンロード（build_real_covariates.pyと同方式）"""
    filepath = os.path.join(RAW_DIR, filename)
    if os.path.exists(filepath):
        return filepath
    url = (f"https://www.e-stat.go.jp/stat-search/file-download"
           f"?statInfId={stat_inf_id}&fileKind={file_kind}")
    print(f"  DL {filename} (statInfId={stat_inf_id}, fileKind={file_kind})")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    with open(filepath, "wb") as f:
        f.write(data)
    print(f"     → {len(data):,} bytes")
    time.sleep(1)
    return filepath


def download_all():
    """全年のExcelファイルをダウンロード"""
    os.makedirs(RAW_DIR, exist_ok=True)
    print("=== 人口推計（年齢各歳×男女別）ダウンロード ===")
    for year, (sid, fname, fk) in sorted(POP_AGE_SEX_IDS.items()):
        _download(sid, fname, file_kind=fk)


# ── Excelパーサー ──

def _parse_age_label(text):
    """年齢ラベルから数値年齢を返す。100歳以上は100、総数行はNone。"""
    s = str(text).strip().replace("　", "").replace(" ", "")
    if "100" in s and ("以上" in s or "over" in s.lower()):
        return 100
    m = re.search(r"(\d+)", s)
    if m:
        age = int(m.group(1))
        if 0 <= age <= 99:
            return age
    return None


def _age_to_group_21(age):
    """各歳を21区分のNDB年齢グループに変換"""
    if age >= 100:
        return "100+"
    group_start = (age // 5) * 5
    return f"{group_start}-{group_start + 4}"


def _age_to_group_19(age):
    """各歳を19区分のNDB年齢グループに変換"""
    if age >= 90:
        return "90+"
    group_start = (age // 5) * 5
    return f"{group_start}-{group_start + 4}"


def parse_population_excel(filepath, year):
    """
    Excelファイルから年齢（各歳）×性別の人口を抽出する。

    フォーマット3パターンに対応:
    - パターンA (2014, 2016-2019 XLS 17列): age_col=7, male_col=10, female_col=11
    - パターンB (2015, 2020 XLS 9列):      age_col=1, male_col=4,  female_col=5
    - パターンC (2021-2024 XLSX 18列):      age_col=9, male_col=11, female_col=12

    動的検出: 「総数」行を見つけて列位置を特定する。

    Returns:
        list of dict: [{age: int, male: int, female: int}, ...]
        単位は千人→人に変換済み
    """
    with open(filepath, "rb") as f:
        sig = f.read(4)
    is_xls = (sig == bytes.fromhex("d0cf11e0"))
    engine = "xlrd" if is_xls else "openpyxl"

    df = pd.read_excel(filepath, sheet_name=0, header=None, engine=engine)

    # 「総数」行を検出 → 年齢列の位置を特定
    total_row = None
    age_col = None
    for i, row in df.iterrows():
        for j, v in enumerate(row):
            s = str(v).strip().replace("　", "").replace(" ", "")
            if s == "総数":
                total_row = i
                age_col = j
                break
        if total_row is not None:
            break

    if total_row is None:
        raise ValueError(f"「総数」行が見つかりません: {filepath}")

    # 総数行から男女計・男・女の列位置を特定
    # 総数行のデータから、最初の大きな数値3つが [男女計, 男, 女] の総人口
    row_vals = list(df.iloc[total_row])
    data_cols = []
    for j, v in enumerate(row_vals):
        if j <= age_col:
            continue
        try:
            num = float(v)
            if num > 1000:  # 千人単位で千以上 = 100万人以上
                data_cols.append(j)
        except (ValueError, TypeError):
            pass

    if len(data_cols) < 3:
        raise ValueError(f"データ列が3つ未満: {filepath}")

    # 最初の3列が [男女計, 男, 女]（総人口セクション）
    male_col = data_cols[1]
    female_col = data_cols[2]

    # データ行の抽出（総数行の次の行〜100歳以上まで）
    results = []
    for i in range(total_row + 1, len(df)):
        age_val = df.iloc[i, age_col]
        age = _parse_age_label(age_val)
        if age is None:
            continue

        try:
            # e-Statの人口推計は千人単位で記載。総数列・男列・女列はそれぞれ独立に
            # 四捨五入されているため、男+女 ≠ 総数 となる場合がある（±1千人の丸め差）。
            # 本パイプラインでは男女別の率を正しく算出するため、男・女列を個別に読み取る。
            male_pop = int(float(df.iloc[i, male_col])) * 1000
            female_pop = int(float(df.iloc[i, female_col])) * 1000
        except (ValueError, TypeError):
            continue

        results.append({"age": age, "male": male_pop, "female": female_pop})

    return results


# ── NDB年齢区分への集計 ──

def aggregate_to_ndb_groups(age_data, year):
    """
    各歳データをNDBの5歳階級年齢区分に集計する。

    Args:
        age_data: parse_population_excelの戻り値
        year: 対象年（2014-2015は19区分、2016以降は21区分）

    Returns:
        list of dict: [{year, sex, age_group, population}, ...]
    """
    if year <= 2015:
        group_func = _age_to_group_19
        expected_groups = set(AGE_GROUPS_19)
    else:
        group_func = _age_to_group_21
        expected_groups = set(AGE_GROUPS_21)

    # 集計用辞書
    male_groups = {}
    female_groups = {}

    for entry in age_data:
        age = entry["age"]
        group = group_func(age)
        male_groups[group] = male_groups.get(group, 0) + entry["male"]
        female_groups[group] = female_groups.get(group, 0) + entry["female"]

    # 結果構築
    records = []
    for group in (AGE_GROUPS_19 if year <= 2015 else AGE_GROUPS_21):
        records.append({
            "year": year,
            "sex": "male",
            "age_group": group,
            "population": male_groups.get(group, 0),
        })
        records.append({
            "year": year,
            "sex": "female",
            "age_group": group,
            "population": female_groups.get(group, 0),
        })

    # 検証: 期待される年齢グループが全て存在するか
    actual_groups = set(r["age_group"] for r in records)
    missing = expected_groups - actual_groups
    if missing:
        print(f"  WARNING: {year}年 - 欠損年齢グループ: {missing}")

    return records


# ── メイン ──

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1. ダウンロード
    print("=" * 60)
    print("STEP 1: ダウンロード")
    print("=" * 60)
    download_all()

    # 2. パース & 集計
    print("\n" + "=" * 60)
    print("STEP 2: パース & NDB年齢区分集計")
    print("=" * 60)

    all_records = []
    for year, (_, fname, _) in sorted(POP_AGE_SEX_IDS.items()):
        fp = os.path.join(RAW_DIR, fname)
        age_data = parse_population_excel(fp, year)

        total_pop = sum(e["male"] + e["female"] for e in age_data)
        print(f"  {year}: {len(age_data)} age entries, 総人口={total_pop:,}")

        records = aggregate_to_ndb_groups(age_data, year)
        all_records.extend(records)

    df = pd.DataFrame(all_records)

    # 3. 出力
    out_path = os.path.join(OUT_DIR, "population_age_sex.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig",
              quoting=csv.QUOTE_NONNUMERIC)

    print(f"\n{'=' * 60}")
    print(f"出力: {out_path}")
    print(f"{'=' * 60}")
    print(f"  行数: {len(df)}")
    print(f"  年範囲: {df['year'].min()} - {df['year'].max()}")
    print(f"  列: {list(df.columns)}")

    # 検証
    print(f"\n=== 検証 ===")

    # 行数チェック: 2014-2015は19×2=38行/年、2016-2024は21×2=42行/年
    expected_rows = 38 * 2 + 42 * 9  # 76 + 378 = 454
    print(f"  期待行数: {expected_rows}, 実際: {len(df)} → {'OK' if len(df) == expected_rows else 'MISMATCH!'}")

    # 各年の男女合計
    for year in sorted(df["year"].unique()):
        yr_data = df[df["year"] == year]
        total = yr_data["population"].sum()
        male_total = yr_data[yr_data["sex"] == "male"]["population"].sum()
        female_total = yr_data[yr_data["sex"] == "female"]["population"].sum()
        n_groups = yr_data["age_group"].nunique()
        print(f"  {year}: 総人口={total:>14,}  男={male_total:>13,}  女={female_total:>13,}  区分数={n_groups}")

    return df


if __name__ == "__main__":
    main()
