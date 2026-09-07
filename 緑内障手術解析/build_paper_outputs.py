"""
Tanito 2023 (J Pers Med 13:1047) と同型の Table/Figure を FY2014-2024 に拡張して作成する。

  Table 1  Classification of procedures（コード・収載年）
  Table 2  Number of glaucoma surgeries by fiscal year（aggregation 1/2, 2014=100 変化率, per 100,000）
  Table 3  Spearman correlations between per-100k rates and prefectural parameters（各年度）
  Figure 1 Change in the number of surgeries by age group（2014=100, 複数年度）
  Figure 2 Geographical distribution（都道府県コロプレス, 2016 vs 2024）
  Table S1 Full dataset by age group / Table S2 by prefecture
  追加（拡張分）: Table 4 COVID O/E・ITS, Table 5 都道府県格差指標, Figure 3 術式構成, Figure 4 年齢標準化率

出力: 05_論文成果物/  (csv, xlsx, png)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
import json
from matplotlib.collections import PathCollection
from matplotlib.path import Path as MplPath
from scipy.stats import spearmanr

GEOJSON = Path(__file__).resolve().parents[1] / "allergy解析" / "data" / "japan_prefectures.geojson"

def load_geometry():
    gj = json.loads(GEOJSON.read_text(encoding="utf-8"))
    geoms = {}
    for feat in gj["features"]:
        name = feat["properties"]["nam_ja"]
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        paths = []
        for poly in polys:
            verts, codes = [], []
            for ring in poly:
                verts.extend(ring); codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 1))
            paths.append(MplPath(np.asarray(verts), codes))
        geoms[name] = paths
    return geoms
GEOMS = load_geometry()

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IN, MID, RES = HERE / "01_抽出データ", HERE / "02_中間データ", HERE / "03_解析結果"
OUT = HERE / "05_論文成果物"
OUT.mkdir(exist_ok=True)
YEARS = list(range(2014, 2025))

nat = pd.read_csv(IN / "glaucoma_surgery_national.csv")
pref = pd.read_csv(IN / "glaucoma_surgery_pref_long.csv")
ags = pd.read_csv(IN / "glaucoma_surgery_agesex_long.csv")
cov = pd.read_csv(ROOT / "data" / "covariates" / "prefecture_covariates.csv")
prates = pd.read_csv(MID / "prefecture_rates_per100k.csv")
agerates = pd.read_csv(MID / "age_sex_rates_per100k.csv")
asr = pd.read_csv(RES / "A4_age_standardized_rates.csv")

LASER_SUB = {"cyclophotocoag", "cyclophotocoag_endoscopic", "cyclophotocoag_other", "laser_iridotomy", "laser_trabeculoplasty"}
NONLASER_SUB = {"iridectomy", "outflow_all", "outflow_ab_externo", "outflow_ab_interno", "istent_phaco",
                "trabeculectomy", "implant_no_plate", "implant_with_plate", "cyclocryo"}
CAT_ORDER = ["iridectomy", "angle_surgery", "filtration", "tube_shunt", "ciliary_coag", "iris_laser", "gonio_laser"]
CAT_EN = {"iridectomy": "Iridectomy", "angle_surgery": "Angle surgery", "filtration": "Filtration surgery",
          "tube_shunt": "Tube shunt", "ciliary_coag": "Ciliary coagulation", "iris_laser": "Iris laser",
          "gonio_laser": "Gonio-laser"}
sheets = {}

# ---------------------------------------------------------------- Table 1
t1 = pd.DataFrame([
    ("K268-1", "150087510", "Iridectomy", "Iridectomy", "Non-laser", "2014-2024"),
    ("K268-2", "150088410", "Trabeculotomy ab externo, Trabectome, KDB, Tanito microhook, GATT, GSL", "Angle surgery", "Non-laser", "2014-2021"),
    ("K268-2 (ab interno)", "150435810", "Trabectome, KDB, Tanito microhook, GATT, GSL (ab interno)", "Angle surgery", "Non-laser", "2022-2024"),
    ("K268-2 (other)", "150427210", "Trabeculotomy ab externo, others", "Angle surgery", "Non-laser", "2022-2024"),
    ("K268-6", "150395150", "iStent / iStent inject W / Hydrus with phacoemulsification", "Angle surgery", "Non-laser", "2017-2024 (iStent approved 2016, first claims FY2017; Hydrus approved Jun 2024, reimbursed Sep 2024)"),
    ("K268-3", "150335910", "Trabeculectomy, NPT", "Filtration surgery", "Non-laser", "2014-2024"),
    ("K268-4", "150356010", "ExPRESS shunt; PRESERFLO MicroShunt (approved Feb 2022, available in Japan from 2023)", "Filtration surgery", "Non-laser", "2014-2024"),
    ("K268-5", "150373010", "Ahmed, Baerveldt", "Tube shunt", "Non-laser", "2014-2024"),
    ("K272", "150088910", "Cyclocryotherapy", "Ciliary coagulation", "Non-laser", "2014-2024"),
    ("K271", "150088810 / 150446710 / 150446810", "Cyclophotocoagulation, micropulse CPC (MP-CPC approved 2017); endoscopic CPC (2024)", "Ciliary coagulation", "Laser", "2014-2024"),
    ("K270", "150088710", "LI, LGP", "Iris laser", "Laser", "2014-2024"),
    ("K273", "150089010", "LTP, SLT", "Gonio-laser", "Laser", "2014-2024"),
    ("K268-7 (excluded)", "150427310", "Bleb needling revision", "-", "-", "2022-2024 (not counted in totals)"),
], columns=["Code", "Procedure code (NDB)", "Representative procedures", "Aggregation 1", "Aggregation 2", "Available fiscal years"])
sheets["Table1"] = t1

# ---------------------------------------------------------------- Table 2
cat = nat.pivot_table(index="category", columns="year", values="total", aggfunc="sum").reindex(CAT_ORDER)
nat["g2"] = np.where(nat.subcategory.isin(LASER_SUB), "Laser", np.where(nat.subcategory.isin(NONLASER_SUB), "Non-laser", "x"))
g2 = nat[nat.g2 != "x"].pivot_table(index="g2", columns="year", values="total", aggfunc="sum").reindex(["Non-laser", "Laser"])
g2.loc["Total"] = g2.sum()
jp_pop = cov.groupby("year").population_total.sum()
per100k = (g2 / jp_pop * 1e5).round(1)
per100k.index = [f"{i} per 100,000" for i in per100k.index]

def block(df, label):
    d = df.copy()
    d.insert(0, "Procedure", [CAT_EN.get(i, i) for i in d.index])
    d.insert(0, "Aggregation", label)
    return d.reset_index(drop=True)
t2 = pd.concat([block(cat, "Aggregation 1"), block(g2, "Aggregation 2"), block(per100k, "Per 100,000 capita")], ignore_index=True)
num_cols = YEARS
t2["Change 2020/2014 (%)"] = (t2[2020] / t2[2014] * 100).round(0)
t2["Change 2024/2014 (%)"] = (t2[2024] / t2[2014] * 100).round(0)
t2["Change 2024/2020 (%)"] = (t2[2024] / t2[2020] * 100).round(0)
t2.loc[t2.Aggregation != "Per 100,000 capita", num_cols] = t2.loc[t2.Aggregation != "Per 100,000 capita", num_cols].round(0)
sheets["Table2"] = t2

# Table 2b: 診療行為コード単位（拡張）
sub = nat.pivot_table(index=["category", "subcategory", "code", "name"], columns="year", values="total", aggfunc="sum").fillna(0).astype(int).reset_index()
sheets["Table2b_by_code"] = sub

# ---------------------------------------------------------------- Table 3 (Spearman by year)
rows = []
for meas in ["non_laser", "laser", "total"]:
    a = prates[prates.measure == meas].copy()
    a["pct65"] = a.population_65plus / a.population_total * 100
    a["oph_per100k"] = a.ophthalmologists / a.population_total * 1e5
    a["fac_per100k"] = a.facilities / a.population_total * 1e5
    for y, d in a.groupby("year"):
        r = {"Measure": meas, "Fiscal year": y}
        for v, lab in [("population_total", "Prefectural population"), ("pct65", "Rate of >=65-year-olds (%)"),
                       ("oph_per100k", "Ophthalmologists per 100,000"), ("fac_per100k", "Ophthalmic facilities per 100,000")]:
            rho, p = spearmanr(d.rate_low, d[v]); r[f"{lab} rho"] = round(rho, 2); r[f"{lab} p"] = round(p, 3)
        rows.append(r)
t3 = pd.DataFrame(rows); sheets["Table3"] = t3

# ---------------------------------------------------------------- Figure 1: change by age group (2014=100)
AGE_ORDER = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
             "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85-89", "90+"]
ag = agerates[agerates.measure.isin(["non_laser", "laser", "total"])]
agn = ag.groupby(["measure", "year", "age_group"]).cnt_low.sum().unstack("year").reindex(AGE_ORDER, level=1)
fig1 = {}
for m in ["non_laser", "laser", "total"]:
    d = agn.loc[m].reindex(AGE_ORDER)
    r = (d.div(d[2014], axis=0) * 100).round(0)
    r[d[2014] < 10] = np.nan          # 2014 年基準が 10 件未満の年齢層は比率を表示しない
    fig1[m] = r
f1 = pd.concat(fig1, names=["measure", "age_group"]).reset_index()
sheets["Fig1_data"] = f1
# 年齢群別 実数も
sheets["Fig1_counts"] = pd.concat({m: agn.loc[m].reindex(AGE_ORDER) for m in ["non_laser", "laser", "total"]}, names=["measure", "age_group"]).reset_index()

fig, axes = plt.subplots(1, 3, figsize=(14, 4.3), sharey=False)
show_years = [2016, 2018, 2020, 2022, 2024]
cols = plt.cm.viridis(np.linspace(0, 0.9, len(show_years)))
for ax, m, ttl in zip(axes, ["non_laser", "laser", "total"], ["Non-laser", "Laser", "Total"]):
    d = fig1[m]
    for y, c in zip(show_years, cols):
        ax.plot(range(len(AGE_ORDER)), d[y], marker="o", ms=3, color=c, label=f"FY{y}")
    ax.axhline(100, color="k", lw=0.8, ls="--")
    ax.set_xticks(range(len(AGE_ORDER))); ax.set_xticklabels(AGE_ORDER, rotation=70, fontsize=7)
    ax.set_title(f"{ttl} glaucoma surgery"); ax.set_ylabel("Change vs FY2014 (%)" if m == "non_laser" else "")
    ax.set_ylim(0, 600); ax.grid(alpha=0.3)
axes[0].legend(fontsize=8)
plt.tight_layout(); plt.savefig(OUT / "Figure1_change_by_age_group.png", dpi=250); plt.close()

# ---------------------------------------------------------------- Figure 2: choropleth
def draw_map(ax, series, title, cmap="Blues", fmt="{:.0f}", unit=""):
    vals = {str(k).strip(): float(v) for k, v in series.items()}
    missing = set(GEOMS) - set(vals)
    if missing:
        raise KeyError(f"都道府県名不一致: {sorted(missing)}")
    vmin, vmax = np.nanmin(list(vals.values())), np.nanmax(list(vals.values()))
    norm = Normalize(vmin, vmax); cm = plt.get_cmap(cmap)
    paths, colors = [], []
    for name, plist in GEOMS.items():
        for p in plist:
            paths.append(p); colors.append(cm(norm(vals[name])))
    ax.add_collection(PathCollection(paths, facecolors=colors, edgecolors="white", linewidths=0.25))
    ax.set_xlim(127.5, 146.5); ax.set_ylim(25.5, 46.0); ax.set_aspect(1.0 / np.cos(np.radians(37)))
    ax.axis("off"); ax.set_title(title, fontsize=9)
    cax = ax.inset_axes([0.80, 0.55, 0.035, 0.30])
    cb = plt.colorbar(ScalarMappable(norm=norm, cmap=cm), cax=cax)
    cb.outline.set_visible(False); cb.set_ticks([vmin, vmax])
    cb.ax.set_yticklabels([fmt.format(vmin), fmt.format(vmax)], fontsize=7); cb.ax.tick_params(length=0, pad=2)
    cb.ax.set_title(unit, fontsize=7, pad=4, loc="left")

pr = prates.copy()
pr["pct65"] = pr.population_65plus / pr.population_total * 100
pr["oph_per100k"] = pr.ophthalmologists / pr.population_total * 1e5
def ser(meas, y, col="rate_low"):
    d = pr[(pr.measure == meas) & (pr.year == y)].set_index("prefecture")
    return d[col]

fig, axes = plt.subplots(3, 3, figsize=(13, 13.5))
draw_map(axes[0, 0], ser("total", 2024, "population_total") / 1e4, "(a) Population (FY2024)", "Greys", unit="x10,000")
draw_map(axes[0, 1], ser("total", 2024, "pct65"), "(b) Rate of >=65-year-olds (FY2024)", "Greys", fmt="{:.1f}", unit="%")
draw_map(axes[0, 2], ser("total", 2024, "oph_per100k"), "(c) Ophthalmologists per 100,000 (FY2024)", "Greys", fmt="{:.1f}", unit="/100,000")
draw_map(axes[1, 0], ser("non_laser", 2016), "(d) Non-laser surgeries/100,000 (FY2016)", "Blues", unit="/100,000")
draw_map(axes[1, 1], ser("laser", 2016), "(e) Laser surgeries/100,000 (FY2016)", "Oranges", unit="/100,000")
draw_map(axes[1, 2], ser("total", 2016), "(f) Total surgeries/100,000 (FY2016)", "Purples", unit="/100,000")
draw_map(axes[2, 0], ser("non_laser", 2024), "(g) Non-laser surgeries/100,000 (FY2024)", "Blues", unit="/100,000")
draw_map(axes[2, 1], ser("laser", 2024), "(h) Laser surgeries/100,000 (FY2024)", "Oranges", unit="/100,000")
draw_map(axes[2, 2], ser("total", 2024), "(i) Total surgeries/100,000 (FY2024)", "Purples", unit="/100,000")
plt.tight_layout(); plt.savefig(OUT / "Figure2_prefecture_maps.png", dpi=200); plt.close()
f2 = pr[pr.measure.isin(["non_laser", "laser", "total"])].pivot_table(index=["prefecture", "year"], columns="measure", values="rate_low").reset_index()
f2 = f2.merge(pr[pr.measure == "non_laser"][["prefecture", "year", "population_total", "pct65", "oph_per100k"]], on=["prefecture", "year"])
sheets["Fig2_data"] = f2.round(2)

# ---------------------------------------------------------------- 拡張 Table 4 / 5, Figure 3 / 4
t4a = pd.read_csv(RES / "A2_covid_observed_expected.csv"); t4b = pd.read_csv(RES / "A2_its_loglinear.csv")
sheets["Table4_COVID_OE"] = t4a; sheets["Table4b_ITS"] = t4b
t5 = pd.read_csv(RES / "A3_disparity_indices_by_year.csv"); sheets["Table5_disparity"] = t5
sheets["Table5b_disparity_trend"] = pd.read_csv(RES / "A3_disparity_trend.csv")
QC = RES / "品質管理_感度分析"
sheets["TableS4_censoring_validation"] = pd.read_csv(QC / "naive_vs_missing_validation.csv")
sheets["TableS5_censoring_rows_pref"] = pd.read_csv(QC / "row_censoring_bounds_pref.csv")
sheets["TableS6_disparity_bounds"] = pd.read_csv(QC / "disparity_indices_bounds.csv")
sheets["Table6_panel_FE"] = pd.read_csv(RES / "A3_panel_FE_summary.csv")
sheets["Table7_age_standardized"] = asr
share = pd.read_csv(RES / "A1_incisional_share_pct.csv"); sheets["Fig3_incisional_share"] = share
import shutil
shutil.copy(HERE / "04_図表" / "Fig1_category_trends.png", OUT / "Figure3_category_trends_and_composition.png")
shutil.copy(HERE / "04_図表" / "Fig5_age_standardized_rates.png", OUT / "Figure4_age_standardized_rates.png")
shutil.copy(HERE / "04_図表" / "Fig3_prefecture_disparity.png", OUT / "Figure5_prefecture_disparity_trend.png")
shutil.copy(HERE / "04_図表" / "Fig2_covid_OE.png", OUT / "Figure6_covid_OE.png")

# ---------------------------------------------------------------- Supplementary S1/S2
s1 = ags.groupby(["year", "code", "name", "category", "subcategory", "sex", "age_group"], as_index=False).agg(count=("count", "sum"), censored=("censored", "sum"))
s1w = s1.pivot_table(index=["year", "code", "name", "category", "subcategory", "sex"], columns="age_group", values="count").reindex(columns=AGE_ORDER).reset_index()
sheets["TableS1_by_age"] = s1w
s2 = pref[pref.prefecture != "全国"].groupby(["year", "code", "name", "category", "subcategory", "prefecture"], as_index=False).agg(count=("count", "sum"), censored=("censored", "sum"))
s2w = s2.pivot_table(index=["year", "code", "name", "category", "subcategory"], columns="prefecture", values="count").reset_index()
sheets["TableS2_by_prefecture"] = s2w
sheets["TableS3_pref_rates"] = prates.round(2)

# ---------------------------------------------------------------- write
with pd.ExcelWriter(OUT / "glaucoma_surgery_2014_2024_tables.xlsx", engine="openpyxl") as xw:
    for name, df in sheets.items():
        df.to_excel(xw, sheet_name=name[:31], index=False)
for name, df in sheets.items():
    df.to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
print("done:", OUT)
print(t2.to_string())
