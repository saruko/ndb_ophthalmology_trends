# -*- coding: utf-8 -*-
"""都道府県比較の年齢調整（間接法）。

緑内障点眼薬の処方量の77%は65歳以上に集中しており、都道府県の粗率（人口10万対）は
年齢構成の違いをそのまま反映してしまう。そこで**間接標準化**により年齢調整を行う。

    期待値_p = Σ_s ( 全国の年齢層別処方率_s × 都道府県pの年齢層s人口 )
    SPR_p    = 観測値_p / 期待値_p            （標準化処方比。1.0が全国平均）
    年齢調整率_p = SPR_p × 全国粗率

**年齢層は 0–64歳 と 65歳以上 の2層である。** NDBオープンデータは都道府県別の年齢内訳を
公表しておらず、都道府県×年齢の人口として本リポジトリが保持しているのは
人口推計の年齢3区分に由来する総人口と65歳以上人口だけであるため。
より細かい階級での調整には都道府県×5歳階級人口の追加取得が必要である。
処方量の大部分が65歳以上に集中していることから、この2層でも粗率よりは
年齢構成の影響を大きく除去できる。

直接法（全国人口を標準人口とする）は都道府県別の年齢層別処方率を必要とするため、
本データでは実施できない。

入力:
  ndb_processed_glaucoma_zero.csv    都道府県×年度×カテゴリ（count_ml, population_total, population_65plus）
  ndb_glaucoma_age_sex_zero.csv      全国の年齢×性別集計
  population_age_sex.csv             全国の年齢×性別人口

出力:
  age_adjusted_prefecture_glaucoma.csv   都道府県×年度×カテゴリの粗率・期待値・SPR・年齢調整率
  age_adjusted_disparity_glaucoma.csv    粗率と年齢調整率それぞれの地域格差指標の対比
"""
import os

import numpy as np
import pandas as pd

from analysis_glaucoma import calculate_gini

ELDERLY = {"65-69", "70-74", "75-79", "80-84", "85-89",
           "90+", "90-94", "95-99", "100+"}


def _national_stratum_rates(agesex_csv, pop_csv):
    """全国の年齢2層（0-64 / 65+）別の処方率を年度×カテゴリで返す。

    戻り値: DataFrame(year, code, stratum, count_ml, population, rate)
    """
    ndb = pd.read_csv(agesex_csv)
    pop = pd.read_csv(pop_csv)
    ndb["stratum"] = np.where(ndb["age_group"].isin(ELDERLY), "65plus", "under65")
    pop["stratum"] = np.where(pop["age_group"].isin(ELDERLY), "65plus", "under65")

    n = ndb.groupby(["year", "code", "stratum"], as_index=False)["count_ml"].sum()
    p = pop.groupby(["year", "stratum"], as_index=False)["population"].sum()
    m = n.merge(p, on=["year", "stratum"], how="left")
    m["rate"] = m["count_ml"] / m["population"]
    return m


def run_age_adjustment(processed_csv, agesex_csv, pop_csv, output_dir,
                       codes=None):
    """間接標準化により年齢調整処方率とSPRを算出する。"""
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(processed_csv)
    rates = _national_stratum_rates(agesex_csv, pop_csv)

    if codes is not None:
        df = df[df["code"].isin(codes)]
        rates = rates[rates["code"].isin(codes)]

    wide = rates.pivot_table(index=["year", "code"], columns="stratum",
                             values="rate")
    wide = wide.rename(columns={"under65": "rate_under65",
                                "65plus": "rate_65plus"}).reset_index()

    d = df.merge(wide, on=["year", "code"], how="inner")
    d = d.dropna(subset=["population_total", "population_65plus"])
    d["population_under65"] = d["population_total"] - d["population_65plus"]

    # 期待値（全国の年齢層別処方率を都道府県の年齢構成に当てはめた場合の処方量）
    d["expected_ml"] = (d["rate_under65"] * d["population_under65"]
                        + d["rate_65plus"] * d["population_65plus"])
    d["spr"] = np.where(d["expected_ml"] > 0, d["count_ml"] / d["expected_ml"], np.nan)

    # 全国粗率（年度×カテゴリ）
    nat = d.groupby(["year", "code"], as_index=False).agg(
        national_ml=("count_ml", "sum"),
        national_pop=("population_total", "sum"))
    nat["national_crude_rate_per_100k"] = (
        nat["national_ml"] / nat["national_pop"] * 100000)
    d = d.merge(nat[["year", "code", "national_crude_rate_per_100k"]],
                on=["year", "code"], how="left")

    d["crude_rate_per_100k"] = d["count_per_100k"]
    d["age_adjusted_rate_per_100k"] = d["spr"] * d["national_crude_rate_per_100k"]
    d["aging_rate"] = d["population_65plus"] / d["population_total"]

    out = d[["year", "code", "procedure_name", "prefecture",
             "count_ml", "expected_ml", "spr",
             "crude_rate_per_100k", "age_adjusted_rate_per_100k",
             "national_crude_rate_per_100k", "aging_rate"]].copy()
    out["crude_rank"] = out.groupby(["year", "code"])["crude_rate_per_100k"].rank(
        ascending=False, method="min")
    out["age_adjusted_rank"] = out.groupby(["year", "code"])[
        "age_adjusted_rate_per_100k"].rank(ascending=False, method="min")
    out["rank_change"] = out["crude_rank"] - out["age_adjusted_rank"]
    out = out.sort_values(["year", "code", "age_adjusted_rank"])
    out.to_csv(os.path.join(output_dir, "age_adjusted_prefecture_glaucoma.csv"),
               index=False, encoding="utf-8-sig")

    # ── 粗率 vs 年齢調整率の地域格差指標 ──
    rows = []
    for (year, code), g in out.groupby(["year", "code"]):
        rec = {"year": int(year), "code": code,
               "procedure_name": g["procedure_name"].iloc[0],
               "n_prefectures": len(g)}
        for label, col in [("crude", "crude_rate_per_100k"),
                           ("age_adjusted", "age_adjusted_rate_per_100k")]:
            v = g[col].dropna().values
            if len(v) < 2 or np.mean(v) <= 0:
                continue
            rec[f"{label}_cv"] = float(np.std(v, ddof=1) / np.mean(v))
            rec[f"{label}_gini"] = calculate_gini(v)
            rec[f"{label}_max_to_min"] = (float(np.max(v) / np.min(v))
                                          if np.min(v) > 0 else np.nan)
        if "crude_cv" in rec and "age_adjusted_cv" in rec:
            rec["cv_reduction_pct"] = (
                (rec["crude_cv"] - rec["age_adjusted_cv"]) / rec["crude_cv"] * 100)
        gg = g.dropna(subset=["age_adjusted_rate_per_100k"])
        if len(gg) > 2:
            from scipy.stats import spearmanr
            rec["spearman_rho_crude_vs_adjusted"] = spearmanr(
                gg["crude_rate_per_100k"], gg["age_adjusted_rate_per_100k"])[0]
            rec["max_rank_change"] = int(gg["rank_change"].abs().max())
            rec["spr_min"] = float(gg["spr"].min())
            rec["spr_max"] = float(gg["spr"].max())
            rec["spr_min_prefecture"] = gg.loc[gg["spr"].idxmin(), "prefecture"]
            rec["spr_max_prefecture"] = gg.loc[gg["spr"].idxmax(), "prefecture"]
        rows.append(rec)
    disp = pd.DataFrame(rows)
    disp.to_csv(os.path.join(output_dir, "age_adjusted_disparity_glaucoma.csv"),
                index=False, encoding="utf-8-sig")

    print(f"Saved age-adjusted prefecture comparison "
          f"({out['code'].nunique()} categories, "
          f"{out['year'].nunique()} years).")
    return out, disp
