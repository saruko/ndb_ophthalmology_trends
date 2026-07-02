#!/usr/bin/env python3
"""
extract_age_stratified.py
NDBオープンデータ「K手術_性年齢別算定回数」（第1回〜第10回, 2014〜2023年度）から
眼腫瘍関連手術（K215-2, K216, K225系, K233〜K245, K265, K266）の
性・年齢階級別（5歳刻み）算定回数を抽出し、
4群（小児 0-14 / AYA 15-39 / 成人 40-64 / 高齢者 65+）に層別化したCSVを出力する。

入力: data/raw/ndb_age_sex/ndb_shujutsu_agesex_{year}.xlsx （厚労省サイトより取得済み）
出力:
  眼腫瘍解析/眼腫瘍手術_年齢階級別_2014_2023.csv        （5歳刻み・男女別の生データ）
  眼腫瘍解析/眼腫瘍手術_4群層別化_2014_2023.csv         （小児/AYA/成人/高齢者の集計）

注意: NDBオープンデータは10件未満の値を「-」でマスクする。
本スクリプトはマスク値を0として合算する（main pipelineのzero補完方針に合わせる）。
そのため4群集計値は真値をやや過小評価する可能性がある（特に虹彩・毛様体・脈絡膜腫瘍等の低頻度術式）。
"""
import os
import re
import glob
import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "ndb_age_sex")
OUT_DIR = os.path.dirname(os.path.dirname(__file__))  # 眼腫瘍解析/

# 対象術式: Behavior_Code(電算コード) -> (K_Code_Group, Behavior_Name)
TARGET_CODES = {
    150291610: ("K215-2", "眼瞼結膜腫瘍手術"),
    150078510: ("K216", "眼瞼結膜悪性腫瘍手術"),
    150080610: ("K225", "結膜腫瘍冷凍凝固術"),
    150291710: ("K225-2", "結膜腫瘍摘出術"),
    150080750: ("K225-3", "結膜肉芽腫摘除術"),
    150427010: ("K225-4", "角結膜悪性腫瘍切除術"),  # 2022年度診療報酬改定でコード新設
    150082110: ("K233", "眼窩内容除去術"),
    150082210: ("K234", "眼窩内腫瘍摘出術（表在性）"),
    150082310: ("K235", "眼窩内腫瘍摘出術（深在性）"),
    150082610: ("K236", "眼窩悪性腫瘍手術"),
    150083010: ("K239", "眼球内容除去術"),
    150083210: ("K241", "眼球摘出術"),
    150083910: ("K245", "眼球摘出及び組織又は義眼台充填術"),
    150087110: ("K265", "虹彩腫瘍切除術"),
    150087210: ("K266", "毛様体腫瘍切除術"),
    150295810: ("K266", "脈絡膜腫瘍切除術"),
}

# 5歳刻み年齢階級（男女とも同じ19区分）
AGE_BRACKETS = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳", "25～29歳", "30～34歳",
    "35～39歳", "40～44歳", "45～49歳", "50～54歳", "55～59歳", "60～64歳", "65～69歳",
    "70～74歳", "75～79歳", "80～84歳", "85～89歳", "90歳以上",
]

# 4群層別化マッピング（小児/AYA/成人/高齢者）
def bracket_to_group(bracket):
    if bracket in ("0～4歳", "5～9歳", "10～14歳"):
        return "小児(0-14)"
    if bracket in ("15～19歳", "20～24歳", "25～29歳", "30～34歳", "35～39歳"):
        return "AYA(15-39)"
    if bracket in ("40～44歳", "45～49歳", "50～54歳", "55～59歳", "60～64歳"):
        return "成人(40-64)"
    return "高齢者(65+)"


def clean_val(v):
    """'-'（10件未満マスク）や欠損を0として扱う。"""
    if pd.isna(v):
        return 0
    s = str(v).strip()
    if s in ("-", "—", "－", ""):
        return 0
    try:
        return int(float(s.replace(",", "")))
    except ValueError:
        return 0


def extract_year(year, file_path):
    """1年分のExcelから対象コードの性・年齢階級別件数を抽出する。"""
    xl = pd.ExcelFile(file_path)
    sheet_names = xl.sheet_names
    # 2014年度のみ「全体」1シート、以降は「外来」「入院」（加算シートは除外）
    target_sheets = [s for s in sheet_names if s in ("全体", "外来", "入院")]

    records = []
    for sheet in target_sheets:
        df = pd.read_excel(file_path, sheet_name=sheet, header=None)

        # ヘッダー行検出: 3列目(index3)="診療行為\nコード" のある行の次が年齢階級行
        header_row = None
        for r in range(min(10, len(df))):
            val = str(df.iloc[r, 3]).replace("\n", "").strip()
            if "診療行為" in val and "コード" in val:
                header_row = r
                break
        if header_row is None:
            raise ValueError(f"ヘッダー行が見つかりません: {file_path} sheet={sheet}")

        age_row = header_row + 1
        # 男性ブロック: col 7-25, 女性ブロック: col 26-44 (0-indexed)
        male_cols = list(range(7, 7 + 19))
        female_cols = list(range(26, 26 + 19))

        for r in range(age_row + 1, len(df)):
            code_raw = df.iloc[r, 3]
            if pd.isna(code_raw):
                continue
            try:
                densen_code = int(float(str(code_raw).strip().replace(",", "")))
            except ValueError:
                continue
            if densen_code not in TARGET_CODES:
                continue

            k_code, behavior_name = TARGET_CODES[densen_code]

            for sex, cols in (("男", male_cols), ("女", female_cols)):
                for bracket, c in zip(AGE_BRACKETS, cols):
                    if c >= df.shape[1]:
                        continue
                    count_raw = df.iloc[r, c]
                    count = clean_val(count_raw)
                    records.append({
                        "year": year,
                        "sheet": sheet,
                        "k_code_group": k_code,
                        "behavior_code": densen_code,
                        "behavior_name": behavior_name,
                        "sex": sex,
                        "age_bracket": bracket,
                        "count_raw": str(count_raw),
                        "count": count,
                    })
    return pd.DataFrame(records)


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "ndb_shujutsu_agesex_*.xlsx")))
    if not files:
        raise FileNotFoundError(f"No age-sex NDB files found in {RAW_DIR}")

    all_dfs = []
    for f in files:
        m = re.search(r"ndb_shujutsu_agesex_(\d{4})\.xlsx", os.path.basename(f))
        if not m:
            continue
        year = int(m.group(1))
        print(f"Processing {year} from {f} ...")
        df_year = extract_year(year, f)
        all_dfs.append(df_year)

    df_all = pd.concat(all_dfs, ignore_index=True)

    # ── 生データ出力（5歳刻み・男女別） ──
    raw_out = os.path.join(OUT_DIR, "眼腫瘍手術_年齢階級別_2014_2023.csv")
    df_all.sort_values(["year", "k_code_group", "sex", "age_bracket"]).to_csv(
        raw_out, index=False, encoding="utf-8-sig"
    )
    print(f"Saved raw age-sex data: {raw_out} (shape={df_all.shape})")

    # ── 4群層別化集計（外来+入院を合算、性別も合算） ──
    df_all["age_group_4"] = df_all["age_bracket"].map(bracket_to_group)
    df_grouped = (
        df_all.groupby(["year", "k_code_group", "behavior_name", "age_group_4"], as_index=False)["count"]
        .sum()
    )

    group_out = os.path.join(OUT_DIR, "眼腫瘍手術_4群層別化_2014_2023.csv")
    df_grouped.sort_values(["k_code_group", "year", "age_group_4"]).to_csv(
        group_out, index=False, encoding="utf-8-sig"
    )
    print(f"Saved 4-group stratified data: {group_out} (shape={df_grouped.shape})")

    # ── 全年齢合計（既存の全国合計値との整合性チェック用） ──
    df_total = df_all.groupby(["year", "k_code_group", "behavior_name"], as_index=False)["count"].sum()
    total_out = os.path.join(OUT_DIR, "眼腫瘍手術_年齢別合計_整合性チェック用_2014_2023.csv")
    df_total.sort_values(["k_code_group", "year"]).to_csv(total_out, index=False, encoding="utf-8-sig")
    print(f"Saved total-check data: {total_out} (shape={df_total.shape})")


if __name__ == "__main__":
    main()
