import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 日本語フォント設定（Windows環境を想定してMSゴシック）
plt.rcParams['font.family'] = 'MS Gothic'
plt.rcParams['axes.unicode_minus'] = False

# adjustTextのインポート試行（存在しない場合はアノテーションの重複自動調整なしで処理）
try:
    from adjustText import adjust_text
    HAS_ADJUST_TEXT = True
except ImportError:
    HAS_ADJUST_TEXT = False

# 散布図・トレンド図を描く対象コード（全25カテゴリを描くと図が読めなくなるため）
SCATTER_CODES = [
    "GLAUCOMA_EYE_TOTAL", "PGA", "BETA", "CAI", "ALPHA2", "ROCK", "FDC_TOTAL",
    "LATANOPROST", "TIMOLOL", "RIPASUDIL", "BRIMONIDINE",
]
# 薬効群（ガイドライン第5版の分類）。preprocess_glaucoma.GROUP_DEFS と対応する
CLASS_CODES = ["PGA", "BETA", "ALPHA1BETA", "ALPHA1", "ALPHA2", "SYMPATHO",
               "PARASYMPATHO", "CAI", "ROCK", "FDC_TOTAL", "GLAUCOMA_EYE_TOTAL"]
SUBGROUP_CODES = ["PGA_FP", "PGA_EP2", "PGA_ION", "BETA_NONSEL", "BETA_B1SEL",
                  "PARASYM_DIR", "PARASYM_IND"]


def _plot_trend_subset(df, codes, title, out_path):
    plt.figure(figsize=(11, 6))
    sns.lineplot(
        data=df[df["code"].isin(codes)],
        x="year",
        y="count_per_100k",
        hue="procedure_name",
        marker="o",
        linewidth=2.5,
        markersize=8
    )
    plt.title(title, fontsize=14, fontweight="bold")
    plt.xlabel("年次", fontsize=12)
    plt.ylabel("処方数量 (mL, 人口10万対)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(title="薬剤カテゴリ", bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved trend plot to {out_path}")


def plot_national_trends(trends_csv, output_dir):
    """緑内障点眼薬の全国経年トレンド（人口10万対mL）をプロットする。

    カテゴリが25以上あり1枚に収まらないため、薬理クラス別と単剤別の2枚に分ける。
    """
    print("Plotting national trends for glaucoma drugs...")
    df = pd.read_csv(trends_csv)

    _plot_trend_subset(
        df, CLASS_CODES,
        "緑内障点眼薬の全国トレンド推移・薬理クラス別 (人口10万対mL)",
        os.path.join(output_dir, "national_trends_glaucoma.png"))

    mono = sorted(set(df["code"]) - set(CLASS_CODES) - set(SUBGROUP_CODES))
    _plot_trend_subset(
        df, mono,
        "緑内障点眼薬の全国トレンド推移・薬剤別 (人口10万対mL)",
        os.path.join(output_dir, "national_trends_by_drug_glaucoma.png"))


def plot_disparity_trends(disparity_csv, output_dir):
    """緑内障点眼薬の地域格差指標（CV、Gini係数）の経年推移をプロットする"""
    print("Plotting disparity trends for glaucoma drugs...")
    df = pd.read_csv(disparity_csv)
    df = df[df["code"].isin(CLASS_CODES)]

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
    axes[0].set_title("都道府県間変動係数 (CV) の推移 (緑内障点眼薬)", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("年次", fontsize=10)
    axes[0].set_ylabel("変動係数 (CV)", fontsize=10)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].legend().remove()
    
    # 2. Gini係数の推移
    sns.lineplot(
        data=df,
        x="year",
        y="gini",
        hue="procedure_name",
        marker="o",
        linewidth=2,
        ax=axes[1]
    )
    axes[1].set_title("都道府県間ジニ係数の推移 (緑内障点眼薬)", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("年次", fontsize=10)
    axes[1].set_ylabel("ジニ係数", fontsize=10)
    axes[1].grid(True, linestyle="--", alpha=0.6)
    axes[1].legend(title="薬剤カテゴリ", bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.tight_layout()
    out_path = os.path.join(output_dir, "geographic_disparity_glaucoma.png")
    plt.savefig(out_path, dpi=300)
    plt.close()
    print(f"Saved disparity plot to {out_path}")

def plot_correlation_scatter(processed_csv, output_dir, target_year=None):
    """直近年度における、緑内障点眼薬普及率と共変量の散布図"""
    df = pd.read_csv(processed_csv)
    if target_year is None:
        target_year = int(df["year"].max())
    print(f"Plotting correlation scatters for year {target_year}...")
    df_year = df[df["year"] == target_year].copy()
    
    if df_year.empty:
        print(f"No data available for year {target_year}. Skipping scatter plot.")
        return
        
    # 緑内障点眼薬は薬剤カテゴリが25以上あり全コードで作図すると図が氾濫するため、
    # 薬理クラス集計と処方量の多い主要単剤に限定する
    codes = [c for c in SCATTER_CODES if c in set(df_year["code"])]
    covariates = [
        ("aging_rate", "高齢化率"),
        ("docs_per_100k", "眼科医数 (人口10万対)"),
        ("facilities_per_100k", "眼科医療施設数 (人口10万対)")
    ]
    
    # 主要コードごとに散布図を作成
    for code in codes:
        df_code = df_year[df_year["code"] == code].copy()
        proc_name = df_code["procedure_name"].iloc[0]
        
        # 3つの共変量に対して1行3列のマルチプロットを作成
        fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
        fig.suptitle(f"{proc_name} 普及率と都道府県共変量との関係 ({target_year}年度)", fontsize=14, fontweight="bold", y=0.98)
        
        for idx, (cov_col, cov_label) in enumerate(covariates):
            ax = axes[idx]
            valid_df = df_code[[cov_col, "count_per_100k", "prefecture"]].dropna()
            if valid_df.empty:
                continue
                
            x = valid_df[cov_col]
            y = valid_df["count_per_100k"]
            
            # 回帰直線付き散布図
            sns.regplot(
                x=x, y=y, ax=ax,
                scatter_kws={"alpha":0.6, "color":"#1f77b4"},
                line_kws={"color":"red", "linestyle":"--", "linewidth":1.5}
            )
            
            ax.set_xlabel(cov_label, fontsize=10)
            ax.set_ylabel("処方数量 (mL, 人口10万対)", fontsize=10)
            ax.grid(True, linestyle="--", alpha=0.5)
            
            # 相関係数（Spearman）の算出と表示
            from scipy.stats import spearmanr
            if len(valid_df) > 2 and np.std(x) > 0 and np.std(y) > 0:
                rho, p_val = spearmanr(x, y)
                ax.text(
                    0.05, 0.95, f"Spearman ρ = {rho:.3f}\np-val = {p_val:.3e}",
                    transform=ax.transAxes, verticalalignment='top',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray')
                )
            
            # 都道府県名のアノテーション
            texts = []
            for i, row in valid_df.iterrows():
                # 特徴的な点（値が大きい/小さい）や、ランダムにいくつかのラベルのみプロットして重なりを抑える
                # ここでは全ての点にアノテーションを配置し、adjustTextで調整する
                t = ax.text(row[cov_col], row["count_per_100k"], row["prefecture"], fontsize=8, alpha=0.8)
                texts.append(t)
                
            if HAS_ADJUST_TEXT and texts:
                adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle="->", color='gray', lw=0.5))
                
        plt.tight_layout()
        out_path = os.path.join(output_dir, f"correlation_scatter_{code}_{target_year}.png")
        plt.savefig(out_path, dpi=300)
        plt.close()
        print(f"Saved correlation scatter plot for {code} to {out_path}")

def visualize_glaucoma_all(processed_csv_path, output_dir):
    """すべての可視化を実行するエントリーポイント"""
    plot_dir = os.path.join(output_dir, "plots")
    os.makedirs(plot_dir, exist_ok=True)
    
    # 1. トレンド
    trends_csv = os.path.join(output_dir, "national_trends_glaucoma.csv")
    if os.path.exists(trends_csv):
        plot_national_trends(trends_csv, plot_dir)
        
    # 2. 格差推移
    disparity_csv = os.path.join(output_dir, "geographic_disparity_glaucoma.csv")
    if os.path.exists(disparity_csv):
        plot_disparity_trends(disparity_csv, plot_dir)
        
    # 3. 直近年度の散布図
    if os.path.exists(processed_csv_path):
        plot_correlation_scatter(processed_csv_path, plot_dir)
        
    print("All glaucoma plots generated successfully!")

if __name__ == "__main__":
    visualize_glaucoma_all(
        processed_csv_path="緑内障点眼/processed_nokouhi/ndb_processed_glaucoma_zero.csv",
        output_dir="緑内障点眼/processed_nokouhi"
    )
