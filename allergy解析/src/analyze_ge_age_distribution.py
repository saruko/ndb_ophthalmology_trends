"""
先発品 vs 後発品の年齢分布解析。

年齢・性別別Excelから個別製品を先発/後発に分類し、
それぞれの年齢分布・平均処方年齢を算出する。

出力:
  allergy解析/processed/ge_age_distribution.csv   — 先発/後発×年齢群別処方量
  allergy解析/processed/ge_age_mean_by_type.csv   — 先発/後発別の平均処方年齢

使用方法:
  python allergy解析/src/analyze_ge_age_distribution.py
"""

import os
import sys
import glob
import re
import numpy as np
import pandas as pd

AGE_GROUPS_21 = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
    "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
    "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+",
]
AGE_GROUPS_19 = AGE_GROUPS_21[:18] + ["90+"]

AGE_MIDPOINTS = {
    "0-4": 2, "5-9": 7, "10-14": 12, "15-19": 17,
    "20-24": 22, "25-29": 27, "30-34": 32, "35-39": 37,
    "40-44": 42, "45-49": 47, "50-54": 52, "55-59": 57,
    "60-64": 62, "65-69": 67, "70-74": 72, "75-79": 77,
    "80-84": 82, "85-89": 87, "90-94": 92, "95-99": 97,
    "90+": 92, "100+": 100,
}

DRUG_CATEGORIES = {
    "OLOPATADINE": {
        "brand_kw": ["パタノール"],
        "generic_kw": ["オロパタジン"],
    },
    "EPINASTINE": {
        "brand_kw": ["アレジオン"],
        "generic_kw": ["エピナスチン"],
    },
    "LEVOCASTINE": {
        "brand_kw": ["リボスチン"],
        "generic_kw": ["レボカバスチン"],
    },
}


def _find_project_root():
    d = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if os.path.isdir(os.path.join(d, "data", "raw")):
        return d
    marker = os.path.normpath(os.path.join(".claude", "worktrees"))
    norm = os.path.normpath(d)
    idx = norm.find(marker)
    if idx > 0:
        return norm[:idx].rstrip(os.sep)
    return d


def classify_brand_generic(drug_name):
    for cat, kw in DRUG_CATEGORIES.items():
        for bk in kw["brand_kw"]:
            if bk in drug_name:
                return cat, "brand"
        for gk in kw["generic_kw"]:
            if gk in drug_name:
                return cat, "generic"
    return None


def _clean(val):
    if pd.isna(val) or str(val).strip() in {"-", "—", "－", ""}:
        return 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return 0.0


def _find_age_header_row(df):
    for r in range(min(10, len(df))):
        vals = [str(v) for v in df.iloc[r] if not pd.isna(v)]
        n_age = sum(1 for v in vals if ("歳" in v or "以上" in v) and any(c.isdigit() for c in v))
        if n_age >= 5:
            return r
    return None


def _detect_sex_col_starts(df, age_row):
    if age_row == 0:
        return None, None
    male_start = female_start = None
    for c in range(df.shape[1]):
        v = str(df.iloc[age_row - 1, c]).strip()
        if "男" in v and male_start is None:
            male_start = c
        elif "女" in v and female_start is None:
            female_start = c
    return male_start, female_start


def _build_age_col_map(df, age_row, male_start, female_start):
    is_age = lambda v: ("歳" in str(v) or "以上" in str(v)) and any(c.isdigit() for c in str(v))
    all_age_cols = sorted(c for c in range(df.shape[1])
                          if not pd.isna(df.iloc[age_row, c]) and is_age(df.iloc[age_row, c]))
    male_cols = [c for c in all_age_cols if female_start is None or c < female_start]
    female_cols = [c for c in all_age_cols if female_start is not None and c >= female_start]
    n = len(male_cols)
    labels = AGE_GROUPS_19[:n] if n <= 19 else AGE_GROUPS_21[:n]
    return (
        list(zip(male_cols, labels[:len(male_cols)])),
        list(zip(female_cols, labels[:len(female_cols)])),
    )


def parse_sheet(year, df):
    df = df.copy()
    df[0] = df[0].ffill()

    age_row = _find_age_header_row(df)
    if age_row is None:
        return []

    male_start, female_start = _detect_sex_col_starts(df, age_row)
    male_age_cols, female_age_cols = _build_age_col_map(df, age_row, male_start, female_start)

    rows = []
    for r in range(age_row + 1, len(df)):
        if str(df.iloc[r, 0]).strip() != "131":
            continue
        drug_name = str(df.iloc[r, 3]).strip()
        if "点眼" not in drug_name:
            continue

        result = classify_brand_generic(drug_name)
        if result is None:
            continue
        cat, bg_type = result

        for sex_label, age_cols in (("male", male_age_cols), ("female", female_age_cols)):
            for col_idx, age_grp in age_cols:
                if col_idx >= df.shape[1]:
                    continue
                val = _clean(df.iloc[r, col_idx])
                rows.append({
                    "year": year,
                    "category": cat,
                    "type": bg_type,
                    "sex": sex_label,
                    "age_group": age_grp,
                    "count": val,
                })
    return rows


def main():
    project_root = _find_project_root()
    age_sex_dir = os.path.join(project_root, "data", "raw", "ndb_age_sex")
    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "processed",
    )
    os.makedirs(out_dir, exist_ok=True)

    all_rows = []
    files = sorted(glob.glob(os.path.join(age_sex_dir, "ndb_gaiyo_agesex_*.xlsx")))

    for fpath in files:
        m = re.search(r"(\d{4})\.xlsx$", fpath)
        if not m:
            continue
        year = int(m.group(1))
        xl = pd.ExcelFile(fpath)
        sheet_count = 0
        for sheet in xl.sheet_names:
            df = pd.read_excel(fpath, sheet_name=sheet, header=None)
            rows = parse_sheet(year, df)
            all_rows.extend(rows)
            sheet_count += len(rows)
        print(f"  {year}: {sheet_count} rows from {len(xl.sheet_names)} sheets")

    df = pd.DataFrame(all_rows)
    if df.empty:
        print("No data found.")
        return

    # Aggregate across sheets and products (sum by year/category/type/sex/age_group)
    agg = df.groupby(["year", "category", "type", "sex", "age_group"],
                      as_index=False)["count"].sum()

    # Also create sex-combined version
    agg_both = agg.groupby(["year", "category", "type", "age_group"],
                           as_index=False)["count"].sum()
    agg_both["sex"] = "both"
    combined = pd.concat([agg, agg_both], ignore_index=True)
    combined = combined.sort_values(["year", "category", "type", "sex", "age_group"])

    dist_path = os.path.join(out_dir, "ge_age_distribution.csv")
    combined.to_csv(dist_path, index=False, encoding="utf-8-sig")
    print(f"\nDistribution: {dist_path} ({len(combined)} rows)")

    # Compute mean age by year/category/type
    both = combined[combined["sex"] == "both"].copy()
    both["midpoint"] = both["age_group"].map(AGE_MIDPOINTS)
    both = both.dropna(subset=["midpoint"])

    mean_rows = []
    for (yr, cat, tp), grp in both.groupby(["year", "category", "type"]):
        total = grp["count"].sum()
        if total == 0:
            continue
        mean_age = (grp["midpoint"] * grp["count"]).sum() / total
        mean_rows.append({
            "year": yr,
            "category": cat,
            "type": tp,
            "mean_age": round(mean_age, 1),
            "total_count": round(total, 0),
        })

    mean_df = pd.DataFrame(mean_rows).sort_values(["category", "type", "year"])
    mean_path = os.path.join(out_dir, "ge_age_mean_by_type.csv")
    mean_df.to_csv(mean_path, index=False, encoding="utf-8-sig")
    print(f"Mean age: {mean_path} ({len(mean_df)} rows)")

    # Print summary
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cat_names = {"OLOPATADINE": "オロパタジン", "EPINASTINE": "エピナスチン", "LEVOCASTINE": "レボカバスチン"}
    print("\n=== 先発品 vs 後発品 平均処方年齢 ===")
    for cat in ["OLOPATADINE", "EPINASTINE", "LEVOCASTINE"]:
        print(f"\n--- {cat_names[cat]} ---")
        sub = mean_df[mean_df["category"] == cat]
        for tp in ["brand", "generic"]:
            s = sub[sub["type"] == tp]
            if s.empty:
                continue
            label = "先発" if tp == "brand" else "後発"
            print(f"  {label}:")
            for _, r in s.iterrows():
                print(f"    {int(r['year'])}: {r['mean_age']:.1f}歳  (n={r['total_count']:,.0f})")


if __name__ == "__main__":
    main()
