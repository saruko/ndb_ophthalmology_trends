import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from adjustText import adjust_text

# 日本語フォント設定（Windows環境を想定してメイリオまたはMSゴシック）
plt.rcParams['font.family'] = 'MS Gothic'
plt.rcParams['axes.unicode_minus'] = False

def plot_national_trends(trends_csv, output_dir):
    """主要術式の全国経年トレンド（人口10万対件数）をプロットする"""
    print("Plotting national trends...")
    df = pd.read_csv(trends_csv)
    
    plt.figure(figsize=(10, 6))
    # 術式ごとにプロット
    sns.lineplot(
        data=df,
        x="year",
        y="count_per_100k",
        hue="procedure_name",
        marker="o",
        linewidth=2.5,
        markersize=8
    )
    
    plt.title("主要眼科診療行為の全国トレンド推移 (人口10万対件数)", fontsize=14, fontweight="bold")
    plt.xlabel("年次", fontsize=12)
    plt.ylabel("人口10万対件数", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(title="診療行為", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, "national_trends_per_100k.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved trend plot to {out_path}")

def plot_disparity_trends(disparity_csv, output_dir):
    """地域格差指標（CV、Gini係数）の経年推移をプロットする"""
    print("Plotting disparity trends...")
    df = pd.read_csv(disparity_csv)
    
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    
    # 1. 変動係数 (CV) の推移
    sns.lineplot(
        data=df,
        x="year",
        y="cv",
        hue="procedure_name",
        marker="s",
        linewidth=2,
        ax=axes[0]
    )
    axes[0].set_title("都道府県間変動係数 (CV) の推移", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("年次", fontsize=10)
    axes[0].set_ylabel("変動係数 (CV)", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend(title="診療行為")
    
    # 2. Gini係数の推移
    sns.lineplot(
        data=df,
        x="year",
        y="gini",
        hue="procedure_name",
        marker="d",
        linewidth=2,
        ax=axes[1]
    )
    axes[1].set_title("都道府県間ジニ係数 (Gini) の推移", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("年次", fontsize=10)
    axes[1].set_ylabel("ジニ係数", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend(title="診療行為")
    
    year_min, year_max = int(df["year"].min()), int(df["year"].max())
    plt.suptitle(f"眼科診療行為における地域格差指標の推移 ({year_min}-{year_max})", fontsize=14, fontweight="bold")
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, "geographic_disparity_trends.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved disparity plot to {out_path}")

def plot_correlation_scatter(processed_csv, output_dir, target_code="J039-2"):
    """
    特定の術式（例: 抗VEGF注射 J039-2）における、
    高齢化率および眼科専門医数との相関散布図をプロットする
    """
    print(f"Plotting correlation scatter for code {target_code}...")
    df = pd.read_csv(processed_csv)
    df_sub = df[df["code"] == target_code].dropna(subset=["count_per_100k", "aging_rate", "docs_per_100k"])
    
    if df_sub.empty:
        print(f"No data available for correlation plotting of {target_code}")
        return
        
    proc_name = df_sub["procedure_name"].iloc[0]
    
    # 最新年度のデータに限定
    latest_year = df_sub["year"].max()
    df_latest = df_sub[df_sub["year"] == latest_year]
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 10))

    # 1. 高齢化率との相関
    sns.regplot(
        data=df_latest,
        x="aging_rate",
        y="count_per_100k",
        ax=axes[0],
        scatter_kws={"alpha":0.7, "color":"teal", "s":30},
        line_kws={"color":"red"}
    )
    texts_0 = []
    for _, row in df_latest.iterrows():
        texts_0.append(axes[0].text(row["aging_rate"], row["count_per_100k"],
                                     row["prefecture"], fontsize=6, ha="center"))
    adjust_text(texts_0, ax=axes[0], arrowprops=dict(arrowstyle="-", color="gray", lw=0.3))
    axes[0].set_title(f"{latest_year}年 高齢化率と診療件数の相関", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("高齢化率 (65歳以上人口比率)", fontsize=10)
    axes[0].set_ylabel(f"人口10万対件数 ({proc_name})", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.6)

    # 2. 医師数との相関
    sns.regplot(
        data=df_latest,
        x="docs_per_100k",
        y="count_per_100k",
        ax=axes[1],
        scatter_kws={"alpha":0.7, "color":"navy", "s":30},
        line_kws={"color":"red"}
    )
    texts_1 = []
    for _, row in df_latest.iterrows():
        texts_1.append(axes[1].text(row["docs_per_100k"], row["count_per_100k"],
                                     row["prefecture"], fontsize=6, ha="center"))
    adjust_text(texts_1, ax=axes[1], arrowprops=dict(arrowstyle="-", color="gray", lw=0.3))
    axes[1].set_title(f"{latest_year}年 人口10万対眼科専門医数と診療件数の相関", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("人口10万対眼科専門医数", fontsize=10)
    axes[1].set_ylabel(f"人口10万対件数 ({proc_name})", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    
    plt.suptitle(f"{proc_name} (コード: {target_code}) の都道府県別要因分析 ({latest_year}年)", fontsize=14, fontweight="bold")
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, f"correlation_scatter_{target_code}.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved correlation scatter to {out_path}")

def plot_prefecture_ranking(processed_csv, output_dir, target_code="J039-2"):
    """最新年度における都道府県別の診療量（人口10万対件数）ランキング"""
    print(f"Plotting prefecture ranking for code {target_code}...")
    df = pd.read_csv(processed_csv)
    df_sub = df[df["code"] == target_code].dropna(subset=["count_per_100k"])
    
    if df_sub.empty:
        return
        
    proc_name = df_sub["procedure_name"].iloc[0]
    latest_year = df_sub["year"].max()
    df_latest = df_sub[df_sub["year"] == latest_year].sort_values("count_per_100k", ascending=False)
    
    plt.figure(figsize=(12, 10))
    sns.barplot(
        data=df_latest,
        x="count_per_100k",
        y="prefecture",
        palette="viridis",
        hue="prefecture",
        legend=False
    )
    
    plt.title(f"{latest_year}年 都道府県別 {proc_name} 人口10万対件数ランキング", fontsize=14, fontweight="bold")
    plt.xlabel("人口10万対件数", fontsize=12)
    plt.ylabel("都道府県", fontsize=12)
    plt.grid(axis="x", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, f"prefecture_ranking_{target_code}.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved ranking plot to {out_path}")

def plot_k280_subanalysis(sub_csv, output_dir):
    """K280（1 網膜付着組織を含むもの）とK280（2 その他のもの）の件数推移比較"""
    print("Plotting K280 sub-analysis (K280_1 vs K280_2)...")
    df = pd.read_csv(sub_csv)
    # 改修後の個別コード K280_1, K280_2 を抽出
    df_k280 = df[df["code"].isin(["K280_1", "K280_2"])]

    if df_k280.empty:
        print("No K280_1/K280_2 data found for sub-analysis.")
        return

    # 全国合計
    df_nat = df_k280.groupby(["year", "code", "procedure_name"]).agg(
        count=("count", "sum"),
        population_total=("population_total", "sum")
    ).reset_index()
    df_nat["count_per_100k"] = (df_nat["count"] / df_nat["population_total"]) * 100000

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 1. 実件数の推移
    for code, grp in df_nat.groupby("code"):
        label = grp["procedure_name"].iloc[0]
        axes[0].plot(grp["year"], grp["count"], marker="o", linewidth=2, label=label)
    axes[0].set_title("K280 サブ分類別 全国件数推移", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("年次", fontsize=10)
    axes[0].set_ylabel("件数", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend(fontsize=8)

    # 2. 人口10万対件数の推移
    for code, grp in df_nat.groupby("code"):
        label = grp["procedure_name"].iloc[0]
        axes[1].plot(grp["year"], grp["count_per_100k"], marker="s", linewidth=2, label=label)
    axes[1].set_title("K280 サブ分類別 人口10万対件数推移", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("年次", fontsize=10)
    axes[1].set_ylabel("人口10万対件数", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend(fontsize=8)

    year_min, year_max = int(df_nat["year"].min()), int(df_nat["year"].max())
    plt.suptitle(f"硝子体茎顕微鏡下離断術 K280 サブ分類比較 ({year_min}-{year_max})",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()

    out_path = os.path.join(output_dir, "k280_subanalysis_trends.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved K280 sub-analysis plot to {out_path}")


def plot_k268_subanalysis(sub_csv, output_dir):
    """K268緑内障手術のサブグループ別（濾過・デバイス・流出路再建・併用ドレーン）の件数推移比較"""
    print("Plotting K268 sub-analysis (by subgroup)...")
    df = pd.read_csv(sub_csv)

    # サブグループ合算コードを抽出
    subgroup_codes = [
        "K268_grp_filtration",
        "K268_grp_device",
        "K268_grp_trabec",
        "K268_grp_combo",
    ]
    df_k268 = df[df["code"].isin(subgroup_codes)]

    if df_k268.empty:
        print("No K268 subgroup data found for sub-analysis.")
        return

    # 全国合計
    df_nat = df_k268.groupby(["year", "code", "procedure_name"]).agg(
        count=("count", "sum"),
        population_total=("population_total", "sum")
    ).reset_index()
    df_nat["count_per_100k"] = (df_nat["count"] / df_nat["population_total"]) * 100000

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 1. 実件数の推移
    for code, grp in df_nat.groupby("code"):
        label = grp["procedure_name"].iloc[0]
        axes[0].plot(grp["year"], grp["count"], marker="o", linewidth=2, label=label)
    axes[0].set_title("K268 サブ分類別 全国件数推移", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("年次", fontsize=10)
    axes[0].set_ylabel("件数", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend(fontsize=7)

    # 2. 人口10万対件数の推移
    for code, grp in df_nat.groupby("code"):
        label = grp["procedure_name"].iloc[0]
        axes[1].plot(grp["year"], grp["count_per_100k"], marker="s", linewidth=2, label=label)
    axes[1].set_title("K268 サブ分類別 人口10万対件数推移", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("年次", fontsize=10)
    axes[1].set_ylabel("人口10万対件数", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend(fontsize=7)

    year_min, year_max = int(df_nat["year"].min()), int(df_nat["year"].max())
    plt.suptitle(f"緑内障手術 K268 サブ分類比較 ({year_min}-{year_max})",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()

    out_path = os.path.join(output_dir, "k268_subanalysis_trends.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved K268 sub-analysis plot to {out_path}")


def plot_all(processed_csv_path, output_dir):
    """すべてのグラフを作成して保存する"""
    plot_dir = os.path.join(output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    plot_national_trends(os.path.join(output_dir, "national_trends.csv"), plot_dir)
    plot_disparity_trends(os.path.join(output_dir, "geographic_disparity.csv"), plot_dir)

    # 主要な術式について相関とランキングを描画
    # K268（緑内障手術合算）とK259（角膜移植術）を追加
    for code in ["K282", "K282_total", "K280", "J039-2", "K268", "K259"]:
        plot_correlation_scatter(processed_csv_path, plot_dir, target_code=code)
        plot_prefecture_ranking(processed_csv_path, plot_dir, target_code=code)

    # K280 サブ解析: 1 網膜付着組織を含むもの vs 2 その他のもの
    base = os.path.basename(processed_csv_path)  # e.g. ndb_processed_zero.csv
    suffix = base.replace("ndb_processed_", "").replace(".csv", "")  # e.g. zero
    sub_csv = os.path.join(output_dir, f"ndb_processed_k280_sub_{suffix}.csv")
    if os.path.exists(sub_csv):
        plot_k280_subanalysis(sub_csv, plot_dir)
        # K268 サブ解析プロットも同じサブ CSVから生成
        plot_k268_subanalysis(sub_csv, plot_dir)

    print("All plots generated successfully!")

if __name__ == "__main__":
    plot_all(
        processed_csv_path="data/processed/ndb_processed_zero.csv",
        output_dir="data/processed"
    )
