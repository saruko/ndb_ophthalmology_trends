# -*- coding: utf-8 -*-
"""秘匿レポート2本（都道府県軸）を再生成する。

  censoring_detailed_report.md   成分×年度×シート区分の秘匿欠落量サマリ
  pref_censoring_readable.md     品目×都道府県の秘匿実態（可読形式）

旧版（2025年8月時点）は次の2点で数値が壊れていたため全面的に作り直した。
  1. 総計列を固定位置で取り、表題セルの「総計」に一致してしまい薬効分類コード
     「131」を総処方量として出力していた
  2. 「秘匿セル」を都道府県列ではなくヘッダの文字列列（薬価基準収載医薬品
     コード・単位）から数えていたため、欠落率が機械的に99〜100%になっていた

入力: 01_抽出データ/product_level_censoring.csv（build_extract.py が生成）
共通の集計・整形ロジックは src/censoring_lib.py にあり、年齢性別軸の
build_agesex_report.py と共有する。
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

import censoring_lib as C                          # noqa: E402
from ndb_reader import CENSOR_THRESHOLD, PREFECTURES, SHEET_ORDER  # noqa: E402
from drug_master import DRUG_NAME_JA, DRUG_ORDER    # noqa: E402
from paths import INPUT_DIR                         # noqa: E402

AXIS = C.PREF_AXIS
N_PREF = len(PREFECTURES)


def load():
    return C.load(AXIS, INPUT_DIR)


# ----------------------------------------------------------------------
# 1. censoring_detailed_report.md
# ----------------------------------------------------------------------
def build_detailed(d):
    L = []
    A = L.append
    A("# 抗アレルギー点眼薬9成分 秘匿欠落量レポート（都道府県軸）")
    A("")
    A("NDBオープンデータ「処方薬（外用薬）都道府県別」から、成分×年度×処方区分ごとに")
    A("秘匿（`-`）によって失われた処方数量を算出した。")
    A("")
    A("- **データ基準**: 公費レセプトを**含まない**集計（2024年度は `ndb_gaiyo_2024_nokouhi.xlsx`）")
    A("- **対象**: 薬効分類131（眼科用剤）かつ品目名に「点眼」を含む9成分")
    A("- **生成**: `build_extract.py` → `build_censoring_reports.py`")
    A("- **年齢性別軸の同種レポート**: [agesex_censoring_report.md](agesex_censoring_report.md)")
    A("")
    A("## 算出方法")
    A("")
    A("```")
    A("欠落量 = 公表された「総計」列の値 − Σ(開示された47都道府県セル)")
    A("```")
    A("")
    A(f"外用薬の処方数量は **{CENSOR_THRESHOLD:,}未満のセルが「-」で秘匿**される。")
    A("総計列には秘匿セルの値も含めた真の合計が入るため、上式で秘匿分の総量が復元できる。")
    A("秘匿セル数は**47の都道府県列のみ**を数える（品目名・単位・薬価などの文字列列は含めない）。")
    A("")
    A("### 秘匿パターンの分類")
    A("")
    A("| 分類 | 定義 | 欠落量の扱い |")
    A("|---|---|---|")
    A("| 秘匿なし | 47都道府県すべて開示 | 0 |")
    A("| 部分秘匿 | 一部の県が「-」 | 総計 − Σ開示で**合計は確定**。個々のセル値は不明 |")
    A("| ブロック秘匿 | 総計は公表されているのに47都道府県すべてが「-」 | 総計の全額。閾値則では説明できない |")
    A(f"| 総計秘匿 | 総計自体が「-」（品目全体が{CENSOR_THRESHOLD:,}未満） | **算出不能**。総量に算入しない |")
    A("")
    A("> **旧版からの変更**: 旧 `censoring_detailed_report.md` は総計列の特定に失敗して")
    A("> 薬効分類コード「131」を総処方量として出力し、また秘匿セルを都道府県列ではなく")
    A("> ヘッダ文字列列から数えていたため、欠落率が全行で機械的に99〜100%になっていた。")
    A("> 本版はいずれも修正済みで、欠落率は成分・年度により0.00%〜100%まで実際に分布する。")
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
    A("処方規模の大きい成分（エピナスチン・オロパタジン）は外来（院外）がほぼ全県開示のため")
    A("欠落率が0.2%以下に収まる。一方、後発品が多数の銘柄に分散する成分")
    A("（ケトチフェン・クロモグリク酸Na・ペミロラスト）は2022年度以降に全銘柄が公開された結果、")
    A("銘柄あたりの処方量が小さくなり欠落率が10%超に上がる。")
    A("2015〜2017年のレボカバスチン・アシタザノラストの高い欠落率はブロック秘匿（Ⅱ章）による。")
    A("処方区分別の内訳はⅣ章を参照。")
    A("")

    A("---")
    A("")
    A("## Ⅱ. ブロック秘匿（都道府県内訳が丸ごと失われている品目）")
    A("")
    A("総計は公表されているのに47都道府県すべてが「-」になっている行。")
    A(f"各セル<{CENSOR_THRESHOLD:,}の閾値則では説明できず、**総計の全額が都道府県別解析から欠落**する。")
    A("都道府県別の集計を行う際は、これらの品目の数量が完全に抜け落ちることに注意。")
    A("")
    L += C.block_table_lines(d, AXIS)
    A("")

    A("---")
    A("")
    A("## Ⅲ. 総計秘匿（品目全体が閾値未満で数量不明）")
    A("")
    A(f"総計列そのものが「-」の行。品目全体の処方数量が{CENSOR_THRESHOLD:,}未満であり、")
    A("**欠落量は算出できない**（総量への算入も不可）。数量の上限は "
      f"「該当行数 × {CENSOR_THRESHOLD - 1:,}」で押さえられる。")
    A("")
    L += C.total_censored_table_lines(d)
    A("大半は入院シートの小規模後発品銘柄であり、外来を含めた全体量への影響は軽微。")
    A("")

    A("---")
    A("")
    A("## Ⅳ. 成分別・年度別・処方区分別の詳細")
    A("")
    L += C.drug_detail_lines(d, AXIS)

    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------
# 2. pref_censoring_readable.md
# ----------------------------------------------------------------------
def pref_phrase(row):
    names = [p for p in row.censored_prefs.split("|") if p]
    n = len(names)
    if n == 0:
        return AXIS.phrase_all_disclosed
    if n >= N_PREF:
        return "**全47都道府県が「-」（ブロック秘匿）**"
    shown = "、".join(names[:8])
    tail = f" ほか計{n}都道府県" if n > 8 else ""
    return f"{n}県が「-」秘匿（{shown}{tail}）"


def build_readable(d):
    L = []
    A = L.append
    A("# 抗アレルギー点眼薬9成分 都道府県別 秘匿実態")
    A("")
    A("品目単位で、どの都道府県セルが秘匿され、どれだけの処方数量が失われたかを一覧する。")
    A("")
    A("- **データ基準**: 公費レセプトを含まない集計（2024年度は `ndb_gaiyo_2024_nokouhi.xlsx`）")
    A(f"- **欠落量** = 公表「総計」− Σ(開示された47都道府県セル)。秘匿閾値は処方数量 {CENSOR_THRESHOLD:,} 未満")
    A("- **総計秘匿** = 総計列自体が「-」の品目。欠落量は算出できない")
    A("")
    A("> 旧版は総計列の特定に失敗して薬効分類コード「131」を総量として出力し、")
    A("> また入院シートの総計秘匿行を一律「欠落量=0」としていた（実際は全量が不明）。")
    A("> 本版はいずれも修正済み。")
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
                    A(f"| {r.product_name} | {tlabel} | {tot} | {mis} | {pref_phrase(r)} |")
                A("")
    return "\n".join(L) + "\n"


def main():
    d = load()
    for name, text in [("censoring_detailed_report.md", build_detailed(d)),
                       ("pref_censoring_readable.md", build_readable(d))]:
        p = os.path.join(BASE, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"-> {name} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
