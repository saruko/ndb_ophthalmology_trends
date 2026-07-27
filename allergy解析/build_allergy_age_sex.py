"""ndb_allergy_age_sex_zero.csv を生データから再構築する。

既存のリポジトリには本ファイルの生成スクリプトが残っていなかったため、
`src/preprocess_allergy.py` の薬剤定義・秘匿補完ロジックを再利用して再生成する。

出力: processed/ndb_allergy_age_sex_zero.csv および 内容まとめ/ndb_allergy_age_sex_zero.csv
列: year, code, procedure_name, sex, age_group, count, count_raw

年齢区分はその年度の公開粒度をそのまま保持する（2014年度は90+まで、
2015年度以降は90-94/95-99/100+ に細分化）。
"""

import argparse
import os
import re
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from preprocess_allergy import (  # noqa: E402
    DRUG_CATEGORIES, INJECTION_DRUG_CATEGORIES, ANTI_HIST_CODES,
    MED_RELEASE_CODES, IMMUNO_CODES, classify_drug, clean_count_value,
)

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RAW = os.path.join(BASE, "..", "data", "raw", "ndb_age_sex")
PROCESSED = os.path.join(BASE, "processed")
SUMMARY = os.path.join(BASE, "内容まとめ")

YEARS = range(2014, 2025)
GROUPS = {
    "ANTI_HIST": ("抗ヒスタミン点眼薬（合計）", ANTI_HIST_CODES),
    "MED_RELEASE": ("メディエーター遊離抑制点眼薬（合計）", MED_RELEASE_CODES),
    "IMMUNO": ("免疫抑制点眼薬（合計）", IMMUNO_CODES),
}
EYE_CODES = {c for c, _, _ in DRUG_CATEGORIES}


def normalize_age(label):
    """「0～4歳」→「0-4」、「90歳以上」→「90+」、「100歳以上」→「100+」"""
    s = re.sub(r"\s", "", str(label))
    m = re.match(r"^(\d+)～(\d+)歳$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d+)歳以上$", s)
    if m:
        return f"{m.group(1)}+"
    return None


def classify_injection(drug_name):
    for code, name, patterns in INJECTION_DRUG_CATEGORIES:
        if any(p in drug_name for p in patterns):
            return code, name
    return None


def load_year(path, year, is_injection, imputation):
    """1年度分のExcelから (code, name, sex, age_group) 別の数量を集計する。"""
    records = {}
    for sheet in pd.ExcelFile(path).sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        row2 = [str(x) for x in df.iloc[2]]
        row3 = [str(x) for x in df.iloc[3]]
        total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
        if total_col is None:
            continue

        # 上段（男/女）を前方補完し、下段の年齢階級と対応づける
        sex_map, last = {}, None
        for i in range(total_col + 1, df.shape[1]):
            v = re.sub(r"\s", "", row2[i])
            if v.startswith("男"):
                last = "male"
            elif v.startswith("女"):
                last = "female"
            age = normalize_age(row3[i])
            if last and age:
                sex_map[i] = (last, age)

        df[0] = df[0].ffill()
        for r_idx in range(4, len(df)):
            if str(df.iloc[r_idx, 0]).strip() != "131" and not is_injection:
                continue
            drug_name = str(df.iloc[r_idx, 3]).strip()
            if is_injection:
                res = classify_injection(drug_name)
            else:
                if "点眼" not in drug_name:
                    continue
                res = classify_drug(drug_name)
            if res is None:
                continue
            code, name = res
            for col, (sex, age) in sex_map.items():
                raw = df.iloc[r_idx, col]
                val = clean_count_value(raw, imputation)
                key = (code, name, sex, age)
                cur = records.setdefault(key, [0.0, ""])
                cur[0] += val
                if str(raw).strip() in ["-", "—", "－"]:
                    cur[1] = "-"
                elif cur[1] != "-":
                    cur[1] = str(cur[0])
    return [{"year": year, "code": c, "procedure_name": n, "sex": s,
             "age_group": a, "count": v[0], "count_raw": v[1]}
            for (c, n, s, a), v in records.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=DEFAULT_RAW,
                    help="ndb_age_sex ディレクトリ")
    ap.add_argument("--imputation", default="zero",
                    choices=["zero", "five", "random", "upper"])
    args = ap.parse_args()

    rows = []
    for year in YEARS:
        gaiyo = os.path.join(args.raw_dir, f"ndb_gaiyo_agesex_{year}.xlsx")
        chusha = os.path.join(args.raw_dir, f"ndb_chusha_agesex_{year}.xlsx")
        if os.path.exists(gaiyo):
            print(f"  {year} 外用薬 ...")
            rows += load_year(gaiyo, year, False, args.imputation)
        if os.path.exists(chusha):
            print(f"  {year} 注射薬 ...")
            rows += load_year(chusha, year, True, args.imputation)

    df = pd.DataFrame(rows)

    # カテゴリ合計と全体合計を追加
    extra = []
    for gcode, (gname, members) in GROUPS.items():
        sub = df[df["code"].isin(members)]
        g = sub.groupby(["year", "sex", "age_group"], as_index=False)["count"].sum()
        g["code"], g["procedure_name"], g["count_raw"] = gcode, gname, ""
        extra.append(g)
    tot = df[df["code"].isin(EYE_CODES)].groupby(
        ["year", "sex", "age_group"], as_index=False)["count"].sum()
    tot["code"] = "ALLERGY_EYE_TOTAL"
    tot["procedure_name"] = "抗アレルギー点眼薬（全体合計）"
    tot["count_raw"] = ""
    extra.append(tot)

    out = pd.concat([df] + extra, ignore_index=True)[
        ["year", "code", "procedure_name", "sex", "age_group", "count", "count_raw"]]
    out = out.sort_values(["year", "code", "sex", "age_group"]).reset_index(drop=True)

    for d in (PROCESSED, SUMMARY):
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "ndb_allergy_age_sex_zero.csv")
        out.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"wrote {path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
