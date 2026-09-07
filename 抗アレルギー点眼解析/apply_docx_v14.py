# -*- coding: utf-8 -*-
"""原稿 v13 → v14 の改訂を変更履歴つきで適用する。

v14 は数値の再計算を伴わない。投稿前の最終チェックで見つかった、
補遺の引用漏れと Supplementary Figure S1 の去就を処理する改訂である。

改訂の柱
--------
A. Supplementary Figure S1（欠測3層構造の模式図）を投稿対象から外す。
   教室内向けの解説資料であり（`投稿改定ver/SupplFigure_en_README.md`）、
   本文からは一度も引用されておらず、図中の数値が v9 以前のまま
   （52品目・62行・245,754 mL・0.105%／第9〜10回は上位500のみ／
   レボカバスチン+427%／クロモグリク酸Na +16,000%）で本文と矛盾していた。
   legend を削除し、Supplementary Figure S2〜S5 を S1〜S4 に繰り上げる。
B. 本文から一度も引用されていなかった補遺に引用を付ける。
   - Supplementary Table S1（対象品目一覧・mL換算係数）→ Methods「Outcome measure」
   - Supplementary Table S6（上限の2つの加算の内訳）→ Results「Temporal trends」
   - Supplementary Figure S4（→新S3。処方量mLの推移）→ 同上
     （これまで Figure 4 の legend でしか引用されていなかった）
   この結果、補遺図の初出順は S1→S2→S3→S4 の昇順になる。

出力（投稿用v14/）:
    NDB抗アレルギー解析_v14.docx           変更履歴つき（教室内回覧用）
    NDB抗アレルギー解析_v14_clean.docx     履歴確定・コメントなし（投稿用）

実行: python apply_docx_v14.py
"""
import os
import sys

from docx import Document

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from docx_track import TrackedEditor                     # noqa: E402
import docx_finalize as F                                # noqa: E402

NEW = os.path.join(BASE, "05_論文成果物", "公費含めない_new")
V13 = os.path.join(NEW, "投稿改定ver", "投稿用v13")
V14 = os.path.join(NEW, "投稿改定ver", "投稿用v14")
SRC = os.path.join(V13, "NDB抗アレルギー解析_v13_clean.docx")
DEST = os.path.join(V14, "NDB抗アレルギー解析_v14.docx")
DEST_CLEAN = os.path.join(V14, "NDB抗アレルギー解析_v14_clean.docx")
DATE = "2026-09-07T12:00:00Z"

# 削除する legend（Supplementary Figure S1）
DROP_LEGEND = "Supplementary Figure S1. NDBオープンデータの欠測の3層構造"

# 繰り上げ。昇順に適用すること（S2→S1 を先に済ませれば S3→S2 が S1 に波及しない）。
RENUMBER = [("Supplementary Figure S2", "Supplementary Figure S1"),
            ("Supplementary Figure S3", "Supplementary Figure S2"),
            ("Supplementary Figure S4", "Supplementary Figure S3"),
            ("Supplementary Figure S5", "Supplementary Figure S4")]

# 補遺の引用追加。RENUMBER のあとに適用するので、新しい番号で書く。
# (anchor, old, new)
CITE = [
    # Supplementary Table S1（対象品目一覧・mL換算係数）
    ("NDBの処方数量の単位は成分により",
     "成分をまたいだ合算・シェア算出はすべてmL換算後に行った。",
     "対象品目の一覧と品目ごとのmL換算係数およびその根拠は"
     "Supplementary Table S1 に示した。"
     "成分をまたいだ合算・シェア算出はすべてmL換算後に行った。"),
    # Supplementary Table S6（上限の内訳）と Supplementary Figure S3（旧S4）
    ("2014〜2024年度の処方量の経年変化を検討した。",
     "成分別・集計別の年次値と識別区間はSupplementary Table S5に、"
     "増減の判定はSupplementary Table S4に示す。",
     "成分別・集計別の年次値と識別区間はSupplementary Table S5に、"
     "増減の判定はSupplementary Table S4に、"
     "主要3成分の上限を構成する2つの加算（総計秘匿による加算と未収載品目による加算）の"
     "内訳はSupplementary Table S6に示す。"
     "人口で割る前の処方数量（mL）の推移と識別区間はSupplementary Figure S3に図示した。"),
]


# C. 抄録の圧縮。和文1,293字（英訳で約435語）は構造化抄録の枠（250〜300語）に
#    収まらない。数値と主張は落とさず、Methods の解法の詳細と Results の
#    人口10万対の値・クロモグリク酸Naの内訳を本文に委ねて約300語に詰める。
#    ※ は250語制限の投稿先に当たった場合の削除候補（原稿 付記16-4）。
ABSTRACT = [
    ("Background: アレルギー性結膜疾患",
     "Background: アレルギー性結膜疾患は日本で有病率が高いが、抗アレルギー点眼薬の"
     "全年齢・全国にわたる長期の処方実態は明らかでない。本研究は、"
     "9成分の全国処方量と成分構成の11年間の変化を、公開データの欠測構造を明示して"
     "記述することを目的とした。"),
    ("Methods: NDBオープンデータ第1回",
     "Methods: NDBオープンデータ第1〜11回（2014〜2024年度）を用いた後ろ向き記述研究"
     "である。抗アレルギー点眼薬9成分を対象に、公費レセプトを含まない集計に統一して"
     "処方数量をmLに正規化した。本データはセル秘匿・総計秘匿・品目非掲載という3層の"
     "欠測をもつため、分布仮定を置かず識別区間として結果を提示した。"
     "都道府県間格差は、集計整合性制約（県別合計は全国総計を超えない）の下で"
     "ジニ係数と変動係数の識別区間として評価した。"
     "成分間シェアの比較は2022年度以降に限定した。"),
    ("Results: 2024年度の9成分合計",
     "Results: 2024年度の9成分合計は234.8〜235.1百万mL（識別区間の幅0.111%）で"
     "あった。エピナスチンは14.5百万mL（2014年度）から118.2百万mL（2024年度）へ、"
     "主要3成分合計は2015年度を起点として、いずれも識別区間を含めて増加が確定した。"
     "2022年度起点では両者とも減少が確定する一方、エピナスチンのみ実数でも増加して"
     "シェアは44.0%から50.3〜50.4%へ上昇し、内部では1日2回点眼の0.1%製剤が65.0%に"
     "達した。処方量は5〜14歳が最多で、性比は14歳を境に男性優位から女性優位へ"
     "転換した。都道府県間には少なくとも2.6倍の差があり、エピナスチン・"
     "オロパタジンでは格差の縮小が確定した。2021年度以前は品目非掲載により成分別の上限が公表値を"
     "30〜983%上回った。"),
    ("Conclusions: エピナスチンは2014年度以降",
     "Conclusions: エピナスチンは2014年度以降一貫して増加し、2024年度には"
     "抗アレルギー点眼薬の約半数を占め、高濃度製剤と後発医薬品への移行が進んだ。"
     "NDBオープンデータの秘匿は2022年度以降の全国集計にはほとんど影響しない一方、"
     "2021年度以前の成分間比較を本質的に制約する。識別区間による提示は、この制約を"
     "明示したまま動向を記述することを可能にする。"),
]


def find(paras, needle, start=0):
    for i in range(start, len(paras)):
        if needle in paras[i].text:
            return i
    raise KeyError(needle[:60])


def replace_everywhere(ed, paras, old, new):
    """全段落の old を new に置き換える。同一段落に複数あってもよい。"""
    n = 0
    for par in paras:
        while old in par.text:
            ed.replace(par, old, new)
            n += 1
    return n


def main():
    os.makedirs(V14, exist_ok=True)
    doc = Document(SRC)
    a0 = F.audit(SRC)
    assert a0["w:ins"] == 0 and a0["w:del"] == 0, a0     # v13 clean が基準
    P = doc.paragraphs
    ed = TrackedEditor(DATE)

    # A-1. Supplementary Figure S1 の legend を削除
    i = find(P, DROP_LEGEND)
    ed.delete_paragraph(P[i])
    print("legend 削除: 段落 %d" % i)

    # A-2. Supplementary Figure S2〜S5 → S1〜S4
    total = 0
    for old, new in RENUMBER:
        k = replace_everywhere(ed, P, old, new)
        print("  %s -> %s : %d 箇所" % (old, new, k))
        total += k
    if total != 13:
        raise SystemExit("繰り上げの件数が想定と違う: %d（想定13）" % total)

    # B. 補遺の引用追加
    for anchor, old, new in CITE:
        j = find(P, anchor)
        if old not in P[j].text:
            raise KeyError("段落は見つかったが置換元がない: %s / %s"
                           % (anchor[:20], old[:40]))
        ed.replace(P[j], old, new)
        print("引用追加: 段落 %d" % j)

    # C. 抄録の圧縮
    before = after = 0
    for prefix, new in ABSTRACT:
        j = find(P, prefix)
        old = P[j].text.rstrip()
        before += len(old)
        after += len(new)
        ed.replace(P[j], old, new)
    print("抄録: %d字 -> %d字（-%d%%）"
          % (before, after, round((1 - after / before) * 100)))

    doc.save(DEST)
    print("-> %s （変更履歴つき）" % DEST)

    d2 = Document(DEST)
    print("accept:", F.accept_revisions(d2))
    d2.save(DEST_CLEAN)
    print("audit clean:", F.audit(DEST_CLEAN))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
