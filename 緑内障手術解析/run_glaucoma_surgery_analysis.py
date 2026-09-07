"""
緑内障手術 2014-2024 解析（Tanito 2023 JPM の 2 時点比較を 11 年時系列へ拡張）

切り口1: 術式別時系列・構成比・濾過手術の代替
切り口2: COVID-19 の影響と回復（2014-2019 トレンド外挿による O/E、ITS）
切り口3: 都道府県格差の時系列（人口10万対率、CV/Gini、固定効果パネル回帰）
切り口4: 年齢×術式（年齢階級別率、年齢標準化率、年齢分布の推移）

秘匿セル ('-') は主解析で 0（下限）、感度解析で 9（上限）として扱う。
"""
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IN = HERE / "01_抽出データ"
MID = HERE / "02_中間データ"
RES = HERE / "03_解析結果"
FIG = HERE / "04_図表"
for d in (MID, RES, FIG):
    d.mkdir(exist_ok=True)

YEARS = list(range(2014, 2025))
CAT_ORDER = ["iridectomy", "angle_surgery", "filtration", "tube_shunt", "ciliary_coag",
             "iris_laser", "gonio_laser"]          # Tanito aggregation 1（bleb_revision は除外）
CAT_LABEL = {"iridectomy": "Iridectomy", "angle_surgery": "Angle surgery (incl. MIGS)",
             "filtration": "Filtration surgery", "tube_shunt": "Tube shunt (plate)",
             "ciliary_coag": "Ciliary coagulation", "iris_laser": "Iris laser (LI)",
             "gonio_laser": "Gonio-laser (SLT/LTP)", "bleb_revision": "Bleb needling"}
NONLASER_SUB = {"iridectomy", "outflow_all", "outflow_ab_externo", "outflow_ab_interno",
                "istent_phaco", "trabeculectomy", "implant_no_plate", "implant_with_plate",
                "cyclocryo"}
LASER_SUB = {"cyclophotocoag", "cyclophotocoag_endoscopic", "cyclophotocoag_other",
             "laser_iridotomy", "laser_trabeculoplasty"}
DEVICE_EVENTS = {2016: "iStent approved", 2017: "MP-CPC approved; first K268-6 claims",
                 2020: "COVID-19", 2022: "PRESERFLO approved (Feb) / K268-2 split (ab interno)",
                 2023: "PRESERFLO available", 2024: "Hydrus (Sep)"}

nat = pd.read_csv(IN / "glaucoma_surgery_national.csv")
pref = pd.read_csv(IN / "glaucoma_surgery_pref_long.csv")
ags = pd.read_csv(IN / "glaucoma_surgery_agesex_long.csv")
cov = pd.read_csv(ROOT / "data" / "covariates" / "prefecture_covariates.csv")
pop_as = pd.read_csv(ROOT / "緑内障点眼" / "02_中間データ" / "population_age_sex.csv")

lines = []
def log(s=""):
    print(s); lines.append(str(s))


# =====================================================================
# 切り口1: 術式別時系列
# =====================================================================
log("=" * 70); log("切り口1: 術式別時系列（全国総計, 外来+入院）"); log("=" * 70)
sub_wide = nat.pivot_table(index=["category", "subcategory"], columns="year", values="total", aggfunc="sum")
sub_wide.to_csv(RES / "A1_subcategory_by_year.csv", encoding="utf-8-sig")
log("\n[術式（診療行為コード単位）別 年次件数]"); log(sub_wide.fillna(0).astype(int).to_string())

cat_wide = nat.pivot_table(index="category", columns="year", values="total", aggfunc="sum").reindex(CAT_ORDER + ["bleb_revision"])
cat_wide.to_csv(RES / "A1_category_by_year.csv", encoding="utf-8-sig")
log("\n[Tanito aggregation1 別 年次件数]"); log(cat_wide.fillna(0).astype(int).to_string())

# aggregation 2
nat["group2"] = np.where(nat.subcategory.isin(LASER_SUB), "laser",
                np.where(nat.subcategory.isin(NONLASER_SUB), "non_laser", "other"))
g2 = nat[nat.group2 != "other"].pivot_table(index="group2", columns="year", values="total", aggfunc="sum")
g2.loc["total"] = g2.sum()
g2.to_csv(RES / "A1_laser_nonlaser_by_year.csv", encoding="utf-8-sig")
log("\n[Laser / Non-laser / Total（needling 除外, Tanito 互換）]"); log(g2.astype(int).to_string())

idx = (cat_wide.loc[CAT_ORDER].div(cat_wide.loc[CAT_ORDER, 2014], axis=0) * 100).round(0)
idx.loc["non_laser"] = (g2.loc["non_laser"] / g2.loc["non_laser", 2014] * 100).round(0)
idx.loc["laser"] = (g2.loc["laser"] / g2.loc["laser", 2014] * 100).round(0)
idx.loc["total"] = (g2.loc["total"] / g2.loc["total", 2014] * 100).round(0)
idx.to_csv(RES / "A1_index_2014eq100.csv", encoding="utf-8-sig")
log("\n[2014=100 の指数]"); log(idx.astype(int).to_string())
log(f"\nTanito 2023 との照合: 2020/2014 non-laser {idx.loc['non_laser',2020]:.0f}% (論文180%), "
    f"laser {idx.loc['laser',2020]:.0f}% (論文111%), total {idx.loc['total',2020]:.0f}% (論文137%)")

# 観血手術（incisional = non-laser − cyclocryo）内の構成比: 濾過手術が置き換わったか
inc = nat[nat.subcategory.isin(NONLASER_SUB - {"cyclocryo"})].copy()
inc["grp"] = inc.subcategory.map({
    "iridectomy": "iridectomy", "outflow_all": "outflow (trabeculotomy etc.)",
    "outflow_ab_externo": "outflow ab externo", "outflow_ab_interno": "outflow ab interno",
    "istent_phaco": "iStent/Hydrus + phaco", "trabeculectomy": "trabeculectomy",
    "implant_no_plate": "plate-less implant (ExPRESS/PRESERFLO)", "implant_with_plate": "plate tube shunt"})
inc_w = inc.pivot_table(index="grp", columns="year", values="total", aggfunc="sum")
share = (inc_w / inc_w.sum() * 100).round(1)
share.to_csv(RES / "A1_incisional_share_pct.csv", encoding="utf-8-sig")
log("\n[観血的緑内障手術に占める構成比 %]"); log(share.fillna(0).to_string())

filt_share = (cat_wide.loc["filtration"] / g2.loc["non_laser"] * 100).round(1)
trab_share = (sub_wide.loc[("filtration", "trabeculectomy")] / g2.loc["non_laser"] * 100).round(1)
migs = sub_wide.loc[[("angle_surgery", s) for s in ["outflow_all", "outflow_ab_externo", "outflow_ab_interno", "istent_phaco"]]].sum()
migs_share = (migs / g2.loc["non_laser"] * 100).round(1)
ss = pd.DataFrame({"filtration_share_%": filt_share, "trabeculectomy_share_%": trab_share,
                   "angle_surgery_share_%": migs_share,
                   "trabeculectomy_n": sub_wide.loc[("filtration", "trabeculectomy")],
                   "plateless_implant_n": sub_wide.loc[("filtration", "implant_no_plate")]}).T
ss.to_csv(RES / "A1_filtration_vs_angle_share.csv", encoding="utf-8-sig")
log("\n[非レーザー手術に占める濾過/線維柱帯切除/隅角手術のシェア]"); log(ss.to_string())
log("\n解釈メモ: 線維柱帯切除術(K268-3)は 2022 年 17,997 → 2024 年 15,170 件（-15.7%）。"
    "同期間にプレートなしインプラント(K268-4: ExPRESS+PRESERFLO)が 3,291 → 15,688 件と 4.8 倍。"
    "ExPRESS 単独は 2019-2022 に 3.0-3.8 千件で安定していたため増分はほぼ PRESERFLO と考えられる。")

# ---- Figure 1: category trends ----
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
ax = axes[0]
for c in CAT_ORDER:
    ax.plot(YEARS, cat_wide.loc[c, YEARS], marker="o", ms=3, label=CAT_LABEL[c])
ax.set_yscale("log"); ax.set_ylabel("Annual procedures (log scale)"); ax.set_xlabel("Fiscal year")
ax.set_title("A. Glaucoma procedures by category, Japan FY2014-2024")
ax.axvspan(2019.5, 2020.5, color="grey", alpha=0.15)
ax.legend(fontsize=7, loc="lower right"); ax.grid(alpha=0.3)
ax = axes[1]
ax.stackplot(YEARS, [inc_w.loc[g, YEARS].fillna(0) for g in inc_w.index], labels=inc_w.index, alpha=0.85)
ax.set_ylabel("Incisional glaucoma surgeries"); ax.set_xlabel("Fiscal year")
ax.set_title("B. Composition of incisional surgery")
ax.legend(fontsize=6.5, loc="upper left"); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(FIG / "Fig1_category_trends.png", dpi=200); plt.close()

# =====================================================================
# 切り口2: COVID-19 影響（2014-2019 log-linear 外挿 → O/E, ITS）
# =====================================================================
log("\n" + "=" * 70); log("切り口2: COVID-19 の影響と回復"); log("=" * 70)
series = {c: cat_wide.loc[c] for c in CAT_ORDER}
series.update({"non_laser": g2.loc["non_laser"], "laser": g2.loc["laser"], "total": g2.loc["total"]})
oe_rows, its_rows = [], []
for name, s in series.items():
    s = s.astype(float)
    pre = s.loc[2014:2019]
    X = sm.add_constant(np.arange(len(pre)))
    m = sm.OLS(np.log(pre.values), X).fit()
    for y in range(2020, 2025):
        xn = np.array([[1, y - 2014]])
        pr = m.get_prediction(xn).summary_frame(alpha=0.05)
        exp_ = np.exp(pr["mean"].iloc[0]); lo = np.exp(pr["obs_ci_lower"].iloc[0]); hi = np.exp(pr["obs_ci_upper"].iloc[0])
        oe_rows.append(dict(series=name, year=y, observed=s[y], expected=round(exp_), pi_low=round(lo), pi_high=round(hi),
                            OE_ratio=round(s[y] / exp_, 3), pct_change_vs_2019=round((s[y] / s[2019] - 1) * 100, 1)))
    # ITS: log(y) = b0 + b1*t + b2*post2020 + b3*(t-2020)*post
    d = pd.DataFrame({"y": np.log(s.values), "t": np.arange(len(s)), "post": (s.index >= 2020).astype(int)})
    d["tpost"] = (d.t - 6).clip(lower=0) * d.post
    r = smf.ols("y ~ t + post + tpost", d).fit(cov_type="HC1")
    its_rows.append(dict(series=name, pre_slope_pct=round((np.exp(r.params["t"]) - 1) * 100, 2),
                         level_change_2020_pct=round((np.exp(r.params["post"]) - 1) * 100, 1),
                         level_p=round(r.pvalues["post"], 3),
                         slope_change_pct=round((np.exp(r.params["tpost"]) - 1) * 100, 2),
                         slope_change_p=round(r.pvalues["tpost"], 3),
                         post_slope_pct=round((np.exp(r.params["t"] + r.params["tpost"]) - 1) * 100, 2)))
oe = pd.DataFrame(oe_rows); oe.to_csv(RES / "A2_covid_observed_expected.csv", index=False, encoding="utf-8-sig")
its = pd.DataFrame(its_rows); its.to_csv(RES / "A2_its_loglinear.csv", index=False, encoding="utf-8-sig")
log("\n[2014-2019 の対数線形トレンドから外挿した期待値に対する観測比 O/E]")
log(oe.pivot(index="series", columns="year", values="OE_ratio").loc[list(series)].to_string())
log("\n[2019 年比 変化率 %]")
log(oe.pivot(index="series", columns="year", values="pct_change_vs_2019").loc[list(series)].to_string())
log("\n[ITS（対数線形, 2020 で水準変化・傾き変化）]"); log(its.to_string(index=False))

fig, ax = plt.subplots(figsize=(7, 4.5))
for name in ["non_laser", "laser", "total"]:
    d = oe[oe.series == name]
    ax.plot(d.year, d.OE_ratio, marker="o", label=name)
ax.axhline(1, color="k", lw=0.8); ax.set_ylabel("Observed / expected (2014-19 trend)"); ax.set_xlabel("Fiscal year")
ax.set_title("COVID-19 period: observed vs pre-pandemic trend"); ax.legend(); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(FIG / "Fig2_covid_OE.png", dpi=200); plt.close()

# =====================================================================
# 切り口3: 都道府県格差
# =====================================================================
log("\n" + "=" * 70); log("切り口3: 都道府県格差の時系列"); log("=" * 70)
p = pref[pref.prefecture != "全国"].copy()
p["grp"] = np.where(p.subcategory.isin(LASER_SUB), "laser",
           np.where(p.subcategory.isin(NONLASER_SUB), "non_laser", "other"))
p["cnt_low"] = p["count"].fillna(0)
# 上限は行 (year, code, sheet) ごとに missing = 公表総計 − Σ開示セル を復元し、
# 各秘匿セルを min(9, missing) で抑える。セル一律 9 は補完的秘匿のため上限として
# 機能しない（build_censoring_bounds_surgery.py が毎回検証）。
_nat_row = pref[pref.prefecture == "全国"].set_index(["year", "code", "sheet"])["count"]
_row = p.groupby(["year", "code", "sheet"]).agg(disclosed=("count", "sum"))
_row["total"] = _nat_row
_row["missing"] = (_row.total - _row.disclosed).clip(lower=0)
_row["cell_upper"] = np.minimum(9, _row.missing)
p = p.merge(_row[["cell_upper"]].reset_index(), on=["year", "code", "sheet"], how="left")
p["cnt_high"] = np.where(p.censored == 1, p.cell_upper, p["count"].fillna(0))
# 2014-2015 の K273 都道府県別は全行秘匿 → laser/total はこの2年を除外
K273_MISSING_YEARS = [2014, 2015]

def pref_rates(keys, label):
    d = p[keys(p)]
    a = d.groupby(["year", "prefecture"], as_index=False)[["cnt_low", "cnt_high", "censored"]].sum()
    a = a.merge(cov[["year", "prefecture", "population_total", "population_65plus", "ophthalmologists", "facilities"]],
                on=["year", "prefecture"], how="left")
    a["rate_low"] = a.cnt_low / a.population_total * 1e5
    a["rate_high"] = a.cnt_high / a.population_total * 1e5
    a["measure"] = label
    return a

rate_sets = {
    "non_laser": pref_rates(lambda d: d.grp == "non_laser", "non_laser"),
    "laser": pref_rates(lambda d: (d.grp == "laser") & ~d.year.isin(K273_MISSING_YEARS), "laser"),
    "total": pref_rates(lambda d: (d.grp != "other") & ~d.year.isin(K273_MISSING_YEARS), "total"),
    "angle_surgery": pref_rates(lambda d: d.category == "angle_surgery", "angle_surgery"),
    "filtration": pref_rates(lambda d: d.category == "filtration", "filtration"),
    "trabeculectomy": pref_rates(lambda d: d.subcategory == "trabeculectomy", "trabeculectomy"),
    "tube_shunt": pref_rates(lambda d: d.category == "tube_shunt", "tube_shunt"),
    "iris_laser": pref_rates(lambda d: d.category == "iris_laser", "iris_laser"),
    "gonio_laser": pref_rates(lambda d: (d.category == "gonio_laser") & ~d.year.isin(K273_MISSING_YEARS), "gonio_laser"),
    "ciliary_coag": pref_rates(lambda d: d.category == "ciliary_coag", "ciliary_coag"),
}
allr = pd.concat(rate_sets.values(), ignore_index=True)
allr.to_csv(MID / "prefecture_rates_per100k.csv", index=False, encoding="utf-8-sig")

def gini(x):
    x = np.sort(np.asarray(x, float)); n = len(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) / (n * x.sum())) - (n + 1) / n

disp = []
for meas, a in rate_sets.items():
    for y, d in a.groupby("year"):
        r = d.rate_low
        disp.append(dict(measure=meas, year=y, national_rate=d.cnt_low.sum() / d.population_total.sum() * 1e5,
                         mean=r.mean(), sd=r.std(), cv=r.std() / r.mean(), gini=gini(r),
                         min=r.min(), max=r.max(), max_min_ratio=r.max() / r.min() if r.min() > 0 else np.nan,
                         p90_p10=r.quantile(.9) / r.quantile(.1), iqr_ratio=r.quantile(.75) / r.quantile(.25),
                         censored_cells=int(d.censored.sum()),
                         uncertainty_pct=(d.cnt_high.sum() - d.cnt_low.sum()) / max(d.cnt_low.sum(), 1) * 100,
                         cv_upper=d.rate_high.std() / d.rate_high.mean(),
                         gini_upper=gini(d.rate_high)))
disp = pd.DataFrame(disp).round(3)
disp.to_csv(RES / "A3_disparity_indices_by_year.csv", index=False, encoding="utf-8-sig")
for m in ["non_laser", "laser", "total", "angle_surgery", "trabeculectomy", "gonio_laser"]:
    log(f"\n[{m}: 人口10万対率の都道府県格差指標]")
    log(disp[disp.measure == m][["year", "national_rate", "cv", "gini", "max_min_ratio", "p90_p10",
                                 "censored_cells", "uncertainty_pct", "cv_upper", "gini_upper"]].to_string(index=False))

# 格差の時間トレンド（CV に対する year の回帰）
tr = []
for m, d in disp.groupby("measure"):
    r = sm.OLS(d.cv.values, sm.add_constant(d.year.values - 2014)).fit()
    rg = sm.OLS(d.gini.values, sm.add_constant(d.year.values - 2014)).fit()
    ru = sm.OLS(d.cv_upper.values, sm.add_constant(d.year.values - 2014)).fit()
    tr.append(dict(measure=m, n_years=len(d), cv_first=d.cv.iloc[0], cv_last=d.cv.iloc[-1],
                   cv_slope_per_year=r.params[1], cv_slope_p=r.pvalues[1],
                   gini_first=d.gini.iloc[0], gini_last=d.gini.iloc[-1],
                   gini_slope_per_year=rg.params[1], gini_slope_p=rg.pvalues[1],
                   # 秘匿の扱い（下限＝0／上限＝missingベース）に対する頑健性
                   cv_upper_slope=ru.params[1], cv_upper_slope_p=ru.pvalues[1],
                   robust_to_censoring=bool((r.params[1] * ru.params[1] > 0)
                                            and (r.pvalues[1] < .05) and (ru.pvalues[1] < .05))))
tr = pd.DataFrame(tr).round(4); tr.to_csv(RES / "A3_disparity_trend.csv", index=False, encoding="utf-8-sig")
log("\n[格差指標の年次トレンド（線形回帰）と秘匿の扱いに対する頑健性]"); log(tr.to_string(index=False))
log("\n注: robust_to_censoring=False の術式は、格差縮小が秘匿セルの扱いに依存するため断定できない。")

# 2020 年 Spearman（Tanito Table3 再現）と全年
from scipy.stats import spearmanr
sp = []
for m in ["non_laser", "laser", "total"]:
    a = rate_sets[m]
    for y, d in a.groupby("year"):
        d = d.assign(oph_per100k=d.ophthalmologists / d.population_total * 1e5,
                     fac_per100k=d.facilities / d.population_total * 1e5,
                     pct65=d.population_65plus / d.population_total * 100)
        row = dict(measure=m, year=y)
        for v in ["population_total", "pct65", "oph_per100k", "fac_per100k"]:
            rho, pv = spearmanr(d.rate_low, d[v]); row[f"rho_{v}"] = round(rho, 3); row[f"p_{v}"] = round(pv, 3)
        sp.append(row)
sp = pd.DataFrame(sp); sp.to_csv(RES / "A3_spearman_by_year.csv", index=False, encoding="utf-8-sig")
log("\n[Spearman: 率 vs 人口・高齢化率・眼科医密度・施設密度（Tanito Table3 の全年版）]")
log(sp[sp.year.isin([2014, 2016, 2020, 2024])].to_string(index=False))

# 固定効果パネル回帰
panel_rows = []
for m in ["non_laser", "laser", "total", "angle_surgery", "trabeculectomy", "filtration", "gonio_laser", "iris_laser"]:
    a = rate_sets[m].copy()
    a["oph_per100k"] = a.ophthalmologists / a.population_total * 1e5
    a["fac_per100k"] = a.facilities / a.population_total * 1e5
    a["pct65"] = a.population_65plus / a.population_total * 100
    a["log_rate"] = np.log(a.rate_low.clip(lower=0.1))
    a = a.dropna(subset=["oph_per100k", "fac_per100k", "pct65"])
    r = smf.ols("log_rate ~ oph_per100k + fac_per100k + pct65 + C(year) + C(prefecture)", a).fit(
        cov_type="cluster", cov_kwds={"groups": a.prefecture})
    panel_rows.append(dict(measure=m, n=int(r.nobs),
                           b_oph=r.params["oph_per100k"], p_oph=r.pvalues["oph_per100k"],
                           b_fac=r.params["fac_per100k"], p_fac=r.pvalues["fac_per100k"],
                           b_pct65=r.params["pct65"], p_pct65=r.pvalues["pct65"],
                           within_r2=r.rsquared))
    with open(RES / f"A3_panel_FE_{m}.txt", "w", encoding="utf-8") as f:
        f.write(r.summary().as_text())
panel = pd.DataFrame(panel_rows).round(4); panel.to_csv(RES / "A3_panel_FE_summary.csv", index=False, encoding="utf-8-sig")
log("\n[二方向固定効果パネル回帰 log(rate) ~ 眼科医密度 + 施設密度 + 高齢化率 + 年FE + 県FE, クラスタSE]")
log(panel.to_string(index=False))

# 県別 2016→2024 の変化（順位の安定性）
for m in ["non_laser", "total"]:
    a = rate_sets[m]
    w = a.pivot(index="prefecture", columns="year", values="rate_low")
    y0 = 2016 if m == "total" else 2014
    w["change_ratio"] = w[2024] / w[y0]
    w = w.round(1).sort_values(2024, ascending=False)
    w.to_csv(RES / f"A3_pref_rate_table_{m}.csv", encoding="utf-8-sig")
    rho, pv = spearmanr(w[y0], w[2024])
    log(f"\n[{m}] 県別率の順位相関 {y0} vs 2024: rho={rho:.3f} p={pv:.3g}; 上位5県(2024): "
        + ", ".join(f"{i}({v:.0f})" for i, v in w[2024].head(5).items())
        + "; 下位5県: " + ", ".join(f"{i}({v:.0f})" for i, v in w[2024].tail(5).items()))

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
for m in ["non_laser", "laser", "total", "angle_surgery", "trabeculectomy", "gonio_laser"]:
    d = disp[disp.measure == m]
    axes[0].plot(d.year, d.cv, marker="o", ms=3, label=m)
    axes[1].plot(d.year, d.gini, marker="o", ms=3, label=m)
axes[0].set_title("Coefficient of variation across 47 prefectures"); axes[1].set_title("Gini index across prefectures")
for ax in axes: ax.set_xlabel("Fiscal year"); ax.grid(alpha=0.3)
axes[0].legend(fontsize=7)
plt.tight_layout(); plt.savefig(FIG / "Fig3_prefecture_disparity.png", dpi=200); plt.close()

# =====================================================================
# 切り口4: 年齢×術式
# =====================================================================
log("\n" + "=" * 70); log("切り口4: 年齢階級別率と年齢標準化率"); log("=" * 70)
a = ags.copy()
a["grp"] = np.where(a.subcategory.isin(LASER_SUB), "laser",
           np.where(a.subcategory.isin(NONLASER_SUB), "non_laser", "other"))
a["cnt_low"] = a["count"].fillna(0)
# --- 2016 年 K268-2 (150088410) 入院の性年齢別が全セル秘匿（総計 9,910 件のみ判明）
#     → 2015・2017 年入院の性年齢分布の平均で按分補完（imputed=1）
a["imputed"] = 0
m16 = (a.year == 2016) & (a.code == 150088410) & (a.sheet == "入院")
tot16 = nat[(nat.year == 2016) & (nat.code == 150088410)].total.sum() \
        - a[(a.year == 2016) & (a.code == 150088410) & (a.sheet == "外来")].cnt_low.sum()
nb = a[(a.year.isin([2015, 2017])) & (a.code == 150088410) & (a.sheet == "入院")]
dist = nb.groupby(["sex", "age_group"]).cnt_low.sum()
dist = dist / dist.sum()
if m16.sum() and a.loc[m16, "cnt_low"].sum() == 0:
    a.loc[m16, "cnt_low"] = a.loc[m16].apply(lambda r: dist.get((r.sex, r.age_group), 0) * tot16, axis=1)
    a.loc[m16, "imputed"] = 1
    log(f"2016 年 K268-2 入院 {tot16:.0f} 件を 2015/2017 分布で按分補完")
pop = pop_as.copy()
pop["age_group"] = pop.age_group.replace({"90-94": "90+", "95-99": "90+", "100+": "90+"})
pop = pop.groupby(["year", "sex", "age_group"], as_index=False).population.sum()
std = pop[pop.year == 2015].groupby("age_group").population.sum()   # 2015 標準人口（男女計）
AGE_ORDER = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
             "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85-89", "90+"]

def age_rates(mask, label):
    d = a[mask].groupby(["year", "sex", "age_group"], as_index=False).cnt_low.sum()
    d = d.merge(pop, on=["year", "sex", "age_group"], how="left")
    d["rate"] = d.cnt_low / d.population * 1e5
    d["measure"] = label
    return d

meas = {
    "non_laser": a.grp == "non_laser", "laser": a.grp == "laser", "total": a.grp != "other",
    "angle_surgery": a.category == "angle_surgery", "istent_phaco": a.subcategory == "istent_phaco",
    "trabeculectomy": a.subcategory == "trabeculectomy", "filtration": a.category == "filtration",
    "tube_shunt": a.category == "tube_shunt", "iris_laser": a.category == "iris_laser",
    "gonio_laser": a.category == "gonio_laser", "ciliary_coag": a.category == "ciliary_coag",
}
age_all = pd.concat([age_rates(mk, k) for k, mk in meas.items()], ignore_index=True)
age_all.to_csv(MID / "age_sex_rates_per100k.csv", index=False, encoding="utf-8-sig")

# 年齢標準化率（男女計、2015 年人口基準） & 粗率
asr_rows = []
for (m, y), d in age_all.groupby(["measure", "year"]):
    both = d.groupby("age_group")[["cnt_low", "population"]].sum()
    both["rate"] = both.cnt_low / both.population
    both = both.reindex(AGE_ORDER)
    asr = (both.rate * std.reindex(AGE_ORDER)).sum() / std.sum() * 1e5
    crude = both.cnt_low.sum() / both.population.sum() * 1e5
    # 年齢分布
    w = both.cnt_low / both.cnt_low.sum()
    mid = np.array([2, 7, 12, 17, 22, 27, 32, 37, 42, 47, 52, 57, 62, 67, 72, 77, 82, 87, 92])
    mean_age = (w.values * mid).sum()
    share65 = both.loc[["65-69", "70-74", "75-79", "80-84", "85-89", "90+"], "cnt_low"].sum() / both.cnt_low.sum() * 100
    share_lt50 = both.loc[AGE_ORDER[:10], "cnt_low"].sum() / both.cnt_low.sum() * 100
    m_ = d[d.sex == "male"].cnt_low.sum(); f_ = d[d.sex == "female"].cnt_low.sum()
    asr_rows.append(dict(measure=m, year=y, n=int(both.cnt_low.sum()), crude_rate=crude, age_std_rate=asr,
                         mean_age=mean_age, pct_65plus=share65, pct_under50=share_lt50, male_female_ratio=m_ / f_ if f_ else np.nan))
asr = pd.DataFrame(asr_rows).round(2)
asr.to_csv(RES / "A4_age_standardized_rates.csv", index=False, encoding="utf-8-sig")
for m in ["non_laser", "laser", "angle_surgery", "istent_phaco", "trabeculectomy", "gonio_laser", "iris_laser", "ciliary_coag"]:
    log(f"\n[{m}]"); log(asr[asr.measure == m].drop(columns="measure").to_string(index=False))
log("\n注: 2016 年 K268-2（流出路再建術）入院分の性年齢別は原データで全セル秘匿のため、2015/2017 年の分布で按分補完済み。")

# 年齢階級別率 2014 vs 2019 vs 2024
ag_w = (age_all.groupby(["measure", "year", "age_group"])[["cnt_low", "population"]].sum().reset_index())
ag_w["rate"] = ag_w.cnt_low / ag_w.population * 1e5
for m in ["non_laser", "laser"]:
    t = ag_w[(ag_w.measure == m) & ag_w.year.isin([2014, 2019, 2024])].pivot(index="age_group", columns="year", values="rate").reindex(AGE_ORDER).round(1)
    t["ratio_2024_2014"] = (t[2024] / t[2014]).round(2)
    t["ratio_2024_2019"] = (t[2024] / t[2019]).round(2)
    t.to_csv(RES / f"A4_age_group_rates_{m}.csv", encoding="utf-8-sig")
    log(f"\n[{m}: 年齢階級別 人口10万対率]"); log(t.to_string())

fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
for ax, m in zip(axes.flat, ["angle_surgery", "trabeculectomy", "tube_shunt", "gonio_laser", "iris_laser", "ciliary_coag"]):
    for y, c in zip([2014, 2017, 2020, 2022, 2024], plt.cm.viridis(np.linspace(0, .9, 5))):
        t = ag_w[(ag_w.measure == m) & (ag_w.year == y)].set_index("age_group").reindex(AGE_ORDER)
        ax.plot(range(len(AGE_ORDER)), t.rate, marker="o", ms=2.5, color=c, label=str(y))
    ax.set_title(CAT_LABEL.get(m, m), fontsize=10); ax.set_xticks(range(0, len(AGE_ORDER), 2)); ax.set_xticklabels(AGE_ORDER[::2], rotation=60, fontsize=7)
    ax.grid(alpha=0.3); ax.set_ylabel("per 100,000")
axes[0, 0].legend(fontsize=7)
plt.tight_layout(); plt.savefig(FIG / "Fig4_age_specific_rates.png", dpi=200); plt.close()

fig, ax = plt.subplots(figsize=(7, 4.5))
for m in ["non_laser", "laser", "angle_surgery", "trabeculectomy", "gonio_laser", "iris_laser"]:
    d = asr[asr.measure == m]
    ax.plot(d.year, d.age_std_rate, marker="o", ms=3, label=m)
ax.set_yscale("log"); ax.set_ylabel("Age-standardized rate per 100,000 (2015 std pop)"); ax.set_xlabel("Fiscal year")
ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.set_title("Age-standardized glaucoma procedure rates")
plt.tight_layout(); plt.savefig(FIG / "Fig5_age_standardized_rates.png", dpi=200); plt.close()

with open(RES / "summary_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("\n-> 出力:", RES, FIG)
