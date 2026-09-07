# -*- coding: utf-8 -*-
"""秘匿レポート（年齢性別軸）を新規生成する。

  agesex_censoring_report.md   成分×年度×シート区分の秘匿欠落量サマリ（都道府県版と対称構造）
  agesex_censoring_readable.md 品目×年齢階級×性別の秘匿実態（可読形式。全セルを付録として収録）

都道府県軸との違いは対象セルの構成のみ。
  - 2014〜2015年度: 38セル（19年齢階級×男女。90歳以上はまとめて1区分）
  - 2016年度以降　: 42セル（21年齢階級×男女。90〜94/95〜99/100歳以上に細分化）
算出方法・秘匿4分類は都道府県軸と共通（src/censoring_lib.py）。

入力: 01_抽出データ/product_agesex_censoring.csv, product_agesex_long.csv
     （いずれも build_extract.py が生成）
"""
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

import censoring_lib as C                          # noqa: E402
from ndb_reader import CENSOR_THRESHOLD, SHEET_ORDER  # noqa: E402
from drug_master import DRUG_NAME_JA, DRUG_ORDER    # noqa: E402
from paths import INPUT_DIR                         # noqa: E402

AXIS = C.AGESEX_AXIS
AGE_ORDER_21 = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳", "25～29歳", "30～34歳",
    "35～39歳", "40～44歳", "45～49歳", "50～54歳", "55～59歳", "60～64歳", "65～69歳",
    "70～74歳", "75～79歳", "80～84歳", "85～89歳", "90～94歳", "95～99歳", "100歳以上",
]
AGE_ORDER_19 = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳", "25～29歳", "30～34歳",
    "35～39歳", "40～44歳", "45～49歳", "50～54歳", "55～59歳", "60～64歳", "65～69歳",
    "70～74歳", "75～79歳", "80～84歳", "85～89歳", "90歳以上",
]


def load():
    return C.load(AXIS, INPUT_DIR)


def load_long():
    return pd.read_csv(os.path.join(INPUT_DIR, "product_agesex_long.csv"))


# ----------------------------------------------------------------------
# 1. agesex_censoring_report.md（都道府県版 censoring_detailed_report.md と対称）
# ----------------------------------------------------------------------
def build_report(d):
    L = []
    A = L.append
    A("# 抗アレルギー点眼薬9成分 秘匿欠落量レポート（年齢性別軸）")
    A("")
    A("NDBオープンデータ「処方薬（外用薬）年齢階級・性別」から、成分×年度×処方区分ごとに")
    A("秘匿（`-`）によって失われた処方数量を算出した。都道府県軸のレポート")
    A("（[censoring_detailed_report.md](censoring_detailed_report.md)）と同じ算出方法・")
    A("同じ4分類を用いており、対象セルの構成だけが異なる。")
    A("")
    A("- **データ基準**: 公費レセプトを**含まない**集計（2024年度は `ndb_gaiyo_agesex_2024_nokouhi.xlsx`）")
    A("- **対象**: 薬効分類131（眼科用剤）かつ品目名に「点眼」を含む9成分")
    A("- **生成**: `build_extract.py` → `build_agesex_report.py`")
    A("")
    A("## 算出方法")
    A("")
    A("```")
    A("欠落量 = 公表された「総計」列の値 − Σ(開示された年齢×性別セル)")
    A("```")
    A("")
    A(f"外用薬の処方数量は **{CENSOR_THRESHOLD:,}未満のセルが「-」で秘匿**される。")
    A("総計列には秘匿セルの値も含めた真の合計が入るため、上式で秘匿分の総量が復元できる。")
    A("")
    A("### セル構成が年度で異なる")
    A("")
    A("| 年度 | 年齢階級数 | 性別 | セル総数 | 備考 |")
    A("|---|---|---|---|---|")
    A("| 2014〜2015 | 19（90歳以上は1区分に統合） | 男・女 | 38 | |")
    A("| 2016以降 | 21（90〜94／95〜99／100歳以上に細分化） | 男・女 | 42 | |")
    A("")
    A("都道府県軸は全年度で47列固定だが、年齢性別軸は2016年度に区分が変わるため、")
    A("欠落率の計算では都道府県軸と異なり「セル総数」を年度ごとの実値で扱う")
    A("（`n_cells_total` 列。集計関数 `agg_group()` は両軸で共通コードを使用）。")
    A("")
    A("### 秘匿パターンの分類（都道府県軸と共通）")
    A("")
    A("| 分類 | 定義 | 欠落量の扱い |")
    A("|---|---|---|")
    A("| 秘匿なし | 全セル開示 | 0 |")
    A("| 部分秘匿 | 一部のセルが「-」 | 総計 − Σ開示で**合計は確定**。個々のセル値は不明 |")
    A("| ブロック秘匿 | 総計は公表されているのに全セルが「-」 | 総計の全額。閾値則では説明できない |")
    A(f"| 総計秘匿 | 総計自体が「-」（品目全体が{CENSOR_THRESHOLD:,}未満） | **算出不能**。総量に算入しない |")
    A("")
    A("> **本レポートは新規生成であり、旧版は存在しない。** 旧 `drug_by_drug_summary.md` Ⅲ章は")
    A("> 「2016・2017年度のエピナスチン外来（院外）で年齢性別ファイルの全42セルがブロック秘匿」")
    A("> という趣旨の記述をしていたが、根拠となる集計は示されていなかった。本レポートはこの主張を")
    A("> 実データで検証する（Ⅱ章）。")
    A("")

    A("---")
    A("")
    A("## Ⅰ. 一覧：成分×年度の欠落率（3処方区分の合算）")
    A("")
    A("外来（院外）・外来（院内）・入院を合算した成分全体の欠落率。")
    A("`—` は当該年度に成分がNDB非掲載（NR）であることを示す。")
    A("")
    L += C.rate_matrix_lines(d, AXIS)
    A("")

    # 都道府県軸との比較コメント（データドリブンに算出）
    pref_d = C.load(C.PREF_AXIS, INPUT_DIR)
    comparison = _axis_comparison(d, pref_d)
    A(comparison)
    A("")

    A("---")
    A("")
    A("## Ⅱ. ブロック秘匿（年齢性別内訳が丸ごと失われている品目）")
    A("")
    A("総計は公表されているのに全セルが「-」になっている行。")
    A(f"閾値則では説明できず、**総計の全額が年齢性別解析から欠落**する。")
    A("")
    blk = d[d.censor_class == "ブロック秘匿"]
    epi_1617 = blk[(blk.code == "EPINASTINE") & (blk.year.isin([2016, 2017]))]
    if len(epi_1617):
        A("旧文書の主張どおり、**2016・2017年度にエピナスチンでブロック秘匿が実在する**")
        A("ことが確認できた（下表）。ただし対象シートは外来（院外）だけでなく、")
        A("年度によって外来（院内）・外来（院外）の両方に及ぶ。")
    else:
        A("旧文書が主張していた2016・2017年度エピナスチンのブロック秘匿は、")
        A("本データでは確認できなかった。")
    A("")
    L += C.block_table_lines(d, AXIS)
    A("")

    A("---")
    A("")
    A("## Ⅲ. 総計秘匿（品目全体が閾値未満で数量不明）")
    A("")
    A(f"総計列そのものが「-」の行。品目全体の処方数量が{CENSOR_THRESHOLD:,}未満であり、")
    A("**欠落量は算出できない**。都道府県軸と対象品目・対象年度は完全に一致する")
    A("（総計秘匿は総計列そのものの秘匿なので、どちらの軸で見ても同じ行が該当する）。")
    A("")
    L += C.total_censored_table_lines(d)
    A("")

    A("---")
    A("")
    A("## Ⅳ. 成分別・年度別・処方区分別の詳細")
    A("")
    L += C.drug_detail_lines(d, AXIS)

    A("---")
    A("")
    A("## Ⅴ. 小児層・超高齢層への秘匿の偏り")
    A("")
    A("`回答_解析方針QA.md` Q3 は「小児層（0〜4歳）」「超高齢層（85歳以上・90歳以上）」で")
    A("セル秘匿が発生しやすいと述べていた。年齢階級別に秘匿発生率を集計して検証する。")
    A("")
    L += _age_censoring_bias_lines()
    A("")

    A("詳細な品目×年齢階級×性別の全セルは")
    A("[agesex_censoring_readable.md](agesex_censoring_readable.md) を参照。")
    A("")

    return "\n".join(L) + "\n"


def _axis_comparison(agesex_d, pref_d):
    """都道府県軸と年齢性別軸の欠落率を成分×年度で突き合わせ、差が大きい箇所を抽出する。"""
    def rate(d, axis):
        rows = []
        for code in DRUG_ORDER:
            for y in sorted(d.year.unique()):
                g = d[(d.code == code) & (d.year == y)]
                if g.empty:
                    continue
                a = C.agg_group(g, axis)
                if a["missing_pct"] is not None:
                    rows.append((code, y, a["missing_pct"]))
        return {(c, y): r for c, y, r in rows}

    ar = rate(agesex_d, AXIS)
    pr = rate(pref_d, C.PREF_AXIS)
    diffs = []
    for k in sorted(set(ar) & set(pr)):
        d_ = ar[k] - pr[k]
        if abs(d_) >= 5:
            diffs.append((k[0], k[1], pr[k], ar[k], d_))
    diffs.sort(key=lambda x: -abs(x[4]))

    lines = ["**都道府県軸との比較**: 同じ品目・年度でも、軸によって欠落率が大きく異なる場合がある",
            "（同じ品目の同じ数量が、片方の軸ではブロック秘匿、もう片方の軸では正常に開示される", "ことがあるため）。差が5ポイント以上の組み合わせ:", ""]
    if not diffs:
        lines.append("5ポイント以上の差はなかった。")
    else:
        lines.append("| 成分 | 年度 | 都道府県軸の欠落率 | 年齢性別軸の欠落率 | 差 |")
        lines.append("|---|---|--:|--:|--:|")
        for code, y, p, a, dd in diffs[:20]:
            lines.append(f"| {DRUG_NAME_JA[code]} | {y} | {p:.2f}% | {a:.2f}% | {dd:+.2f}pt |")
    return "\n".join(lines)


def _age_censoring_bias_lines():
    """年齢階級別の秘匿発生率（2016年度以降・21階級ベースに統一して集計）。"""
    long_df = load_long()
    d21 = long_df[long_df.age_group.isin(AGE_ORDER_21)]
    g = d21.groupby("age_group").agg(
        n_cells=("censored", "size"), n_censored=("censored", "sum")).reset_index()
    g["censor_rate_pct"] = g.n_censored / g.n_cells * 100
    order = {a: i for i, a in enumerate(AGE_ORDER_21)}
    g["_ord"] = g.age_group.map(order)
    g = g.sort_values("_ord")

    lines = ["| 年齢階級 | 対象セル数 | 秘匿セル数 | 秘匿発生率 |",
            "|---|--:|--:|--:|"]
    for _, r in g.iterrows():
        lines.append(f"| {r.age_group} | {int(r.n_cells):,} | {int(r.n_censored):,} "
                     f"| {r.censor_rate_pct:.1f}% |")
    lines.append("")
    top = g.nlargest(3, "censor_rate_pct")
    bot = g.nsmallest(3, "censor_rate_pct")
    lines.append(f"秘匿発生率が最も高いのは {'、'.join(top.age_group)}"
                f"（{top.censor_rate_pct.min():.1f}〜{top.censor_rate_pct.max():.1f}%）、")
    lines.append(f"最も低いのは {'、'.join(bot.age_group)}"
                f"（{bot.censor_rate_pct.min():.1f}〜{bot.censor_rate_pct.max():.1f}%）。")
    return lines


# ----------------------------------------------------------------------
# 2. agesex_censoring_readable.md（都道府県版 pref_censoring_readable.md と対称）
#    付録として品目×年齢階級×性別の全セルを完全なピボット表で収録する。
# ----------------------------------------------------------------------
def cell_phrase(row):
    names = [c for c in row.censored_cells.split("|") if c]
    n = len(names)
    if n == 0:
        return AXIS.phrase_all_disclosed
    if n >= row.n_cells_total:
        return "**全セルが「-」（ブロック秘匿）**"
    shown = "、".join(names[:8])
    tail = f" ほか計{n}セル" if n > 8 else ""
    return f"{n}セルが「-」秘匿（{shown}{tail}）"


def pivot_table_lines(long_df, year, sheet, code, product_name):
    """品目1件ぶんの 男/女 × 年齢階級 ピボット表（Markdown）。秘匿セルは「-」。"""
    sub = long_df[(long_df.year == year) & (long_df.sheet == sheet)
                  & (long_df.code == code) & (long_df.product_name == product_name)]
    if sub.empty:
        return []
    ages = AGE_ORDER_21 if year >= 2016 else AGE_ORDER_19
    lines = ["| 性別 | " + " | ".join(a.replace("歳", "") for a in ages) + " |",
            "|---" * (len(ages) + 1) + "|"]
    for sex in ["男", "女"]:
        row = []
        for age in ages:
            m = sub[(sub.sex == sex) & (sub.age_group == age)]
            if m.empty:
                row.append("")
            else:
                r = m.iloc[0]
                row.append("-" if r.censored else f"{r.value:,.0f}")
        lines.append(f"| {sex} | " + " | ".join(row) + " |")
    return lines


def build_readable(d, long_df):
    L = []
    A = L.append
    A("# 抗アレルギー点眼薬9成分 年齢性別 秘匿実態")
    A("")
    A("品目単位で、どの年齢×性別セルが秘匿され、どれだけの処方数量が失われたかを一覧する。")
    A("都道府県版は [pref_censoring_readable.md](pref_censoring_readable.md)。")
    A("")
    A("- **データ基準**: 公費レセプトを含まない集計（2024年度は `ndb_gaiyo_agesex_2024_nokouhi.xlsx`）")
    A(f"- **欠落量** = 公表「総計」− Σ(開示された年齢×性別セル)。秘匿閾値は処方数量 {CENSOR_THRESHOLD:,} 未満")
    A("- **総計秘匿** = 総計列自体が「-」の品目。欠落量は算出できない")
    A("- **付録**: 各品目の42セル（21年齢階級×男女）を完全なピボット表で収録")
    A("")
    A("## 目次")
    A("")
    for code in DRUG_ORDER:
        if not d[d.code == code].empty:
            A(f"- [{DRUG_NAME_JA[code]}](#{code.lower()})")
    A("")

    for code in DRUG_ORDER:
        sub = d[d.code == code]
        if sub.empty:
            continue
        A("---")
        A("")
        A(f"<a id=\"{code.lower()}\"></a>")
        A(f"## {DRUG_NAME_JA[code]}")
        A("")
        years = sorted(sub.year.unique())
        miss = [y for y in sorted(d.year.unique()) if y not in years]
        if miss:
            A(f"NDB非掲載（NR）の年度: {'、'.join(str(y) for y in miss)}")
            A("")
        for y in years:
            A(f"### {y}年度")
            A("")
            gy = sub[sub.year == y].sort_values(["sheet_ord", "total"],
                                                ascending=[True, False])
            for s in SHEET_ORDER:
                gs = gy[gy.sheet == s]
                if gs.empty:
                    continue
                A(f"#### {s}")
                A("")
                A("| 品目名 | 区分 | 公表総計 | 欠落量 | 秘匿状況 |")
                A("|---|---|--:|--:|---|")
                for _, r in gs.iterrows():
                    tlabel = {"brand": "先発",
                              "generic_maker": "後発（銘柄）",
                              "generic_unified": "後発（統一名）"}[r.product_type]
                    if r.total_censored:
                        tot, mis = "総計も「-」", "**算出不能**"
                    else:
                        tot, mis = C.fmt(r.total), C.fmt(r.missing)
                    A(f"| {r.product_name} | {tlabel} | {tot} | {mis} | {cell_phrase(r)} |")
                A("")

        A("#### 付録：品目×年齢階級×性別 全セル")
        A("")
        for y in years:
            gy = sub[sub.year == y].sort_values(["sheet_ord", "total"],
                                                ascending=[True, False])
            for s in SHEET_ORDER:
                gs = gy[gy.sheet == s]
                if gs.empty:
                    continue
                for _, r in gs.iterrows():
                    A(f"**{y}年度 {s} {r.product_name}**（総計: "
                      f"{'総計も「-」' if r.total_censored else C.fmt(r.total)}）")
                    A("")
                    L += pivot_table_lines(long_df, y, s, code, r.product_name)
                    A("")
    return "\n".join(L) + "\n"


def main():
    d = load()
    long_df = load_long()
    for name, text in [("agesex_censoring_report.md", build_report(d)),
                       ("agesex_censoring_readable.md", build_readable(d, long_df))]:
        p = os.path.join(BASE, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"-> {name} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
