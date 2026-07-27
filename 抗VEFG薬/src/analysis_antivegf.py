"""抗VEGF薬の統計解析（全国トレンド・APC・地域格差・共変量相関・パネル回帰）。

allergy解析/src/analysis_allergy.py と同じ手法を踏襲している。
"""

import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

from drug_master import GROUPS, MOLECULE_NAMES


def calculate_gini(array):
    """Gini係数を計算する"""
    array = np.array(array, dtype=np.float64)
    if np.any(array < 0):
        array -= np.min(array)
    array = array + 1e-7  # ゼロ除算防止
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return (np.sum((2 * index - n - 1) * array)) / (n * np.sum(array))


def calculate_apc_linear(years, rates):
    """対数線形回帰による Annual Percent Change (APC)"""
    rates = np.maximum(rates, 0.001)
    log_rates = np.log(rates)
    X = sm.add_constant(years)
    results = sm.OLS(log_rates, X).fit()

    b1 = results.params[1]
    b1_se = results.bse[1]
    return {
        "apc": (np.exp(b1) - 1) * 100,
        "apc_low": (np.exp(b1 - 1.96 * b1_se) - 1) * 100,
        "apc_high": (np.exp(b1 + 1.96 * b1_se) - 1) * 100,
        "p_value": results.pvalues[1],
        "r2": results.rsquared,
    }


def _aggregate_national(national, covariates_path):
    """公表総計を成分レベル／グループレベルに畳み、全国人口を結合する。"""
    anti = national[national["category"] == "ANTI_VEGF"]
    mol = anti.groupby(["year", "molecule"], as_index=False)["quantity"].sum()
    mol = mol.rename(columns={"molecule": "code"})

    frames = [mol]
    for gcode, (gname, members) in GROUPS.items():
        g = anti[anti["molecule"].isin(members)].groupby(
            ["year"], as_index=False)["quantity"].sum()
        g["code"] = gcode
        frames.append(g)
    nat = pd.concat(frames, ignore_index=True)

    names = dict(MOLECULE_NAMES)
    names.update({k: v[0] for k, v in GROUPS.items()})
    nat["name"] = nat["code"].map(names)

    pop = pd.read_csv(covariates_path).groupby("year", as_index=False)[
        ["population_total", "population_65plus"]].sum()
    return nat.merge(pop, on="year", how="left")


def analyze_national_trends(national, covariates_path, output_dir):
    """全国トレンド（処方数量・人口10万対）とAPCを算出する。

    全国値は公表総計ベース（秘匿の影響を受けない）。
    """
    print("Analyzing national trends and APC (published totals)...")
    nat = _aggregate_national(national, covariates_path)
    nat["count_per_100k"] = nat["quantity"] / nat["population_total"] * 100000
    nat["count_per_100k_65plus"] = nat["quantity"] / nat["population_65plus"] * 100000

    # 抗VEGF全体に占めるシェア
    total = nat[nat["code"] == "ANTI_VEGF_TOTAL"].set_index("year")["quantity"]
    nat["share_of_antivegf_pct"] = nat["quantity"] / nat["year"].map(total) * 100

    apc_rows = []
    for code, g in nat.groupby("code"):
        # 収載されていない年（数量0が全国で続く年）は除外して収載期間のみ評価
        g = g[g["quantity"] > 0].sort_values("year")
        if len(g) < 3:
            print(f"  {code}: データ点が {len(g)} 点のためAPCを算出しない")
            continue
        res = calculate_apc_linear(g["year"].values, g["count_per_100k"].values)
        res.update({"code": code, "name": g["name"].iloc[0],
                    "start_year": int(g["year"].min()),
                    "end_year": int(g["year"].max()), "n_years": len(g)})
        apc_rows.append(res)

    nat.to_csv(os.path.join(output_dir, "national_trends_antivegf.csv"),
               index=False, encoding="utf-8-sig")
    df_apc = pd.DataFrame(apc_rows)
    df_apc.to_csv(os.path.join(output_dir, "national_apc_antivegf.csv"),
                  index=False, encoding="utf-8-sig")
    return nat, df_apc


def analyze_geographic_disparity(panel, output_dir):
    """都道府県間格差（CV・Gini・最大最小比）を年次×解析単位で算出する。"""
    print("Analyzing geographic disparity...")
    rows = []
    for (year, code), g in panel.groupby(["year", "code"]):
        rates = g["count_per_100k"].values
        if np.nansum(rates) == 0:
            continue
        mean_rate = np.nanmean(rates)
        std_rate = np.nanstd(rates, ddof=1) if len(rates) > 1 else 0.0
        imin, imax = int(np.nanargmin(rates)), int(np.nanargmax(rates))
        rows.append({
            "year": year, "code": code, "name": g["name"].iloc[0],
            "mean_rate_per_100k": mean_rate,
            "cv": std_rate / mean_rate if mean_rate > 0 else np.nan,
            "gini": calculate_gini(rates),
            "min_prefecture": g["prefecture"].iloc[imin], "min_rate": rates[imin],
            "max_prefecture": g["prefecture"].iloc[imax], "max_rate": rates[imax],
            "max_to_min_ratio": rates[imax] / rates[imin] if rates[imin] > 0 else np.nan,
            # 秘匿補完により0の県が出ると最大最小比が定義できないため、頑健な指標も併記
            "p90_to_p10_ratio": (np.nanpercentile(rates, 90) / np.nanpercentile(rates, 10)
                                 if np.nanpercentile(rates, 10) > 0 else np.nan),
            "n_zero_prefectures": int((rates == 0).sum()),
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(output_dir, "geographic_disparity_antivegf.csv"),
              index=False, encoding="utf-8-sig")
    return df


def analyze_covariates_correlation(panel, output_dir):
    """高齢化率・眼科医師数・眼科施設数とのSpearman相関。"""
    print("Analyzing covariate correlations...")
    rows = []
    cols = ["count_per_100k", "aging_rate", "docs_per_100k", "facilities_per_100k"]
    for (year, code), g in panel.groupby(["year", "code"]):
        v = g[cols].dropna()
        if len(v) < 5 or v["count_per_100k"].std() == 0:
            continue
        rate = v["count_per_100k"].values
        out = {"year": year, "code": code, "name": g["name"].iloc[0],
               "sample_size": len(v)}
        for label, col in [("aging", "aging_rate"), ("docs", "docs_per_100k"),
                           ("facilities", "facilities_per_100k")]:
            rho, p = spearmanr(rate, v[col].values)
            out[f"spearman_rho_{label}"] = rho
            out[f"p_value_{label}"] = p
        rows.append(out)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(output_dir, "covariates_correlation_antivegf.csv"),
              index=False, encoding="utf-8-sig")
    return df


def run_panel_regression(panel, output_dir):
    """Two-way FE（都道府県＋年固定効果）、都道府県クラスターSEのパネル回帰。"""
    print("Running panel regressions...")
    xvars = ["aging_rate", "docs_per_100k", "facilities_per_100k"]
    summary = []
    for code, g in panel.groupby("code"):
        d = g.set_index(["prefecture", "year"])[["count_per_100k"] + xvars].dropna()
        # 収載期間が短い薬剤は固定効果モデルが成立しないため除外
        if d.empty or d.index.get_level_values("year").nunique() < 3:
            print(f"  {code}: 年次が不足のため回帰を実施しない")
            continue
        try:
            results = PanelOLS(d["count_per_100k"], d[xvars],
                               entity_effects=True, time_effects=True
                               ).fit(cov_type="clustered", cluster_entity=True)
        except Exception as e:
            print(f"  {code}: パネル回帰に失敗 ({e})")
            continue
        for var in xvars:
            summary.append({
                "code": code, "name": g["name"].iloc[0], "variable": var,
                "coefficient": results.params[var], "std_err": results.std_errors[var],
                "t_stat": results.tstats[var], "p_value": results.pvalues[var],
                "r2_within": results.rsquared_within, "n_obs": results.nobs,
            })
        with open(os.path.join(output_dir, f"panel_regression_{code}_report.txt"),
                  "w", encoding="utf-8") as f:
            f.write(str(results))
    df = pd.DataFrame(summary)
    df.to_csv(os.path.join(output_dir, "panel_regression_summary_antivegf.csv"),
              index=False, encoding="utf-8-sig")
    return df


def build_prefecture_pivots(panel, output_dir):
    """都道府県別のピボット（数量・人口10万対・順位）を出力する。"""
    print("Building prefecture pivots...")
    total = panel[panel["code"] == "ANTI_VEGF_TOTAL"]

    piv_q = total.pivot_table(index="prefecture", columns="year", values="quantity")
    piv_q.columns = [f"{y}年度_処方数量" for y in piv_q.columns]
    piv_q.to_csv(os.path.join(output_dir, "prefecture_quantity_antivegf.csv"),
                 encoding="utf-8-sig")

    piv_r = total.pivot_table(index="prefecture", columns="year", values="count_per_100k")
    piv_r.columns = [f"{y}年度_人口10万対" for y in piv_r.columns]
    last = piv_r.columns[-1]
    piv_r[f"{max(total['year'])}年度_順位"] = piv_r[last].rank(ascending=False).astype(int)
    piv_r.sort_values(last, ascending=False).to_csv(
        os.path.join(output_dir, "prefecture_per_capita_ranking_antivegf.csv"),
        encoding="utf-8-sig")

    by_drug = panel.pivot_table(index=["prefecture", "name"], columns="year",
                                values="count_per_100k")
    by_drug.columns = [f"{y}年度_人口10万対" for y in by_drug.columns]
    by_drug.to_csv(os.path.join(output_dir, "prefecture_per_capita_by_drug_antivegf.csv"),
                   encoding="utf-8-sig")
