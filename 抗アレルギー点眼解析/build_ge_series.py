# -*- coding: utf-8 -*-
"""後発品（GE）比率の年次系列を、解釈可能性の4分類つきで構築する。

問題の所在:
  NDBオープンデータは第8回（2021年度）まで薬効分類ごとに上位品目しか公開せず、
  処方量の小さい後発品銘柄は品目ごと非掲載だった。このため公表値から算出した
  GE比率は、成分によって意味がまったく異なる。

    - エピナスチン・オロパタジン … 後発品の初収載が2021年度。それ以前の0%は真値
    - レボカバスチン・ケトチフェン・クロモグリク酸Na・トラニラスト・ペミロラスト
      … 後発品は2014年より前から収載済み。それ以前の低いGE比率は足切りの産物
    - イブジラスト・アシタザノラスト … 後発品が存在せず、0%は常に真値

  この違いを無視して一律に経年比較すると、2021→2022のGE比率の急上昇を
  「後発品置換の進行」と誤読する。実際には第9回（2022年度）での足切り撤廃が主因。

分類:
  A 真値0%（後発品が未収載）
  B 算出不能（後発品は収載済みだが足切りで非掲載）
  C 比較不能（後発品の収載初年度・部分年のみ）
  D 信頼可（2022年度以降、足切り撤廃後）

出力:
  03_解析結果/後発品_剤形/ge_share_annotated.csv   成分×年度のGE比率＋4分類
  03_解析結果/後発品_剤形/ge_maker_counts.csv      成分×年度の後発品銘柄数の内訳
  03_解析結果/後発品_剤形/ge_share_report.md       解説つきレポート
  04_図表/plots/ge_share_annotated.png             D区分のみ実線で描いた図
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from drug_master import (DRUG_NAME_JA, DRUG_ORDER,  # noqa: E402
                         GE_CLASS_LABEL, GE_CLASS_NOTE, GE_FIRST_LISTING,
                         UNCAPPED_FROM_YEAR, ge_class, ge_usable)
from ndb_reader import CENSOR_THRESHOLD  # noqa: E402
from paths import FIGURE_DIR, INPUT_DIR, RESULT_GE, ensure  # noqa: E402

plt.rcParams["font.family"] = "MS Gothic"
plt.rcParams["axes.unicode_minus"] = False


def build():
    d = pd.read_csv(os.path.join(INPUT_DIR, "product_level_censoring.csv"))
    # 数量は公表「総計」列を3シート合算。総計が秘匿の品目は数量不明のため
    # 分子・分母に算入できない（各品目 <1,000 なので上限は行数×999）。
    known = d[~d.total_censored]

    rows = []
    for code in DRUG_ORDER:
        for year in sorted(d.year.unique()):
            g = known[(known.code == code) & (known.year == year)]
            present = not d[(d.code == code) & (d.year == year)].empty
            gen = g[g.product_type.str.startswith("generic")]
            brand = g[g.product_type == "brand"]
            q_gen, q_brand = gen["total"].sum(), brand["total"].sum()
            total = q_gen + q_brand
            cls = ge_class(code, year)
            dropped = d[(d.code == code) & (d.year == year) & d.total_censored]
            rows.append({
                "year": year,
                "code": code,
                "drug": DRUG_NAME_JA[code],
                "listed_in_ndb": present,
                "ge_class": cls,
                "ge_class_label": GE_CLASS_LABEL[cls],
                "usable": present and ge_usable(cls),
                "quantity_brand": q_brand,
                "quantity_generic": q_gen,
                "quantity_total": total,
                # 生の計算値。B/C区分では実態を表さないため参考値扱い。
                "ge_share_pct_raw": round(q_gen / total * 100, 2) if total else None,
                # 提示・比較に使ってよい値のみ入る列。
                "ge_share_pct": (round(q_gen / total * 100, 2)
                                 if total and present and ge_usable(cls) else None),
                "n_generic_maker": int((gen.product_type == "generic_maker")
                                       .sum()) if len(gen) else 0,
                "has_generic_unified": bool((gen.product_type == "generic_unified").any()),
                "n_products_dropped_total_censored": len(dropped),
                "dropped_quantity_upper_bound": len(dropped) * (CENSOR_THRESHOLD - 1),
            })
    return pd.DataFrame(rows)


def maker_counts():
    """成分×年度の後発品銘柄数。統一名収載品はメーカー社数に数えない。"""
    d = pd.read_csv(os.path.join(INPUT_DIR, "product_level_censoring.csv"))
    rows = []
    for code in DRUG_ORDER:
        for year in sorted(d.year.unique()):
            g = d[(d.code == code) & (d.year == year)]
            if g.empty:
                continue
            gm = g[g.product_type == "generic_maker"]["product_name"].nunique()
            gu = g[g.product_type == "generic_unified"]["product_name"].nunique()
            br = g[g.product_type == "brand"]["product_name"].nunique()
            rows.append({
                "year": year, "code": code, "drug": DRUG_NAME_JA[code],
                "n_brand_products": br,
                "n_generic_maker_brands": gm,
                "n_generic_unified_products": gu,
                # 旧 drug_by_drug_summary.md は統一名収載品を1社として
                # 社数に加算していた。統一名は銘柄不特定の集計行であり、
                # メーカー社数には数えない。
                "n_generic_makers_reported": gm,
            })
    return pd.DataFrame(rows)


def _runs(sub, all_years):
    """連続した年度のまとまりごとに分割して返す（線を途切れさせるため）。

    all_years は当該成分が掲載されている全年度。ここに含まれる年度が
    sub から欠けていれば、そこで系列を切る。
    """
    yrs = sorted(sub.year.tolist())
    if not yrs:
        return []
    order = {y: i for i, y in enumerate(sorted(all_years))}
    out, cur = [], [yrs[0]]
    for prev, y in zip(yrs, yrs[1:]):
        if order[y] - order[prev] == 1:
            cur.append(y)
        else:
            out.append(cur)
            cur = [y]
    out.append(cur)
    return [(i, sub[sub.year.isin(g)].sort_values("year"))
            for i, g in enumerate(out)]


def figure(df):
    ensure(os.path.join(FIGURE_DIR, "plots"))
    focus = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE", "KETOTIFEN",
             "CROMOGLICATE", "TRANILAST", "PEMIROLAST"]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    cmap = plt.get_cmap("tab10")
    for i, code in enumerate(focus):
        s = df[(df.code == code) & df.listed_in_ndb].sort_values("year")
        if s.empty:
            continue
        col = cmap(i)
        # 使える区分（A/D）は実線。ただし途中に使えない年度が挟まる場合は
        # 線をつながず区切る（2021年度を跨いで実線を引くと、比較不能な年を
        # 飛び越えて連続的に推移したように見えてしまうため）。
        first = True
        for _, run in _runs(s[s.usable], s.year.tolist()):
            ax.plot(run.year, run.ge_share_pct_raw, "o-", color=col, lw=2.2,
                    label=DRUG_NAME_JA[code] if first else None)
            first = False
        # B/C区分（算出不能・比較不能）は破線＋中抜きで「使えない値」と示す
        for _, run in _runs(s[~s.usable], s.year.tolist()):
            ax.plot(run.year, run.ge_share_pct_raw, "o--", color=col, lw=1.0,
                    mfc="white", alpha=0.55)

    ax.axvline(UNCAPPED_FROM_YEAR - 0.5, color="crimson", ls=":", lw=2)
    ax.annotate("第9回NDB\n上位品目の足切り撤廃",
                xy=(UNCAPPED_FROM_YEAR - 0.5, 96), xytext=(2018.6, 88),
                color="crimson", fontsize=10,
                arrowprops=dict(arrowstyle="->", color="crimson"))
    ax.axvspan(df.year.min() - 0.5, UNCAPPED_FROM_YEAR - 0.5,
               color="0.85", alpha=0.35, zorder=0)
    ax.text(2017.5, 4, "上位品目の足切り期間\n（破線＝実態を表さない値）",
            fontsize=9.5, color="0.35", ha="center")

    ax.set_xlabel("年度")
    ax.set_ylabel("後発品比率（処方数量ベース, %）")
    ax.set_title("抗アレルギー点眼薬の後発品比率\n"
                 "実線＝経年比較に使える区分（A: 真値0% / D: 足切り撤廃後）、"
                 "破線＝算出不能・比較不能", fontsize=12, fontweight="bold")
    ax.set_ylim(-3, 103)
    ax.set_xticks(sorted(df.year.unique()))
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9, ncol=2, loc="upper left")
    fig.tight_layout()
    p = os.path.join(FIGURE_DIR, "plots", "ge_share_annotated.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def report(df, mk):
    L = []
    A = L.append
    A("# 後発品比率の年次系列と解釈可能性")
    A("")
    A("- **データ基準**: 公費レセプトを含まない集計（2024年度は `ndb_gaiyo_2024_nokouhi.xlsx`）")
    A("- **数量**: 公表「総計」列を外来（院外）・外来（院内）・入院の3区分で合算")
    A("- **後発品**: 先発品名で始まらない品目。メーカー銘柄（「○○」付き）と統一名収載品を含む")
    A("")
    A("## なぜ年度に注釈が要るのか")
    A("")
    A("NDBオープンデータは第8回（2021年度）まで薬効分類ごとに上位品目しか公開せず、")
    A("処方量の小さい後発品銘柄は品目ごと非掲載だった。第9回（2022年度）で足切りが")
    A("撤廃された結果、眼科用剤（薬効分類131）の公開品目数は154 → 522に急増している。")
    A("")
    A("したがって公表値から算出したGE比率は、成分によって意味がまったく異なる。")
    A("**2021→2022のGE比率の急上昇は、大半が公開仕様の変更であって後発品置換の進行ではない。**")
    A("")
    A("## 解釈可能性の4分類")
    A("")
    A("| 区分 | 定義 | 経年比較 |")
    A("|---|---|---|")
    for k in ["A", "B", "C", "D"]:
        A(f"| **{k}** | {GE_CLASS_LABEL[k]} | {'使える' if ge_usable(k) else '**使えない**'} |")
    A("")
    for k in ["A", "B", "C", "D"]:
        A(f"- **{k}**: {GE_CLASS_NOTE[k]}")
    A("")
    A("### 成分ごとの後発品初収載")
    A("")
    A("| 成分 | 後発品の初収載 | 足切り期（〜2021年度）の扱い |")
    A("|---|---|---|")
    for code in DRUG_ORDER:
        first, note = GE_FIRST_LISTING[code]
        if first == "none":
            tr = "全年度A（後発品なし。0%は真値）"
        elif first is None or first < 2014:
            tr = "全年度B（解析期間前から後発品が流通。算出不能）"
        elif first >= 2014:
            tr = f"{first}年度未満はA、{first}年度はC、以降はB"
        A(f"| {DRUG_NAME_JA[code]} | {note} | {tr} |")
    A("")
    A("---")
    A("")
    A("## Ⅰ. 年度別の解釈可能性マトリクス")
    A("")
    A("`—` はNDB非掲載（NR）。")
    A("")
    years = sorted(df.year.unique())
    A("| 成分 | " + " | ".join(str(y) for y in years) + " |")
    A("|---" * (len(years) + 1) + "|")
    for code in DRUG_ORDER:
        cells = []
        for y in years:
            r = df[(df.code == code) & (df.year == y)].iloc[0]
            cells.append("—" if not r.listed_in_ndb else r.ge_class)
        A(f"| {DRUG_NAME_JA[code]} | " + " | ".join(cells) + " |")
    A("")
    A("---")
    A("")
    A("## Ⅱ. 提示可能な後発品比率（A・D区分のみ）")
    A("")
    A("**この表の数値のみが経年比較に使える。** B・C区分は空欄とした。")
    A("")
    A("| 成分 | " + " | ".join(str(y) for y in years) + " |")
    A("|---" * (len(years) + 1) + "|")
    for code in DRUG_ORDER:
        cells = []
        for y in years:
            r = df[(df.code == code) & (df.year == y)].iloc[0]
            cells.append("—" if pd.isna(r.ge_share_pct) else f"{r.ge_share_pct:.1f}%")
        A(f"| {DRUG_NAME_JA[code]} | " + " | ".join(cells) + " |")
    A("")
    A(f"**経年比較は{UNCAPPED_FROM_YEAR}年度以降に限定すること。** ")
    A("A区分（後発品未収載の0%）はそれ以前の年度にも数値が入るが、これは")
    A("「後発品が存在しない」ことの確認であり、比率の推移としては0%が続くだけである。")
    A("")
    A("---")
    A("")
    A("## Ⅲ. 参考：生の計算値（B・C区分を含む）")
    A("")
    A("**B・C区分の値は実態を表さない。** 旧版の系列がなぜ誤読を招いたかを示すために掲載する。")
    A("")
    A("| 成分 | " + " | ".join(str(y) for y in years) + " |")
    A("|---" * (len(years) + 1) + "|")
    for code in DRUG_ORDER:
        cells = []
        for y in years:
            r = df[(df.code == code) & (df.year == y)].iloc[0]
            if not r.listed_in_ndb or pd.isna(r.ge_share_pct_raw):
                cells.append("—")
            elif r.usable:
                cells.append(f"{r.ge_share_pct_raw:.1f}%")
            else:
                cells.append(f"_{r.ge_share_pct_raw:.1f}%_ ({r.ge_class})")
        A(f"| {DRUG_NAME_JA[code]} | " + " | ".join(cells) + " |")
    A("")
    A("### 誤読しやすい代表例")
    A("")
    lv = df[(df.code == "LEVOCASTINE")].set_index("year")
    A("**レボカバスチン**（後発品は2008年収載済み）")
    A("")
    A("| 年度 | 生の計算値 | 区分 | 実際に起きていること |")
    A("|---|--:|---|---|")
    for y, why in [(2014, "後発品は6年前から流通しているが、上位30品目の足切りで全社が非掲載"),
                   (2020, "掲載されている後発品は上位3銘柄のみ。残りは非掲載"),
                   (2021, "掲載銘柄が3→2に減っただけ。市場で後発品が減ったわけではない"),
                   (2022, "足切り撤廃で11銘柄すべてが公開された")]:
        if y in lv.index:
            r = lv.loc[y]
            A(f"| {y} | {r.ge_share_pct_raw:.1f}% | {r.ge_class} | {why} |")
    A("")
    A("2020年度56.0% → 2021年度44.6% の低下は市場実態ではなく掲載銘柄数の変動である。")
    A("同様に2014年度の0.0%は「後発品が無い」ことを意味しない。")
    A("")
    A("---")
    A("")
    A("## Ⅳ. 後発品の銘柄数（統一名収載品を分離）")
    A("")
    A("統一名収載品（例: `レボカバスチン塩酸塩０．０２５％１ｍＬ点眼液`）は特定メーカーの")
    A("銘柄ではなく銘柄不特定の集計行である。数量は後発品に算入するが、**メーカー社数には")
    A("数えない**。旧 `drug_by_drug_summary.md` はこれを1社として加算していた。")
    A("")
    A("| 年度 | 成分 | 先発品目数 | 後発メーカー銘柄数 | 統一名収載品 |")
    A("|---|---|--:|--:|---|")
    for _, r in mk.sort_values(["year", "code"]).iterrows():
        if r.n_generic_maker_brands == 0 and r.n_generic_unified_products == 0:
            continue
        A(f"| {r.year} | {r.drug} | {r.n_brand_products} | {r.n_generic_maker_brands} "
          f"| {'あり (1品目)' if r.n_generic_unified_products else 'なし'} |")
    A("")
    A("---")
    A("")
    A("## Ⅴ. 総計秘匿により数量から脱落した品目")
    A("")
    A(f"総計列が「-」の品目（全体が{CENSOR_THRESHOLD:,}未満）は数量が不明なため、")
    A("GE比率の分子・分母どちらにも算入できない。脱落分はすべて小規模な後発品銘柄であり、")
    A("**GE比率をわずかに過小評価する方向**に働く。")
    A("")
    A("| 年度 | 脱落品目数 | 数量の上限（品目数×999） | 当該年度の総数量 | 上限が総量に占める割合 |")
    A("|---|--:|--:|--:|--:|")
    for y in years:
        g = df[df.year == y]
        n = int(g.n_products_dropped_total_censored.sum())
        ub = int(g.dropped_quantity_upper_bound.sum())
        tot = g.quantity_total.sum()
        if n == 0:
            continue
        A(f"| {y} | {n} | {ub:,} | {tot:,.0f} | {ub / tot * 100:.4f}% |")
    A("")
    A("いずれの年度も総量の0.01%未満であり、GE比率への影響は無視できる。")
    A("")
    return "\n".join(L) + "\n"


def main():
    ensure(RESULT_GE)
    df = build()
    mk = maker_counts()

    p1 = os.path.join(RESULT_GE, "ge_share_annotated.csv")
    df.to_csv(p1, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p1, BASE)} ({len(df)} rows)")

    p2 = os.path.join(RESULT_GE, "ge_maker_counts.csv")
    mk.to_csv(p2, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p2, BASE)} ({len(mk)} rows)")

    p3 = os.path.join(RESULT_GE, "ge_share_report.md")
    with open(p3, "w", encoding="utf-8") as f:
        f.write(report(df, mk))
    print(f"-> {os.path.relpath(p3, BASE)}")

    p4 = figure(df)
    print(f"-> {os.path.relpath(p4, BASE)}")


if __name__ == "__main__":
    main()
