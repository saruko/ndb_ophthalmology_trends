# -*- coding: utf-8 -*-
"""原稿 docx の「小児」のうち、データに基づく記述を具体的な年齢階級に置き換える。

「小児」の定義（乳児/幼児/学童/思春期の含み方）は文脈により幅があり、NDBオープンデータの
集計単位（5歳刻み）と一対一に対応しない。数値を伴う記述では階級を明示する。
制度名（小児医療費助成）と一般的な臨床概念（小児期のアレルギー疾患）はそのまま残す。

編集は変更履歴（author="Claude"）として入れる。
"""
import os
import shutil

import docx
from docx.oxml.ns import qn

from docx_track import TrackedEditor

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "05_論文成果物", "公費含めない_new")
SRC = os.path.join(OUT, "NDB抗アレルギー解析_ver公費なしnew.docx")
BACKUP = os.path.join(OUT, "NDB抗アレルギー解析_ver公費なしnew_backup_20260821.docx")
DATE = "2026-08-21T00:00:00Z"


def text_of(el):
    return "".join(n.text or "" for n in el.iter(qn("w:t")))


def para_by(doc, needle):
    for p in doc.paragraphs:
        if needle in text_of(p._p):
            return p
    raise KeyError(needle[:40])


def main():
    if not os.path.exists(BACKUP):
        shutil.copyfile(SRC, BACKUP)
        print("-> backup %s" % os.path.basename(BACKUP))
    d = docx.Document(SRC)
    ed = TrackedEditor(DATE)

    # --- Limitations（第一の限界：mLベースの過小評価） ---
    p = para_by(d, "第一に、アウトカムは処方数量（mL）であり")
    ed.replace(p, "mLベースで観察された小児側の処方量は、実際の処方実態に対して過小評価方向の値である。",
               "mLベースで観察された0〜14歳の処方量は、実際の処方実態に対して過小評価方向の値である。")
    ed.replace(p, "その0.1%製剤シェアは小児で高く（0–4歳83.0%、5–9歳82.7%）、"
                  "高齢者で低い（70〜84歳56〜58%；Results参照）",
               "その0.1%製剤シェアは0〜14歳で高く（0〜4歳83.0%、5〜9歳82.7%、10〜14歳78.7%）、"
               "70歳以上で低い（70〜84歳56〜58%、85歳以上54〜55%；Results参照）")
    ed.replace(p, "したがってmLベースでは小児側の処方量が相対的に目減りしており、"
                  "真の小児優位はmLベースの値を上回ると考えられる。",
               "したがってmLベースでは0〜14歳の処方量が相対的に目減りしており、"
               "0〜14歳の真の優位はmLベースの値を上回ると考えられる。")

    # --- Results（Figure 5B の記述） ---
    ed.replace(para_by(d, "2024年度の0.1%製剤の割合は年齢によっても異なり"),
               "10〜14歳78.7%と小児で高く", "10〜14歳78.7%と0〜14歳で高く")

    # --- Discussion（性差の段落。制度名・臨床概念としての「小児」は残す） ---
    p = para_by(d, "本研究で観察された男女差は14歳を境に方向が反転した")
    ed.replace(p, "小児のアレルギー性結膜疾患が処方量の面で本剤群の中心的な対象であることを示す",
               "0〜14歳のアレルギー性結膜疾患が処方量の面で本剤群の中心的な対象であることを示す")
    ed.replace(p, "小児医療費助成のような保険と公費の併用は含まれるため、小児の値が系統的に欠落しているわけでない",
               "小児医療費助成のような保険と公費の併用は含まれるため、0〜14歳の値が系統的に欠落しているわけではない")

    d.save(SRC)
    print("-> %s（変更履歴 %d 件）" % (os.path.basename(SRC), ed.n))


if __name__ == "__main__":
    main()
