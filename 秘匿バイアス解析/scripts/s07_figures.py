# -*- coding: utf-8 -*-
"""
s07: 論文用図表
Fig1: コード×年度の秘匿率ヒートマップ
Fig2: Gini識別区間（bounds）の帯グラフ（秘匿率上位コード）
Fig3: 人工秘匿実験の手法別バイアス（Gini / APC、RMSE）
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")
FIG_DIR = os.path.join(OUT_DIR, "plots")

plt.rcParams["font.family"] = ["Yu Gothic", "MS Gothic", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False


def fig1_heatmap():
    m = pd.read_csv(os.path.join(OUT_DIR, "census_by_code_year.csv"), index_col=0)
    m = m.loc[m.mean(axis=1).sort_values(ascending=False).index]
    fig, ax = plt.subplots(figsize=(9, 6.5))
    im = ax.imshow(m.values, aspect="auto", cmap="YlOrRd", vmin=0, vmax=1)
    ax.set_xticks(range(m.shape[1]), m.columns, rotation=45)
    ax.set_yticks(range(m.shape[0]), m.index)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6,
                        color="white" if v > 0.6 else "black")
    fig.colorbar(im, label="秘匿セル割合")
    ax.set_title("Figure 1. 診療行為コード×年度別の秘匿率（都道府県セルに占める '-' の割合）")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig1_censoring_heatmap.png"), dpi=200)
    plt.close(fig)


def fig2_bounds():
    d = pd.read_csv(os.path.join(OUT_DIR, "bounds_disparity.csv"))
    # 構造的欠測の除外後に6年度以上残るコードのみを対象とする
    ok = d.groupby("code")["year"].nunique()
    d = d[d["code"].isin(ok[ok >= 6].index)]
    top = (d.groupby("code")["gini_width"].mean()
           .sort_values(ascending=False).head(6).index.tolist())
    fig, axes = plt.subplots(2, 3, figsize=(12, 7), sharex=True)
    for ax, code in zip(axes.ravel(), top):
        dc = d[d["code"] == code].sort_values("year")
        ax.fill_between(dc["year"], dc["gini_lower"], dc["gini_upper"],
                        alpha=0.35, label="識別区間 [imput=1, imput=9]")
        ax.plot(dc["year"], (dc["gini_lower"] + dc["gini_upper"]) / 2,
                marker="o", ms=3, lw=1)
        ax.set_title(code, fontsize=10)
        ax.set_ylim(0, 1)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle("Figure 2. Gini係数の部分識別区間（識別幅の大きい6コード）")
    fig.supxlabel("年度")
    fig.supylabel("Gini係数")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig2_gini_bounds.png"), dpi=200)
    plt.close(fig)


def fig3_experiment():
    s = pd.read_csv(os.path.join(OUT_DIR, "experiment_mle_summary.csv"))
    labels = {"zero": "0補完", "five": "5補完", "random": "乱数補完",
              "censored_mle_poisson": "打ち切りMLE (Poisson)",
              "censored_mle_nb": "打ち切りMLE (NB)",
              "censored_mle": "打ち切りMLE (Poisson)"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, metric, name in zip(
            axes, ["gini_rmse", "apc_rmse"],
            ["Gini係数 RMSE", "APC RMSE（％ポイント）"]):
        for strat, ds in s.groupby("strategy"):
            ds = ds.sort_values("censoring_rate")
            ax.plot(ds["censoring_rate"] * 100, ds[metric],
                    marker="o", label=labels.get(strat, strat))
        ax.set_xlabel("秘匿セル割合（%）")
        ax.set_ylabel(name)
        ax.set_yscale("log")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.suptitle("Figure 3. 人工秘匿実験における手法別推定誤差（K282実データのthinning、真値既知）")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig3_method_rmse.png"), dpi=200)
    plt.close(fig)


def run():
    os.makedirs(FIG_DIR, exist_ok=True)
    fig1_heatmap()
    fig2_bounds()
    fig3_experiment()
    print(f"figures saved to {FIG_DIR}")


if __name__ == "__main__":
    run()
