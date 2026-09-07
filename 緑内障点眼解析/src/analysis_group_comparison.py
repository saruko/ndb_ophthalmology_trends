# -*- coding: utf-8 -*-
"""薬効群（眼圧下降の作用機序に基づく分類）どうしを比較する。

個別薬剤単位の解析（analysis_glaucoma.py）とは別に、群レベルで
「どの群がどれだけ処方され、どう推移し、地域差がどれだけあるか」を並べて比較する。

出力:
  group_comparison_glaucoma.csv       群×年度の数量・人口10万対・シェア・CV・ジニ
  group_apc_glaucoma.csv              群別のAPC（対数線形回帰, 95%CI）
  group_share_pivot_glaucoma.csv      群×年度のシェア（%）ピボット（表用）
  group_prefecture_ranking_glaucoma.csv 群×都道府県の人口10万対（最新年度・順位付き）
"""
import os

import numpy as np
import pandas as pd

from analysis_glaucoma import calculate_apc_linear, calculate_gini
from preprocess_glaucoma import GROUP_DEFS


def run_group_comparison(processed_csv_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(processed_csv_path)

    group_codes = [c for c, _, _ in GROUP_DEFS]
    order = {c: i for i, c in enumerate(group_codes)}

    # ── 1. 群×年度の記述統計 ──
    rows = []
    total_by_year = (df[df["code"] == "GLAUCOMA_EYE_TOTAL"]
                     .groupby("year")["count_ml"].sum())
    for (year, code), g in df[df["code"].isin(group_codes)].groupby(["year", "code"]):
        rates = g["count_per_100k"].values
        mean_rate = float(np.mean(rates))
        national_ml = float(g["count_ml"].sum())
        pop = float(g["population_total"].sum())
        rows.append({
            "year": int(year),
            "group_code": code,
            "group_name": g["procedure_name"].iloc[0],
            "count_ml": national_ml,
            "count_per_100k": national_ml / pop * 100000 if pop else np.nan,
            "share": national_ml / total_by_year[year] if total_by_year[year] else np.nan,
            "mean_rate_per_100k": mean_rate,
            "cv": float(np.std(rates, ddof=1) / mean_rate) if mean_rate > 0 else np.nan,
            "gini": calculate_gini(rates) if mean_rate > 0 else np.nan,
            "min_prefecture": g.loc[g["count_per_100k"].idxmin(), "prefecture"],
            "max_prefecture": g.loc[g["count_per_100k"].idxmax(), "prefecture"],
            "max_to_min_ratio": (float(np.max(rates) / np.min(rates))
                                 if np.min(rates) > 0 else np.nan),
        })
    comp = pd.DataFrame(rows)
    comp["_o"] = comp["group_code"].map(order)
    comp = comp.sort_values(["year", "_o"]).drop(columns="_o")
    comp.to_csv(os.path.join(output_dir, "group_comparison_glaucoma.csv"),
                index=False, encoding="utf-8-sig")

    # ── 2. 群別APC ──
    apc_rows = []
    for code in group_codes:
        g = comp[comp["group_code"] == code].sort_values("year")
        g = g[g["count_per_100k"] > 0]
        if len(g) < 3:
            continue
        res = calculate_apc_linear(g["year"].values, g["count_per_100k"].values)
        res.update({
            "group_code": code,
            "group_name": g["group_name"].iloc[0],
            "start_year": int(g["year"].min()),
            "end_year": int(g["year"].max()),
            "n_years": int(len(g)),
        })
        apc_rows.append(res)
    apc = pd.DataFrame(apc_rows)
    apc["_o"] = apc["group_code"].map(order)
    apc = apc.sort_values("_o").drop(columns="_o")
    apc.to_csv(os.path.join(output_dir, "group_apc_glaucoma.csv"),
               index=False, encoding="utf-8-sig")

    # ── 3. 群シェアのピボット（%）──
    piv = comp.pivot(index="year", columns="group_name", values="share") * 100
    piv = piv.reindex(columns=[n for _, n, _ in GROUP_DEFS])
    piv.to_csv(os.path.join(output_dir, "group_share_pivot_glaucoma.csv"),
               encoding="utf-8-sig")

    # ── 4. 群×都道府県（最新年度）──
    latest = int(df["year"].max())
    pref = df[(df["year"] == latest) & df["code"].isin(group_codes)][
        ["prefecture", "code", "procedure_name", "count_ml", "count_per_100k"]].copy()
    pref["rank"] = pref.groupby("code")["count_per_100k"].rank(
        ascending=False, method="min").astype(int)
    pref["_o"] = pref["code"].map(order)
    pref = pref.sort_values(["_o", "rank"]).drop(columns="_o")
    pref.to_csv(os.path.join(output_dir, "group_prefecture_ranking_glaucoma.csv"),
                index=False, encoding="utf-8-sig")

    print(f"Saved group comparison CSVs (latest year: {latest}).")
    return comp, apc


if __name__ == "__main__":
    run_group_comparison(
        processed_csv_path="緑内障点眼解析/processed_nokouhi/ndb_processed_glaucoma_zero.csv",
        output_dir="緑内障点眼解析/processed_nokouhi",
    )
