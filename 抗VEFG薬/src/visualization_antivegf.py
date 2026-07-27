"""抗VEGF薬解析の図表作成。"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# 日本語フォント設定（Windows環境を想定してMSゴシック）
plt.rcParams["font.family"] = "MS Gothic"
plt.rcParams["axes.unicode_minus"] = False

# 経年比較用（90歳以上に統合した区分）
AGE_ORDER = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳", "25～29歳",
    "30～34歳", "35～39歳", "40～44歳", "45～49歳", "50～54歳", "55～59歳",
    "60～64歳", "65～69歳", "70～74歳", "75～79歳", "80～84歳", "85～89歳",
    "90歳以上",
]
# 公開粒度（2015年度以降は90歳以上が3区分に細分化）
AGE_ORDER_PUBLISHED = AGE_ORDER[:-1] + ["90～94歳", "95～99歳", "100歳以上", "90歳以上"]


def _save(fig_path):
    plt.tight_layout()
    plt.savefig(fig_path, dpi=200)
    plt.close()
    print(f"  saved {os.path.basename(fig_path)}")


def plot_all(processed_dir, plots_dir):
    os.makedirs(plots_dir, exist_ok=True)
    print("Plotting figures...")

    # 1. 製品別 処方数量トレンド
    prod = pd.read_csv(os.path.join(processed_dir, "product_trends_antivegf.csv"))
    plt.figure(figsize=(11, 6))
    sns.lineplot(data=prod, x="year", y="quantity", hue="product_name",
                 marker="o", linewidth=2)
    plt.title("抗VEGF薬 製品別 処方数量の推移（全国・外来＋入院）", fontweight="bold")
    plt.xlabel("年度")
    plt.ylabel("処方数量（バイアル・シリンジ本数）")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(title="製品", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    _save(os.path.join(plots_dir, "product_trends.png"))

    # 2. 製品別シェアの積み上げ
    piv = prod.pivot_table(index="year", columns="product_name", values="share_pct").fillna(0)
    piv.plot(kind="area", stacked=True, figsize=(11, 6), colormap="tab20")
    plt.title("抗VEGF薬 製品別シェアの推移（%）", fontweight="bold")
    plt.xlabel("年度")
    plt.ylabel("シェア（%）")
    plt.ylim(0, 100)
    plt.legend(title="製品", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    _save(os.path.join(plots_dir, "product_share_stacked.png"))

    # 3. 剤形比率（全体）
    form = pd.read_csv(os.path.join(processed_dir, "formulation_total_antivegf.csv"))
    piv = form.pivot_table(index="year", columns="formulation", values="share_pct").fillna(0)
    piv.plot(kind="bar", stacked=True, figsize=(10, 5), color=["#4C78A8", "#F58518"])
    plt.title("抗VEGF薬全体の剤形比率（注射液 vs キット）", fontweight="bold")
    plt.xlabel("年度")
    plt.ylabel("シェア（%）")
    plt.legend(title="剤形")
    _save(os.path.join(plots_dir, "formulation_share_total.png"))

    # 4. 成分別の剤形比率（両剤形がある成分のみ）
    fm = pd.read_csv(os.path.join(processed_dir, "formulation_by_molecule_antivegf.csv"))
    fm = fm[fm["has_both_formulations"] & (fm["formulation"] == "キット")]
    if not fm.empty:
        plt.figure(figsize=(10, 5))
        sns.lineplot(data=fm, x="year", y="share_within_molecule_pct",
                     hue="molecule_name", marker="o", linewidth=2)
        plt.title("成分別 キット製剤の比率", fontweight="bold")
        plt.xlabel("年度")
        plt.ylabel("キット比率（%）")
        plt.ylim(0, 100)
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.legend(title="成分", fontsize=9)
        _save(os.path.join(plots_dir, "formulation_kit_share_by_molecule.png"))

    # 5. 先発 vs バイオシミラー
    bs = pd.read_csv(os.path.join(processed_dir, "biosimilar_national_share.csv"))
    piv = bs.pivot_table(index="year", columns="brand_type", values="quantity").fillna(0)
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    piv.plot(kind="bar", stacked=True, ax=ax[0], color=["#E45756", "#54A24B"])
    ax[0].set_title("ラニビズマブ 処方数量（先発 vs BS）", fontweight="bold")
    ax[0].set_xlabel("年度")
    ax[0].set_ylabel("処方数量")
    pivs = bs.pivot_table(index="year", columns="brand_type", values="share_pct").fillna(0)
    pivs.plot(kind="line", marker="o", ax=ax[1], color=["#E45756", "#54A24B"])
    ax[1].set_title("ラニビズマブ シェア推移（%）", fontweight="bold")
    ax[1].set_xlabel("年度")
    ax[1].set_ylabel("シェア（%）")
    ax[1].set_ylim(0, 100)
    ax[1].grid(True, linestyle="--", alpha=0.5)
    _save(os.path.join(plots_dir, "biosimilar_share.png"))

    # 6. 年齢・性別ピラミッド（最新年度）— 単年のためその年度の公開粒度を使う
    pub = pd.read_csv(os.path.join(processed_dir,
                                   "agesex_distribution_published_antivegf.csv"))
    latest = pub[pub["year"] == pub["year"].max()].copy()
    latest["age_group_detail"] = pd.Categorical(
        latest["age_group_detail"], AGE_ORDER_PUBLISHED, ordered=True)
    latest = latest.sort_values("age_group_detail")
    male = latest[latest["sex"] == "男"].set_index("age_group_detail")["quantity"]
    female = latest[latest["sex"] == "女"].set_index("age_group_detail")["quantity"]
    plt.figure(figsize=(9, 7))
    plt.barh(male.index.astype(str), -male.values, color="#4C78A8", label="男")
    plt.barh(female.index.astype(str), female.values, color="#E45756", label="女")
    plt.title(f"抗VEGF薬 年齢階級・性別分布（{int(pub['year'].max())}年度）",
              fontweight="bold")
    plt.xlabel("処方数量（左：男 / 右：女）")
    plt.axvline(0, color="black", linewidth=0.8)
    plt.legend()
    _save(os.path.join(plots_dir, "agesex_pyramid_latest.png"))

    # 7. 年齢分布の経年変化（男女計）— 経年比較のため統合区分を使う
    dist = pd.read_csv(os.path.join(processed_dir,
                                    "agesex_distribution_comparable_antivegf.csv"))
    age = dist.groupby(["year", "age_group"], as_index=False)["quantity"].sum()
    age["share"] = age.groupby("year")["quantity"].transform(lambda s: s / s.sum() * 100)
    piv = age.pivot_table(index="age_group", columns="year", values="share")
    piv = piv.reindex(AGE_ORDER)
    plt.figure(figsize=(11, 6))
    sns.heatmap(piv, cmap="YlOrRd", annot=False, cbar_kws={"label": "構成比（%）"})
    plt.title("抗VEGF薬 年齢構成比の推移（%）", fontweight="bold")
    plt.xlabel("年度")
    plt.ylabel("年齢階級")
    _save(os.path.join(plots_dir, "age_distribution_heatmap.png"))

    # 8. 都道府県別 人口10万対ランキング（最新年度）
    panel_files = [f for f in os.listdir(processed_dir)
                   if f.startswith("panel_") and f.endswith(".csv")]
    panel = pd.read_csv(os.path.join(processed_dir, "panel_zero.csv"))
    total = panel[(panel["code"] == "ANTI_VEGF_TOTAL")
                  & (panel["year"] == panel["year"].max())]
    total = total.sort_values("count_per_100k", ascending=False)
    plt.figure(figsize=(9, 10))
    sns.barplot(data=total, y="prefecture", x="count_per_100k", color="#4C78A8")
    plt.title(f"抗VEGF薬 都道府県別 人口10万対処方数量（{int(panel['year'].max())}年度）",
              fontweight="bold")
    plt.xlabel("人口10万対 処方数量")
    plt.ylabel("")
    _save(os.path.join(plots_dir, "prefecture_ranking_latest.png"))

    # 9. 地域格差指標の推移
    disp = pd.read_csv(os.path.join(processed_dir, "geographic_disparity_antivegf.csv"))
    sub = disp[disp["code"].isin(["ANTI_VEGF_TOTAL", "AFLIBERCEPT", "RANIBIZUMAB_ALL",
                                  "FARICIMAB", "RANIBIZUMAB_BS"])]
    plt.figure(figsize=(10, 5))
    sns.lineplot(data=sub, x="year", y="gini", hue="name", marker="o", linewidth=2)
    plt.title("都道府県間格差（Gini係数）の推移", fontweight="bold")
    plt.xlabel("年度")
    plt.ylabel("Gini係数")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(fontsize=8)
    _save(os.path.join(plots_dir, "gini_trends.png"))

    # 10. 薬剤費の推移
    plt.figure(figsize=(11, 6))
    cost = prod.groupby(["year", "product_name"], as_index=False)["cost"].sum()
    piv = cost.pivot_table(index="year", columns="product_name", values="cost").fillna(0)
    (piv / 1e8).plot(kind="area", stacked=True, figsize=(11, 6), colormap="tab20")
    plt.title("抗VEGF薬 薬剤費の推移（薬価×処方数量）", fontweight="bold")
    plt.xlabel("年度")
    plt.ylabel("薬剤費（億円）")
    plt.legend(title="製品", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    _save(os.path.join(plots_dir, "cost_trends.png"))
