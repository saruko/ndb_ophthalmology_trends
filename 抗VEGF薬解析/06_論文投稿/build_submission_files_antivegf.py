# -*- coding: utf-8 -*-
"""
抗VEGF薬（硝子体内注射）論文 投稿用ファイルの生成

入力: 抗VEGF薬解析/公費含まない/03_解析結果/ 配下のCSV（全年度「公費レセプトを含まない」集計）
出力: 抗VEGF薬解析/06_論文投稿/投稿用/  Figure1〜6.png, Figure*_data.csv/xlsx,
      Table1〜5.csv, SupplTableS1〜S9.csv, SupplFigureS1〜S3.png, README は手書き

本スクリプト内で新たに計算するもの（原稿の査読対応で差し替えた値）:
  - APC の 95%CI を t 分布基準（df = n−2）で再計算（元CSVは z=1.96 近似）
  - ラニビズマブBSによる薬剤費削減額を「先発キット薬価」基準で再計算
    （元CSVは先発注射液薬価基準。両方を Table 3 に併記）

実行:  .venv\\Scripts\\python.exe 抗VEGF薬解析/06_論文投稿/build_submission_files_antivegf.py
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # 抗VEGF薬解析/
SRC = ROOT / "公費含まない" / "03_解析結果"
PLOTS = ROOT / "公費含まない" / "04_図表" / "plots"
KABATA = ROOT / "公費含まない" / "05_先行研究再現_Kabata"
PANEL = ROOT / "公費含まない" / "02_中間データ" / "panel_zero.csv"
OUT = HERE / "投稿用"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.labelweight": "bold",
    "legend.fontsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 100,
    "savefig.dpi": 300,
})

YEARS = list(range(2014, 2025))
OKU = 1e8  # 億円

UNIT_EN = {
    "AFLIBERCEPT": "Aflibercept 2 mg",
    "AFLIBERCEPT_8MG": "Aflibercept 8 mg",
    "AFLIBERCEPT_ALL": "Aflibercept (2 mg + 8 mg)",
    "FARICIMAB": "Faricimab",
    "BROLUCIZUMAB": "Brolucizumab",
    "RANIBIZUMAB_ORIG": "Ranibizumab originator",
    "RANIBIZUMAB_BS": "Ranibizumab biosimilar",
    "RANIBIZUMAB_ALL": "Ranibizumab (originator + biosimilar)",
    "PEGAPTANIB": "Pegaptanib",
    "ANTI_VEGF_TOTAL": "All anti-VEGF agents",
}
UNIT_ORDER = ["AFLIBERCEPT", "AFLIBERCEPT_8MG", "FARICIMAB", "BROLUCIZUMAB",
              "RANIBIZUMAB_ORIG", "RANIBIZUMAB_BS", "PEGAPTANIB"]
UNIT_COLOR = {
    "AFLIBERCEPT": "#1f77b4", "AFLIBERCEPT_8MG": "#aec7e8", "FARICIMAB": "#2ca02c",
    "BROLUCIZUMAB": "#9467bd", "RANIBIZUMAB_ORIG": "#d62728", "RANIBIZUMAB_BS": "#ff9896",
    "PEGAPTANIB": "#7f7f7f", "ANTI_VEGF_TOTAL": "#000000",
}
PRODUCT_EN = {
    "アイリーア2mg 注射液": "Aflibercept 2 mg vial",
    "アイリーア2mg キット": "Aflibercept 2 mg PFS",
    "アイリーア8mg 注射液": "Aflibercept 8 mg vial",
    "バビースモ 注射液": "Faricimab vial",
    "ベオビュ キット": "Brolucizumab PFS",
    "ルセンティス 注射液(2.3/0.23)": "Ranibizumab originator vial (2.3 mg/0.23 mL)",
    "ルセンティス 注射液(10mg/mL)": "Ranibizumab originator vial (10 mg/mL)",
    "ルセンティス キット": "Ranibizumab originator PFS",
    "ラニビズマブBS キット": "Ranibizumab biosimilar PFS",
    "マクジェン キット": "Pegaptanib PFS",
}
PRODUCT_ORDER = list(PRODUCT_EN.keys())
PRODUCT_COLOR = {
    "アイリーア2mg 注射液": "#1f77b4", "アイリーア2mg キット": "#6baed6", "アイリーア8mg 注射液": "#c6dbef",
    "バビースモ 注射液": "#2ca02c", "ベオビュ キット": "#9467bd",
    "ルセンティス 注射液(2.3/0.23)": "#a50f15", "ルセンティス 注射液(10mg/mL)": "#d62728",
    "ルセンティス キット": "#fb6a4a", "ラニビズマブBS キット": "#fcbba1", "マクジェン キット": "#7f7f7f",
}
SEX_EN = {"男": "Male", "女": "Female"}

fig_data_rows: dict[str, list[dict]] = {}


def add_rows(fig: str, panel: str, series: str, cats, values, lower=None, upper=None):
    rows = fig_data_rows.setdefault(fig, [])
    for i, (c, v) in enumerate(zip(cats, values)):
        rows.append({
            "panel": panel, "series": series, "category": c,
            "value_plotted": v,
            "value_lower": None if lower is None else lower[i],
            "value_upper": None if upper is None else upper[i],
        })


def save_fig_data(fig: str):
    rows = fig_data_rows.get(fig, [])
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"{fig}_data.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(OUT / f"{fig}_data.xlsx") as xw:
        for panel, g in df.groupby("panel", sort=False):
            wide = g.pivot_table(index="category", columns="series", values="value_plotted",
                                 aggfunc="first", sort=False)
            wide.to_excel(xw, sheet_name=panel[:31])


def thousands(x, _):
    return f"{x:,.0f}"


def panel_title(ax, text):
    ax.set_title(text, loc="left", pad=8)


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", name)


# ----------------------------------------------------------------------------
# load
# ----------------------------------------------------------------------------
nat = pd.read_csv(SRC / "全国トレンド/national_trends_antivegf.csv")
prod = pd.read_csv(SRC / "製品_剤形_バイオシミラー/product_trends_antivegf.csv")
price_tab = pd.read_csv(SRC / "製品_剤形_バイオシミラー/product_price_table_antivegf.csv")
bs_share = pd.read_csv(SRC / "製品_剤形_バイオシミラー/biosimilar_national_share.csv")
bs_cost = pd.read_csv(SRC / "製品_剤形_バイオシミラー/biosimilar_cost_impact.csv")
form_total = pd.read_csv(SRC / "製品_剤形_バイオシミラー/formulation_total_antivegf.csv")
form_mol = pd.read_csv(SRC / "製品_剤形_バイオシミラー/formulation_by_molecule_antivegf.csv")
setting = pd.read_csv(SRC / "製品_剤形_バイオシミラー/product_by_setting_antivegf.csv")
kit_pref = pd.read_csv(SRC / "製品_剤形_バイオシミラー/formulation_kit_share_by_prefecture.csv")
bs_pref = pd.read_csv(SRC / "製品_剤形_バイオシミラー/biosimilar_share_by_prefecture.csv")
age_pub = pd.read_csv(SRC / "年齢性別/agesex_distribution_published_antivegf.csv")
age_cmp = pd.read_csv(SRC / "年齢性別/agesex_distribution_comparable_antivegf.csv")
age_sum = pd.read_csv(SRC / "年齢性別/agesex_summary_antivegf.csv")
age_bounds = pd.read_csv(SRC / "品質管理_感度分析/agesex_bounds_antivegf.csv")
pref_rank = pd.read_csv(SRC / "都道府県_地域格差/prefecture_per_capita_ranking_antivegf.csv")
pref_65 = pd.read_csv(SRC / "都道府県_地域格差/prefecture_per_65plus_ranking_antivegf.csv")
pref_qty = pd.read_csv(SRC / "都道府県_地域格差/prefecture_quantity_antivegf.csv")
disp = pd.read_csv(SRC / "都道府県_地域格差/geographic_disparity_antivegf.csv")
disp65 = pd.read_csv(SRC / "都道府県_地域格差/geographic_disparity_65plus_antivegf.csv")
conv = pd.read_csv(SRC / "都道府県_地域格差/convergence_beta_antivegf.csv")
corr = pd.read_csv(SRC / "都道府県_地域格差/covariates_correlation_antivegf.csv")
panel_reg = pd.read_csv(SRC / "都道府県_地域格差/panel_regression_summary_antivegf.csv")
pref_bounds = pd.read_csv(SRC / "品質管理_感度分析/prefecture_bounds_antivegf.csv")
nat_bounds = pd.read_csv(SRC / "品質管理_感度分析/national_bounds_antivegf.csv")
listing = pd.read_csv(SRC / "品質管理_感度分析/listing_completeness_antivegf.csv")
mask_qc = pd.read_csv(SRC / "品質管理_感度分析/masking_qc_antivegf.csv")
sens_imp = pd.read_csv(SRC / "品質管理_感度分析/sensitivity_imputation_antivegf.csv")
sens_apc = pd.read_csv(SRC / "品質管理_感度分析/sensitivity_apc_antivegf.csv")
cost_dec = pd.read_csv(SRC / "医療費/cost_decomposition_yearly.csv")
cost_tot = pd.read_csv(SRC / "医療費/cost_total_with_procedure.csv")
cost_cf = pd.read_csv(SRC / "医療費/cost_counterfactual_scenarios.csv")
joinpoint = pd.read_csv(SRC / "全国トレンド/trend_joinpoint_antivegf.csv")
g016_nat = pd.read_csv(SRC / "G016硝子体内注射/g016_national_trends.csv")
g016_apc = pd.read_csv(SRC / "G016硝子体内注射/g016_apc.csv")
g016_val = pd.read_csv(SRC / "G016硝子体内注射/g016_vs_drug_validation.csv")
g016_pref = pd.read_csv(SRC / "G016硝子体内注射/g016_vs_drug_by_prefecture.csv")
kab_t1 = pd.read_csv(KABATA / "kabata_table1_national_counts.csv")
kab_t2 = pd.read_csv(KABATA / "kabata_table2_crude_rate_distribution.csv")
panel_zero = pd.read_csv(PANEL)

prod["product_en"] = prod["product_name"].map(PRODUCT_EN)
assert prod["product_en"].notna().all(), prod.loc[prod["product_en"].isna(), "product_name"].unique()

# ----------------------------------------------------------------------------
# 再計算 1: APC（t分布CI）
# ----------------------------------------------------------------------------
def apc_t(df: pd.DataFrame, value_col: str, year_col: str = "year"):
    d = df[[year_col, value_col]].dropna()
    d = d[d[value_col] > 0]
    n = len(d)
    x = d[year_col].to_numpy(float)
    y = np.log(d[value_col].to_numpy(float))
    res = stats.linregress(x, y)
    df_ = n - 2
    if df_ <= 0:
        return dict(n=n, apc=np.nan, low=np.nan, high=np.nan, p=np.nan, r2=np.nan,
                    start=int(x.min()), end=int(x.max()))
    tcrit = stats.t.ppf(0.975, df_)
    b, se = res.slope, res.stderr
    apc = (math.exp(b) - 1) * 100
    low = (math.exp(b - tcrit * se) - 1) * 100
    high = (math.exp(b + tcrit * se) - 1) * 100
    return dict(n=n, apc=apc, low=low, high=high, p=res.pvalue, r2=res.rvalue ** 2,
                start=int(x.min()), end=int(x.max()))


apc_rows = []
apc_units = ["ANTI_VEGF_TOTAL", "AFLIBERCEPT_ALL", "AFLIBERCEPT", "RANIBIZUMAB_ALL",
             "RANIBIZUMAB_ORIG", "RANIBIZUMAB_BS", "FARICIMAB", "BROLUCIZUMAB", "PEGAPTANIB"]
for code in apc_units:
    d = nat[nat["code"] == code]
    r = apc_t(d, "count_per_100k")
    apc_rows.append(dict(unit=UNIT_EN[code], code=code, period=f"{r['start']}–{r['end']}",
                         n_years=r["n"], apc_pct=r["apc"], ci95_low=r["low"], ci95_high=r["high"],
                         r2=r["r2"]))
for st, lab in [("合計", "G016 intravitreal injection, total"), ("外来", "G016, outpatient"), ("入院", "G016, inpatient")]:
    d = g016_nat[g016_nat["setting"] == st]
    r = apc_t(d, "count_per_100k")
    apc_rows.append(dict(unit=lab, code=f"G016_{st}", period=f"{r['start']}–{r['end']}",
                         n_years=r["n"], apc_pct=r["apc"], ci95_low=r["low"], ci95_high=r["high"],
                         r2=r["r2"]))
apc_df = pd.DataFrame(apc_rows)
apc_df["note"] = ("log-linear regression of rate per 100,000; 95%CI from t distribution (df=n−2); "
                  "descriptive study: no hypothesis testing, p values not reported")
apc_df.to_csv(OUT / "Table4.csv", index=False, encoding="utf-8-sig")
print(apc_df[["unit", "period", "apc_pct", "ci95_low", "ci95_high"]].round(3).to_string())

# ----------------------------------------------------------------------------
# 再計算 2: BS 削減額（先発キット薬価基準）
# ----------------------------------------------------------------------------
kit_price = (prod[prod["product_name"] == "ルセンティス キット"].set_index("year")["price"])
vial_price = (prod[prod["product_name"] == "ルセンティス 注射液(10mg/mL)"].set_index("year")["price"])
bs_rows = []
for y in YEARS:
    o = prod[(prod["year"] == y) & (prod["brand_type"] == "先発") & (prod["molecule_name"].str.startswith("ラニビズマブ"))]
    b = prod[(prod["year"] == y) & (prod["brand_type"] != "先発") & (prod["molecule_name"].str.startswith("ラニビズマブ"))]
    oq, bq = o["quantity"].sum(), b["quantity"].sum()
    bprice = b["price"].iloc[0] if len(b) else np.nan
    kp = kit_price.get(y, np.nan)
    vp = vial_price.get(y, np.nan)
    tot = oq + bq
    bs_rows.append(dict(
        year=y, originator_vials=oq, biosimilar_vials=bq, ranibizumab_total=tot,
        biosimilar_share_pct=(bq / tot * 100) if bq > 0 else np.nan,
        originator_pfs_price_jpy=kp, originator_vial_price_jpy=vp, biosimilar_price_jpy=bprice,
        biosimilar_cost_100M_jpy=(bq * bprice / OKU) if bq > 0 else np.nan,
        saving_pfs_basis_100M_jpy=(bq * (kp - bprice) / OKU) if bq > 0 else np.nan,
        saving_vial_basis_100M_jpy=(bq * (vp - bprice) / OKU) if bq > 0 else np.nan,
    ))
bs_df = pd.DataFrame(bs_rows)
cum = bs_df[["saving_pfs_basis_100M_jpy", "saving_vial_basis_100M_jpy", "biosimilar_cost_100M_jpy"]].sum()
bs_df.loc[len(bs_df)] = dict(year="cumulative 2021–2024", originator_vials=np.nan, biosimilar_vials=np.nan,
                             ranibizumab_total=np.nan, biosimilar_share_pct=np.nan,
                             originator_pfs_price_jpy=np.nan, originator_vial_price_jpy=np.nan,
                             biosimilar_price_jpy=np.nan,
                             biosimilar_cost_100M_jpy=cum["biosimilar_cost_100M_jpy"],
                             saving_pfs_basis_100M_jpy=cum["saving_pfs_basis_100M_jpy"],
                             saving_vial_basis_100M_jpy=cum["saving_vial_basis_100M_jpy"])
bs_df.to_csv(OUT / "Table3.csv", index=False, encoding="utf-8-sig")
print(bs_df.round(2).to_string())

# ----------------------------------------------------------------------------
# Table 1: 全国年次
# ----------------------------------------------------------------------------
tot = nat[nat["code"] == "ANTI_VEGF_TOTAL"].set_index("year")
cost_year = prod.groupby("year")["cost"].sum() / OKU
inpat = setting[setting["setting"] == "入院"].groupby("year")["quantity"].sum()
allq = setting.groupby("year")["quantity"].sum()
g_tot = g016_nat[g016_nat["setting"] == "合計"].set_index("year")["count"]
t1 = pd.DataFrame({
    "fiscal_year": YEARS,
    "anti_vegf_vials": [tot.loc[y, "quantity"] for y in YEARS],
    "per_100k_population": [tot.loc[y, "count_per_100k"] for y in YEARS],
    "per_100k_population_65plus": [tot.loc[y, "count_per_100k_65plus"] for y in YEARS],
    "drug_cost_100M_jpy": [cost_year[y] for y in YEARS],
    "inpatient_share_pct": [inpat[y] / allq[y] * 100 for y in YEARS],
    "g016_procedures": [g_tot.get(y, np.nan) for y in YEARS],
})
t1["anti_vegf_per_g016_pct"] = t1["anti_vegf_vials"] / t1["g016_procedures"] * 100
t1.to_csv(OUT / "Table1.csv", index=False, encoding="utf-8-sig")

# Table 2: 2024 製品別
p24 = prod[prod["year"] == 2024].copy()
p24["formulation_en"] = p24["formulation"].map({"注射液": "vial", "キット": "PFS"})
p24["brand_en"] = p24["brand_type"].map(lambda s: "biosimilar" if "BS" in str(s) or "バイオ" in str(s) else "originator")
t2 = p24[["product_en", "drug_code", "formulation_en", "brand_en", "quantity", "share_pct", "price", "cost", "cost_share_pct"]].copy()
t2["cost_100M_jpy"] = t2["cost"] / OKU
t2 = t2.drop(columns="cost").sort_values("quantity", ascending=False)
t2.loc[len(t2)] = ["Total", "", "", "", t2["quantity"].sum(), 100.0, np.nan, 100.0, t2["cost_100M_jpy"].sum()]
t2.to_csv(OUT / "Table2.csv", index=False, encoding="utf-8-sig")

# Table 5: 地域格差
d_tot = disp[disp["code"] == "ANTI_VEGF_TOTAL"].set_index("year")
d65 = disp65[disp65["code"] == "ANTI_VEGF_TOTAL"].set_index("year") if "code" in disp65.columns else None
t5 = pd.DataFrame({
    "fiscal_year": YEARS,
    "gini": [d_tot.loc[y, "gini"] for y in YEARS],
    "cv": [d_tot.loc[y, "cv"] for y in YEARS],
    "max_to_min_ratio": [d_tot.loc[y, "max_to_min_ratio"] for y in YEARS],
    "p90_to_p10_ratio": [d_tot.loc[y, "p90_to_p10_ratio"] for y in YEARS],
    "n_zero_prefectures": [d_tot.loc[y, "n_zero_prefectures"] for y in YEARS],
    "max_prefecture": [d_tot.loc[y, "max_prefecture"] for y in YEARS],
    "min_prefecture": [d_tot.loc[y, "min_prefecture"] for y in YEARS],
})
if d65 is not None and "gini_65plus" in d65.columns:
    t5["gini_65plus_denominator"] = [d65.loc[y, "gini_65plus"] if y in d65.index else np.nan for y in YEARS]
    t5["cv_65plus_denominator"] = [d65.loc[y, "cv_65plus"] if y in d65.index else np.nan for y in YEARS]
    t5["max_to_min_ratio_65plus"] = [d65.loc[y, "max_to_min_ratio_65plus"] if y in d65.index else np.nan for y in YEARS]
t5.to_csv(OUT / "Table5.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------
# Supplementary tables
# ----------------------------------------------------------------------------
# S1 drug master + prices
s1 = prod.groupby(["drug_code", "product_name", "product_en", "molecule_name", "formulation", "brand_type"]).agg(
    first_year=("year", "min"), last_year=("year", "max")).reset_index()
price_wide = prod.pivot_table(index="drug_code", columns="year", values="price", aggfunc="first")
price_wide.columns = [f"price_FY{c}_jpy" for c in price_wide.columns]
s1 = s1.merge(price_wide, left_on="drug_code", right_index=True, how="left")
s1 = s1.merge(listing[["code", "marketed_from", "marketed_to", "listed_years", "expected_years", "complete"]],
              left_on="drug_code", right_on="code", how="left").drop(columns="code")
s1.to_csv(OUT / "SupplTableS1.csv", index=False, encoding="utf-8-sig")

# S2 prefecture per 100k by year
s2 = pref_rank.copy()
s2.to_csv(OUT / "SupplTableS2.csv", index=False, encoding="utf-8-sig")

# S3 prefecture BS share, PFS share, capture ratio (2024)
kit24 = kit_pref[kit_pref["formulation"] == "キット"][["prefecture", "share_pct"]].rename(columns={"share_pct": "pfs_share_pct_2024"})
g24 = g016_pref[g016_pref["year"] == 2024][["prefecture", "antivegf_vials", "g016_procedures", "ratio_pct"]].rename(
    columns={"ratio_pct": "antivegf_per_g016_pct_2024"})
s3 = bs_pref.merge(kit24, on="prefecture", how="outer").merge(g24, on="prefecture", how="outer")
s3 = s3.merge(pref_rank[["prefecture", "2024年度_人口10万対", "2024年度_順位"]], on="prefecture", how="left")
s3 = s3.merge(pref_65[["prefecture", "2024年度_65歳以上10万対", "2024年度_順位"]].rename(
    columns={"2024年度_65歳以上10万対": "per_100k_65plus_2024", "2024年度_順位": "rank_65plus_2024"}), on="prefecture", how="left")
s3 = s3.rename(columns={"2024年度_人口10万対": "per_100k_2024", "2024年度_順位": "rank_2024"})
s3.to_csv(OUT / "SupplTableS3.csv", index=False, encoding="utf-8-sig")

# S4 masking QC summary + imputation sensitivity
qc = mask_qc.copy()
qc_sum = qc.groupby(["table", "year"]).apply(
    lambda g: pd.Series({
        "n_cells": g["n_cells"].sum(), "n_masked": g["n_masked"].sum(),
        "masked_cell_pct": g["n_masked"].sum() / g["n_cells"].sum() * 100,
        "observed_sum": g["observed"].sum(), "reported_total_sum": g["reported_total"].sum(),
        "coverage_pct": g["observed"].sum() / g["reported_total"].sum() * 100,
    })).reset_index()
with open(OUT / "SupplTableS4.csv", "w", encoding="utf-8-sig", newline="") as f:
    f.write("# Part A: cell suppression and coverage by table and fiscal year (zero-imputed breakdown sum / published national total)\n")
    qc_sum.to_csv(f, index=False)
    f.write("\n# Part B: sensitivity of Gini coefficient and prefecture ranking to imputation (zero / five / random 1-9)\n")
    sens_imp.to_csv(f, index=False)
    f.write("\n# Part C: sensitivity of APC (prefecture-breakdown-based national rate) to imputation\n")
    sens_apc.to_csv(f, index=False)

# S5 panel regression + correlations
with open(OUT / "SupplTableS5.csv", "w", encoding="utf-8-sig", newline="") as f:
    f.write("# Part A: two-way fixed-effects panel regression (prefecture and year FE; prefecture-clustered robust SE). Outcome: vials per 100,000 population\n")
    panel_reg.to_csv(f, index=False)
    f.write("\n# Part B: Spearman rank correlation between prefecture-level rate per 100,000 and covariates, by fiscal year\n")
    corr.to_csv(f, index=False)
    f.write("\n# Part C: beta/sigma convergence\n")
    conv.to_csv(f, index=False)

# S6 Kabata comparison
kab_t1.to_csv(OUT / "SupplTableS6.csv", index=False, encoding="utf-8-sig")
with open(OUT / "SupplTableS6.csv", "a", encoding="utf-8-sig", newline="") as f:
    f.write("\n# Part B: distribution of crude prefecture rates (per 100,000), cf. Kabata et al. 2026 Table 2\n")
    kab_t2.to_csv(f, index=False)

# S7 prefecture bounds 2024 (all anti-VEGF) with per 100k
pop24 = panel_zero[(panel_zero["year"] == 2024) & (panel_zero["code"] == "ANTI_VEGF_TOTAL")][["prefecture", "population_total"]]
pb = pref_bounds[(pref_bounds["year"] == 2024)].copy()
pb = pb.merge(pop24, left_on="都道府県", right_on="prefecture", how="left")
pb["lower_per_100k"] = pb["lower"] / pb["population_total"] * 1e5
pb["upper_per_100k"] = pb["upper"] / pb["population_total"] * 1e5
pb["unit"] = pb["molecule"].map(UNIT_EN)
pb = pb[["year", "molecule", "unit", "都道府県", "lower", "upper", "width_pct", "population_total", "lower_per_100k", "upper_per_100k"]]
pb = pb.rename(columns={"都道府県": "prefecture"})
pb.to_csv(OUT / "SupplTableS7.csv", index=False, encoding="utf-8-sig")

# S8 joinpoint
joinpoint.to_csv(OUT / "SupplTableS8.csv", index=False, encoding="utf-8-sig")

# S9 age-sex bounds 2024 (all anti-VEGF, published granularity)
ab = age_bounds[(age_bounds["year"] == 2024) & (age_bounds["molecule"] == "ANTI_VEGF_TOTAL")].copy()
ab["sex"] = ab["性別"].map(SEX_EN)
ab = ab.rename(columns={"年齢階級": "age_group"})[["year", "molecule", "sex", "age_group", "lower", "upper", "width_pct"]]
ab.to_csv(OUT / "SupplTableS9.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------
# Figure 1: 全国トレンド（製品別積み上げ、解析単位別シェア）
# ----------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(8.5, 10.5))
ax = axes[0]
pq = prod.pivot_table(index="year", columns="product_name", values="quantity", aggfunc="sum").reindex(YEARS).fillna(0)
pq = pq[[p for p in PRODUCT_ORDER if p in pq.columns]]
bottom = np.zeros(len(YEARS))
for p in pq.columns:
    vals = pq[p].to_numpy() / 1000
    ax.bar(YEARS, vals, bottom=bottom, color=PRODUCT_COLOR[p], label=PRODUCT_EN[p], width=0.75, edgecolor="white", linewidth=0.4)
    add_rows("Figure1", "Fig1A_quantity_by_product_thousand_vials", PRODUCT_EN[p], YEARS, vals)
    bottom += vals
ax.plot(YEARS, bottom, color="black", marker="o", ms=3, lw=1.2, label="All anti-VEGF agents (total)")
add_rows("Figure1", "Fig1A_quantity_by_product_thousand_vials", "All anti-VEGF agents (total)", YEARS, bottom)
ax.set_ylabel("Vials / prefilled syringes (thousands)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.yaxis.set_major_formatter(FuncFormatter(thousands))
ax.legend(ncol=2, frameon=False, fontsize=8, loc="upper left")
panel_title(ax, "A. Nationwide quantity of anti-VEGF intravitreal agents by product, FY2014–2024")

ax = axes[1]
sh = nat[nat["code"].isin(UNIT_ORDER)].pivot_table(index="year", columns="code", values="share_of_antivegf_pct").reindex(YEARS).fillna(0)
sh = sh[[c for c in UNIT_ORDER if c in sh.columns]]
bottom = np.zeros(len(YEARS))
for c in sh.columns:
    ax.bar(YEARS, sh[c].to_numpy(), bottom=bottom, color=UNIT_COLOR[c], label=UNIT_EN[c], width=0.75, edgecolor="white", linewidth=0.4)
    add_rows("Figure1", "Fig1B_share_pct_by_unit", UNIT_EN[c], YEARS, sh[c].to_numpy())
    bottom += sh[c].to_numpy()
ax.set_ylim(0, 100)
ax.set_ylabel("Share of anti-VEGF quantity (%)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.legend(ncol=2, frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14))
panel_title(ax, "B. Composition by agent (analysis unit), FY2014–2024")
fig.text(0.01, 0.995, "Fig. 1", fontsize=16, va="top")
fig.tight_layout(rect=(0, 0, 1, 0.97))
save(fig, "Figure1")
save_fig_data("Figure1")

# ----------------------------------------------------------------------------
# Figure 2: 剤形（バイアル vs プレフィルドシリンジ）
# ----------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(8.5, 9.5))
ax = axes[0]
ft = form_total.pivot_table(index="year", columns="formulation", values="share_pct").reindex(YEARS)
ax.bar(YEARS, ft["注射液"], color="#9ecae1", label="Vial", width=0.75)
ax.bar(YEARS, ft["キット"], bottom=ft["注射液"], color="#3182bd", label="Prefilled syringe (PFS)", width=0.75)
for y in YEARS:
    ax.text(y, ft.loc[y, "注射液"] + ft.loc[y, "キット"] / 2, f"{ft.loc[y, 'キット']:.1f}", ha="center", va="center", color="white", fontsize=8)
add_rows("Figure2", "Fig2A_formulation_share_pct", "Vial", YEARS, ft["注射液"].to_numpy())
add_rows("Figure2", "Fig2A_formulation_share_pct", "Prefilled syringe", YEARS, ft["キット"].to_numpy())
ax.set_ylim(0, 100)
ax.set_ylabel("Share of all anti-VEGF quantity (%)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, 1.0), ncol=2)
panel_title(ax, "A. Formulation share of all anti-VEGF agents (labels: PFS %)")

ax = axes[1]
fm = form_mol[(form_mol["formulation"] == "キット") & (form_mol["has_both_formulations"])]
for code, lab, col, mk in [("AFLIBERCEPT", "Aflibercept 2 mg (PFS launched FY2020)", "#1f77b4", "o"),
                           ("RANIBIZUMAB_ORIG", "Ranibizumab originator", "#d62728", "s")]:
    d = fm[fm["molecule"] == code].set_index("year")["share_within_molecule_pct"].reindex(YEARS)
    ax.plot(YEARS, d, marker=mk, ms=4, lw=1.5, color=col, label=lab)
    add_rows("Figure2", "Fig2B_pfs_share_within_molecule_pct", lab, YEARS, d.to_numpy())
# ラニビズマブ全体（先発キット＋先発注射液＋BS キット）。BS はキット専用のため BS 置換に伴い機械的に上昇する
# （曝露・構成の指標）。剤形選好の指標は先発内の比率（上の実線）。
rq = form_mol[form_mol["molecule"].isin(["RANIBIZUMAB_ORIG", "RANIBIZUMAB_BS"])]
rq_all = rq.groupby("year")["quantity"].sum()
rq_kit = rq[rq["formulation"] == "キット"].groupby("year")["quantity"].sum()
ranib_all_pfs = (rq_kit / rq_all * 100).reindex(YEARS)
ax.plot(YEARS, ranib_all_pfs, color="#d62728", ls="--", lw=1.2, marker="s", ms=3, mfc="white",
        label="Ranibizumab, all (originator + biosimilar; biosimilar is PFS-only)")
add_rows("Figure2", "Fig2B_pfs_share_within_molecule_pct", "Ranibizumab all (originator + biosimilar)", YEARS, ranib_all_pfs.to_numpy())
ax.plot(YEARS, ft["キット"], color="black", ls="--", lw=1.2, label="All anti-VEGF agents (overall PFS share)")
add_rows("Figure2", "Fig2B_pfs_share_within_molecule_pct", "All anti-VEGF agents", YEARS, ft["キット"].to_numpy())
ax.set_ylim(0, 100)
ax.set_ylabel("PFS share within the agent (%)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.legend(frameon=False, loc="lower right", fontsize=8)
panel_title(ax, "B. PFS share within agents marketed in both formulations")
fig.text(0.01, 0.995, "Fig. 2", fontsize=16, va="top")
fig.tight_layout(rect=(0, 0, 1, 0.97))
save(fig, "Figure2")
save_fig_data("Figure2")

# ----------------------------------------------------------------------------
# Figure 3: ラニビズマブ 先発 vs BS
# ----------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(8.5, 9.5))
ax = axes[0]
b = bs_df[bs_df["year"].apply(lambda v: isinstance(v, (int, np.integer)))].set_index("year")
ax.bar(YEARS, b["originator_vials"] / 1000, color="#d62728", label="Originator (Lucentis)", width=0.75)
ax.bar(YEARS, b["biosimilar_vials"] / 1000, bottom=b["originator_vials"] / 1000, color="#fcbba1", label="Biosimilar", width=0.75)
ax.plot(YEARS, b["ranibizumab_total"] / 1000, color="black", marker="o", ms=3, lw=1.2, label="Ranibizumab total")
add_rows("Figure3", "Fig3A_ranibizumab_thousand_vials", "Originator", YEARS, (b["originator_vials"] / 1000).to_numpy())
add_rows("Figure3", "Fig3A_ranibizumab_thousand_vials", "Biosimilar", YEARS, (b["biosimilar_vials"] / 1000).to_numpy())
add_rows("Figure3", "Fig3A_ranibizumab_thousand_vials", "Total", YEARS, (b["ranibizumab_total"] / 1000).to_numpy())
ax.set_ylabel("Vials / PFS (thousands)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.set_ylim(0, 240)
ax.legend(frameon=False, loc="upper left", ncol=3)
panel_title(ax, "A. Ranibizumab: originator versus biosimilar quantity")

ax = axes[1]
share = b["biosimilar_share_pct"]
ax.plot(YEARS, share, color="#b2182b", marker="o", ms=5, lw=2, label="Biosimilar share of ranibizumab (%)")
for y in [2021, 2022, 2023, 2024]:
    ax.annotate(f"{share[y]:.1f}%", (y, share[y]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
add_rows("Figure3", "Fig3B_bs_share_and_prices", "Biosimilar share (%)", YEARS, share.to_numpy())
ax.set_ylim(0, 100)
ax.set_ylabel("Biosimilar share (%)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax2 = ax.twinx()
ax2.spines["right"].set_visible(True)
kp = b["originator_pfs_price_jpy"] / 1000
vp = b["originator_vial_price_jpy"] / 1000
bp = b["biosimilar_price_jpy"] / 1000
ax2.plot(YEARS, kp, color="#d62728", ls="--", marker="s", ms=3, lw=1.2, label="Originator PFS price")
ax2.plot(YEARS, vp, color="#d62728", ls=":", marker="^", ms=3, lw=1.2, label="Originator vial price")
ax2.plot(YEARS, bp, color="#fb6a4a", ls="--", marker="D", ms=3, lw=1.2, label="Biosimilar price")
add_rows("Figure3", "Fig3B_bs_share_and_prices", "Originator PFS price (thousand JPY)", YEARS, kp.to_numpy())
add_rows("Figure3", "Fig3B_bs_share_and_prices", "Originator vial price (thousand JPY)", YEARS, vp.to_numpy())
add_rows("Figure3", "Fig3B_bs_share_and_prices", "Biosimilar price (thousand JPY)", YEARS, bp.to_numpy())
ax2.set_ylabel("NHI drug price (thousand JPY per unit)")
ax2.set_ylim(0, 200)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, frameon=False, loc="center left", fontsize=8)
panel_title(ax, "B. Biosimilar share and NHI drug prices of ranibizumab products")
fig.text(0.01, 0.995, "Fig. 3", fontsize=16, va="top")
fig.tight_layout(rect=(0, 0, 1, 0.97))
save(fig, "Figure3")
save_fig_data("Figure3")

# ----------------------------------------------------------------------------
# Figure 4: 年齢・性別
# ----------------------------------------------------------------------------
def age_sort_key(s: str):
    s = str(s)
    if s.startswith("100"):
        return 100
    return int(s.split("～")[0].split("歳")[0])


def age_en(s: str):
    s = str(s)
    if s.startswith("100"):
        return "100+"
    if "歳以上" in s:
        return s.replace("歳以上", "+")
    return s.replace("～", "–").replace("歳", "")


fig = plt.figure(figsize=(8.5, 13))
gs = fig.add_gridspec(3, 1, height_ratios=[1.1, 1.2, 0.9], hspace=0.45)
# A heatmap
ax = fig.add_subplot(gs[0])
cmp_tot = age_cmp.groupby(["year", "age_group"])["quantity"].sum().reset_index()
cmp_tot["share"] = cmp_tot["quantity"] / cmp_tot.groupby("year")["quantity"].transform("sum") * 100
groups = sorted(cmp_tot["age_group"].unique(), key=age_sort_key)
hm = cmp_tot.pivot_table(index="age_group", columns="year", values="share").reindex(groups).reindex(columns=YEARS)
im = ax.imshow(hm.to_numpy(), aspect="auto", cmap="YlOrRd", origin="lower")
ax.set_yticks(range(len(groups)))
ax.set_yticklabels([age_en(g) for g in groups], fontsize=8)
ax.set_xticks(range(len(YEARS)))
ax.set_xticklabels(YEARS)
ax.set_xlabel("Fiscal year")
ax.set_ylabel("Age group (years)")
for i, g in enumerate(groups):
    for j, y in enumerate(YEARS):
        v = hm.loc[g, y]
        if v >= 1:
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6.5, color="black" if v < 15 else "white")
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("Share of annual quantity (%)")
for g in groups:
    add_rows("Figure4", "Fig4A_age_share_pct_heatmap", age_en(g), YEARS, hm.loc[g].to_numpy())
panel_title(ax, "A. Age distribution of anti-VEGF quantity by fiscal year (%, 90+ pooled)")

# B pyramid 2024 with bounds
ax = fig.add_subplot(gs[1])
pub24 = age_pub[age_pub["year"] == 2024]
ab24 = age_bounds[(age_bounds["year"] == 2024) & (age_bounds["molecule"] == "ANTI_VEGF_TOTAL")]
g21 = sorted(pub24["age_group_detail"].unique(), key=age_sort_key)
g21 = [g for g in g21 if not str(g).startswith("100")]  # 100+ excluded (fully suppressed)
ypos = np.arange(len(g21))
for sex, sign, col in [("男", -1, "#3182bd"), ("女", 1, "#e6550d")]:
    d = pub24[pub24["sex"] == sex].set_index("age_group_detail")["quantity"].reindex(g21).fillna(0) / 1000
    bd = ab24[ab24["性別"] == sex].set_index("年齢階級").reindex(g21)
    up = (bd["upper"] / 1000).fillna(d)
    ax.barh(ypos, sign * d, color=col, height=0.8, label=SEX_EN[sex])
    ax.errorbar(sign * d, ypos, xerr=[np.zeros(len(d)), (up - d).clip(lower=0)] if sign > 0 else [(up - d).clip(lower=0), np.zeros(len(d))],
                fmt="none", ecolor="black", elinewidth=0.8, capsize=2)
    add_rows("Figure4", "Fig4B_pyramid_2024_thousand_vials", SEX_EN[sex], [age_en(g) for g in g21], d.to_numpy(),
             lower=d.to_numpy(), upper=up.to_numpy())
ax.set_yticks(ypos)
ax.set_yticklabels([age_en(g) for g in g21], fontsize=8)
ax.set_ylabel("Age group (years)")
ax.set_xlabel("Vials / PFS (thousands)")
lim = max(abs(v) for v in ax.get_xlim()) * 1.05
ax.set_xlim(-lim, lim)
ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{abs(x):,.0f}"))
ax.axvline(0, color="black", lw=0.8)
ax.legend(frameon=False, loc="lower right")
panel_title(ax, "B. Age–sex distribution, FY2024 (bars = zero-imputed; whiskers = upper bound)")

# C trends
ax = fig.add_subplot(gs[2])
s = age_sum.set_index("year").reindex(YEARS)
ax.plot(YEARS, s["share_75plus_pct"], marker="o", ms=4, color="#e6550d", label="Share aged 75+ (%)")
ax.plot(YEARS, s["male_share_pct"], marker="s", ms=4, color="#3182bd", label="Male share (%)")
ax.set_ylabel("Percent (%)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.set_ylim(40, 70)
ax2 = ax.twinx()
ax2.spines["right"].set_visible(True)
ax2.plot(YEARS, s["mean_age_approx"], marker="^", ms=4, color="black", ls="--", label="Approximate mean age (years)")
ax2.set_ylabel("Approximate mean age (years)")
ax2.set_ylim(72, 78)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper left", ncol=3, fontsize=8)
add_rows("Figure4", "Fig4C_patient_profile_trends", "Share aged 75+ (%)", YEARS, s["share_75plus_pct"].to_numpy())
add_rows("Figure4", "Fig4C_patient_profile_trends", "Male share (%)", YEARS, s["male_share_pct"].to_numpy())
add_rows("Figure4", "Fig4C_patient_profile_trends", "Approximate mean age (years)", YEARS, s["mean_age_approx"].to_numpy())
panel_title(ax, "C. Ageing and sex composition, FY2014–2024")
fig.text(0.01, 0.995, "Fig. 4", fontsize=16, va="top")
fig.subplots_adjust(top=0.96, bottom=0.05)
save(fig, "Figure4")
save_fig_data("Figure4")

# ----------------------------------------------------------------------------
# Figure 5: 都道府県
# ----------------------------------------------------------------------------
PREF_EN = {
    "北海道": "Hokkaido", "青森県": "Aomori", "岩手県": "Iwate", "宮城県": "Miyagi", "秋田県": "Akita", "山形県": "Yamagata",
    "福島県": "Fukushima", "茨城県": "Ibaraki", "栃木県": "Tochigi", "群馬県": "Gunma", "埼玉県": "Saitama", "千葉県": "Chiba",
    "東京都": "Tokyo", "神奈川県": "Kanagawa", "新潟県": "Niigata", "富山県": "Toyama", "石川県": "Ishikawa", "福井県": "Fukui",
    "山梨県": "Yamanashi", "長野県": "Nagano", "岐阜県": "Gifu", "静岡県": "Shizuoka", "愛知県": "Aichi", "三重県": "Mie",
    "滋賀県": "Shiga", "京都府": "Kyoto", "大阪府": "Osaka", "兵庫県": "Hyogo", "奈良県": "Nara", "和歌山県": "Wakayama",
    "鳥取県": "Tottori", "島根県": "Shimane", "岡山県": "Okayama", "広島県": "Hiroshima", "山口県": "Yamaguchi",
    "徳島県": "Tokushima", "香川県": "Kagawa", "愛媛県": "Ehime", "高知県": "Kochi", "福岡県": "Fukuoka", "佐賀県": "Saga",
    "長崎県": "Nagasaki", "熊本県": "Kumamoto", "大分県": "Oita", "宮崎県": "Miyazaki", "鹿児島県": "Kagoshima", "沖縄県": "Okinawa",
}
fig = plt.figure(figsize=(8.5, 13))
gs = fig.add_gridspec(2, 1, height_ratios=[2.4, 1], hspace=0.25)
ax = fig.add_subplot(gs[0])
r = pref_rank[["prefecture", "2024年度_人口10万対"]].rename(columns={"2024年度_人口10万対": "rate"})
r = r.merge(g24[["prefecture", "antivegf_per_g016_pct_2024"]], on="prefecture", how="left")
r = r.sort_values("rate", ascending=True)
nat_rate = tot.loc[2024, "count_per_100k"]
cols = ["#9e9e9e" if v < 90 else "#3182bd" for v in r["antivegf_per_g016_pct_2024"]]
bars = ax.barh(range(len(r)), r["rate"], color=cols, height=0.75)
for i, (v, cap) in enumerate(zip(r["rate"], r["antivegf_per_g016_pct_2024"])):
    if cap < 90:
        bars[i].set_hatch("///")
        bars[i].set_edgecolor("white")
ax.axvline(nat_rate, color="black", ls="--", lw=1)
ax.text(nat_rate, len(r) - 0.5, f" National {nat_rate:,.0f}", va="top", fontsize=8)
ax.set_yticks(range(len(r)))
ax.set_yticklabels([PREF_EN[p] for p in r["prefecture"]], fontsize=7.5)
ax.set_xlabel("Vials / PFS per 100,000 population, FY2024")
ax.xaxis.set_major_formatter(FuncFormatter(thousands))
ax.set_ylim(-0.6, len(r) - 0.4)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#3182bd", label="Zero-imputed prefecture breakdown"),
                   Patch(facecolor="#9e9e9e", hatch="///", edgecolor="white", label="Breakdown captures <90% of G016 claims (under-estimated)")],
          frameon=False, loc="center right", fontsize=8)
add_rows("Figure5", "Fig5A_prefecture_per_100k_2024", "Rate per 100,000 (zero-imputed)", [PREF_EN[p] for p in r["prefecture"]], r["rate"].to_numpy())
add_rows("Figure5", "Fig5A_prefecture_per_100k_2024", "Anti-VEGF vials / G016 claims (%)", [PREF_EN[p] for p in r["prefecture"]], r["antivegf_per_g016_pct_2024"].to_numpy())
panel_title(ax, "A. Prefecture-level utilisation per 100,000 population, FY2024")

ax = fig.add_subplot(gs[1])
ax.plot(YEARS, t5["gini"], marker="o", ms=4, color="#b2182b", label="Gini coefficient")
ax.plot(YEARS, t5["cv"], marker="s", ms=4, color="#3182bd", label="Coefficient of variation")
if "gini_65plus_denominator" in t5.columns:
    ax.plot(YEARS, t5["gini_65plus_denominator"], marker="o", ms=3, ls=":", color="#b2182b", label="Gini (per 65+ population)")
    add_rows("Figure5", "Fig5B_disparity_indices", "Gini (65+ denominator)", YEARS, t5["gini_65plus_denominator"].to_numpy())
ax.set_ylim(0, 0.5)
ax.set_ylabel("Gini / CV")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax2 = ax.twinx()
ax2.spines["right"].set_visible(True)
ax2.plot(YEARS, t5["p90_to_p10_ratio"], marker="^", ms=4, color="black", ls="--", label="P90/P10 ratio")
ax2.set_ylabel("P90/P10 ratio")
ax2.set_ylim(1, 3.5)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper right", fontsize=8)
add_rows("Figure5", "Fig5B_disparity_indices", "Gini", YEARS, t5["gini"].to_numpy())
add_rows("Figure5", "Fig5B_disparity_indices", "CV", YEARS, t5["cv"].to_numpy())
add_rows("Figure5", "Fig5B_disparity_indices", "P90/P10", YEARS, t5["p90_to_p10_ratio"].to_numpy())
panel_title(ax, "B. Inter-prefecture disparity in utilisation per 100,000, FY2014–2024")
fig.text(0.01, 0.995, "Fig. 5", fontsize=16, va="top")
fig.subplots_adjust(top=0.96, bottom=0.05)
save(fig, "Figure5")
save_fig_data("Figure5")

# ----------------------------------------------------------------------------
# Figure 6: 薬剤費
# ----------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(8.5, 10))
ax = axes[0]
pc = prod.pivot_table(index="year", columns="product_name", values="cost", aggfunc="sum").reindex(YEARS).fillna(0) / OKU
pc = pc[[p for p in PRODUCT_ORDER if p in pc.columns]]
bottom = np.zeros(len(YEARS))
for p in pc.columns:
    ax.bar(YEARS, pc[p], bottom=bottom, color=PRODUCT_COLOR[p], label=PRODUCT_EN[p], width=0.75, edgecolor="white", linewidth=0.4)
    add_rows("Figure6", "Fig6A_drug_cost_100M_jpy_by_product", PRODUCT_EN[p], YEARS, pc[p].to_numpy())
    bottom += pc[p].to_numpy()
ax.plot(YEARS, bottom, color="black", marker="o", ms=3, lw=1.2, label="Total")
add_rows("Figure6", "Fig6A_drug_cost_100M_jpy_by_product", "Total", YEARS, bottom)
ax.set_ylabel("Estimated drug cost (100 million JPY)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.yaxis.set_major_formatter(FuncFormatter(thousands))
ax.legend(ncol=2, frameon=False, fontsize=8, loc="upper left")
panel_title(ax, "A. Estimated anti-VEGF drug cost (NHI price × quantity) by product")

ax = axes[1]
cd = cost_dec.set_index("year")
yrs = list(cd.index)
w = 0.26
ax.bar([y - w for y in yrs], cd["volume_effect"] / OKU, width=w, color="#3182bd", label="Volume effect")
ax.bar(yrs, cd["mix_effect"] / OKU, width=w, color="#fd8d3c", label="Product-mix effect")
ax.bar([y + w for y in yrs], cd["price_effect"] / OKU, width=w, color="#756bb1", label="Price-revision effect")
ax.plot(yrs, cd["cost_change"] / OKU, color="black", marker="o", ms=4, lw=1.2, label="Net change in drug cost")
ax.axhline(0, color="black", lw=0.8)
ax.set_ylabel("Change from previous year (100 million JPY)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(yrs)
ax.legend(frameon=False, fontsize=8, loc="upper left", ncol=2)
add_rows("Figure6", "Fig6B_cost_decomposition_100M_jpy", "Volume effect", yrs, (cd["volume_effect"] / OKU).to_numpy())
add_rows("Figure6", "Fig6B_cost_decomposition_100M_jpy", "Product-mix effect", yrs, (cd["mix_effect"] / OKU).to_numpy())
add_rows("Figure6", "Fig6B_cost_decomposition_100M_jpy", "Price-revision effect", yrs, (cd["price_effect"] / OKU).to_numpy())
add_rows("Figure6", "Fig6B_cost_decomposition_100M_jpy", "Net change", yrs, (cd["cost_change"] / OKU).to_numpy())
panel_title(ax, "B. Decomposition of the year-on-year change in drug cost")
fig.text(0.01, 0.995, "Fig. 6", fontsize=16, va="top")
fig.tight_layout(rect=(0, 0, 1, 0.97))
save(fig, "Figure6")
save_fig_data("Figure6")

# ----------------------------------------------------------------------------
# Supplementary figures
# ----------------------------------------------------------------------------
# S1: choropleth maps (copied from 04_図表/plots)
for src_name, dst in [("prefecture_choropleth_latest.png", "SupplFigureS1A.png"),
                      ("prefecture_choropleth_65plus_latest.png", "SupplFigureS1B.png")]:
    p = PLOTS / src_name
    if p.exists():
        shutil.copy(p, OUT / dst)
        print("copied", dst)

# S2: G016 vs anti-VEGF
fig, ax = plt.subplots(figsize=(8.5, 5))
gv = g016_val.set_index("year")
yrs = list(gv.index)
ax.bar([y - 0.2 for y in yrs], gv["g016_procedures"] / 1000, width=0.4, color="#bdbdbd", label="G016 intravitreal injection claims")
ax.bar([y + 0.2 for y in yrs], gv["antivegf_vials"] / 1000, width=0.4, color="#3182bd", label="Anti-VEGF vials / PFS")
ax.set_ylabel("Thousands")
ax.set_xlabel("Fiscal year")
ax.set_xticks(yrs)
ax2 = ax.twinx()
ax2.spines["right"].set_visible(True)
ax2.plot(yrs, gv["antivegf_per_g016_pct"], color="black", marker="o", ms=4, label="Anti-VEGF / G016 (%)")
ax2.set_ylim(90, 101)
ax2.set_ylabel("Anti-VEGF vials per G016 claim (%)")
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper left", fontsize=8)
panel_title(ax, "Suppl Fig S2. Anti-VEGF quantity versus G016 claims (published national totals)")
fig.tight_layout()
save(fig, "SupplFigureS2")
gv_out = gv.reset_index()[["year", "g016_procedures", "antivegf_vials", "antivegf_per_g016_pct", "triamcinolone_vials"]]
gv_out.to_csv(OUT / "SupplFigureS2_data.csv", index=False, encoding="utf-8-sig")

# S3: joinpoint fitted vs observed for total
fig, ax = plt.subplots(figsize=(8.5, 5))
d = tot["count_per_100k"].reindex(YEARS)
ax.plot(YEARS, d, "o", color="black", label="Observed (per 100,000)")
jp = joinpoint[joinpoint["code"] == "ANTI_VEGF_TOTAL"]
for _, row in jp.iterrows():
    ys = list(range(int(row["segment_start"]), int(row["segment_end"]) + 1))
    seg = d.loc[ys]
    res = stats.linregress(ys, np.log(seg))
    ax.plot(ys, np.exp(res.intercept + res.slope * np.array(ys)), lw=2,
            label=f"Segment {int(row['segment_start'])}–{int(row['segment_end'])}: APC {row['apc']:+.1f}% ({row['apc_low']:.1f} to {row['apc_high']:.1f})")
ax.set_yscale("log")
ax.set_ylabel("Vials / PFS per 100,000 (log scale)")
ax.set_xlabel("Fiscal year")
ax.set_xticks(YEARS)
ax.legend(frameon=False, fontsize=8)
panel_title(ax, "Suppl Fig S3. Segmented log-linear trend of all anti-VEGF agents (joinpoint FY2017)")
fig.tight_layout()
save(fig, "SupplFigureS3")

# ----------------------------------------------------------------------------
# key numbers for the manuscript
# ----------------------------------------------------------------------------
print("\n=== key numbers ===")
print("2021->2024 originator decline %:", (1 - b.loc[2024, "originator_vials"] / b.loc[2021, "originator_vials"]) * 100)
print("2019->2024 originator decline %:", (1 - b.loc[2024, "originator_vials"] / b.loc[2019, "originator_vials"]) * 100)
print("inpatient share 2014/2024:", t1.loc[0, "inpatient_share_pct"], t1.loc[10, "inpatient_share_pct"])
print("cost 2014/2024:", t1.loc[0, "drug_cost_100M_jpy"], t1.loc[10, "drug_cost_100M_jpy"])
print("n pref capture<90% 2024:", (r["antivegf_per_g016_pct_2024"] < 90).sum(), r.loc[r["antivegf_per_g016_pct_2024"] < 90, "prefecture"].tolist())
print("done")
