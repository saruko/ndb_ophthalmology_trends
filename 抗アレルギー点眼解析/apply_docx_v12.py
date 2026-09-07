# -*- coding: utf-8 -*-
"""原稿 v11 → v12 の改訂を変更履歴つきで適用する。

改訂の柱
--------
1. 都道府県間格差指標（ジニ係数・CV）の識別区間を、箱制約のみの外側包絡から
   **全国総計との集計整合性制約を課した共同実行可能集合**上の区間に置き換える。
   数値は ジニ係数あり/gini_cv_bounds.csv から読み、原稿に手で書かない。
2. タイトルを研究対象（抗アレルギー点眼薬9成分）と整合させる。
3. 未収載品目の上限式を品目ごとの換算係数 c_i で定義し直し、実装で用いている
   c(d,y)=max_i c_i による置換の妥当性と過大評価の大きさを明記する。
4. 「2022〜2024年度は点識別」を第3層（品目非掲載）限定に修正する
   （第2層の総計秘匿による区間は残るため）。
5. 根拠のない解釈（ジニ0.1前後＝極端でない／外れ値に頑健／患者数ベースの外挿）を
   削るか、仮定を明示した条件つきの記述に改める。
6. 制度的背景（2024年10月の長期収載品の選定療養、小児医療費助成の対象年齢）と
   0.1%後発医薬品の収載時期を Discussion に追加する。
7. 早期公開のままだった文献5件を確定した書誌情報に更新し、選定療養の出典を追加する。

入力の docx には査読・共著者回覧時の変更履歴とWordコメントが残っているため、
まずそれらを確定・除去して v12 の基準版を作り、そのうえで本改訂を履歴として乗せる。

出力（投稿用v12/）:
    NDB抗アレルギー解析_v12.docx           変更履歴つき（教室内回覧用）
    NDB抗アレルギー解析_v12_clean.docx     履歴確定・コメントなし（投稿用）

実行: C:\\Users\\goodt\\anaconda3\\python.exe apply_docx_v12.py
"""
import math
import os
import shutil
import sys

import pandas as pd
from docx import Document

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from docx_track import TrackedEditor, _ParaLike          # noqa: E402
import docx_finalize as F                                # noqa: E402

NEW = os.path.join(BASE, "05_論文成果物", "公費含めない_new")
V11 = os.path.join(NEW, "投稿改定ver", "投稿用v11")
V12 = os.path.join(NEW, "投稿改定ver", "投稿用v12")
SRC = os.path.join(V11, "NDB抗アレルギー解析_verジニ+改定_v11_num.docx")
BASE_DOC = os.path.join(V12, "_v12_base.docx")
DEST = os.path.join(V12, "NDB抗アレルギー解析_v12.docx")
DEST_CLEAN = os.path.join(V12, "NDB抗アレルギー解析_v12_clean.docx")
GINI = os.path.join(NEW, "ジニ係数あり", "gini_cv_bounds.csv")
DATE = "2026-09-06T09:00:00Z"

SER_JA = {"TOP3": "主要3成分合計", "Epinastine": "エピナスチン",
          "Olopatadine": "オロパタジン", "Levocabastine": "レボカバスチン"}


# ------------------------------------------------------------------ 数値
class Numbers:
    """gini_cv_bounds.csv から原稿に載せる数値を組み立てる。"""

    def __init__(self, path):
        self.d = pd.read_csv(path)

    def _row(self, series, year):
        r = self.d[(self.d.series == series) & (self.d.year == year)]
        assert len(r) == 1, (series, year)
        return r.iloc[0]

    @staticmethod
    def _floor(v, nd):
        return f"{math.floor(v * 10 ** nd) / 10 ** nd:.{nd}f}"

    @staticmethod
    def _ceil(v, nd):
        return f"{math.ceil(v * 10 ** nd) / 10 ** nd:.{nd}f}"

    def iv(self, series, year, metric, nd=3, suffix=""):
        """識別区間の表示。下限は切り捨て、上限は切り上げ。

        四捨五入すると表示区間が計算値より狭くなりうる（例: 上限0.1225→0.122）。
        識別区間は「真値がこの範囲にある」という主張なので、表示も外向きに丸める。
        """
        r = self._row(series, year)
        return (self._floor(r[metric + "_min" + suffix], nd) + "〜"
                + self._ceil(r[metric + "_max" + suffix], nd))

    def pub(self, series, year, metric, nd=3):
        return f"{self._row(series, year)[metric + '_published']:.{nd}f}"

    def box(self, series, year, metric, nd=3):
        return self.iv(series, year, metric, nd, suffix="_boxonly")

    def val(self, series, year, col):
        return float(self._row(series, year)[col])

    def disjoint(self, series, y0, y1, metric):
        """y0 と y1 の区間が重ならないか（重ならなければ方向が確定する）。"""
        a, b = self._row(series, y0), self._row(series, y1)
        return (a[metric + "_max"] < b[metric + "_min"]
                or b[metric + "_max"] < a[metric + "_min"])

    def width_reduction(self, metric):
        """箱制約のみに対する区間幅の縮小率（比較可能年度、点識別のセルは除く）。

        戻り値は (中央値, 最小, 最大)。
        """
        rows = []
        for s, y0 in (("TOP3", 2022), ("Epinastine", 2014),
                      ("Olopatadine", 2014), ("Levocabastine", 2022)):
            sub = self.d[(self.d.series == s) & (self.d.year >= y0)]
            for _, r in sub.iterrows():
                v = r.get(metric + "_width_reduction_pct")
                if v is not None and v == v:            # NaN を除く
                    rows.append(float(v))
        rows.sort()
        med = rows[len(rows) // 2] if len(rows) % 2 else \
            0.5 * (rows[len(rows) // 2 - 1] + rows[len(rows) // 2])
        return med, rows[0], rows[-1]

    def gini_all_certified(self):
        return bool(self.d["gini_max_certified"].all())

    def n_certified(self):
        return int(self.d["gini_max_certified"].sum()), len(self.d)


# ------------------------------------------------------------------ 補助
def find(paras, needle, start=0):
    for i in range(start, len(paras)):
        if needle in paras[i].text:
            return i
    raise KeyError(needle[:60])


def replace_in(ed, paras, needle, old, new):
    ed.replace(paras[find(paras, needle)], old, new)


# ------------------------------------------------------------------ 本体
def build_methods_paragraphs(N):
    med, lo, hi = N.width_reduction("gini")
    n_ok, n_all = N.n_certified()
    gap = N.d["gini_max_gap"].max()
    cert = (f"全{n_all}セル（4系列×11年度）で達成値と一致し、最大値が大域最適で"
            "あることを確認した" if n_ok == n_all else
            f"{n_all}セル中{n_ok}セルで達成値と上界が一致して大域最適が確定し、"
            # 上界の主張なので切り上げる（.4f だと 0.000123 が「0.0001以下」になり偽になる）
            f"残る{n_all - n_ok}セルでも両者の差は{math.ceil(gap * 1e4) / 1e4:.4f}以下で、"
            "本稿が示す小数第3位までの表示には影響しなかった")
    return [
        "都道府県間格差の要約指標として、47都道府県の人口10万対処方量（人口で重み付け"
        "しない県単位の値）に対する変動係数（CV＝標準偏差／平均）とジニ係数を算出した"
        "（主要3成分合計とエピナスチン・オロパタジン・レボカバスチンの各単剤の4系列、"
        "2014〜2024年度。Figure 7）。これらの指標も点推定ではなく識別区間として提示した。",

        "真値ベクトル x＝(x_1, …, x_47) が動く範囲は、各県の周辺識別区間の直積である箱 "
        "B＝Π_i［下限_i, 上限_i］ではなく、これに集計整合性の制約を課した共同実行可能"
        "集合とした。県別内訳と全国総計は同一の集計対象についての値であり、県別の絶対"
        "処方量の合計が全国総計を超えることはできないためである。県 i の人口を N_i、"
        "全国総計の識別区間の上限を S とすると、実行可能集合は "
        "F＝{ x ∈ B : Σ_i (N_i/100000)·x_i ≦ S } である。下側の制約（合計が全国総計の"
        "下限以上）は課していない。ブロック秘匿された品目は県別内訳から丸ごと脱落し、"
        "その分を県に配分できないためであり、上側のみであれば追加の仮定を要しない。"
        "実際、秘匿セルが1つも存在しない成分・年度（エピナスチンの2014・2015年度、"
        "レボカバスチンの2014年度）では Σ_i (N_i/100000)·x_i ／ S が 1.000000 となり、"
        "この制約がデータ生成上の恒等式であることが確認できる（Supplementary Table S10）。"
        "箱 B のみで評価すると、47県が同時に上限を取るような実在しえない配置を許すため、"
        "得られる区間は真の識別集合の外側包絡となり、valid ではあるが sharp ではない。"
        f"本研究の比較可能年度では、集計整合性制約を課すことでジニ係数の区間幅が"
        f"中央値{med:.0f}%（範囲{lo:.0f}〜{hi:.0f}%）狭まった"
        "（箱制約のみの値は Supplementary Table S10 に併記した）。",

        "F は凸多面体であり、CV・ジニ係数はいずれも x ≧ 0 上で準凸である（CVの劣位集合 "
        "{x : n·Σx² ≦ (α+1)(Σx)²} は二次錐、ジニ係数の劣位集合 "
        "{x : ΣΣ|x_i−x_j| ≦ α·2n·Σx} は凸多面体で、いずれも凸集合）。準凸関数の"
        "コンパクト凸集合上の最大は端点で達成されるため、最大は F の頂点を探索した。"
        "ここで F の頂点は箱 B の頂点（各県が下限か上限のいずれか）とは異なり、"
        "高々1県のみが内点値を取る点である。そこで、構造化初期値と乱数初期値の計368通りを"
        "制約に射影したうえで、合計を保存する転送移動（1県を上げ他の1県を下げる最大ステップ）"
        "による局所探索を行い、その達成値を真の最大値の下界とした。一方、最小値は内点で"
        "達成されうる（識別区間が重なる県どうしを等しい値に置くほど、ばらつきはさらに"
        "小さくなる）ため、頂点のみを探索すると最小値を過大評価する。",

        "最小値は、両指標が0次同次であること（x を定数倍しても値が不変）を用いて厳密に"
        "解いた。y＝t·x、Σy＝1、t ≧ 0 と置くと、箱制約も集計整合性制約もいずれも線形制約"
        "（t·下限 ≦ y ≦ t·上限、Σ_i (N_i/100000)·y_i ≦ t·S）に変換される。ジニ係数の"
        "最小化は線形計画に、CVの最小化は Σy² の最小化（t を固定すると2乗和最小化の射影と"
        "なり2つの乗数の二分法で閉形式に解ける。値関数は t について凸であるため三分探索で"
        "大域最小に到達する）に帰着し、いずれも大域最適解が得られる。",

        "最大値については、ジニ係数が Σ_r w_r·x_(r)/(n·Σx)（w_r＝2r−n−1、r は昇順の順位）"
        "と書けることを用い、県と順位の対応を自由にしてよいと緩めた割当問題に集計整合性"
        "制約のラグランジュ緩和を組み合わせ、Dinkelbach型の二分探索により valid な上界を"
        f"求めた。その結果、{cert}。CVについては、(Σx)² を接線で線形化して可分化した緩和"
        "により valid な上界を計算したが、これは達成値との一致を保証しない。したがって"
        "CVの最大値は達成値（真の最大値の下界）として提示し、上界は Supplementary Table "
        "S10 に併記した。",

        "Figure 7 には最小値と最大値の中点を描いた。最小値・最大値、下限（＝公表値）のみで"
        "計算した参考値、集計整合性制約を課さない箱制約のみの区間（感度分析）、および"
        "ジニ係数の最大値の証明付き上界は Supplementary Table S10 に示した。",
    ]


def main():
    os.makedirs(V12, exist_ok=True)
    N = Numbers(GINI)

    # ---- v12 の基準版（履歴確定・コメント除去） --------------------
    doc = Document(SRC)
    print("accept revisions:", F.accept_revisions(doc))
    doc.save(BASE_DOC)
    print("strip comment refs:", F.strip_comments(BASE_DOC))
    print("audit base:", F.audit(BASE_DOC))

    doc = Document(BASE_DOC)
    P = doc.paragraphs
    ed = TrackedEditor(DATE)
    n = 0

    # ---- 1. タイトル ------------------------------------------------
    ed.replace(P[find(P, "主要な抗ヒスタミン点眼薬の全国処方動向")],
               "主要な抗ヒスタミン点眼薬の全国処方動向 2014–2024年度："
               "NDBオープンデータの秘匿・非掲載を考慮した解析",
               "抗アレルギー点眼薬の全国処方動向 2014–2024年度："
               "NDBオープンデータの秘匿・非掲載を考慮した部分識別解析"); n += 1
    ed.replace(P[find(P, "National Prescription Trends for Major Antihistamine")],
               "National Prescription Trends for Major Antihistamine Eye Drops in Japan",
               "National Prescription Trends for Anti-allergic Eye Drops in Japan"); n += 1

    # ---- 2. Abstract ------------------------------------------------
    ed.replace(P[find(P, "Methods: NDBオープンデータ第1回")],
               "点推定ではなく識別区間として結果を提示した。",
               "点推定ではなく識別区間として結果を提示した。都道府県間格差の要約指標"
               "（ジニ係数・変動係数）は、各県の区間の直積ではなく、県別処方量の合計が"
               "全国総計を超えないという集計整合性制約を課した共同実行可能集合の上で"
               "最小・最大を求めた。"); n += 1

    olo_id = N.disjoint("Olopatadine", 2014, 2024, "gini")
    abst = ("都道府県間の処方量には少なくとも2.6倍の差があり、エピナスチンと"
            "オロパタジンの県間格差はいずれも縮小が確定した。") if olo_id else \
           ("都道府県間の処方量には少なくとも2.6倍の差があり、エピナスチンの県間格差は"
            "縮小が確定した。")
    ed.replace(P[find(P, "Results: 2024年度の9成分合計は")],
               "都道府県間の処方量には少なくとも2.6倍の差があり、"
               "エピナスチンの県間格差は縮小が確定した。", abst); n += 1

    # ---- 3. Methods: 未収載品目の上限式 -----------------------------
    ed.replace(P[find(P, "上限(d,y) = 公表総量(d,y)")],
               "上限(d,y) = 公表総量(d,y) + n(d,y) × Σ_s m(y,s) × c",
               "上限(d,y) = 公表総量(d,y) + Σ_{i=1}^{n(d,y)} c_i × Σ_s m(y,s)"); n += 1

    i50 = find(P, "この上限は追加の仮定を要しない。")
    ed.replace(P[i50],
               "c は未収載品目自身の単位に対応する換算係数（mL＝×1、瓶＝×5、個＝×0.35）"
               "であり、生値の上界 m(y,s) に当該品目の c を乗じることでmL単位の上界を"
               "得るため、両者は同一の次元で結合している。未収載品目の単位は薬価基準"
               "収載品目リストの規格表記から品目ごとに確定するため、c は品目単位で"
               "一意に定まる。",
               "c_i は未収載品目 i 自身の単位に対応するmL換算係数（mL＝×1、瓶＝×5、"
               "個＝×0.35）であり、生値の上界 m(y,s) に当該品目の c_i を乗じることで"
               "mL単位の上界を得るため、両者は同一の次元で結合している。実際の計算では "
               "c_i を成分・年度ごとの最大値 c(d,y)＝max_i c_i で置き換え、"
               "上限(d,y) = 公表総量(d,y) + n(d,y) × c(d,y) × Σ_s m(y,s) として評価した。"
               "max_i c_i ≧ c_i であるからこの置換は上限の validity を保つ。単位の異なる"
               "品目が未収載として混在するのは9成分×11年度のうち5セル（クロモグリク酸"
               "ナトリウムの2014・2019・2020年度、ケトチフェンの2014・2015年度）のみで、"
               "いずれもユニットドーズ製剤（個、×0.35）1品目に対し残り8〜16品目が瓶"
               "（×5）であるため、この置換による上限の過大評価は最大11.5%"
               "（クロモグリク酸ナトリウム2020年度）である。該当セルはいずれも足切り期に"
               "属し、解釈の対象とする2022〜2024年度には含まれない。"); n += 1

    # ---- 4. 「点識別」を第3層限定に（2箇所） ------------------------
    old_pt = "当該3年度は上限と下限が一致し、点識別となる。"
    new_pt = ("当該3年度は第3層による加算が生じず、品目非掲載に関しては点識別となる"
              "（第2層の総計秘匿による区間は残るため、当該年度の推計が全体として"
              "点識別になるわけではない）。")
    k = 0
    idx = 0
    while True:
        try:
            i = find(P, old_pt, idx)
        except KeyError:
            break
        ed.replace(P[i], old_pt, new_pt)
        idx = i + 1
        k += 1
    assert k == 2, k
    n += k

    # ---- 5. Methods: 地域格差指標の段落を差し替え -------------------
    i61 = find(P, "都道府県間格差の要約指標として、47都道府県の人口10万対処方量")
    anchor = P[i61]
    a = anchor
    for txt in build_methods_paragraphs(N):
        newp = ed.add_paragraph_after_styled(a, txt, anchor)
        a = _ParaLike(newp)
    ed.delete_paragraph(anchor)
    n += 1

    # ---- 6. Results: 2024年度の指標値 -------------------------------
    def iv(s, m):
        return N.iv(s, 2024, m)

    def pb(s, m):
        return N.pub(s, 2024, m)

    old78 = ("2024年度のジニ係数は、主要3成分合計0.083〜0.130（公表値のみで計算すると"
             "0.117）、エピナスチン0.111〜0.139（同0.133）、オロパタジン0.078〜0.139"
             "（同0.118）、レボカバスチン0.083〜0.231（同0.180）、CVはそれぞれ"
             "0.154〜0.230（同0.209）、0.198〜0.245（同0.233）、0.152〜0.248（同0.218）、"
             "0.161〜0.408（同0.322）であった。")
    new78 = (f"2024年度のジニ係数は、主要3成分合計{iv('TOP3','gini')}（公表値のみで"
             f"計算すると{pb('TOP3','gini')}）、エピナスチン{iv('Epinastine','gini')}"
             f"（同{pb('Epinastine','gini')}）、オロパタジン{iv('Olopatadine','gini')}"
             f"（同{pb('Olopatadine','gini')}）、レボカバスチン{iv('Levocabastine','gini')}"
             f"（同{pb('Levocabastine','gini')}）、CVはそれぞれ{iv('TOP3','cv')}"
             f"（同{pb('TOP3','cv')}）、{iv('Epinastine','cv')}（同{pb('Epinastine','cv')}）、"
             f"{iv('Olopatadine','cv')}（同{pb('Olopatadine','cv')}）、"
             f"{iv('Levocabastine','cv')}（同{pb('Levocabastine','cv')}）であった。")
    p78 = P[find(P, "47都道府県にわたる格差の要約指標")]
    ed.replace(p78, old78, new78); n += 1

    lev_top = (N.val("Levocabastine", 2024, "gini_min")
               > max(N.val(s, 2024, "gini_max")
                     for s in ("Epinastine", "Olopatadine")))
    old_lev = ("処方量が最も小さいレボカバスチンは、公表値ベースの格差が3成分中で最も"
               "大きい一方、秘匿セルの影響で区間も最も広く、エピナスチンとの区間が"
               "重なるため単剤間の順位づけは確定しない。")
    new_lev = ("処方量が最も小さいレボカバスチンは秘匿セルの影響で区間が3成分中で最も"
               "広いが、集計整合性制約を課すと区間の下限がエピナスチン・オロパタジンの"
               "上限を上回るため、レボカバスチンの県間格差が3成分中で最も大きいことは"
               "確定する。") if lev_top else \
              ("処方量が最も小さいレボカバスチンは、公表値ベースの格差が3成分中で最も"
               "大きい一方、秘匿セルの影響で区間も最も広く、他剤との区間が重なるため"
               "単剤間の順位づけは確定しない。")
    ed.replace(p78, old_lev, new_lev); n += 1

    # ---- 7. Results: 経年比較 ---------------------------------------
    p79 = P[find(P, "エピナスチンは県別区間が完全な2014年度")]
    epi = (f"エピナスチンは県別区間が完全な2014年度（ジニ係数"
           f"{N.pub('Epinastine',2014,'gini')}、CV {N.pub('Epinastine',2014,'cv')}、"
           f"いずれも区間幅0）を起点に、2024年度（ジニ係数{iv('Epinastine','gini')}、"
           f"CV {iv('Epinastine','cv')}）への縮小が識別区間を含めて確定した。")
    ed.replace(p79,
               "エピナスチンは県別区間が完全な2014年度（ジニ係数0.235、CV 0.415、"
               "いずれも区間幅0）を起点に、2024年度（ジニ係数0.111〜0.139、"
               "CV 0.198〜0.245）への縮小が識別区間を含めて確定した。", epi); n += 1

    olo_id = N.disjoint("Olopatadine", 2014, 2024, "gini")
    if olo_id:
        olo = (f"オロパタジンも2014年度（{N.iv('Olopatadine',2014,'gini')}）と"
               f"2024年度（{iv('Olopatadine','gini')}）の区間が重ならず、縮小が確定した"
               f"（公表値ベースでは{N.pub('Olopatadine',2014,'gini')}→"
               f"{pb('Olopatadine','gini')}）。集計整合性制約を課さない箱制約のみでは"
               f"2014年度{N.box('Olopatadine',2014,'gini')}と2024年度"
               f"{N.box('Olopatadine',2024,'gini')}の区間が重なり、方向は確定しなかった"
               f"（Supplementary Table S10）。")
    else:
        olo = (f"オロパタジンは2014年度（{N.iv('Olopatadine',2014,'gini')}）と"
               f"2024年度（{iv('Olopatadine','gini')}）の区間が重なるため方向を"
               f"確定できない（公表値ベースでは{N.pub('Olopatadine',2014,'gini')}→"
               f"{pb('Olopatadine','gini')}）。")
    ed.replace(p79,
               "オロパタジンは2014年度（0.129〜0.131）と2024年度（0.078〜0.139）の"
               "区間が重なるため方向を確定できない（公表値ベースでは0.131→0.118）。",
               olo); n += 1

    top3_id = N.disjoint("TOP3", 2022, 2024, "gini")
    lev_id = N.disjoint("Levocabastine", 2022, 2024, "gini")
    if not top3_id and not lev_id:
        tail = ("レボカバスチンと主要3成分合計は2022年度を起点として比較したが、"
                "2022〜2024年度の3年度の区間がいずれも重なるため、縮小と拡大のいずれの"
                f"方向も確定しない（主要3成分合計の公表値ベースはジニ係数"
                f"{N.pub('TOP3',2022,'gini')}→{N.pub('TOP3',2023,'gini')}→"
                f"{N.pub('TOP3',2024,'gini')}とほぼ横ばい）。")
    else:
        parts = []
        for key, name, ident in (("TOP3", "主要3成分合計", top3_id),
                                 ("Levocabastine", "レボカバスチン", lev_id)):
            d = "確定した" if ident else "確定しない"
            parts.append(f"{name}は{N.iv(key,2022,'gini')}（2022年度）から"
                         f"{N.iv(key,2024,'gini')}（2024年度）で方向は{d}")
        tail = ("レボカバスチンと主要3成分合計は2022年度を起点として比較した："
                + "、".join(parts) + "。")
    ed.replace(p79,
               "レボカバスチンと主要3成分合計は2022年度を起点として比較したが、"
               "2022〜2024年度の3年度の区間がいずれも重なるため、縮小と拡大のいずれの"
               "方向も確定しない（主要3成分合計の公表値ベースはジニ係数0.113→0.119→"
               "0.117とほぼ横ばい）。", tail); n += 1

    # ---- 8. Discussion: 学童期→思春期の段差（小児医療費助成） --------
    replace_in(ed, P, "学童期の第1ピークは、小児期のアレルギー性結膜炎",
               "一方、思春期〜若年成人期の急減（20–24歳の谷）は、この年代の医療機関"
               "受診率の低さ（セルフメディケーションとしてのOTC点眼薬への依存を含む）を"
               "反映していると考えられる。",
               "一方、思春期〜若年成人期の急減（20–24歳の谷）は、この年代の医療機関"
               "受診率の低さ（セルフメディケーションとしてのOTC点眼薬への依存を含む）を"
               "反映していると考えられる。ただし低下は20〜24歳で始まるのではなく、"
               "10〜14歳（296,200〜302,594 mL）から15〜19歳（185,645〜193,411 mL）への"
               "37%の減少としてすでに現れている。多くの自治体で子ども医療費助成の対象が"
               "中学校卒業（15歳到達年度末）で終了することと、この最初の段差の位置は"
               "一致しており、窓口負担の不連続な上昇が受療行動の変曲点として寄与している"
               "可能性がある。ただし助成の対象年齢・所得制限・自己負担は自治体ごとに"
               "異なり、本研究は自治体別の制度情報を統合していないため、その寄与の"
               "大きさを評価することはできない。"); n += 1

    # ---- 9. Discussion: mLベースの解釈を仮定つきに --------------------
    replace_in(ed, P, "このmLベースの指標の性質は、本研究の年齢プロファイル",
               "すなわち本研究が観察したエピナスチンの増加とシェア上昇は、1回量を減らす"
               "製剤への移行を相殺してなお生じたものであり、処方患者数ベースの増加は、"
               "処方数量が示す以上に大きいと考えられる。",
               "すなわち本研究が観察したエピナスチンの増加とシェア上昇は、1回量を減らす"
               "製剤への移行を相殺してなお生じたものである。ただしこの議論は同一の投与"
               "日数とアドヒアランスを仮定したうえでの符号の向きにとどまる。処方数量は"
               "1回点眼量・点眼回数・投与日数の積のみで決まるわけではなく、1回の受診"
               "あたり定型的に一定本数（あるいは1シーズン分）を処方する慣行や残薬の発生"
               "にも左右され、点眼回数と厳密に連動するとは限らない。したがって本研究では、"
               "mLベースの指標が製剤構成の変化によって下方に歪む方向を示すにとどめ、"
               "処方患者数への換算は行わない。"); n += 1

    # ---- 10. Discussion: ジニ係数の解釈から根拠のない主張を削る -------
    # 同じ段落を複数回編集するので、段落は先に特定しておく（先頭文は削除されるため
    # 2度目以降は本文検索で見つからなくなる）。
    p96 = P[find(P, "格差の大きさを一つの数値に要約すると")]
    # (a) 2024年度の主要3成分合計の値
    ed.replace(p96,
               "2024年度の主要3成分合計のジニ係数は0.083〜0.130、CVは0.154〜0.230で"
               "あった（Figure 7）。",
               f"2024年度の主要3成分合計のジニ係数は{iv('TOP3','gini')}、CVは"
               f"{iv('TOP3','cv')}であった（Figure 7）。"); n += 1
    # (b) 根拠のない水準解釈と「外れ値に頑健」を削る
    ed.replace(p96,
               "ジニ係数0.1前後という水準は、県間に体系的な差はあるものの極端な偏在では"
               "ないことを示す。最大／最小比のような端点の比較と異なり、これらの指標は"
               "分布全体の形状を反映するため、少数の外れ値の影響を受けにくい。",
               "最大／最小比のような端点の比較と異なり、これらの指標は47都道府県の分布"
               "全体を反映するため、地域差の要約として併用した。ただしジニ係数の水準の"
               "高低を判定する外的な基準はないため、本稿では値そのものの絶対的な解釈は"
               "行わない。"); n += 1
    # (c) 単剤の経年変化（オロパタジンが確定するかで文を切り替える）
    olo_sent = ("オロパタジンについても、集計整合性制約を課すことで2014年度と2024年度の"
                f"区間が分離し（{N.iv('Olopatadine',2014,'gini')} と "
                f"{iv('Olopatadine','gini')}）、縮小が確定した。箱制約のみでは両者が"
                "重なり、方向は識別できなかった。") if olo_id else ""
    ed.replace(p96,
               "単剤別にみると、エピナスチンの県間格差は2014年度（ジニ係数0.235）から"
               "2024年度（0.111〜0.139）への縮小が確定した。",
               f"単剤別にみると、エピナスチンの県間格差は2014年度"
               f"（ジニ係数{N.pub('Epinastine',2014,'gini')}）から2024年度"
               f"（{iv('Epinastine','gini')}）への縮小が確定した。" + olo_sent); n += 1
    # 直後の「これは」が指す対象が曖昧になるので明示する
    ed.replace(p96,
               "これは処方量が8倍超に増加した期間における縮小であり、",
               "エピナスチンの縮小は処方量が8倍超に増加した期間に生じたものであり、"); n += 1

    if top3_id:
        ed.replace(p96,
                   "一方で、識別区間を考慮すると主要3成分合計では2022〜2024年度の3年間で"
                   "格差の縮小・拡大の方向は確定せず、指標の値そのものも",
                   "一方で、指標の値そのものは"); n += 1

    # ---- 10b. シェアの区間が valid であって sharp でないことを明示 ----
    replace_in(ed, P, "全国総計に基づく割合のうち Figure 5A",
               "シェア下限＝後発下限／（後発下限＋先発上限）、シェア上限＝後発上限／"
               "（後発上限＋先発下限）とした。",
               "シェア下限＝後発下限／（後発下限＋先発上限）、シェア上限＝後発上限／"
               "（後発上限＋先発下限）とした。この構成は分子と分母の各成分が同時に端点を"
               "取りうることを前提としており、到達可能とは限らないため、得られる区間は"
               "妥当（valid）ではあるが到達可能（sharp）とは限らない。"); n += 1

    # ---- 11. Discussion: 2024年度の後発医薬品比率の機序 --------------
    ge = pd.read_csv(os.path.join(NEW, "brand_generic_share_bounds.csv"))

    def gshare(code, year):
        r = ge[(ge.code == code) & (ge.year == year)]
        return float(r["share_pct_generic_lower"].iloc[0])

    d_olo_23 = gshare("OLOPATADINE", 2023) - gshare("OLOPATADINE", 2022)
    d_olo_24 = gshare("OLOPATADINE", 2024) - gshare("OLOPATADINE", 2023)
    d_lev_23 = gshare("LEVOCASTINE", 2023) - gshare("LEVOCASTINE", 2022)
    d_lev_24 = gshare("LEVOCASTINE", 2024) - gshare("LEVOCASTINE", 2023)
    epi_23, epi_24 = gshare("EPINASTINE", 2023), gshare("EPINASTINE", 2024)

    senteiryoyo = (
        "2024年度の後発医薬品比率の動きには、成分によって異なる機序が関与している。"
        f"エピナスチンでは、2024年12月6日に薬価収載された0.1%製剤の後発医薬品が同年度の"
        f"エピナスチン処方総量の25.0%を占め、後発医薬品比率の{epi_23:.1f}%（2023年度）"
        f"から{epi_24:.1f}%（2024年度）への上昇のほぼ全量を説明する（0.05%製剤の"
        "後発医薬品の比率は29.4%から29.5%とほぼ横ばいであった）。収載から年度末までは"
        "約4か月にすぎないが、この期間はスギ・ヒノキ花粉の飛散期にあたり抗アレルギー"
        "点眼薬の需要が年間で最も集中する時期であるため、新規収載品が短期間で大きな"
        "数量シェアを占めうる。一方、2024年度に新規収載のなかったオロパタジン"
        f"（前年度比＋{d_olo_23:.1f}ポイント→＋{d_olo_24:.1f}ポイント）と"
        f"レボカバスチン（同＋{d_lev_23:.1f}ポイント→＋{d_lev_24:.1f}ポイント）では、"
        "2024年度に後発医薬品比率の上昇が加速した。2024年10月に導入された長期収載品の"
        "選定療養（医療上の必要性等がある場合を除き、後発医薬品のある先発医薬品を患者の"
        "希望で選択する際に薬価差の4分の1相当の特別の料金が生じる仕組み）が、制度的背景"
        "の一つとして作用した可能性がある23。ただし本研究のデータは年度単位であり、制度の"
        "導入は年度途中の10月であるため、導入前後を分離した比較はできない。供給状況や"
        "処方慣行の変化を含む他の要因との寄与を分離することもできず、因果関係を主張する"
        "ものではない。")
    i100 = find(P, "オロパタジン（2024年度83.1%）とエピナスチン")
    ed.add_paragraph_after_styled(P[i100], senteiryoyo, P[i100]); n += 1

    # ---- 12. Figure 7 の脚注 -----------------------------------------
    replace_in(ed, P, "(A) ジニ係数、(B) 変動係数（CV）",
               "点は各県の識別区間内で指標が取りうる最小値と最大値の中点であり、"
               "エラーバーは描いていない（最小値・最大値および下限のみで計算した値は"
               "Supplementary Table S10）。",
               "点は最小値と最大値の中点であり、エラーバーは描いていない。最小値・最大値は、"
               "各県の真値がその識別区間内にあり、かつ県別処方量の合計が全国総計を超えない"
               "という集計整合性制約（Methods参照）を満たす範囲で指標が取りうる値である。"
               "最小値・最大値、下限のみで計算した値、および集計整合性制約を課さない"
               "箱制約のみの区間はSupplementary Table S10 に示した。"); n += 1

    # ---- 13. Supplementary Table S7・S10 の脚注 -----------------------
    replace_in(ed, P, "Supplementary Table S7. 2024年度の都道府県別",
               "各県の区間は当該県単独では妥当であるが、県間で同時に上限を取ることは"
               "できない（47県の上限の合計は全国集計の上限を主要3成分合計で約1.04倍、"
               "9成分合計で約1.39倍上回る）。",
               "各県の区間は当該県単独では妥当であるが、県間で同時に上限を取ることは"
               "できない（47県の上限の合計は全国集計の上限を主要3成分合計で約1.04倍、"
               "9成分合計で約1.39倍上回る）。本表の区間は県ごとの周辺区間であり、"
               "Figure 7 の格差指標ではこの同時達成不能性を集計整合性制約として明示的に"
               "課している（Methods参照）。ただし当該制約は周辺区間そのものは狭めない。"
               "ある県の上限を、他の46県が下限を取るという最も緩い条件のもとで評価しても、"
               "本表のいずれの県・いずれの系列でも公表された上限を下回らないためであり、"
               "本表および Figure 3 の値は制約の導入による影響を受けない。"); n += 1

    med_r, lo_r, hi_r = N.width_reduction("gini")
    replace_in(ed, P, "Supplementary Table S10. 都道府県間格差指標",
               "公表値列は下限（＝公表値）のみで計算した参考値、最小列・最大列は各県の"
               "真値が識別区間内の任意の値を取りうるとしたときに指標が取りうる最小・"
               "最大値である。",
               "公表値列は下限（＝公表値）のみで計算した参考値、最小列・最大列は、各県の"
               "真値がその識別区間内にあり、かつ県別処方量の合計が全国総計を超えないと"
               "したときに指標が取りうる最小・最大値である（Methods参照）。"
               "*_boxonly 列は集計整合性制約を課さない箱制約のみの区間であり、"
               f"感度分析として併記した（比較可能年度でジニ係数の区間幅は中央値"
               f"{med_r:.0f}%、範囲{lo_r:.0f}〜{hi_r:.0f}%狭まる）。gini_max_upper_certificate 列はジニ係数の最大値の"
               "証明付き上界、n_censored_prefectures 列は秘匿セルを含む県数であり、"
               "これが0の成分・年度では県別合計と全国総計が一致する（集計整合性制約が"
               "恒等式であることの確認）。"); n += 1

    # ---- 14. References ----------------------------------------------
    refs = [
        ("A contemporary look at allergic conjunctivitis. Allergy Asthma Clin Immunol. "
         "Published online 2020.",
         "A contemporary look at allergic conjunctivitis. Allergy Asthma Clin Immunol. "
         "2020;16(1):5."),
        ("Japanese cedar pollinosis in Tokyo residents born after massive national "
         "afforestation policy. Allergy. Published online 2018.",
         "Japanese cedar pollinosis in Tokyo residents born after massive national "
         "afforestation policy. Allergy. 2018;73(12):2395-2397."),
        ("Sex-related allergic rhinitis prevalence switch from childhood to adulthood: "
         "a systematic review and meta-analysis. Int Arch Allergy Immunol. "
         "Published online 2017.",
         "Sex-related allergic rhinitis prevalence switch from childhood to adulthood: "
         "a systematic review and meta-analysis. Int Arch Allergy Immunol. "
         "2017;172(4):224-235."),
        ("Prevalence and risk factors of dry eye disease in Japan: koumi study. "
         "Ophthalmology. Published online 2011.",
         "Prevalence and risk factors of dry eye disease in Japan: koumi study. "
         "Ophthalmology. 2011;118(12):2361-2367."),
        ("conjunctival cedar pollen allergen challenge. Ann Allergy Asthma Immunol. "
         "Published online 2014:1-6.",
         "conjunctival cedar pollen allergen challenge. Ann Allergy Asthma Immunol. "
         "2014;113(4):476-481."),
    ]
    for old, new in refs:
        key = old.split(".")[0][:40]
        ed.replace(P[find(P, key)], old, new); n += 1

    i22 = find(P, "Patients’ attitudes towards generic drug substitution in Japan")
    ed.add_paragraph_after_styled(
        P[i22],
        "23.\tMinistry of Health, Labour and Welfare. Selected medical care "
        "(senteiryoyo) for long-listed drugs with generic equivalents. Accessed "
        "September 6, 2026. https://www.mhlw.go.jp/stf/newpage_39830.html",
        P[i22]); n += 1

    doc.save(DEST)
    print("-> %s （変更履歴つき、%d 箇所）" % (DEST, n))

    d2 = Document(DEST)
    print("accept:", F.accept_revisions(d2))
    d2.save(DEST_CLEAN)
    print("audit clean:", F.audit(DEST_CLEAN))
    return doc, ed, N, P, n


if __name__ == "__main__":
    main()
