# -*- coding: utf-8 -*-
"""v11 docx に、ジニ係数・CV の識別区間の大域最適性の訂正を変更履歴つきで反映する。

指摘（妥当）: 原稿は「極値は区間の端点で達成される」としていたが、これは最小側で偽。
準凸関数の最大は箱の頂点で達成されるが、最小は内点をとりうる。旧実装は最小も頂点上で
探索していたため、識別区間が内側に狭すぎた（inner bound）。

出力:
  投稿用v11/NDB抗アレルギー解析_verジニ+改定_v11rev.docx        （変更履歴つき）
  投稿用v11/NDB抗アレルギー解析_verジニ+改定_v11rev_マークなし.docx
"""
import os
import sys

from docx import Document

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from docx_track import TrackedEditor, _ParaLike        # noqa: E402

V11 = os.path.join(BASE, "05_論文成果物", "公費含めない_new", "投稿改定ver",
                   "投稿用v11")
SRC = os.path.join(V11, "NDB抗アレルギー解析_verジニ+改定_v11.docx")
DEST = os.path.join(V11, "NDB抗アレルギー解析_verジニ+改定_v11rev.docx")
# 履歴確定版は _v11.docx 自体にも上書きする（バックアップを取ってから）
INPLACE = SRC
DEST_CLEAN = os.path.join(V11,
                          "NDB抗アレルギー解析_verジニ+改定_v11rev_マークなし.docx")
DATE = "2026-09-04T09:00:00Z"

# ---- Methods に追加する段落（Statistical analysis 内） ----------------
METHOD_PARAS = [
    "地域格差指標の識別区間：都道府県間格差の要約指標として、47都道府県の人口10万対"
    "処方量（人口で重み付けしない県単位の値）に対する変動係数（CV＝標準偏差／平均）と"
    "ジニ係数を算出した。各県の真値が識別区間［下限, 上限］内の任意の値を取りうることを"
    "踏まえ、指標そのものも点推定ではなく識別区間として提示する。最小と最大では最適化の"
    "性質が異なるため、別々の解法を用いた。",

    "CV・ジニ係数はいずれも x ≧ 0 上で準凸である（CV の劣位集合 {x : n·Σx² ≦ "
    "(α+1)(Σx)²} は二次錐、ジニ係数の劣位集合 {x : ΣΣ|xᵢ−xⱼ| ≦ α·2n·Σx} は"
    "凸多面体で、いずれも凸集合）。準凸関数の最大は箱の頂点で達成されるため、"
    "最大は各県を下限か上限に置く組み合わせの座標上昇（構造化初期値と乱数初期値の"
    "計368通り）で探索した。一方、最小は箱の内点で達成されうる。識別区間が重なる県"
    "どうしを同じ値に揃えるとばらつきが下がるためであり、全県の区間に共通点があれば"
    "最小は0になる。したがって頂点のみを探索すると最小を過大評価し、識別区間が"
    "内側に狭くなる。",

    "そこで最小は、両指標が0次同次であること（x を定数倍しても値が不変）を利用して"
    "厳密に解いた。y = t·x、Σy = 1、t ≧ 0 と置くと箱は線形制約 t·下限 ≦ y ≦ t·上限 に"
    "変換され、ジニ係数の最小化は線形計画、CV の最小化は Σy² の最小化（t を固定すると"
    "箱と超平面の交わりへの射影で閉形式が得られ、値関数は t について凸）となり、"
    "いずれも大域最適解が得られる。最大についても、ジニ係数は Σᵣ wᵣ·y₍ᵣ₎/(n·Σy)"
    "（wᵣ = 2r−n−1、r は昇順の順位）と書けることを使い、県と順位の対応を自由にしてよいと"
    "緩めた割当問題とDinkelbach型の二分探索により valid な上界を計算した。"
    "その結果、全44セル（4系列×11年度）で探索値と上界が一致し、最大が大域最適で"
    "あることを確認した。参考として、下限（＝公表値）のみで計算した値を併記した。",
]

# ---- 数値の差し替え ---------------------------------------------------
REPLACEMENTS = [
    # Results §（都道府県）
    ("2024年度のジニ係数は、主要3成分合計0.084〜0.130（公表値のみで計算すると0.117）、"
     "エピナスチン0.111〜0.140（同0.133）、オロパタジン0.079〜0.139（同0.118）、"
     "レボカバスチン0.107〜0.231（同0.180）、CVはそれぞれ0.155〜0.231（同0.209）、"
     "0.198〜0.245（同0.234）、0.152〜0.248（同0.218）、0.190〜0.408（同0.322）であった。",
     "2024年度のジニ係数は、主要3成分合計0.083〜0.130（公表値のみで計算すると0.117）、"
     "エピナスチン0.111〜0.139（同0.133）、オロパタジン0.078〜0.139（同0.118）、"
     "レボカバスチン0.083〜0.231（同0.180）、CVはそれぞれ0.154〜0.230（同0.209）、"
     "0.198〜0.245（同0.233）、0.152〜0.248（同0.218）、0.161〜0.408（同0.322）であった。"),
    # Results §（経年）
    ("オロパタジンは2014年度（0.129〜0.131）と2024年度（0.079〜0.139）の区間が重なるため",
     "オロパタジンは2014年度（0.129〜0.131）と2024年度（0.078〜0.139）の区間が重なるため"),
    # Discussion
    ("2024年度の主要3成分合計のジニ係数は0.084〜0.130、CVは0.155〜0.231であった（Figure 7）。",
     "2024年度の主要3成分合計のジニ係数は0.083〜0.130、CVは0.154〜0.230であった（Figure 7）。"),
    # Figure 7 legend（破線＝識別できていない年度、の描き分けを明記）
    ("レボカバスチン（後発品が2021年度以前非掲載）とそれを含む主要3成分合計は2022年度以降に"
     "限定する（それ以前は公表品目のみに基づく参考値）。レボカバスチンは処方量が小さく"
     "秘匿セルの比率が高いため区間が最も広い（2015–2017年度はCVの上限が軸の範囲外に達する）。",
     "レボカバスチン（後発品が2021年度以前非掲載）とそれを含む主要3成分合計は2022年度以降に"
     "限定する。識別できていない年度（レボカバスチンと主要3成分合計の2014–2021年度）は"
     "破線と白抜きマーカーで描き分けた。当該年度は区間がほぼ0から最大値まで開くため中点は"
     "水準の情報を持たず、2015–2017年度に見えるピークは格差の上昇ではなく欠測の産物である"
     "（レボカバスチン2015年度のジニ係数の区間は0.000–0.733、CVは0.000–3.171）。"
     "実線と塗りつぶしマーカーが比較可能な年度を示す。"),
    # 丸めの訂正（cv_max 0.23049→0.230、gini_max 0.13946→0.139）。
    # 0.231/0.140 は v11 以前からの誤りで、今回の再計算とは独立。
    ("2024年度（ジニ係数0.111〜0.140、CV 0.198〜0.245）への縮小が識別区間を含めて確定した。",
     "2024年度（ジニ係数0.111〜0.139、CV 0.198〜0.245）への縮小が識別区間を含めて確定した。"),
]


def find(paras, needle):
    for p in paras:
        if needle in p.text:
            return p
    raise KeyError(needle[:60])


def main():
    doc = Document(SRC)
    ed = TrackedEditor(DATE)
    P = doc.paragraphs
    n = 0

    for old, new in REPLACEMENTS:
        p = find(P, old)          # 完全一致で段落を特定する（短い接頭辞だと誤ヒットする）
        ed.replace(p, old, new)
        n += 1

    # Statistical analysis の「秘匿の影響」段落の直前に手法の記述を差し込む
    anchor = find(P, "秘匿の影響：全国集計には公表「総計」列を用いた")
    prev = P[P.index(anchor) - 1]
    a = prev
    for txt in METHOD_PARAS:
        newp = ed.add_paragraph_after_styled(a, txt, anchor)
        a = _ParaLike(newp)
    n += 1

    doc.save(DEST)
    print("-> %s （変更履歴つき、%d 箇所）" % (DEST, n))
    return DEST


def make_clean(path):
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    doc = Document(path)
    body = doc.element.body
    dropped = 0
    for para in list(body.iter("{%s}p" % W)):
        pPr = para.find("{%s}pPr" % W)
        if pPr is None:
            continue
        rPr = pPr.find("{%s}rPr" % W)
        if rPr is None or rPr.find("{%s}del" % W) is None:
            continue
        parent = para.getparent()
        if parent is not None:
            parent.remove(para)
            dropped += 1
    for el in list(body.iter("{%s}del" % W)):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    for el in list(body.iter("{%s}ins" % W)):
        parent = el.getparent()
        if parent is None:
            continue
        idx = list(parent).index(el)
        for k, ch in enumerate(list(el)):
            el.remove(ch)
            parent.insert(idx + k, ch)
        parent.remove(el)
    doc.save(DEST_CLEAN)
    print("-> %s （履歴確定版、削除段落 %d）" % (DEST_CLEAN, dropped))


if __name__ == "__main__":
    make_clean(main())
