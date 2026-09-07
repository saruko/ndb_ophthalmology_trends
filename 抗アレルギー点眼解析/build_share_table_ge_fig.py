# -*- coding: utf-8 -*-
"""原稿 draft v6 で追加した Table 3（成分間シェア 2022〜2024）、Suppl Table S7（都道府県別）、
Suppl Fig S2（後発品比率）を生成する。

Table 3: 旧 Fig 2（Fig4C_top3_share_bounds）を廃止し、Suppl Table S1（成分×年度の識別区間）から
  シェア区間を算出した表に置き換える。
  区間は分子が分母の一部であることを使った sharp な式
  [成分下限/(成分下限+他成分上限), 成分上限/(成分上限+他成分下限)] で算出する
  （build_bounded_outputs.py のGEシェア・build_paper_figures_bounds.py の主要3成分シェア・
  Suppl Table S8 と同一。旧版は [成分下限/9成分上限, 成分上限/9成分下限] で、
  分子と分母が同時に最悪値を取れない事実を使っていない緩い区間だった）。
  出力: 論文図表/csv/Table3_share_2022_2024.csv

Suppl Fig S2: §2.6 の「後発品比率は全期間を図示するが、経年比較・解釈は2022年度以降に限定」に対応。
  A: 成分別の後発品比率 2014〜2024（ge_class D=足切り撤廃後 のみ実線・塗り、A〜C は白抜き）
  B: エピナスチンの製剤別処方量（標準0.05%製剤＋後発品／高濃度LX 0.1%製剤）
  入力: 論文図表/csv/Fig5_ge_formulation_bounds__Fig5B_GE_share_bounds.csv, __Fig5A_epinastine_LX.csv
  出力: 論文図表/SupplFig_GE_share.png
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = ["Meiryo", "Yu Gothic", "MS Gothic"]
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "05_論文成果物", "公費含めない_new")
FIG = os.path.join(OUT, "論文図表")
CSV = os.path.join(FIG, "csv")


def table3_share():
    s1 = pd.read_csv(os.path.join(CSV, "SupplTable_annual_totals_bounds__SupplTable_annual_mL.csv"))
    s1 = s1[s1["Fiscal year"] >= 2022].set_index("Fiscal year")
    cols = ["Top 3 total", "Epinastine", "Olopatadine", "Levocabastine",
            "Antihistamines subtotal", "Mediator release inhibitors subtotal"]
    t_lo, t_hi = s1["All 9 agents_lower"], s1["All 9 agents_upper"]
    out = pd.DataFrame({"Fiscal year": s1.index})
    for c in cols:
        g_lo, g_hi = s1[f"{c}_lower"], s1[f"{c}_upper"]
        o_lo, o_hi = t_lo - g_lo, t_hi - g_hi   # 当該系列以外の8(6)成分の下限・上限
        out[f"{c}_share_lower_pct"] = (g_lo / (g_lo + o_hi) * 100).values
        out[f"{c}_share_upper_pct"] = (g_hi / (g_hi + o_lo) * 100).values
    p = os.path.join(CSV, "Table3_share_2022_2024.csv")
    out.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {p}")
    print(out.round(2).to_string(index=False))
    return out


def suppl_table_s7_prefecture():
    """Suppl Table S7: 2024年度 都道府県別 人口10万対（主要3成分合計・9成分合計）の識別区間と下限基準の順位。"""
    b = pd.read_csv(os.path.join(OUT, "prefecture_per_capita_bounds.csv"))
    b = b[b.year == 2024]
    out = None
    for code, tag in (("TOP3_TOTAL", "Top3"), ("ALLERGY_EYE_TOTAL", "All9")):
        s = b[b.code == code][["prefecture", "per100k_lower", "per100k_upper", "width_pct"]].copy()
        s[f"{tag}_rank_by_lower"] = s.per100k_lower.rank(ascending=False, method="min").astype(int)
        s = s.rename(columns={"per100k_lower": f"{tag}_per100k_lower",
                              "per100k_upper": f"{tag}_per100k_upper",
                              "width_pct": f"{tag}_width_pct"})
        out = s if out is None else out.merge(s, on="prefecture")
    out = out.sort_values("All9_rank_by_lower")
    p = os.path.join(CSV, "SupplTable_S7_prefecture_2024.csv")
    out.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {p}")


def suppl_fig_ge():
    ge = pd.read_csv(os.path.join(CSV, "Fig5_ge_formulation_bounds__Fig5B_GE_share_bounds.csv"))
    lx = pd.read_csv(os.path.join(CSV, "Fig5_ge_formulation_bounds__Fig5A_epinastine_LX.csv"))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8))

    # A. 後発品比率
    ax1.axvspan(2013.5, 2021.5, color="#e0e0e0", alpha=0.6, lw=0, zorder=0)
    ax1.text(2014, 96, "比較不能期間（上位品目の足切りにより\n後発品が非掲載の成分・年度あり）",
             fontsize=7.5, va="top", color="#444444")
    order = ["Epinastine", "Olopatadine", "Levocabastine", "Ketotifen", "Tranilast", "Pemirolast"]
    ja = {"Epinastine": "エピナスチン", "Olopatadine": "オロパタジン", "Levocabastine": "レボカバスチン",
          "Ketotifen": "ケトチフェン", "Tranilast": "トラニラスト", "Pemirolast": "ペミロラスト"}
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    for d, col in zip(order, palette):
        s = ge[ge.drug_en == d].sort_values("Year")
        ok = s[s.ge_class == "D"]
        ng = s[s.ge_class != "D"]
        ax1.plot(ok.Year, ok.share_pct_generic_lower, "o-", color=col, lw=1.8, ms=5, label=ja[d])
        ax1.fill_between(ok.Year, ok.share_pct_generic_lower, ok.share_pct_generic_upper,
                         color=col, alpha=0.25, lw=0)
        ax1.plot(ng.Year, ng.share_pct_generic_lower, "o", mfc="white", mec=col, ms=5, lw=0)
    ax1.axvline(2021.5, color="black", ls="--", lw=1)
    ax1.set_xticks(range(2014, 2025))
    ax1.tick_params(axis="x", labelsize=8)
    ax1.set_ylim(0, 100)
    ax1.set_xlabel("年度")
    ax1.set_ylabel("後発品比率（%、mL基準）")
    ax1.set_title("A. 成分別の後発品比率（塗り＝2022年度以降の識別区間、白抜き＝比較不能年度の見かけの値）",
                  fontsize=9.5, loc="left")
    ax1.grid(alpha=0.3)
    ax1.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False)

    # B. エピナスチンの製剤別
    ax2.plot(lx.Year, lx["Standard+GE_lower"] / 1e6, "o-", color="#1f77b4", lw=1.8, ms=4,
             label="標準0.05%製剤（先発＋後発）")
    ax2.plot(lx.Year, lx["LX_lower"] / 1e6, "s-", color="#17becf", lw=1.8, ms=4,
             label="高濃度0.1%製剤（LX）")
    ax2.axvline(2021.5, color="black", ls="--", lw=1)
    ax2.set_xticks(range(2014, 2025))
    ax2.tick_params(axis="x", labelsize=8)
    ax2.set_ylim(bottom=0)
    ax2.set_xlabel("年度")
    ax2.set_ylabel("処方量（百万mL）")
    ax2.set_title("B. エピナスチンの製剤別処方量（下限=公表値、区間幅は0.02%未満）",
                  fontsize=9.5, loc="left")
    ax2.grid(alpha=0.3)
    ax2.legend(fontsize=8, loc="upper left")

    fig.suptitle("後発品比率と製剤構成の推移 2014〜2024年度（縦破線＝2021→2022年度の公開仕様変更）", fontsize=11)
    fig.tight_layout()
    p = os.path.join(FIG, "SupplFig_GE_share.png")
    fig.savefig(p, dpi=300)
    plt.close(fig)
    print(f"-> {p}")


if __name__ == "__main__":
    table3_share()
    suppl_table_s7_prefecture()
    suppl_fig_ge()
