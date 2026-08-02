# -*- coding: utf-8 -*-
"""紫外線 vs 翼状片手術率の相関 可視化"""
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import find, uv_path, output_dir  # noqa: E402

plt.rcParams["font.family"] = "MS Gothic"
plt.rcParams["axes.unicode_minus"] = False

PLOTS = os.path.join(output_dir(), "plots")
os.makedirs(PLOTS, exist_ok=True)

UV = {
    "jma_uv": ("jma_uv_index_annual_mean.csv", "uv_index_annual_mean", "JMA UVインデックス"),
    "openmeteo_radiation": ("openmeteo_radiation_annual_mean.csv", "radiation_annual_mean", "Open-Meteo 日射量"),
}
SETTING_JA = {"outpatient": "外来", "inpatient": "入院", "total": "全体"}


def load():
    rate = pd.read_csv(find("pterygium_rate_per100k.csv"))
    rate = rate[["year", "prefecture", "setting", "count_per_100k"]]
    out = {}
    for src, (fn, col, _) in UV.items():
        uv = pd.read_csv(uv_path(fn))[["year", "prefecture", col]].rename(columns={col: "uv"})
        out[src] = pd.merge(rate, uv, on=["year", "prefecture"], how="inner")
    return out


def plot_yearly_r(df_b):
    """解析B: 年次横断相関 r の推移"""
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    for ax, src in zip(axes, UV):
        g = df_b[df_b["uv_source"] == src]
        for setting in ["outpatient", "total", "inpatient"]:
            gs = g[g["setting"] == setting].sort_values("year")
            ax.plot(gs["year"], gs["pearson_r"], marker="o", label=SETTING_JA[setting])
        ax.axhline(0, color="gray", lw=0.8, ls="--")
        ax.set_title(f"{UV[src][2]} との年次横断相関 (Pearson r)", fontweight="bold")
        ax.set_xlabel("年度"); ax.set_ylabel("相関係数 r")
        ax.set_ylim(-0.4, 1.0); ax.grid(alpha=0.4); ax.legend(title="手術区分")
    plt.tight_layout()
    p = os.path.join(PLOTS, "uv_yearly_correlation.png")
    plt.savefig(p, dpi=200); plt.close(); print(f"Saved {p}")


def plot_scatter_latest(merged, year=2024):
    """代表年の散布図（47都道府県, 外来）"""
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, src in zip(axes, UV):
        d = merged[src]
        d = d[(d["year"] == year) & (d["setting"] == "outpatient")]
        ax.scatter(d["uv"], d["count_per_100k"], s=40)
        r, p = stats.pearsonr(d["uv"], d["count_per_100k"])
        # 回帰直線
        m, b = np.polyfit(d["uv"], d["count_per_100k"], 1)
        xs = np.linspace(d["uv"].min(), d["uv"].max(), 50)
        ax.plot(xs, m * xs + b, color="red", lw=1.5)
        # 南方県を強調ラベル
        for _, row in d.iterrows():
            if row["prefecture"] in ["沖縄県", "鹿児島県", "宮崎県", "北海道", "青森県", "東京都"]:
                ax.annotate(row["prefecture"], (row["uv"], row["count_per_100k"]), fontsize=9)
        ax.set_title(f"{year}年 外来 vs {UV[src][2]}\nPearson r={r:.3f} (p={p:.1e})", fontweight="bold")
        ax.set_xlabel(UV[src][2]); ax.set_ylabel("外来手術 人口10万対")
        ax.grid(alpha=0.4)
    plt.tight_layout()
    p = os.path.join(PLOTS, f"uv_scatter_{year}_outpatient.png")
    plt.savefig(p, dpi=200); plt.close(); print(f"Saved {p}")


if __name__ == "__main__":
    merged = load()
    df_b = pd.read_csv(find("uv_correlation_by_year.csv"))
    plot_yearly_r(df_b)
    plot_scatter_latest(merged, 2024)
