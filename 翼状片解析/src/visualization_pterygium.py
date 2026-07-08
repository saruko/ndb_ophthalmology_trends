import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 日本語フォント設定（Windows環境のMSゴシック）
plt.rcParams['font.family'] = 'MS Gothic'
plt.rcParams['axes.unicode_minus'] = False

def plot_national_trends(rate_csv_path, output_dir):
    """全国手術件数トレンド（人口10万対）の経年推移をプロットする"""
    print("Plotting national trends...")
    df = pd.read_csv(rate_csv_path)
    
    # 全国合計を算出
    df_national = df.groupby(["year", "setting"]).agg({
        "count": "sum",
        "population_total": "sum"
    }).reset_index()
    df_national["count_per_100k"] = (df_national["count"] / df_national["population_total"]) * 100000
    
    # 2017年のinpatientとtotalを除外（欠測として線を繋げないための処理）
    # pandas + matplotlib でのプロット時に線を不連続にするため、
    # 2017年のレコードを count_per_100k = NaN として明示的に挿入する
    all_combinations = pd.MultiIndex.from_product(
        [range(2014, 2025), ["outpatient", "inpatient", "total"]],
        names=["year", "setting"]
    ).to_frame().reset_index(drop=True)
    
    df_plot = pd.merge(all_combinations, df_national, on=["year", "setting"], how="left")
    
    # 2017年のinpatientとtotal、および2014年のoutpatient/inpatientを明示的にNaNにする
    df_plot.loc[(df_plot["year"] == 2017) & (df_plot["setting"].isin(["inpatient", "total"])), "count_per_100k"] = np.nan
    df_plot.loc[(df_plot["year"] == 2014) & (df_plot["setting"].isin(["outpatient", "inpatient"])), "count_per_100k"] = np.nan
    
    # setting名のラベル日本語化
    label_map = {
        "outpatient": "外来 (2015-2024)",
        "inpatient": "入院 (2015-2024, 2017年欠測)",
        "total": "全体 [外来+入院] (2014-2024, 2017年欠測)"
    }
    df_plot["setting_ja"] = df_plot["setting"].map(label_map)
    
    # プロット
    plt.figure(figsize=(11, 6))
    
    # seabornはNaNを適切に不連続線として扱う
    sns.lineplot(
        data=df_plot,
        x="year",
        y="count_per_100k",
        hue="setting_ja",
        marker="o",
        linewidth=2.5,
        markersize=8,
        hue_order=[label_map["total"], label_map["outpatient"], label_map["inpatient"]]
    )
    
    plt.title("翼状片手術（K224）の全国トレンド推移 (人口10万対件数)", fontsize=14, fontweight="bold")
    plt.xlabel("年度", fontsize=12)
    plt.ylabel("人口10万対手術件数 (件)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.xticks(range(2014, 2025))
    plt.legend(title="設定", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, "pterygium_national_trends.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved trend plot to {out_path}")

def plot_disparity_trends(disp_csv_path, output_dir):
    """地域格差指標（CV、Gini係数）の経年推移をプロットする"""
    print("Plotting disparity trends...")
    df_disp = pd.read_csv(disp_csv_path)
    
    # 2017年のinpatientとtotalを除外した状態の折れ線を不連続にするためのマージ
    all_combinations = pd.MultiIndex.from_product(
        [range(2014, 2025), ["outpatient", "inpatient", "total"]],
        names=["year", "setting"]
    ).to_frame().reset_index(drop=True)
    
    df_plot = pd.merge(all_combinations, df_disp, on=["year", "setting"], how="left")
    
    label_map = {
        "outpatient": "外来 (2015-2024)",
        "inpatient": "入院 (2015-2024, 2017年欠測)",
        "total": "全体 [外来+入院] (2014-2024, 2017年欠測)"
    }
    df_plot["setting_ja"] = df_plot["setting"].map(label_map)
    
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    
    # 1. 変動係数 (CV) の推移
    sns.lineplot(
        data=df_plot,
        x="year",
        y="cv",
        hue="setting_ja",
        marker="s",
        linewidth=2,
        ax=axes[0],
        hue_order=[label_map["total"], label_map["outpatient"], label_map["inpatient"]]
    )
    axes[0].set_title("都道府県間 変動係数 (CV) の推移", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("年度", fontsize=10)
    axes[0].set_ylabel("変動係数 (CV)", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].set_xticks(range(2014, 2025))
    axes[0].legend().remove()
    
    # 2. Gini係数の推移
    sns.lineplot(
        data=df_plot,
        x="year",
        y="gini",
        hue="setting_ja",
        marker="o",
        linewidth=2,
        ax=axes[1],
        hue_order=[label_map["total"], label_map["outpatient"], label_map["inpatient"]]
    )
    axes[1].set_title("都道府県間 ジニ係数の推移", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("年度", fontsize=10)
    axes[1].set_ylabel("ジニ係数", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].set_xticks(range(2014, 2025))
    axes[1].legend(title="設定", bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    out_path = os.path.join(output_dir, "pterygium_geographic_disparity.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved disparity plot to {out_path}")

def plot_prefecture_ranking(rate_csv_path, output_dir, target_year=2024, setting="outpatient"):
    """特定年度・設定における都道府県別の人口10万対手術件数のランキング棒グラフ"""
    print(f"Plotting prefecture ranking for {target_year} ({setting})...")
    df = pd.read_csv(rate_csv_path)
    
    # 該当データの抽出
    df_sub = df[(df["year"] == target_year) & (df["setting"] == setting)].copy()
    if df_sub.empty:
        print(f"  Warning: No data for {target_year} ({setting}) to plot ranking.")
        return
        
    df_sub = df_sub.sort_values(by="count_per_100k", ascending=False)
    
    plt.figure(figsize=(14, 6))
    
    # 南方とそれ以外の可視化のためにグラデーションか色分け
    # 例：沖縄・鹿児島などを強調、または単一色
    # ここでは、件数に応じた色合いにするため、viridisカラーマップを使用
    colors = plt.cm.viridis(np.linspace(0.8, 0.2, len(df_sub)))
    
    sns.barplot(
        data=df_sub,
        x="prefecture",
        y="count_per_100k",
        palette="viridis",
        hue="prefecture",
        legend=False
    )
    
    plt.title(f"{target_year}年度 都道府県別 翼状片手術件数（{setting}、人口10万対）", fontsize=14, fontweight="bold")
    plt.xlabel("都道府県", fontsize=12)
    plt.ylabel("人口10万対手術件数 (件)", fontsize=12)
    plt.xticks(rotation=90)
    plt.grid(True, axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    
    out_path = os.path.join(output_dir, f"pterygium_prefecture_ranking_{target_year}_{setting}.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved ranking plot to {out_path}")

def visualize_pterygium_all(processed_dir):
    """すべてのグラフを描画する"""
    rate_csv = os.path.join(processed_dir, "pterygium_rate_per100k.csv")
    disp_csv = os.path.join(processed_dir, "pterygium_gini_cv_trend.csv")
    plots_dir = os.path.join(processed_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    
    plot_national_trends(rate_csv, plots_dir)
    plot_disparity_trends(disp_csv, plots_dir)
    plot_prefecture_ranking(rate_csv, plots_dir, target_year=2024, setting="outpatient")
    # 入院と全体のランキングも念のため描画
    plot_prefecture_ranking(rate_csv, plots_dir, target_year=2024, setting="total")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    processed = os.path.join(base_dir, "processed")
    visualize_pterygium_all(processed)
