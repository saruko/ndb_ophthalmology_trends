# -*- coding: utf-8 -*-
"""論文用の追加図2点を生成する。

1. Fig_MF_ratio_forest.png
   Table2（2024年度・主要3成分合計）の年齢階級別 男/女比（人口10万対）を
   区間バーつきの横向きフォレスト風プロットにしたもの。
   区間は [男下限/女上限, 男上限/女下限]。比=1 に基準線。
   区間が1をまたぐ階級（方向判定不能）はグレーで描く。

2. SupplFig_missingness_schema.png
   NDBオープンデータの欠測3層構造（セル秘匿・総計秘匿・品目非掲載）と
   各層の識別区間の導出をまとめた模式図（Suppl用）。

入力: 論文図表/csv/Tables_123_bounds__Table2_MF_ratio.csv（既存パイプラインの生成物）
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd

plt.rcParams["font.family"] = ["Meiryo", "Yu Gothic", "MS Gothic"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.join(BASE, "05_論文成果物", "公費含めない_new", "論文図表")
CSV = os.path.join(FIG_DIR, "csv", "Tables_123_bounds__Table2_MF_ratio.csv")


# ----------------------------------------------------------------------
# 1. 男女比フォレスト風プロット
# ----------------------------------------------------------------------
def mf_forest():
    df = pd.read_csv(CSV)
    df = df.iloc[::-1].reset_index(drop=True)  # 高齢を上、幼児を下 → 逆順で描く

    lo = df.MF_per100k_ratio_lower
    hi = df.MF_per100k_ratio_upper
    crosses_one = (lo < 1) & (hi > 1)

    fig, ax = plt.subplots(figsize=(7, 8))
    y = range(len(df))
    for i in y:
        wide = crosses_one[i]
        color = "#9e9e9e" if wide else ("#1f77b4" if hi[i] < 1 else "#d62728")
        # 点推定は置かない（§2.8 の方針）。区間の両端をキャップつきの横棒で示す
        ax.plot([lo[i], hi[i]], [i, i], color=color, lw=2.5,
                solid_capstyle="butt", zorder=2)
        for x in (lo[i], hi[i]):
            ax.plot([x, x], [i - 0.18, i + 0.18], color=color, lw=1.5, zorder=3)

    ax.axvline(1.0, color="black", lw=0.8, ls="--", zorder=1)
    ax.set_yticks(list(y))
    ax.set_yticklabels(df["Age Group"])
    ax.set_xscale("log")
    ax.set_xlim(0.05, 50)
    ax.set_xticks([0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50])
    ax.set_xticklabels(["0.1", "0.2", "0.5", "1", "2", "5", "10", "20", "50"])
    ax.set_xlabel("男/女比（人口10万対処方量、対数軸）")
    ax.set_ylabel("年齢階級")
    ax.set_title("主要3成分合計の処方量 男/女比（2024年度）\n"
                 "横棒は識別区間 [男下限/女上限, 男上限/女下限]（点推定なし）", fontsize=11)

    handles = [
        plt.Line2D([], [], color="#1f77b4", lw=2.5, label="女性優位（区間<1）"),
        plt.Line2D([], [], color="#d62728", lw=2.5, label="男性優位（区間>1）"),
        plt.Line2D([], [], color="#9e9e9e", lw=2.5, label="判定不能（区間が1をまたぐ）"),
    ]
    # 左上（0.1〜0.3、若年側）はデータがないので凡例を置いても区間を隠さない
    ax.legend(handles=handles, loc="upper left", fontsize=9, framealpha=0.9)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "Fig_MF_ratio_forest.png")
    fig.savefig(path, dpi=300)
    plt.close(fig)
    print(f"-> {path}")


# ----------------------------------------------------------------------
# 2. 欠測3層構造の模式図（Suppl）
# ----------------------------------------------------------------------
def box(ax, x, y, w, h, title, lines, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.015",
                                fc=fc, ec="#444444", lw=1.2))
    ax.text(x + 0.012, y + h - 0.045, title, fontsize=11.5, weight="bold",
            va="top")
    ax.text(x + 0.012, y + h - 0.105, "\n".join(lines), fontsize=9.3,
            va="top", linespacing=1.55)


def schema():
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.97, "NDBオープンデータの欠測3層構造と識別区間の導出",
            ha="center", fontsize=13.5, weight="bold")
    ax.text(0.5, 0.925, "（抗アレルギー点眼薬9成分・2014〜2024年度）",
            ha="center", fontsize=10, color="#555555")

    box(ax, 0.03, 0.585, 0.45, 0.295,
        "第1層　セル秘匿",
        ["都道府県・年齢性別セルの数量が1,000未満で「-」。",
         "補完的秘匿により1,000以上のセルも伏せられうる",
         "（「秘匿セル≤999」は実データで反証済み）。",
         "",
         "総計列は真の合計 → 欠落量を厳密に復元できる：",
         "  missing = 総計 − Σ(開示セル)",
         "  各秘匿セルの真値 ∈ [0, missing]"],
        "#dbe9f6")

    box(ax, 0.52, 0.585, 0.45, 0.295,
        "第2層　総計秘匿",
        ["品目全体の総計が閾値未満 → 総計列自体が「-」。",
         "その品目の処方量は公表値からは一切不明。",
         "",
         "全国集計への寄与区間：",
         "  [0, 999 × mL換算係数 × 該当シート数]",
         "",
         "2024年度: 52品目（延べ62行）、上限合計245,754 mL",
         "＝9成分合計の0.105%"],
        "#fdeddc")

    box(ax, 0.03, 0.27, 0.94, 0.27,
        "第3層　品目単位の非掲載（2021年度以前の上位品目足切り）",
        ["第1回:上位30 ／ 第2〜8回:上位100 ／ 第9〜10回:上位500 のみ公開。ランク外の品目は行そのものが存在しない。",
         "未収載品目は必ずランク外 → その総計は当該年度・当該シートの最小公表総計を超えられない（追加仮定なし）：",
         "  上限 = 公表総量 + Σ区分( 未収載品目数 × その区分の最小公表総計 )",
         "例）レボカバスチン2014年度: 公表値の+427%　／　クロモグリク酸Na 2015〜2018年度: +16,000%超",
         "→ 2021年度以前の成分間シェアは確定できない。シェア比較は2022年度以降に限定する。"],
        "#e8e0f0")

    box(ax, 0.03, 0.045, 0.94, 0.16,
        "統合：識別区間（partial identification）",
        ["下限 = 公表値（秘匿セル・総計秘匿・未収載品目をすべて0とみなす）　／　上限 = 第1〜3層の上限をすべて加算",
         "分布仮定・補完を一切用いず、真値が必ず区間内に含まれることのみを保証する。",
         "全国合計の区間幅：2022年度以降 ≤0.11%（結論に影響なし）　⇔　2021年度以前は公表値と同オーダー。"],
        "#e2f0e2")

    for x in (0.255, 0.745):
        ax.annotate("", xy=(x, 0.545), xytext=(x, 0.595),
                    arrowprops=dict(arrowstyle="-|>", color="#444444", lw=1.4))
    ax.annotate("", xy=(0.5, 0.212), xytext=(0.5, 0.262),
                arrowprops=dict(arrowstyle="-|>", color="#444444", lw=1.4))

    fig.tight_layout()
    path = os.path.join(FIG_DIR, "SupplFig_missingness_schema.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"-> {path}")


if __name__ == "__main__":
    mf_forest()
    schema()
