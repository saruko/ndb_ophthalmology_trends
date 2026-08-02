"""G016（硝子体内注射）算定回数の解析。

秘匿値の扱いは薬剤解析と同じ（zero/five/random）。
薬剤の処方数量との突合により「1バイアル＝1注射」の妥当性を検証する。
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from analysis_antivegf import calculate_gini, calculate_apc_linear  # noqa: E402
from preprocess_antivegf import impute  # noqa: E402
from paths import input_path  # noqa: E402

ANTIVEGF_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(ANTIVEGF_DIR)
DATA_DIR = ANTIVEGF_DIR
OUT_DIR = os.path.join(DATA_DIR, "processed")
COVARIATES = os.path.join(BASE, "data", "covariates", "prefecture_covariates.csv")


def _load(path, strategy, value_col="算定回数"):
    df = pd.read_csv(path)
    df = df.rename(columns={"処方数量": value_col})
    df["count"] = impute(df.rename(columns={value_col: "処方数量"}), strategy)
    return df


def national_trends(pref, cov, output_dir):
    """公表総計ベースの全国トレンドとAPC。"""
    nat = pref.groupby(["年度", "区分"], as_index=False)["総計_算定回数"].first()
    nat = nat.rename(columns={"年度": "year", "区分": "setting",
                              "総計_算定回数": "count"})
    total = nat.groupby("year", as_index=False)["count"].sum()
    total["setting"] = "合計"
    nat = pd.concat([nat, total], ignore_index=True)

    pop = pd.read_csv(cov).groupby("year", as_index=False)[
        ["population_total", "population_65plus"]].sum()
    nat = nat.merge(pop, on="year", how="left")
    nat["count_per_100k"] = nat["count"] / nat["population_total"] * 100000
    nat["count_per_100k_65plus"] = nat["count"] / nat["population_65plus"] * 100000
    nat["inpatient_share_pct"] = np.where(
        nat["setting"] == "入院",
        nat["count"] / nat["year"].map(total.set_index("year")["count"]) * 100, np.nan)
    nat.to_csv(os.path.join(output_dir, "g016_national_trends.csv"),
               index=False, encoding="utf-8-sig")

    rows = []
    for setting, g in nat.groupby("setting"):
        g = g.sort_values("year")
        res = calculate_apc_linear(g["year"].values, g["count_per_100k"].values)
        res.update({"setting": setting, "start_year": int(g["year"].min()),
                    "end_year": int(g["year"].max()), "n_years": len(g)})
        rows.append(res)
    pd.DataFrame(rows).to_csv(os.path.join(output_dir, "g016_apc.csv"),
                              index=False, encoding="utf-8-sig")
    return nat


def prefecture_analysis(pref, cov, output_dir):
    """都道府県別の人口10万対と格差指標。"""
    p = pref.groupby(["年度", "都道府県"], as_index=False)["count"].sum()
    p = p.rename(columns={"年度": "year", "都道府県": "prefecture"})
    c = pd.read_csv(cov)
    p = p.merge(c, on=["year", "prefecture"], how="left")
    p["count_per_100k"] = p["count"] / p["population_total"] * 100000
    p["aging_rate"] = p["population_65plus"] / p["population_total"] * 100
    p["docs_per_100k"] = p["ophthalmologists"] / p["population_total"] * 100000
    p["facilities_per_100k"] = p["facilities"] / p["population_total"] * 100000
    p.to_csv(os.path.join(output_dir, "g016_prefecture_panel.csv"),
             index=False, encoding="utf-8-sig")

    piv = p.pivot_table(index="prefecture", columns="year", values="count_per_100k")
    piv.columns = [f"{y}年度_人口10万対" for y in piv.columns]
    last = piv.columns[-1]
    piv[f"{int(p['year'].max())}年度_順位"] = piv[last].rank(ascending=False).astype(int)
    piv.sort_values(last, ascending=False).to_csv(
        os.path.join(output_dir, "g016_prefecture_ranking.csv"), encoding="utf-8-sig")

    rows = []
    for year, g in p.groupby("year"):
        r = g["count_per_100k"].values
        imin, imax = int(np.argmin(r)), int(np.argmax(r))
        rows.append({
            "year": year, "mean_rate_per_100k": r.mean(),
            "sd": r.std(ddof=1), "cv": r.std(ddof=1) / r.mean(),
            "gini": calculate_gini(r),
            "min_prefecture": g["prefecture"].iloc[imin], "min_rate": r[imin],
            "max_prefecture": g["prefecture"].iloc[imax], "max_rate": r[imax],
            "max_to_min_ratio": r[imax] / r[imin],
            "p90_to_p10_ratio": np.percentile(r, 90) / np.percentile(r, 10),
        })
    pd.DataFrame(rows).to_csv(
        os.path.join(output_dir, "g016_geographic_disparity.csv"),
        index=False, encoding="utf-8-sig")
    return p


def agesex_analysis(agesex, output_dir):
    """年齢階級・性別分布。"""
    a = agesex.groupby(["年度", "性別", "年齢階級"], as_index=False)["count"].sum()
    a = a.rename(columns={"年度": "year", "性別": "sex", "年齢階級": "age_group"})
    a["share_pct"] = a.groupby("year")["count"].transform(lambda s: s / s.sum() * 100)
    a.to_csv(os.path.join(output_dir, "g016_agesex_distribution.csv"),
             index=False, encoding="utf-8-sig")

    mid = {g: (92.5 if g == "90歳以上" else int(g.split("～")[0]) + 2.5)
           for g in a["age_group"].unique()}
    a["age_mid"] = a["age_group"].map(mid)
    summ = a.groupby("year").apply(lambda g: pd.Series({
        "mean_age_approx": np.average(g["age_mid"], weights=g["count"]),
        "share_75plus_pct": g.loc[g["age_mid"] >= 75, "count"].sum() / g["count"].sum() * 100,
        "male_share_pct": g.loc[g["sex"] == "男", "count"].sum() / g["count"].sum() * 100,
    }), include_groups=False).reset_index()
    summ.to_csv(os.path.join(output_dir, "g016_agesex_summary.csv"),
                index=False, encoding="utf-8-sig")
    return a


def validate_against_drugs(nat_g016, output_dir):
    """薬剤の処方数量とG016算定回数の突合（1バイアル＝1注射の妥当性検証）。"""
    drug = pd.read_csv(os.path.join(output_dir, "processed_national_published_total.csv"))
    anti = drug[drug["category"] == "ANTI_VEGF"].groupby(
        "year", as_index=False)["quantity"].sum().rename(
        columns={"quantity": "antivegf_vials"})
    ref = drug[drug["category"] == "REFERENCE"].groupby(
        "year", as_index=False)["quantity"].sum().rename(
        columns={"quantity": "triamcinolone_vials"})

    g = nat_g016[nat_g016["setting"] == "合計"][["year", "count"]].rename(
        columns={"count": "g016_procedures"})
    v = g.merge(anti, on="year", how="left").merge(ref, on="year", how="left")
    v["antivegf_per_g016_pct"] = v["antivegf_vials"] / v["g016_procedures"] * 100
    v["non_antivegf_pct"] = 100 - v["antivegf_per_g016_pct"]
    v["all_drug_vials"] = v["antivegf_vials"] + v["triamcinolone_vials"].fillna(0)
    v["all_drug_per_g016_pct"] = v["all_drug_vials"] / v["g016_procedures"] * 100
    v.to_csv(os.path.join(output_dir, "g016_vs_drug_validation.csv"),
             index=False, encoding="utf-8-sig")
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imputation", choices=["zero", "five", "random"], default="zero")
    ap.add_argument("--nokouhi", action="store_true",
                    help="公費レセプトを含まないデータ（抗VEFG薬/公費含まない）で解析する")
    args = ap.parse_args()

    global DATA_DIR, OUT_DIR
    if args.nokouhi:
        DATA_DIR = os.path.join(ANTIVEGF_DIR, "公費含まない")
        OUT_DIR = os.path.join(DATA_DIR, "processed")
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"=== G016 解析 (imputation={args.imputation}) ===")

    pref = _load(input_path(DATA_DIR, "g016_prefecture.csv"), args.imputation)
    agesex = _load(input_path(DATA_DIR, "g016_agesex.csv"), args.imputation)

    nat = national_trends(pref, COVARIATES, OUT_DIR)
    prefecture_analysis(pref, COVARIATES, OUT_DIR)
    agesex_analysis(agesex, OUT_DIR)
    validate_against_drugs(nat, OUT_DIR)
    print(f"完了: {OUT_DIR}")


if __name__ == "__main__":
    main()
