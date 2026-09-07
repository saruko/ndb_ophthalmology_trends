# -*- coding: utf-8 -*-
"""日本語の作業原稿（.md）を v13 → v14 に更新する。

apply_docx_v14.py と同じ改訂（Suppl Fig S1 の削除と S2〜S5 の繰り上げ、
補遺の引用漏れ）を作業原稿にも反映し、あわせて **v13 の時点で docx にだけ
反映され作業原稿に取り残されていた3件の数値**（付記15-2 の項目6・
品目非掲載の上限の幅）を同期する。付記16 に改訂を記録する。

繰り上げは本文（§1〜§10）のみに適用し、冒頭の版歴ブロックと付記1〜15 は
改訂の記録であるため当時の番号のまま残す。

出力: 投稿用v14/論文下書き_総量2014_シェア2022_区間解析_投稿改定ver14.md

実行: python apply_md_v14.py
"""
import io
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
NEW = os.path.join(BASE, "05_論文成果物", "公費含めない_new")
V13 = os.path.join(NEW, "投稿改定ver", "投稿用v13")
V14 = os.path.join(NEW, "投稿改定ver", "投稿用v14")
SRC = os.path.join(V13, "論文下書き_総量2014_シェア2022_区間解析_投稿改定ver13.md")
DEST = os.path.join(V14, "論文下書き_総量2014_シェア2022_区間解析_投稿改定ver14.md")

BODY_START = "## 1. 緒言（Introduction）"
BODY_END = "## 付記1：編集方針"


def _pat(old):
    """old の各文字の間に改行（と行頭のインデント）を許す正規表現。"""
    return re.compile(r"(?:\n[ \t]*)?".join(re.escape(ch) for ch in old))


def sub1(text, old, new, n=1, label=""):
    pat = _pat(old)
    text, k = pat.subn(lambda m: new, text)
    if k != n:
        raise SystemExit("置換件数が想定と違う（%s）: %d（想定%d）／%s"
                         % (label, k, n, old[:50]))
    return text


# ---------------------------------------------------------------- 数値の同期
# 付記15-2 の項目6・および品目非掲載の上限の幅は docx にだけ反映されていた。
STALE = [
    # 抄録：95歳以上は男／女比の区間が1をまたぐので「15歳以上の全階級」は過剰主張
    ("15歳以上の全階級で女性優位（20〜59歳で0.39〜0.69）であった。",
     "15〜94歳の全階級で女性優位（20〜59歳で0.39〜0.69）であった"
     "（95歳以上は区間が1をまたぎ判定不能）。", 1, "抄録の男女比"),
    # 抄録・§3.7：Suppl Table S3 の upper1_width_pct は 30.0〜983.2%、
    # クロモグリク酸Na は 17,550〜24,949%
    ("公表値の+50〜+430%（クロモグリク酸Naでは+16,000%超）",
     "公表値の+30〜+983%（クロモグリク酸Naでは+17,550%超）", 2, "品目非掲載の上限の幅"),
    # §4.6：同じ出典の値
    ("順位ベース上限は2015〜2018年度で公表値の+16,000%超に達し",
     "順位ベース上限は2015〜2018年度で公表値の+17,550%超に達し", 1, "§4.6 の上限"),
]

# ------------------------------------------------------------------ 抄録の圧縮
# 投稿用 docx と同じ本文に差し替える（apply_docx_v14.py の ABSTRACT と同一）。
# ※ は250語制限の投稿先に当たった場合の削除候補（2文で約42語）。
ABSTRACT_HEAD = "## 構造化抄録（Structured Abstract）"
ABSTRACT_TAIL = "**Keywords**:"
ABSTRACT_NEW = """## 構造化抄録（Structured Abstract）

> 投稿用 docx と同一の本文。和文913字で、英訳すると299語（見出し語を含め303語)
> となり、構造化抄録の一般的な上限に収まる。250語制限の投稿先に当たった場合の
> 削除候補に ※ を付した（※の2文を落とすと263語）。圧縮前の版は
> `投稿用v13/NDB抗アレルギー解析_v13_clean.docx` にある。付記16-4。

**Background**
アレルギー性結膜疾患は日本で有病率が高いが、抗アレルギー点眼薬の全年齢・全国に
わたる長期の処方実態は明らかでない。本研究は、9成分の全国処方量と
成分構成の11年間の変化を、公開データの欠測構造を明示して記述することを目的とした。

**Methods**
NDBオープンデータ第1〜11回（2014〜2024年度）を用いた後ろ向き記述研究である。
抗アレルギー点眼薬9成分を対象に、公費レセプトを含まない集計に統一して処方数量を
mLに正規化した。本データはセル秘匿・総計秘匿・品目非掲載という3層の欠測をもつため、
分布仮定を置かず識別区間として結果を提示した。
※都道府県間格差は、集計整合性制約（県別合計は全国総計を超えない）の下で
ジニ係数と変動係数の識別区間として評価した。
成分間シェアの比較は2022年度以降に限定した。

**Results**
2024年度の9成分合計は234.8〜235.1百万mL（識別区間の幅0.111%）であった。
エピナスチンは14.5百万mL（2014年度）から118.2百万mL（2024年度）へ、主要3成分合計は
2015年度を起点として、いずれも識別区間を含めて増加が確定した。2022年度起点では
両者とも減少が確定する一方、エピナスチンのみ実数でも増加してシェアは44.0%から
50.3〜50.4%へ上昇し、内部では1日2回点眼の0.1%製剤が65.0%に達した。
処方量は5〜14歳が最多で、性比は14歳を境に男性優位から女性優位へ転換した。
※都道府県間には少なくとも2.6倍の差があり、エピナスチン・オロパタジンでは
格差の縮小が確定した。
2021年度以前は品目非掲載により成分別の上限が公表値を30〜983%上回った。

**Conclusions**
エピナスチンは2014年度以降一貫して増加し、2024年度には抗アレルギー点眼薬の
約半数を占め、高濃度製剤と後発医薬品への移行が進んだ。NDBオープンデータの秘匿は
2022年度以降の全国集計にはほとんど影響しない一方、2021年度以前の成分間比較を
本質的に制約する。識別区間による提示は、この制約を明示したまま動向を記述できる。

"""

# ------------------------------------------------------- Suppl Fig S1 の削除
# §2.4 冒頭（模式図の参照）
S1_SENTENCE = ("NDBオープンデータの3層の欠測構造と、各層に対する識別区間の導出は"
               "Suppl Figure S1に模式図として示した。")
S1_SENTENCE_NEW = "NDBオープンデータの欠測は3層からなり、各層について識別区間を導出する。"

# §8 の legend（S1 のブロックを丸ごと落とす）
S1_LEGEND_HEAD = "- **Supplementary Figure S1.** NDBオープンデータの欠測3層構造"

# §9 の生成パイプライン一覧（S1 を落として S3 だけ残す）
S1_PIPELINE = ("`build_extra_figures.py`（Suppl Fig S1・S3）",
               "`build_extra_figures.py`（Suppl Fig S3）")

PREFIXES = ("Supplementary Figure ", "Suppl Figure ", "Suppl Fig ")
# 昇順に適用する（S2→S1 を先に終えれば S3→S2 が S1 に波及しない）
RENUMBER = [("S2", "S1"), ("S3", "S2"), ("S4", "S3"), ("S5", "S4")]


def drop_legend_block(body):
    """S1 の legend ブロック（`- **Supplementary Figure S1.**` から次の `- **` 直前まで）を削除。"""
    i = body.index(S1_LEGEND_HEAD)
    j = body.index("\n- **", i + 1) + 1
    return body[:i] + body[j:]


def main():
    os.makedirs(V14, exist_ok=True)
    text = io.open(SRC, encoding="utf-8").read()

    for old, new, n, label in STALE:
        text = sub1(text, old, new, n, label)
    print("数値の同期: %d 項目" % len(STALE))

    # 抄録の差し替え（STALE のうち抄録側の修正は、この差し替えで置き換わる）
    i = text.index(ABSTRACT_HEAD)
    j = text.index(ABSTRACT_TAIL)
    print("抄録: %d字 -> %d字" % (j - i, len(ABSTRACT_NEW)))
    text = text[:i] + ABSTRACT_NEW + text[j:]

    i = text.index(BODY_START)
    j = text.index(BODY_END)
    head, body, tail = text[:i], text[i:j], text[j:]

    body = sub1(body, S1_SENTENCE, S1_SENTENCE_NEW, 1, "§2.4 の模式図参照")
    body = drop_legend_block(body)
    body = sub1(body, S1_PIPELINE[0], S1_PIPELINE[1], 1, "§9 のパイプライン一覧")
    left = re.findall(r"Suppl(?:ementary)? Fig(?:ure)? S1", body)
    if left:
        raise SystemExit("本文に Suppl Fig S1 が残っている: %s" % left)

    total = 0
    for old, new in RENUMBER:
        for pre in PREFIXES:
            body, k = _pat(pre + old).subn(lambda m, p=pre, v=new: p + v, body)
            total += k
    print("繰り上げ: %d 箇所" % total)
    if total != 23:
        raise SystemExit("繰り上げの件数が想定と違う: %d（想定23）" % total)

    text = head + body + tail + NOTE16
    with io.open(DEST, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("-> %s" % DEST)


NOTE16 = """

---

## 付記16：Suppl Fig S1 の削除と補遺の引用漏れ（v14・2026-09-07）

投稿前の最終チェックで見つかった、原稿の外形上の問題を処理した。数値の再計算はない。
投稿用 docx（`投稿用v14/NDB抗アレルギー解析_v14_clean.docx`）が正である。

### 16-1. Supplementary Figure S1 を投稿対象から外し、S2〜S5 を繰り上げた

`投稿改定ver/SupplFigure_en_README.md`（2026-09-06）は Suppl Fig S1（欠測3層構造の
模式図）を「教室内向けの解説資料であり投稿には含めない」としていたが、原稿には
legend が残り、投稿用フォルダの README も提出物として掲載していた。実際 S1 は

- 本文から一度も引用されていない（legend にしか現れない）
- 図中が全面日本語で、英語版が存在しない
- 図中の数値が v9 以前のままで本文と矛盾する

という状態であった。図中の古い数値は次の4点である。

| S1 の記載 | 原稿 v13・データ |
|---|---|
| 2024年度 52品目（延べ62行）、上限合計 245,754 mL＝0.105% | 55品目・65行・260,739 mL・0.111% |
| 第9〜10回:上位500 のみ公開 | 薬効分類内の医薬品数に応じて上位100／300／500（付記15-2 の項目8） |
| レボカバスチン2014年度 公表値の+427% | +384%（Suppl Table S3 `upper1_width_pct`） |
| クロモグリク酸Na 2015〜2018年度 +16,000% | +17,550〜+24,949%（同上） |

方針は「提出から外して繰り上げ」とした。Supplementary Figure S2〜S5 を **S1〜S4** に
繰り上げ、S1 の legend を削除した（docx 13箇所、本作業原稿の本文23箇所）。
繰り上げは本文（§1〜§10）のみに適用し、冒頭の版歴ブロックと付記1〜15 は改訂の記録
であるため当時の番号のまま残してある。

| 旧 | 新 | 内容 |
|---|---|---|
| Suppl Fig S1 | （削除） | 欠測3層構造の模式図 |
| Suppl Fig S2 | **S1** | 後発品比率と製剤構成の推移 |
| Suppl Fig S3 | **S2** | 主要3成分合計の男/女比（フォレスト） |
| Suppl Fig S4 | **S3** | 全国処方量（mL）の推移と識別区間 |
| Suppl Fig S5 | **S4** | 品目非掲載まで拡張した感度分析 |

### 16-2. 本文から引用されていなかった補遺に引用を付けた

docx の本文で一度も引用されていない補遺が4点あった。うち Suppl Fig S1 は 16-1 で
削除し、残る3点に引用を追加した。

| 補遺 | 追加した場所 |
|---|---|
| Supplementary Table S1（対象品目一覧・mL換算係数） | Methods「Outcome measure」の単位正規化 |
| Supplementary Table S6（上限を構成する2つの加算の内訳） | Results「Temporal trends」冒頭 |
| Supplementary Figure S3（旧S4。処方量mLの推移） | 同上（従来は Figure 4 の legend のみ） |

この結果、補遺図の初出順は S1→S2→S3→S4 の昇順になった。補遺表の初出順は依然として
昇順ではない（付記11-3）。

### 16-3. 作業原稿に取り残されていた数値を docx と同期した

v13 で docx にだけ反映され、本作業原稿に旧値が残っていた3件を直した。

| 箇所 | 旧 | 新 | 根拠 |
|---|---|---|---|
| 抄録 | 15歳以上の全階級で女性優位 | 15〜94歳の全階級（95歳以上は判定不能） | 付記15-2 の項目6 |
| 抄録・§3.7 | +50〜+430%（クロモグリク酸Naでは+16,000%超） | +30〜+983%（同+17,550%超） | Suppl Table S3 `upper1_width_pct` |
| §4.6 | 2015〜2018年度で+16,000%超 | +17,550%超 | 同上 |

### 16-4. 抄録を圧縮した

圧縮前の抄録は和文1,293字で、英訳すると約435語になり、構造化抄録の一般的な上限
（250〜300語）に収まらなかった。数値と主張は落とさず、**Methods の解法の詳細**
（準凸性・頂点探索・Dinkelbach型二分探索）と、**Results の人口10万対の値・
クロモグリク酸Naの内訳・後発品シェアの区間幅**を本文に委ねて詰めた。

| | 圧縮前 | 圧縮後 |
|---|---|---|
| Background | 207字 | 126字 |
| Methods | 380字 | 241字 |
| Results | 503字 | 362字 |
| Conclusions | 203字 | 184字 |
| 合計 | 1,293字（英訳で約435語） | 913字（英訳で**299語**、見出し語込み303語） |

250語制限の投稿先に当たった場合は、県間格差（ジニ係数・変動係数）に触れる
**Methods 1文と Results 1文**を対で落とす（40語減、263語）。作業原稿の抄録では
この2文に ※ を付してある。圧縮前の版は `投稿用v13/NDB抗アレルギー解析_v13_clean.docx`
に残っている。

なお圧縮に伴い、作業原稿の抄録の見出しを docx に合わせて
**Purpose → Background** に改め、docx と同一の本文にした。v13 まで作業原稿の抄録だけに
残っていた「15歳以上の全階級で女性優位」（16-3）も、この差し替えで解消している。

### 16-5. Figure4.png を pptx から書き出し直した

付記15-1 で `Figure4.pptx` の英文キャプションを 1.9x→1.8x、37.7→35.7 pp に訂正したが、
**PNG を書き出し直していなかった**ため、`投稿用v13/Figure4.png` には訂正前の
「1.9x」「37.7 pp」が残っていた。v14 では Figure2・Figure4・Figure6 の PNG を
pptx から書き出し直した（Figure2・Figure6 は 16-1 の繰り上げでキャプション中の
Suppl Fig 番号が変わるため）。

### 16-6. 未処理（投稿前に著者が埋めること）

- **文献23件のうち21件が空欄**（埋まっているのは #2 Dupuis と #20 Fujishima のみ）。
- **Data availability の記述が事実と異なる**。GitHub リポジトリ
  `saruko/ndb_ophthalmology_trends` のリモートには本解析のコードが1件も入っていない
  （`origin/main` は別解析）。公開するか、記述を実態に合わせるかの判断が要る。
- **Conflict of interest**（「要相談」のまま）・**Author contributions**（空欄）。
- **著者名・所属・責任著者・Running title**（タイトルページが未作成）。
- **補遺表の初出順**が昇順でない（S2→S1→S7→S11→…。付記11-3）。
- **本文図PNGに解像度情報がない**（dpi タグなし。補遺図は300 dpi）。

### 16-7. 再生成

```
python apply_docx_v14.py     # 原稿 v14（履歴つき／clean）
python apply_md_v14.py       # 本ファイル
python build_v14_folder.py   # 図表を v13 から複製・S番号の繰り上げ・PNG再書き出し
python verify_v14.py         # 検証
```
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
