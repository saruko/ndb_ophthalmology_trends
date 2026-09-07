# -*- coding: utf-8 -*-
"""3ファイル（drug_by_drug_summary.md / censoring_detailed_report.md /
pref_censoring_readable.md）と新規の年齢性別秘匿解析・未収載品目感度分析を
1つの文書に統合する。

方針:
  - 各セクションは対応する build_*.py が生成したMarkdownファイルをそのまま
    読み込んで貼り込む（このスクリプト自身は集計を行わない）。数値の再計算を
    2箇所で行うと食い違いのリスクが生じるため、常に一次生成物を単一の出典とする。
  - drug_by_drug_summary.md の旧Ⅳ章（秘匿実態の要約）は、本統合版の④章
    （censoring_detailed_report.md 全文）と内容が重複するため、要約は削除して
    ④章への参照に置き換える。
  - 都道府県軸・年齢性別軸それぞれの「品目×都道府県／年齢階級×性別 全セル」
    の完全な内訳は分量が大きいため、④⑤章には要約表のみを残し、全セルは
    付録A・付録Bに回す。

出力: NDB公開構造と秘匿実態_9成分_統合版.md
入力: 各 build_*.py が生成した既存ファイル（本スクリプトを実行する前に、
     build_extract.py / build_censoring_reports.py / build_agesex_report.py /
     build_unlisted_sensitivity.py を実行しておくこと）
"""
import datetime
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(BASE, "NDB公開構造と秘匿実態_9成分_統合版.md")


def read(name):
    p = os.path.join(BASE, name)
    with open(p, encoding="utf-8") as f:
        return f.read()


def read_unlisted(name):
    p = os.path.join(BASE, "05_論文成果物", "公費含めない_new", name)
    with open(p, encoding="utf-8") as f:
        return f.read()


def split_h1_and_h2(text):
    """先頭の `# Title` 行を取り除き、`## ` 見出しごとにセクション分割する。

    戻り値: (title, intro_text, {見出し名: 本文}) 見出し名の出現順は保持される。
    """
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip()
    body = "\n".join(lines[1:]).lstrip("\n")

    parts = re.split(r"(?m)^## (.+)$", body)
    intro = parts[0].strip("\n")
    sections = {}
    order = []
    for i in range(1, len(parts), 2):
        head = parts[i].strip()
        content = parts[i + 1]
        sections[head] = content
        order.append(head)
    return title, intro, sections, order


def renumber(text, mapping):
    """本文中の `## Ⅰ.` 等の見出し記号を、統合版での通し番号に付け替える。"""
    for old, new in mapping.items():
        text = re.sub(rf"(?m)^## {re.escape(old)}", f"## {new}", text)
        text = re.sub(rf"(?m)^### {re.escape(old)}", f"### {new}", text)
    return text


def indent_headers(text, levels=1):
    """本文中の `#` 見出しレベルを levels 段シフトする（正=下げる、負=上げる）。

    貼り込み先の新しい親見出しのレベルに合わせて、元ファイルの内部見出しの
    深さを揃えるために使う。例えば元ファイルが `## Ⅲ.` の下に `### 1. …`
    （1段下）を持つ構成を、統合版の `# ③ …`（親そのものがH1）の下に
    そのままネストさせるには、本文の見出しを1段（H3→H2）引き上げる
    （levels=-1）必要がある。
    """
    def _shift(m):
        return "#" * max(1, len(m.group(1)) + levels) + m.group(2)
    return re.sub(r"(?m)^(#+)(\s.*)$", _shift, text)


# ②と③の間に挟む章。上司査読で受けた2つの指摘に対する回答の要旨
# （2026-08-07、数値の一次出典は⑦章・bounded_outputs_report.md）。
REVIEW_RESPONSE = """\
# ②′ 査読指摘への回答要旨（薬剤選定の妥当性・秘匿データの扱い）

上司査読で受けた次の2点の指摘に対する回答の要旨。数値の一次出典は
⑦章（未収載品目まで拡張した秘匿感度分析）と
`05_論文成果物/公費含めない_new/bounded_outputs_report.md`。
数量はすべてmL換算（瓶=×1容器あたりmL、個=×0.35mL）で統一している。

## 指摘1: 2014〜2021年度は集計に載らない秘匿・未収載の薬剤があるのに、主要3成分（エピナスチン・オロパタジン・レボカバスチン）の処方シェアが本当に多いと言えるのか

**結論: 「3成分で最大シェア」を公表データだけから厳密に主張できるのは、
上位品目の足切りが撤廃された2022年度以降に限られる。薬剤選定の根拠は
2022年度以降の実測シェアに置き、2021年度以前は識別区間を併記する。**

- 全品目が公開された2022〜2024年度の実測では、3成分合計は
  約196〜203百万mL/年、9成分合計は約232〜243百万mL/年で、
  **3成分のシェアは83.6%（2022）／84.6%（2023）／85.8%（2024）**。
  これは公開仕様（足切り）に依存しない確定値である。
- 順位ベースの論理（仮定ゼロ）により、未収載品目の総量は当該年度・当該シートで
  公表された最小総計を超えない。したがって**単一品目として3成分の主要銘柄を
  上回る「隠れた薬剤」は存在し得ない**。3成分が2014年度から一貫して足切りを
  超えて掲載され続けたこと自体が上位である証拠になる。
- ただし成分合計では逆転可能性が残る。多数の銘柄が未収載だった
  クロモグリク酸Naの順位ベース上限は2015〜2018年度で公表値の
  +16000〜23000%（mL換算後）に達し、理論上の最悪ケースでは
  レボカバスチンを上回り得る。**この点は限界として明示する**一方、
  足切り撤廃直後の2022年度実測でクロモグリク酸Naは7.1百万mL
  （3成分合計の約1/30）に過ぎなかったことを反証として併記できる。

## 指摘2: 外来（院内）・外来（院外）・入院で公開されていないデータがある中で正確に解析できるのか。最大値・最小値の処理は不要か

**結論: 全集計表を下限・上限（識別区間）つきで再生成済みであり、
点推定ではなく区間で提示する。**

- 品目×年度×処方区分ごとに、公表「総計」列から
  `missing = 総計 − Σ開示セル` として**秘匿分の合計量を厳密に復元**できる。
  各秘匿セルの真値は `[0, missing]` に収まる。総計自体が秘匿の行は
  「999 − Σ開示」を上限とする。
- 「秘匿セル=999以下」という単純な仮定は**使えない**ことを実データで確認した。
  NDBは補完的秘匿を行っており、部分秘匿行で秘匿セルが1個だけの行は両軸とも
  0行（単独秘匿の回避）、`missing` が 秘匿セル数×999 を超える行が
  都道府県軸8行・年齢性別軸41行ある。
- 区間の実際の幅は、**全国合計では3成分とも0.1%未満**であり主要な結論に影響しない。
  一方、都道府県別・年齢性別の小さなセル（90歳以上など）では区間が大きく開くため、
  それらは区間を併記し、値の断定を避ける。
  一次出典: `national_trends_bounds.csv` / `prefecture_per_capita_bounds.csv` /
  `agesex_bounds.csv`（いずれも 05_論文成果物/公費含めない_new/）。

---
"""


def main():
    dbd_title, dbd_intro, dbd_sec, dbd_order = split_h1_and_h2(read("drug_by_drug_summary.md"))
    det_title, det_intro, det_sec, det_order = split_h1_and_h2(read("censoring_detailed_report.md"))
    prefr_text = read("pref_censoring_readable.md")
    age_title, age_intro, age_sec, age_order = split_h1_and_h2(read("agesex_censoring_report.md"))
    agerd_text = read("agesex_censoring_readable.md")
    uns_title, uns_intro, uns_sec, uns_order = split_h1_and_h2(
        read_unlisted("unlisted_sensitivity_report.md"))

    today = datetime.date.today().isoformat()

    L = []
    A = L.append

    # ------------------------------------------------------------------
    # 表紙・前書き
    # ------------------------------------------------------------------
    A("# NDBオープンデータ 抗アレルギー点眼薬9成分 公開構造と秘匿実態の統合版")
    A("")
    A(f"生成日: {today}")
    A("")
    A("以下3ファイル＋新規解析2件を1つの文書に統合したもの。個別ファイルは")
    A("そのまま残しており、本文書は再生成スクリプト（下記）の実行結果を")
    A("貼り合わせているだけで、独自の集計は行っていない。")
    A("")
    A("| 章 | 内容 | 出典ファイル | 生成スクリプト |")
    A("|---|---|---|---|")
    A("| ① | NDB処方薬データの公開範囲と構造 | drug_by_drug_summary.md | （手動整理・ファクトチェック） |")
    A("| ② | 秘匿ルールの共通構造 | drug_by_drug_summary.md | 同上 |")
    A("| ②′ | 査読指摘への回答要旨 | build_combined_report.py 内で管理 | build_combined_report.py |")
    A("| ③ | 9成分の個別詳細（上市メーカー突合） | drug_by_drug_summary.md | 同上 |")
    A("| ④ | **都道府県データ**の秘匿実態 | censoring_detailed_report.md | build_extract.py → build_censoring_reports.py |")
    A("| ⑤ | **年齢性別データ**の秘匿実態 | agesex_censoring_report.md | build_extract.py → build_agesex_report.py |")
    A("| ⑥ | 公開品目数と足切り制限の検証 | drug_by_drug_summary.md | （手動整理・実データ検証） |")
    A("| ⑦ | 未収載品目まで拡張した秘匿感度分析 | unlisted_sensitivity_report.md | build_unlisted_sensitivity.py |")
    A("| 付録A | 都道府県：品目×都道府県 全セル | pref_censoring_readable.md | build_censoring_reports.py |")
    A("| 付録B | 年齢性別：品目×年齢階級×性別 全セル | agesex_censoring_readable.md | build_agesex_report.py |")
    A("")
    A("**データ基準**: 全章共通で公費レセプトを**含まない**集計（2024年度は")
    A("`ndb_gaiyo_2024_nokouhi.xlsx` / `ndb_gaiyo_agesex_2024_nokouhi.xlsx`）。")
    A("**対象**: 薬効分類131（眼科用剤）かつ品目名に「点眼」を含む9成分")
    A("（エピナスチン・オロパタジン・レボカバスチン・ケトチフェン・クロモグリク酸Na・")
    A("トラニラスト・ペミロラスト・イブジラスト・アシタザノラスト）。")
    A("")
    A("**再生成手順**:")
    A("")
    A("```bash")
    A("python build_extract.py               # 生Excel -> 01_抽出データ/*.csv")
    A("python build_censoring_reports.py      # -> censoring_detailed_report.md, pref_censoring_readable.md")
    A("python build_agesex_report.py          # -> agesex_censoring_report.md, agesex_censoring_readable.md")
    A("python build_unlisted_sensitivity.py   # -> 05_論文成果物/公費含めない_new/*")
    A("python build_combined_report.py        # -> 本ファイル")
    A("```")
    A("")
    A("---")
    A("")

    # ------------------------------------------------------------------
    # ① ② ③  drug_by_drug_summary.md の該当章をそのまま流用
    # ------------------------------------------------------------------
    ch_map = [
        ("Ⅰ. NDBオープンデータにおける処方薬データの公開範囲と構造", "①"),
        ("Ⅱ. NDBオープンデータにおける「秘匿（非公開項目）」の共通ルールと構造", "②"),
        ("Ⅲ. 9成分 抗アレルギー点眼薬の個別詳細（ファクトチェック済み）", "③"),
    ]
    for head, num in ch_map:
        content = dbd_sec[head]
        title_text = head.split(". ", 1)[1] if ". " in head else head
        A(f"# {num} {title_text}")
        A("")
        A(indent_headers(content.strip("\n"), levels=-1))
        A("")
        if num == "③":
            A("> **編集注**: 旧 `drug_by_drug_summary.md` にあった「Ⅳ. 9成分における")
            A("> 処方区分・都道府県別の『-』秘匿実態」章は、本統合版では④章")
            A("> （都道府県データの秘匿実態）に一本化し、ここでは省略した。")
            A("> 年齢性別データの秘匿実態は⑤章、未収載品目まで拡張した感度分析は")
            A("> ⑦章を参照。")
            A("")
        A("---")
        A("")
        if num == "②":
            A(REVIEW_RESPONSE)
            A("")

    # ------------------------------------------------------------------
    # ④ 都道府県データの秘匿実態（censoring_detailed_report.md 全文）
    # ------------------------------------------------------------------
    A("# ④ 都道府県データの秘匿実態")
    A("")
    A(det_intro.strip("\n"))
    A("")
    for i, head in enumerate(det_order, start=1):
        A(f"## ④-{i} " + re.sub(r"^Ⅰ+\.\s*|^Ⅱ+\.\s*|^Ⅲ+\.\s*|^Ⅳ+\.\s*", "", head))
        A("")
        A(indent_headers(det_sec[head].strip("\n"), levels=0))
        A("")
    A("都道府県別の完全な内訳（品目×都道府県 全セル）は付録Aを参照。")
    A("")
    A("---")
    A("")

    # ------------------------------------------------------------------
    # ⑤ 年齢性別データの秘匿実態（agesex_censoring_report.md 全文）
    # ------------------------------------------------------------------
    A("# ⑤ 年齢性別データの秘匿実態")
    A("")
    A(age_intro.strip("\n"))
    A("")
    for i, head in enumerate(age_order, start=1):
        A(f"## ⑤-{i} " + re.sub(r"^Ⅰ+\.\s*|^Ⅱ+\.\s*|^Ⅲ+\.\s*|^Ⅳ+\.\s*|^Ⅴ+\.\s*", "", head))
        A("")
        A(indent_headers(age_sec[head].strip("\n"), levels=0))
        A("")
    A("品目×年齢階級×性別の完全な内訳（全セルのピボット表）は付録Bを参照。")
    A("")
    A("---")
    A("")

    # ------------------------------------------------------------------
    # ⑥ 公開品目数と足切り制限の検証（drug_by_drug_summary.md Ⅴ章）
    # ------------------------------------------------------------------
    head5 = "Ⅴ. 公開品目数と足切り制限の検証（薬効分類131：眼科用剤）"
    A("# ⑥ 公開品目数と足切り制限の検証（薬効分類131：眼科用剤）")
    A("")
    A(indent_headers(dbd_sec[head5].strip("\n"), levels=-1))
    A("")
    A("---")
    A("")

    # ------------------------------------------------------------------
    # ⑦ 未収載品目まで拡張した秘匿感度分析
    # ------------------------------------------------------------------
    A("# ⑦ 未収載品目まで拡張した秘匿感度分析")
    A("")
    A(uns_intro.strip("\n"))
    A("")
    for i, head in enumerate(uns_order, start=1):
        A(f"## ⑦-{i} " + re.sub(r"^Ⅰ+\.\s*|^Ⅱ+\.\s*|^Ⅲ+\.\s*|^Ⅳ+\.\s*", "", head))
        A("")
        A(indent_headers(uns_sec[head].strip("\n"), levels=0))
        A("")
    A("生成物（CSV・図）は `05_論文成果物/公費含めない_new/` を参照。")
    A("")
    A("---")
    A("")

    # ------------------------------------------------------------------
    # 付録A・付録B
    # ------------------------------------------------------------------
    pa_title, pa_intro, pa_sec, pa_order = split_h1_and_h2(prefr_text)
    A("# 付録A. 都道府県：品目×都道府県 全セル")
    A("")
    A(pa_intro.strip("\n"))
    A("")
    for head in pa_order:
        A(f"## {head}")
        A("")
        A(indent_headers(pa_sec[head].strip("\n"), levels=0))
        A("")
    A("---")
    A("")

    # 付録Aと付録Bは同じ生成ロジック（code.lower()）でアンカーID（<a id="epinastine">等）を
    # 振っているため、そのまま連結すると id が重複し、目次リンクが常に付録Aへ飛んでしまう。
    # 付録B側のみ id に "b-" 接頭辞を付けて一意化する。
    def _prefix_ids(text):
        text = re.sub(r'<a id="([a-z_]+)">', r'<a id="b-\1">', text)
        text = re.sub(r'\(#([a-z_]+)\)', r'(#b-\1)', text)
        return text

    pb_title, pb_intro, pb_sec, pb_order = split_h1_and_h2(_prefix_ids(agerd_text))
    A("# 付録B. 年齢性別：品目×年齢階級×性別 全セル")
    A("")
    A(pb_intro.strip("\n"))
    A("")
    for head in pb_order:
        A(f"## {head}")
        A("")
        A(indent_headers(pb_sec[head].strip("\n"), levels=0))
        A("")

    text = "\n".join(L) + "\n"
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"-> {os.path.basename(OUT_PATH)} ({len(text.splitlines())} lines, "
          f"{len(text.encode('utf-8')):,} bytes)")


if __name__ == "__main__":
    main()
