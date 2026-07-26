# -*- coding: utf-8 -*-
"""
年齢×性別の人口10万対処方量および男女比（M:F ratio）を算出する。

入力:
  processed/ndb_allergy_age_sex_zero.csv   (year, code, procedure_name, sex, age_group, count)
  processed/population_age_sex.csv         (year, sex, age_group, population)

出力:
  processed/age_sex_rates_allergy.csv      年度×薬剤×性別×年齢群の人口10万対処方量 (Fig 1A/1B)
  processed/mf_ratio_by_age_allergy.csv    年度×薬剤×年齢群の男女比 (Table 2)
"""
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROCESSED = BASE / "processed"

AGE_ORDER = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
             "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
             "70-74", "75-79", "80-84", "85-89", "90+", "90-94", "95-99", "100+"]


def main():
    ndb = pd.read_csv(PROCESSED / "ndb_allergy_age_sex_zero.csv")
    pop = pd.read_csv(PROCESSED / "population_age_sex.csv")

    df = ndb.merge(pop, on=["year", "sex", "age_group"], how="left")
    if df.population.isna().any():
        missing = df[df.population.isna()][["year", "sex", "age_group"]].drop_duplicates()
        raise ValueError(f"人口分母が結合できない行があります:\n{missing}")

    # ── 1. 性別×年齢群の人口10万対処方量 ──
    df["count_per_100k"] = df["count"] / df["population"] * 100_000
    rates = df[["year", "code", "procedure_name", "sex", "age_group",
                "count", "population", "count_per_100k"]].copy()

    # 性別合算（Fig 1A 用）
    both = (df.groupby(["year", "code", "procedure_name", "age_group"], as_index=False)
              .agg(count=("count", "sum"), population=("population", "sum")))
    both["sex"] = "both"
    both["count_per_100k"] = both["count"] / both["population"] * 100_000
    rates = pd.concat([rates, both[rates.columns]], ignore_index=True)

    rates["age_order"] = rates["age_group"].map({a: i for i, a in enumerate(AGE_ORDER)})
    if rates.age_order.isna().any():
        unknown = sorted(rates[rates.age_order.isna()]["age_group"].astype(str).unique())
        raise ValueError(
            f"未知の age_group ラベルがあります（ExcelでCSVを保存し日付に化けた可能性）: {unknown}"
        )
    rates = rates.sort_values(["year", "code", "sex", "age_order"]).drop(columns="age_order")
    rates.to_csv(PROCESSED / "age_sex_rates_allergy.csv", index=False, encoding="utf-8-sig")

    # ── 2. 男女比（M:F）: 処方量比と人口10万対率の比 ──
    wide = df.pivot_table(index=["year", "code", "procedure_name", "age_group"],
                          columns="sex", values=["count", "count_per_100k"])
    wide.columns = [f"{v}_{s}" for v, s in wide.columns]
    wide = wide.reset_index()
    wide["mf_ratio_count"] = wide["count_male"] / wide["count_female"]
    wide["mf_ratio_rate"] = wide["count_per_100k_male"] / wide["count_per_100k_female"]
    wide["age_order"] = wide["age_group"].map({a: i for i, a in enumerate(AGE_ORDER)})
    wide = wide.sort_values(["year", "code", "age_order"]).drop(columns="age_order")
    wide.to_csv(PROCESSED / "mf_ratio_by_age_allergy.csv", index=False, encoding="utf-8-sig")

    # ── サマリー表示（2024年度・全体合計） ──
    latest = rates[(rates.year == 2024) & (rates.code == "ALLERGY_EYE_TOTAL")]
    print("=== 2024年度 抗アレルギー点眼薬（全体合計） 人口10万対処方量 ===")
    piv = latest.pivot_table(index="age_group", columns="sex", values="count_per_100k")
    piv["age_order"] = piv.index.map({a: i for i, a in enumerate(AGE_ORDER)})
    piv = piv.sort_values("age_order").drop(columns="age_order")
    print(piv.round(0).to_string())

    mf = wide[(wide.year == 2024) & (wide.code == "ALLERGY_EYE_TOTAL")]
    print("\n=== 2024年度 M:F比（率ベース） ===")
    print(mf.set_index("age_group")["mf_ratio_rate"].round(2).to_string())

    print("\n出力:")
    print(" -", PROCESSED / "age_sex_rates_allergy.csv")
    print(" -", PROCESSED / "mf_ratio_by_age_allergy.csv")


if __name__ == "__main__":
    main()
