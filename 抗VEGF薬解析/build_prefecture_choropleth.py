"""都道府県別の抗VEGF薬処方数量（2024年度）をコロプレス図に描画する。

分母を2通り選べる。

  --denominator total   総人口10万対   （antivegf_fig_plots.xlsx / P08）
  --denominator 65plus  65歳以上10万対（antivegf_fig_methods.xlsx / M02）

塗り分けは率の実測値に対する連続グラデーション（順位と単調に対応）。
右パネルに同一配色の順位バーを並べ、地図と順位を対応させる。
"""

import argparse
import os

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from japanmap import picture, pref_code

plt.rcParams["font.family"] = "MS Gothic"
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "公費含まない", "04_図表")
CMAP = plt.get_cmap("YlOrRd")

# japanmap.picture が塗り分けに使う各県のシード座標（県内の点）。ラベルの基準に流用する。
SEEDS = [
    (0, 0), (15, 15), (52, 6), (57, 9), (54, 19), (52, 9), (52, 19), (52, 24),
    (52, 34), (49, 31), (47, 31), (47, 34), (52, 36), (47, 36), (47, 37),
    (47, 24), (37, 31), (34, 32), (32, 34), (44, 36), (42, 34), (37, 34),
    (42, 39), (37, 39), (34, 43), (32, 39), (29, 39), (29, 41), (27, 39),
    (31, 44), (29, 44), (19, 38), (12, 42), (22, 39), (17, 41), (11, 44),
    (22, 46), (22, 44), (17, 46), (19, 48), (7, 48), (3, 50), (2, 52),
    (7, 54), (8, 49), (9, 54), (5, 59), (54, 56),
]
SCALE = 4  # 地図画像の拡大率（ラベル座標も同じ倍率で拡大する）

# 密集地域は引き出し線で余白に逃がす。値は拡大後ピクセルの絶対座標（県内に収まる県は省略）。
LABEL_POS = {
    # 東北
    "青森県": (2020, 150), "岩手県": (2430, 330), "秋田県": (1950, 330),
    "宮城県": (2440, 720), "山形県": (1870, 700), "福島県": (2410, 930),
    "新潟県": (1650, 880),
    # 関東（太平洋側の余白に縦積み）
    "群馬県": (1790, 1050), "栃木県": (2060, 1060), "埼玉県": (1550, 1170),
    "茨城県": (2570, 1230), "千葉県": (2570, 1400), "東京都": (2570, 1570),
    "神奈川県": (2570, 1740),
    # 北陸・中部
    "富山県": (1370, 1100), "石川県": (1170, 1180), "福井県": (1120, 1330),
    "岐阜県": (1360, 1430), "長野県": (1730, 1300),
    # 中国（日本海側・瀬戸内）
    "鳥取県": (640, 1330), "島根県": (370, 1400), "岡山県": (870, 1250),
    "広島県": (560, 1720), "山口県": (230, 1660),
    # 太平洋側の3段バンド
    "高知県": (680, 1960), "徳島県": (980, 1960), "和歌山県": (1280, 1960),
    "三重県": (1580, 1960), "愛知県": (1860, 1960), "静岡県": (2140, 1960),
    "愛媛県": (540, 2110), "香川県": (900, 2110), "大阪府": (1240, 2110),
    "奈良県": (1580, 2110), "山梨県": (2400, 2010),
    "兵庫県": (880, 2270), "京都府": (1180, 2270), "滋賀県": (1480, 2270),
    # 九州
    "福岡県": (150, 1870), "大分県": (430, 1900), "佐賀県": (-110, 2010),
    "長崎県": (-160, 2130), "熊本県": (-120, 2270), "宮崎県": (540, 2330),
    "鹿児島県": (-40, 2450),
}
XLIM = (-360, 2800)
YLIM = (2560, -60)

# 分母ごとの設定（入力シート・出力名・ラベル・出典脚注）
SPECS = {
    "total": {
        "xlsx": "antivegf_fig_plots.xlsx",
        "sheet": "P08_prefecture_ranking_latest",
        "out": "prefecture_choropleth_latest.png",
        "map_title": "抗VEGF薬 処方数量（総人口10万対）2024年度",
        "axis_label": "総人口10万対 処方数量（本）",
        "source": (
            "分子: NDBオープンデータ第11回（2024年度・公費レセプトを含まない）都道府県別処方数量、秘匿セルは0で補完。\n"
            "分母: 総務省統計局「人口推計」令和6年10月1日現在 都道府県別 年齢3区分別人口（e-Stat statInfId=000040268919）の総人口。"
        ),
    },
    "65plus": {
        "xlsx": "antivegf_fig_methods.xlsx",
        "sheet": "M02_65歳以上分母",
        "out": "prefecture_choropleth_65plus_latest.png",
        "map_title": "抗VEGF薬 処方数量（65歳以上人口10万対）2024年度",
        "axis_label": "65歳以上人口10万対 処方数量（本）",
        "source": (
            "分子: NDBオープンデータ第11回（2024年度・公費レセプトを含まない）都道府県別処方数量、秘匿セルは0で補完。\n"
            "分母: 総務省統計局「人口推計」令和6年10月1日現在 都道府県別 年齢3区分別人口（e-Stat statInfId=000040268919）の65歳以上人口。\n"
            "※都道府県×年齢のクロス表が非公表のため真の年齢調整率ではなく、65歳以上人口内部の年齢構成差は補正されていない。"
        ),
    },
}


def load_total(path, sheet):
    df = pd.read_excel(path, sheet_name=sheet, skiprows=2)
    df.columns = ["prefecture", "rate"]
    return df.dropna(subset=["prefecture", "rate"])


def load_65plus(path, sheet):
    """M02 の【2】都道府県別 65歳以上10万対 ブロックから2024年度列を取り出す。"""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr = raw.index[raw[0] == "prefecture"]
    if len(hdr) != 1:
        raise ValueError(f"prefecture 見出し行を一意に特定できない: {list(hdr)}")
    hdr = hdr[0]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = raw.iloc[hdr].tolist()
    df = df[["prefecture", "2024年度_65歳以上10万対"]]
    df.columns = ["prefecture", "rate"]
    return df.dropna(subset=["prefecture", "rate"])


def load(spec):
    path = os.path.join(BASE, spec["xlsx"])
    df = load_65plus(path, spec["sheet"]) if spec["out"].endswith("65plus_latest.png") \
        else load_total(path, spec["sheet"])
    df["rate"] = df["rate"].astype(float)
    df = df.sort_values("rate", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    if len(df) != 47:
        raise ValueError(f"都道府県が47件でない: {len(df)}")
    return df


def draw(df, spec, out_path):
    norm = Normalize(vmin=df["rate"].min(), vmax=df["rate"].max())
    colors = {r.prefecture: tuple(int(c * 255) for c in CMAP(norm(r.rate))[:3])
              for r in df.itertuples()}
    pad = df["rate"].max() * 0.01

    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1], wspace=0.18)

    # 左: 地図
    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(picture(colors))
    ax.axis("off")
    ax.set_title(spec["map_title"], fontsize=15, fontweight="bold", pad=12)

    sm = ScalarMappable(norm=norm, cmap=CMAP)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal",
                      fraction=0.045, pad=0.02, shrink=0.75)
    cb.set_label(spec["axis_label"], fontsize=11)

    # 右: 同一配色の順位バー
    ax2 = fig.add_subplot(gs[0, 1])
    y = np.arange(len(df))
    ax2.barh(y, df["rate"], color=[CMAP(norm(v)) for v in df["rate"]],
             edgecolor="white", linewidth=0.4)
    ax2.set_yticks(y)
    ax2.set_yticklabels([f"{r.rank:2d}. {r.prefecture}" for r in df.itertuples()],
                        fontsize=9)
    ax2.invert_yaxis()
    ax2.set_xlabel(spec["axis_label"], fontsize=11)
    ax2.set_title("都道府県ランキング", fontsize=13, fontweight="bold", pad=12)
    ax2.grid(axis="x", alpha=0.3)
    for s in ("top", "right", "left"):
        ax2.spines[s].set_visible(False)
    ax2.tick_params(axis="y", length=0)
    for r in df.itertuples():
        ax2.text(r.rate + pad, r.rank - 1, f"{r.rate:,.0f}",
                 va="center", fontsize=8, color="#444444")
    ax2.set_xlim(0, df["rate"].max() * 1.12)

    fig.suptitle("抗VEGF薬 処方数量の地域分布（NDBオープンデータ・公費レセプトを含まない）",
                 fontsize=16, fontweight="bold", y=0.97)
    fig.text(0.5, 0.005, spec["source"], ha="center", va="bottom",
             fontsize=9, color="#555555")

    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def draw_labeled(df, spec, out_path):
    """県名・順位・値を地図上に直接表記した版（凡例バーなし）。"""
    norm = Normalize(vmin=df["rate"].min(), vmax=df["rate"].max())
    colors = {r.prefecture: tuple(int(c * 255) for c in CMAP(norm(r.rate))[:3])
              for r in df.itertuples()}
    img = cv2.resize(picture(colors), None, fx=SCALE, fy=SCALE,
                     interpolation=cv2.INTER_NEAREST)

    fig, ax = plt.subplots(figsize=(15, 12.4))
    ax.imshow(img)
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.axis("off")

    for r in df.itertuples():
        sx, sy = SEEDS[pref_code(r.prefecture)]
        x, y = sx * 10 * SCALE, sy * 10 * SCALE
        lx, ly = LABEL_POS.get(r.prefecture, (x, y))
        if (lx, ly) != (x, y):
            ax.plot([x, lx], [y, ly], color="#666666", lw=0.7, zorder=3)
            ax.plot([x], [y], marker="o", ms=2.4, color="#666666", zorder=3)
        ax.text(lx, ly, f"{r.prefecture}\n{r.rank}位 / {r.rate:,.0f}",
                ha="center", va="center", fontsize=9, linespacing=1.3,
                color="#1a1a1a", zorder=4,
                path_effects=[pe.withStroke(linewidth=2.8, foreground="white")])

    ax.set_title(spec["map_title"], fontsize=17, fontweight="bold", pad=14)

    sm = ScalarMappable(norm=norm, cmap=CMAP)
    cb = fig.colorbar(sm, ax=ax, orientation="horizontal",
                      fraction=0.035, pad=0.01, shrink=0.5, anchor=(0.12, 1.0))
    cb.set_label(spec["axis_label"], fontsize=11)

    fig.text(0.5, 0.045, spec["source"], ha="center", va="top",
             fontsize=9, color="#555555")
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--denominator", choices=list(SPECS), default="total")
    p.add_argument("--layout", choices=["rank", "labeled"], default="rank",
                   help="rank=地図+順位バー, labeled=県名を地図に表記")
    args = p.parse_args()

    spec = SPECS[args.denominator]
    df = load(spec)
    name = spec["out"]
    if args.layout == "labeled":
        name = name.replace("latest.png", "labeled.png")
    out_path = os.path.join(BASE, "plots", name)
    (draw_labeled if args.layout == "labeled" else draw)(df, spec, out_path)
    spec = dict(spec, out=name)
    print(f"saved {spec['out']}")
    print(f"  {len(df)} prefectures / {df['rate'].min():,.1f}-{df['rate'].max():,.1f}")
    print(f"  top3: " + " ".join(f"{r.prefecture}{r.rate:,.0f}" for r in df.head(3).itertuples()))


if __name__ == "__main__":
    main()
