# -*- coding: utf-8 -*-
"""追加図表（査読対応・検討用）を 06_論文投稿/追加図表/ に生成する。

FigureA1: Figure 5A の 65 歳以上人口分母版（2024 年度、都道府県別 65 歳以上10万対）
FigureA2: 二元固定効果パネル回帰（抗VEGF合計）の係数プロット（95%CI）と
          回帰補正後（固定効果＋共変量除去後）の 2024 年度県別残差プロット

入力は 公費含まない/03_解析結果/ と リポジトリ直下の prefecture_covariates.csv。
実行: .venv\\Scripts\\python.exe 抗VEGF薬解析/06_論文投稿/build_additional_figures_antivegf.py
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
from linearmodels.panel import PanelOLS

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "公費含まない", "03_解析結果")
OUT = os.path.join(HERE, "追加図表")
os.makedirs(OUT, exist_ok=True)

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
thousands = lambda x, _: f"{x:,.0f}"


def save(fig, name):
    for ext in ("png",):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {name}")


# ----------------------------------------------------------------------------
# FigureA1: 65歳以上人口分母の県別ランキング（2024年度）
# ----------------------------------------------------------------------------
rank65 = pd.read_csv(os.path.join(RES, "都道府県_地域格差",
                                  "prefecture_per_65plus_ranking_antivegf.csv"))
g016 = pd.read_csv(os.path.join(RES, "G016硝子体内注射", "g016_vs_drug_by_prefecture.csv"))
g24 = g016[g016["year"] == 2024][["prefecture", "ratio_pct"]]

r = rank65[["prefecture", "2024年度_65歳以上10万対"]].rename(
    columns={"2024年度_65歳以上10万対": "rate"})
r = r.merge(g24, on="prefecture", how="left").sort_values("rate", ascending=True)

# 全国値（Table 1 と同じ公表総計ベース: 2024年度 65歳以上10万対）
tab1 = pd.read_csv(os.path.join(HERE, "投稿用", "Table1.csv"))
nat_rate = float(tab1.loc[tab1["fiscal_year"] == 2024, "per_100k_population_65plus"].iloc[0])

fig, ax = plt.subplots(figsize=(8.5, 9))
cols = ["#9e9e9e" if v < 90 else "#3182bd" for v in r["ratio_pct"]]
bars = ax.barh(range(len(r)), r["rate"], color=cols, height=0.75)
for i, cap in enumerate(r["ratio_pct"]):
    if cap < 90:
        bars[i].set_hatch("///")
        bars[i].set_edgecolor("white")
ax.axvline(nat_rate, color="black", ls="--", lw=1)
ax.text(nat_rate, len(r) - 0.5, f" National {nat_rate:,.0f}", va="top", fontsize=8)
ax.set_yticks(range(len(r)))
ax.set_yticklabels([PREF_EN[p] for p in r["prefecture"]], fontsize=7.5)
ax.set_xlabel("Vials / PFS per 100,000 population aged 65+, FY2024")
ax.xaxis.set_major_formatter(FuncFormatter(thousands))
ax.set_ylim(-0.6, len(r) - 0.4)
ax.legend(handles=[Patch(color="#3182bd", label="Zero-imputed prefecture breakdown"),
                   Patch(facecolor="#9e9e9e", hatch="///", edgecolor="white",
                         label="Breakdown captures <90% of G016 claims (under-estimated)")],
          frameon=True, edgecolor="none", facecolor="white", framealpha=0.9,
          loc="lower right", fontsize=8)
ax.set_title("Prefecture-level utilisation per 100,000 population aged 65+, FY2024",
             fontsize=11, loc="left")
save(fig, "FigureA1_prefecture_per_65plus_2024")

csv_a1 = r.rename(columns={"rate": "per_100k_65plus_2024",
                           "ratio_pct": "antivegf_per_g016_pct_2024"})
csv_a1["prefecture_en"] = csv_a1["prefecture"].map(PREF_EN)
csv_a1.sort_values("per_100k_65plus_2024", ascending=False).to_csv(
    os.path.join(OUT, "FigureA1_data.csv"), index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------
# FigureA2: パネル回帰の係数プロット＋回帰補正後残差（抗VEGF合計）
# ----------------------------------------------------------------------------
# パネルの再構築（run_panel_regression と同じ定義: preprocess_antivegf.py 参照）
per_cap = pd.read_csv(os.path.join(RES, "都道府県_地域格差",
                                   "prefecture_per_capita_ranking_antivegf.csv"))
per_cap = per_cap[[c for c in per_cap.columns if c == "prefecture" or "人口10万対" in c]]
long = per_cap.melt(id_vars="prefecture", var_name="year", value_name="count_per_100k")
long["year"] = long["year"].str.extract(r"(\d{4})").astype(int)

cov = pd.read_csv(os.path.join(HERE, "..", "..", "data", "covariates", "prefecture_covariates.csv"))
cov["aging_rate"] = cov["population_65plus"] / cov["population_total"] * 100
cov["docs_per_100k"] = cov["ophthalmologists"] / cov["population_total"] * 100000
cov["facilities_per_100k"] = cov["facilities"] / cov["population_total"] * 100000

panel = long.merge(cov[["year", "prefecture", "aging_rate", "docs_per_100k",
                        "facilities_per_100k"]], on=["year", "prefecture"], how="inner")
xvars = ["aging_rate", "docs_per_100k", "facilities_per_100k"]
d = panel.set_index(["prefecture", "year"])[["count_per_100k"] + xvars].dropna()
res = PanelOLS(d["count_per_100k"], d[xvars], entity_effects=True,
               time_effects=True).fit(cov_type="clustered", cluster_entity=True)
print(res.params.round(3).to_dict())

# 既存出力との整合チェック（panel_regression_summary_antivegf.csv と一致するはず）
summ = pd.read_csv(os.path.join(RES, "都道府県_地域格差",
                                "panel_regression_summary_antivegf.csv"))
ref = summ[summ["code"] == "ANTI_VEGF_TOTAL"].set_index("variable")["coefficient"]
for v in xvars:
    if not np.isclose(res.params[v], ref[v], rtol=1e-4):
        print(f"WARNING: {v} coefficient differs from pipeline output "
              f"({res.params[v]:.3f} vs {ref[v]:.3f})")

fig = plt.figure(figsize=(8.5, 11))
gs = fig.add_gridspec(2, 1, height_ratios=[1, 2.2], hspace=0.3)

# A. 係数プロット（95%CI, 都道府県クラスターSE）
ax = fig.add_subplot(gs[0])
ci = res.conf_int()
labels = {"aging_rate": "Ageing rate (%)",
          "docs_per_100k": "Ophthalmologists per 100,000",
          "facilities_per_100k": "Facilities per 100,000"}
ys = np.arange(len(xvars))[::-1]
ax.errorbar(res.params[xvars], ys,
            xerr=[res.params[xvars] - ci.loc[xvars, "lower"],
                  ci.loc[xvars, "upper"] - res.params[xvars]],
            fmt="o", color="#3182bd", ecolor="#3182bd", capsize=4)
ax.axvline(0, color="black", lw=1)
ax.set_yticks(ys)
ax.set_yticklabels([labels[v] for v in xvars])
ax.set_xlabel("Coefficient (vials per 100,000; 95% CI, prefecture-clustered SE)")
ax.set_title("A. Two-way fixed-effects panel regression, total anti-VEGF, FY2014–2024",
             fontsize=11, loc="left")

# B. 回帰補正後の県別残差（県・年固定効果＋共変量を除去、2024年度）
resid = res.resids.rename("residual").reset_index()
r24 = resid[resid["year"] == 2024].sort_values("residual", ascending=True)
ax = fig.add_subplot(gs[1])
cols = ["#b2182b" if v > 0 else "#3182bd" for v in r24["residual"]]
ax.barh(range(len(r24)), r24["residual"], color=cols, height=0.75)
ax.axvline(0, color="black", lw=1)
ax.set_yticks(range(len(r24)))
ax.set_yticklabels([PREF_EN[p] for p in r24["prefecture"]], fontsize=7.5)
ax.set_xlabel("Residual utilisation per 100,000, FY2024\n"
              "(after removing prefecture and year fixed effects and covariates)")
ax.set_ylim(-0.6, len(r24) - 0.4)
ax.set_title("B. Regression-adjusted prefecture residuals, FY2024", fontsize=11, loc="left")
save(fig, "FigureA2_panel_regression_adjusted")

coef_out = pd.DataFrame({"variable": xvars,
                         "coefficient": res.params[xvars].values,
                         "ci_lower": ci.loc[xvars, "lower"].values,
                         "ci_upper": ci.loc[xvars, "upper"].values})
coef_out.to_csv(os.path.join(OUT, "FigureA2A_coefficients.csv"),
                index=False, encoding="utf-8-sig")
r24out = r24.copy()
r24out["prefecture_en"] = r24out["prefecture"].map(PREF_EN)
r24out.sort_values("residual", ascending=False).to_csv(
    os.path.join(OUT, "FigureA2B_residuals_2024.csv"), index=False, encoding="utf-8-sig")
print("done")
