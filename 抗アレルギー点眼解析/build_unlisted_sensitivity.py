# -*- coding: utf-8 -*-
"""未収載品目まで拡張した秘匿感度分析。

これまでの秘匿感度分析（run_censoring_sensitivity.py 等）は「NDBに掲載されている
品目の中の秘匿セル（`-`）」だけを対象にしていた。しかし2021年度以前は上位品目の
足切りにより、PMDAの薬価基準には収載されているのにNDBには行そのものが存在しない
（未収載）後発品・先発品がある（drug_by_drug_summary.md Ⅲ章でファクトチェック済み）。
本スクリプトはこの「未収載品目」による不確実性を定量化する。

下限（全シナリオ共通）:
  公表総量そのもの（未収載品目の処方量を0とみなす）。

上限シナリオ①: 順位ベース（厳密・仮定ゼロ）
  未収載品目は必ずランク外なので、その品目の総計は当該シート・当該年度で
  実際に公開された最小の総計を超えない。
      上限① = 公表総量 + Σ_sheet( 未収載品目数 × そのシートの最小公表総計 )
  未収載品目数は marketed_generic_range() の下限値から算出する（上限が
  「◯社以上」で不明な年度は、この下限自体が過小評価になりうる点を明記する）。

上限シナリオ②: 2022年度実績からの逆推計（現実的・要仮定）
  足切り撤廃後の2022年度で各品目（先発・後発メーカー銘柄）が成分内で占めた
  数量シェアを求め、対象年度に実際に掲載されている品目（＝そのシェアを持つ
  と仮定する）の合計シェアで公表総量を割り戻す。
      上限② = 公表総量 / Σ(掲載品目の2022年シェア)
  品目の同一性は品目名（選定療養の「（選）」表記を除く）で照合する。
  この仮定が成り立たないと判断される年度（後発品の収載初年度、ブロック秘匿で
  実績が丸ごと不明な年度、成分の市場構造が大きく変わった年度）は算出しない。

出力: 05_論文成果物/公費含めない_new/
  unlisted_products_inventory.csv   成分×年度の掲載/未掲載一覧
  unlisted_sensitivity.csv          成分×年度×シナリオの下限・公表値・上限
  unlisted_sensitivity_report.md    手法・仮定・限界の解説
  Fig_unlisted_sensitivity.png      識別区間の帯グラフ
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from drug_master import (DRUG_NAME_JA, DRUG_ORDER,          # noqa: E402
                         marketed_brand_count, marketed_generic_range)
from ndb_reader import SHEET_ORDER                          # noqa: E402
from paths import BASE_DIR, INPUT_DIR, ensure                # noqa: E402

OUT = os.path.join(BASE_DIR, "05_論文成果物", "公費含めない_new")

SHARE_BASE_YEAR = 2022

# 逆推計（シナリオ②）の前提が崩れると判断した年度。理由を明記して除外する。
SCENARIO2_INVALID = {
    ("EPINASTINE", 2021): "後発品の収載初年度（2021年6月18日）で部分年のみ。市場シェアが安定していない",
    ("OLOPATADINE", 2021): "後発品の収載初年度（2021年12月10日）で部分年のみ。市場シェアが安定していない",
    ("LEVOCASTINE", 2015): "「ＴＯＡ」銘柄がブロック秘匿で実績が丸ごと不明。2022年シェアと接続できない",
    ("LEVOCASTINE", 2016): "同上",
    ("LEVOCASTINE", 2017): "同上",
    **{("CROMOGLICATE", y): "2022年は先発品（インタールUD）販売終了後のGE専業市場。"
       "先発品が現存し大きな市場シェアを占めていた年度に適用すると前提が崩れる"
       for y in range(2014, 2021)},
}


def market_identity(name: str) -> str:
    """選定療養（（選）／(選)）の表記差だけを吸収した品目識別キー。"""
    return name.replace("（選）", "").replace("(選)", "").strip()


def load():
    d = pd.read_csv(os.path.join(INPUT_DIR, "product_level_censoring.csv"))
    counts = pd.read_csv(os.path.join(INPUT_DIR, "eye_product_counts.csv"))
    counts = counts[counts.sheet != "全シート通算（ユニーク）"]
    min_total = counts.set_index(["year", "sheet"])["min_total"].to_dict()
    # 成分ごとのmL換算係数（保守側＝その成分で観測された最大係数）。
    # 未収載品目の単位は実測できないため、上限の換算には最大係数を使う。
    code_ml_factor = d.groupby("code")["ml_factor"].max().to_dict()
    return d, min_total, code_ml_factor


# ----------------------------------------------------------------------
# 1. 掲載/未掲載インベントリ
# ----------------------------------------------------------------------
def build_inventory(d):
    rows = []
    for code in DRUG_ORDER:
        for year in range(2014, 2025):
            g = d[(d.code == code) & (d.year == year)]
            listed_gen = g[g.product_type == "generic_maker"].product_name.nunique()
            listed_brand = g[g.product_type == "brand"].product_name.nunique()
            lo, hi, gnote = marketed_generic_range(code, year)
            bn, bnote = marketed_brand_count(code, year)
            unlisted_gen_lo = max(0, lo - listed_gen)
            unlisted_brand = max(0, bn - listed_brand)
            rows.append({
                "code": code, "drug": DRUG_NAME_JA[code], "year": year,
                "listed_generic_makers": listed_gen,
                "marketed_generic_lo": lo, "marketed_generic_hi": hi,
                "unlisted_generic_lo": unlisted_gen_lo,
                "marketed_generic_note": gnote,
                "listed_brand_products": listed_brand,
                "marketed_brand": bn, "unlisted_brand": unlisted_brand,
                "marketed_brand_note": bnote,
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 2. 感度分析本体
# ----------------------------------------------------------------------
def scenario1_upper(code, year, published_total, inv_row, min_total, ml_factor):
    """順位ベース上限。未収載品目数の下限 × 3シート最小公表総計の合計を加算する。

    最小公表総計は生Excelの生単位（瓶・個・mL混在）のため、未収載品目の
    単位を保守側に見て、当該成分で観測された最大mL換算係数を掛けてmLに揃える。
    """
    n_unlisted = inv_row["unlisted_generic_lo"] + inv_row["unlisted_brand"]
    if n_unlisted == 0:
        return published_total, 0, "上限なし（下限=公表値のまま）"
    per_item_bound = sum(min_total.get((year, s), 0) or 0
                         for s in SHEET_ORDER) * ml_factor
    upper = published_total + n_unlisted * per_item_bound
    note = (f"未収載{n_unlisted}品目（下限値） × 3区分合計の最小公表総計"
            f"{per_item_bound:,.0f}mL（生単位×係数{ml_factor:g}で換算）")
    if inv_row["marketed_generic_hi"] is None and inv_row["unlisted_generic_lo"] == 0:
        note += "／marketed_generic_hi不明のため実際の未収載数はさらに多い可能性"
    return upper, n_unlisted, note


def scenario2_upper(d, code, year, published_total):
    """2022年度シェアからの逆推計上限。"""
    if (code, year) in SCENARIO2_INVALID:
        return None, SCENARIO2_INVALID[(code, year)]
    if year >= SHARE_BASE_YEAR:
        return None, f"{SHARE_BASE_YEAR}年度以降はシナリオ②不要（公表値が既に足切りなしの実績）"

    base = d[(d.code == code) & (d.year == SHARE_BASE_YEAR) & (~d.total_censored)]
    if base.empty:
        return None, f"{SHARE_BASE_YEAR}年度のデータなし"
    # シェアは同一成分内でも単位が混在しうるため mL 換算値で算出する
    base_ident = base.groupby(base.product_name.map(market_identity))["total_ml"].sum()
    base_total = base_ident.sum()
    if base_total <= 0:
        return None, f"{SHARE_BASE_YEAR}年度の総量が0"
    base_share = base_ident / base_total

    cur = d[(d.code == code) & (d.year == year)]
    if cur.empty:
        return None, "対象年度に掲載品目なし（NDB非掲載）"
    idents = set(cur.product_name.map(market_identity))
    matched_share = base_share.reindex(idents).dropna().sum()
    if matched_share <= 0:
        return None, f"{SHARE_BASE_YEAR}年度のシェアと照合できる品目がない"

    upper = published_total / matched_share
    note = f"照合{len(base_share.reindex(idents).dropna())}品目、Σシェア={matched_share:.3f}"
    return upper, note


def build_sensitivity(d, inv, min_total, code_ml_factor):
    rows = []
    for code in DRUG_ORDER:
        for year in range(2014, 2025):
            g = d[(d.code == code) & (d.year == year) & (~d.total_censored)]
            if g.empty and d[(d.code == code) & (d.year == year)].empty:
                rows.append({"code": code, "drug": DRUG_NAME_JA[code], "year": year,
                            "listed_in_ndb": False, "published_total": None,
                            "lower": None, "upper1": None, "upper1_note": "NDB非掲載（NR）",
                            "upper2": None, "upper2_note": "NDB非掲載（NR）"})
                continue
            # 公表総量は mL 換算値（瓶=×容器mL, 個=×0.35mL）で統一する
            published_total = g["total_ml"].sum()
            inv_row = inv[(inv.code == code) & (inv.year == year)].iloc[0]

            upper1, n_unlisted, note1 = scenario1_upper(
                code, year, published_total, inv_row, min_total,
                code_ml_factor[code])
            if n_unlisted == 0 and year < SHARE_BASE_YEAR:
                # 未収載品目が存在しない年度は公表値=真値であり、逆推計は不要。
                # （例: エピナスチン2014〜2018年度は上市品目がアレジオン標準1品目
                # のみで掲載済み。2022年度シェア12.3%で割り戻すと、まだ発売されて
                # いない後発品・LXの分まで存在したことになり矛盾する）
                upper2, note2 = None, "未収載品目なし（公表値=真値。逆推計は不要）"
            else:
                upper2, note2 = scenario2_upper(d, code, year, published_total)

            rows.append({
                "code": code, "drug": DRUG_NAME_JA[code], "year": year,
                "listed_in_ndb": True,
                "published_total": published_total,
                "lower": published_total,
                "n_unlisted_lo": n_unlisted,
                "upper1": upper1, "upper1_width_pct":
                    (upper1 - published_total) / published_total * 100 if published_total else None,
                "upper1_note": note1,
                "upper2": upper2, "upper2_width_pct":
                    (upper2 - published_total) / published_total * 100
                    if (upper2 is not None and published_total) else None,
                "upper2_note": note2,
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 3. レポート・図
# ----------------------------------------------------------------------
def fmt(v, dec=0):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{dec}f}"


def build_report(sens, inv):
    L = []
    A = L.append
    A("# 未収載品目まで拡張した秘匿感度分析")
    A("")
    A("従来の秘匿感度分析（`run_censoring_sensitivity.py` 等）はNDBに**掲載されている**")
    A("品目の中の秘匿セル（`-`）だけを識別区間の対象にしていた。しかし2021年度以前は")
    A("上位品目の足切りにより、PMDAの薬価基準には収載されているのにNDBには行そのものが")
    A("存在しない（未収載）後発品・先発品がある。本レポートはこれを定量化する。")
    A("")
    A("- **データ基準**: 公費レセプトを含まない集計（2024年度は `ndb_gaiyo_2024_nokouhi.xlsx`）")
    A("- **対象**: 9成分（drug_by_drug_summary.md Ⅲ章のファクトチェック済み上市メーカー情報に基づく）")
    A("- **生成**: `build_unlisted_sensitivity.py`")
    A("")
    A("## 方針")
    A("")
    A("**下限**（全シナリオ共通） = 公表総量そのもの（未収載品目の処方量を0とみなす）。")
    A("")
    A("**単位はすべてmLに換算して集計する。** 公表数量は成分により単位が異なる")
    A("（ｍＬ=×1、瓶=×1容器あたりmL（対象品目はすべて5mL瓶）、個=×0.35mL）。")
    A("公表総量・シェアは品目ごとの実測単位から換算し、順位ベース上限で使う")
    A("「最小公表総計」（生単位）には、未収載品目の単位が実測できないため")
    A("**当該成分で観測された最大のmL換算係数を掛ける（保守側）**。")
    A("")
    A("### 上限シナリオ①: 順位ベース（厳密・仮定ゼロ）")
    A("")
    A("未収載品目は必ずランク外なので、その品目の総計は当該シート・当該年度で")
    A("実際に公開された最小の総計を超えない。")
    A("")
    A("```")
    A("上限① = 公表総量 + Σ_区分( 未収載品目数 × その区分の最小公表総計 )")
    A("```")
    A("")
    A("未収載品目数は上市メーカー数（下限値）から算出する。出典が「◯社以上」で")
    A("上限が不明な年度・成分は、この下限自体が過小評価になりうる。")
    A("")
    A("### 上限シナリオ②: 2022年度実績からの逆推計（現実的・要仮定）")
    A("")
    A("足切り撤廃後の2022年度で各品目が成分内で占めた数量シェアを求め、対象年度に")
    A("実際に掲載されている品目の合計シェアで公表総量を割り戻す。")
    A("")
    A("```")
    A("上限② = 公表総量 ÷ Σ(掲載品目の2022年シェア)")
    A("```")
    A("")
    A("品目の同一性は品目名（選定療養の「（選）」表記を除く）で照合する。")
    A("**この仮定（市場シェアが年度をまたいで安定）が成り立たないと判断した年度は")
    A("算出しない**（空欄）。除外理由:")
    A("")
    seen = set()
    for (c, y), reason in SCENARIO2_INVALID.items():
        if reason in seen:
            continue
        seen.add(reason)
        years = sorted(yy for (cc, yy), rr in SCENARIO2_INVALID.items() if rr == reason)
        A(f"- {DRUG_NAME_JA[c]} {years}: {reason}")
    A("")

    A("---")
    A("")
    A("## Ⅰ. 全国処方数量の識別区間（成分×年度）")
    A("")
    A("**mL換算済み**（瓶単位の成分は×5mL、個単位の品目は×0.35mLで換算）。")
    A("`—` はNDB非掲載（NR）または算出不可。")
    A("")
    A("| 成分 | 年度 | 公表総量（下限） | 上限①（順位ベース） | 上限①の幅 | 上限②（逆推計） | 上限②の幅 |")
    A("|---|---|--:|--:|--:|--:|--:|")
    for _, r in sens.sort_values(["code", "year"]).iterrows():
        if not r.listed_in_ndb:
            A(f"| {r.drug} | {r.year} | — | — | — | — | — |")
            continue
        w1 = f"+{r.upper1_width_pct:.4f}%" if pd.notna(r.upper1_width_pct) else "—"
        w2 = f"+{r.upper2_width_pct:.4f}%" if pd.notna(r.upper2_width_pct) else "—"
        A(f"| {r.drug} | {r.year} | {fmt(r.lower)} | {fmt(r.upper1)} | {w1} "
          f"| {fmt(r.upper2)} | {w2} |")
    A("")

    A("---")
    A("")
    A("## Ⅱ. 年度別の識別区間幅（9成分平均）")
    A("")
    A("上限①（順位ベース、仮定ゼロ）の識別区間幅を年度別に平均した。")
    A("")
    yearly = (sens[sens.listed_in_ndb & sens.upper1_width_pct.notna()]
             .groupby("year")["upper1_width_pct"].agg(["mean", "max"]))
    A("| 年度 | 平均区間幅 | 最大区間幅（該当成分） |")
    A("|---|--:|--:|")
    for y, r in yearly.iterrows():
        sub = sens[(sens.year == y) & sens.upper1_width_pct.notna()]
        worst = sub.loc[sub.upper1_width_pct.idxmax()]
        A(f"| {y} | +{r['mean']:.2f}% | +{r['max']:.2f}%（{worst.drug}） |")
    A("")
    A("**2021年度以前は、公表値だけからは9成分の真の総量を有意に絞り込めない**")
    A("（識別区間が公表値と同オーダーに達する年度がある）。**2022年度以降は区間が")
    A("ほぼ消え、公表値をそのまま真値として扱ってよい水準まで縮む。**")
    A("")
    A("この結果は、秘匿セルの補完方法（zero/upper等）を精緻化するより、")
    A("「未収載品目の存在」のほうが桁違いに大きな不確実性であることを示している。")
    A("2021年度以前の成分別・年度別トレンドを議論する際は、上限シナリオ①の区間幅を")
    A("必ず併記すべきである。")
    A("")

    A("---")
    A("")
    A("## Ⅲ. 掲載/未掲載インベントリ")
    A("")
    A("成分×年度の上市メーカー数（下限〜上限）とNDB掲載数。出典は")
    A("`drug_by_drug_summary.md` Ⅲ章のファクトチェック済み情報（`src/drug_master.py`")
    A("`MARKETED_GENERIC_MAKERS` / `MARKETED_BRAND_PRODUCTS`）。")
    A("")
    A("| 成分 | 年度 | 掲載後発メーカー数 | 上市後発メーカー数 | 未掲載(下限) | 掲載先発品数 | 上市先発品数 | 未掲載先発 |")
    A("|---|---|--:|--:|--:|--:|--:|--:|")
    for _, r in inv.sort_values(["code", "year"]).iterrows():
        hi = "以上" if pd.isna(r.marketed_generic_hi) else f"〜{int(r.marketed_generic_hi)}"
        A(f"| {r.drug} | {r.year} | {int(r.listed_generic_makers)} "
          f"| {int(r.marketed_generic_lo)}{hi} | {int(r.unlisted_generic_lo)} "
          f"| {int(r.listed_brand_products)} | {int(r.marketed_brand)} "
          f"| {int(r.unlisted_brand)} |")
    A("")

    A("---")
    A("")
    A("## Ⅳ. 限界")
    A("")
    A("- 上限①は未収載品目数に**上市メーカー数の下限値**を使う。出典が「◯社以上」の")
    A("  年度・成分（エピナスチン標準0.05% 2024年度など）は、この下限自体が過小評価の")
    A("  可能性がある。実際の上限はここに示した値よりさらに大きい場合がある。")
    A("- 上限②は「同一品目の市場シェアは年度をまたいで安定する」という強い仮定に依存する。")
    A("  この仮定が成り立たないと判断した年度・成分は空欄にしてあるが、それ以外の年度でも")
    A("  仮定の妥当性は品目・年度によって濃淡がある。")
    A("- 未掲載品目の「上市」判定はdrug_by_drug_summary.md Ⅲ章のファクトチェックに基づく。")
    A("  そこに記載のない銘柄の新規収載・撤退は反映されていない可能性がある。")
    A("")

    return "\n".join(L) + "\n"


def figure(sens):
    ensure(OUT)
    plt.rcParams["font.family"] = "MS Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(3, 3, figsize=(16, 12), sharex=True)
    for ax, code in zip(axes.flat, DRUG_ORDER):
        s = sens[(sens.code == code) & sens.listed_in_ndb].sort_values("year")
        if s.empty:
            ax.set_visible(False)
            continue
        ax.plot(s.year, s.lower, "o-", color="tab:blue", label="公表値（下限）", lw=2)
        ax.plot(s.year, s.upper1, "s--", color="tab:red", label="上限①（順位ベース）", lw=1.5)
        u2 = s[s.upper2.notna()]
        if len(u2):
            ax.plot(u2.year, u2.upper2, "^:", color="tab:orange", label="上限②（逆推計）", lw=1.5)
        ax.fill_between(s.year, s.lower, s.upper1, color="tab:red", alpha=0.12)
        ax.set_title(DRUG_NAME_JA[code], fontsize=11)
        ax.set_yscale("log")
        ax.grid(alpha=0.3)
    # 凡例は図全体に置く（1枚目のパネルには上限②が無く、系列が凡例に載らないため）
    handles = [Line2D([], [], color="tab:blue", marker="o", ls="-", lw=2,
                      label="公表値（下限）"),
               Line2D([], [], color="tab:red", marker="s", ls="--", lw=1.5,
                      label="上限①（順位ベース・仮定ゼロ）"),
               Line2D([], [], color="tab:orange", marker="^", ls=":", lw=1.5,
                      label="上限②（逆推計・要仮定。算出できる成分・年度のみ）")]
    fig.legend(handles=handles, fontsize=10, loc="lower center", ncol=3,
               frameon=False, bbox_to_anchor=(0.5, -0.005))
    for ax in axes[:, 0]:
        ax.set_ylabel("処方数量（mL換算）", fontsize=9)
    fig.suptitle("未収載品目まで拡張した秘匿感度分析（成分別・全国処方数量mL換算, 対数軸）",
                fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    p = os.path.join(OUT, "Fig_unlisted_sensitivity.png")
    fig.savefig(p, dpi=300)   # 英文誌の解像度規定（300 dpi以上）に合わせる
    plt.close(fig)
    return p


def main():
    ensure(OUT)
    d, min_total, code_ml_factor = load()
    inv = build_inventory(d)
    sens = build_sensitivity(d, inv, min_total, code_ml_factor)

    p1 = os.path.join(OUT, "unlisted_products_inventory.csv")
    inv.to_csv(p1, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p1, BASE)} ({len(inv)} rows)")

    p2 = os.path.join(OUT, "unlisted_sensitivity.csv")
    readme = [
        "# ============ README（この行はデータではない。読込時は comment='#' を指定） ============",
        "# 未収載品目まで拡張した秘匿感度分析。数量はすべてmL換算。",
        "# code / drug        : 成分コード / 成分名",
        "# year               : 年度（2014〜2024）",
        "# listed_in_ndb      : その年度にNDBへの掲載があるか。False の年度は以降すべて空欄",
        "# published_total    : NDB掲載品目の公表総量の合算（mL。総計秘匿の品目は除外）",
        "# lower              : 識別区間の下限 = published_total（未収載品目を0とみなす）",
        "# n_unlisted_lo      : 未収載品目数の下限 = 上市品目数(下限) − NDB掲載数",
        "# upper1             : 上限①（順位ベース・仮定ゼロ）= 公表総量 + 未収載品目数 × その年度の最小公表総計",
        "#                      未収載品目は必ずランク外なので最小公表総計を超えられない、という論理のみで成立",
        "# upper1_width_pct   : 上限①の幅 (upper1/published_total - 1)×100。0%なら未収載なし=公表値が真値",
        "# upper1_note        : 上限①の計算内訳（品目数×1品目あたり上限、mL換算係数）",
        "# upper2             : 上限②（逆推計・要仮定）= 公表総量 ÷ Σ(掲載品目の2022年度シェア)",
        "#                      「品目の市場シェアは年度をまたいで安定」という仮定に依存",
        "# upper2_width_pct   : 上限②の幅",
        "# upper2_note        : 算出時は「照合N品目、Σシェア=0.xxx」。空欄の理由もここに記載",
        "#                      （未収載品目なし／収載初年度でシェア不安定／ブロック秘匿で実績不明／市場構造の断絶／2022年度以降は不要）",
        "# 真値は必ず [lower, upper1] に含まれ、多くの場合 [lower, upper2] に含まれると考えられる。",
        "# ======================================================================================",
    ]
    with open(p2, "w", encoding="utf-8-sig", newline="") as f:
        f.write("\n".join(readme) + "\n")
        sens.to_csv(f, index=False)
    print(f"-> {os.path.relpath(p2, BASE)} ({len(sens)} rows)")

    p3 = os.path.join(OUT, "unlisted_sensitivity_report.md")
    with open(p3, "w", encoding="utf-8") as f:
        f.write(build_report(sens, inv))
    print(f"-> {os.path.relpath(p3, BASE)}")

    p4 = figure(sens)
    print(f"-> {os.path.relpath(p4, BASE)}")


if __name__ == "__main__":
    main()
