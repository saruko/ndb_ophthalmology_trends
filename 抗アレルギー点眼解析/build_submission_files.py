# -*- coding: utf-8 -*-
"""投稿用に図表ファイルを原稿（draft v8）の番号どおりの名前で書き出す。

本文 Figure 1〜6 の実体は `figureまとめnew.pptx` のスライド1〜6 にある
（Fig 3B の地図画像は `build_fig3_map.py`、Fig 4 の縦破線は `build_fig4_dividers.py`、
Fig 1A・1B・2・3A・4A の識別区間のひげは `build_fig_bounds_master.py` がマスターに書き込む）。本スクリプトは
PowerPoint COM（PowerShell 経由）で 1 スライド＝1 図の pptx と PNG を書き出し、
余白を自動トリミングして 05_論文成果物/公費含めない_new/投稿用/ に置く。
Table 1〜3・Suppl Table S1〜S7・Suppl Fig S1〜S5 はコピー元からコピーする。

**マスター pptx は書き換えない。** スライド上に赤字で残っている未処理の指示
（Fig 5B「100+のデータは削除」、Fig 6A「2015年度からにする」）と、Fig 1A・1B・2 からの
100歳以上の除外は、投稿用コピーに対してのみ本スクリプトが適用する（FIGURE_FIXES を参照）。

コピー元を更新したら再実行すること（毎回上書きする）。Windows + PowerPoint が必要。
"""
import csv
import os
import shutil
import subprocess
import sys

import openpyxl
from lxml import etree
from PIL import Image, ImageChops
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.oxml.ns import qn
from pptx.util import Pt

from build_share_bounds import bounds as share_bounds
from pptx_bounds import add_error_bars
from xlsx_native_charts import add_native_charts

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "05_論文成果物", "公費含めない_new")
FIG = os.path.join(OUT, "論文図表")
CSV = os.path.join(FIG, "csv")
DEST = os.path.join(OUT, "投稿用")
MASTER = os.path.join(OUT, "figureまとめnew.pptx")
GE_DIR = os.path.join(BASE, "03_解析結果", "後発品_剤形")   # Fig 6A の公表値（後発品比率）

PNG_W, PNG_H, MARGIN = 3000, 4000, 40

# 原稿 Figure 番号 -> マスター pptx のスライド番号
FIGURE_SLIDES = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}

FIGURE_DESC = {
    1: "2024年度 年齢群別の処方プロファイル（A: 3剤合計の人口10万対、B: 薬剤別、C: 3剤内シェア）",
    2: "2024年度 性・年齢群別の人口10万対処方数量",
    3: "2024年度 都道府県別の人口10万対処方数量（A: 棒グラフ、B: 日本地図）",
    4: "2014〜2024年度の推移（A: 人口10万対、B: 主要3成分内シェア。いずれも識別区間つき）",
    5: "エピナスチンの製剤構成（A: 0.1%/0.05%の割合の推移、B: 2024年度の年齢別0.1%割合）",
    6: "後発品比率（A: 主要3成分、B: エピナスチンの製剤別4区分）",
}


# Fig 1B の3系列（pptx 側に系列名が入っていないので、下限の値で同定して名前を付ける）
FIG1B_DRUGS = ("Epinastine", "Olopatadine", "Levocabastine")


def ps(script):
    """PowerShell を実行する（PowerPoint COM 用）。"""
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write((r.stdout or "") + "\n" + (r.stderr or "") + "\n")
        raise RuntimeError("PowerShell failed")
    return r.stdout


def export_figures():
    """マスターの各スライドを 1 枚 pptx として切り出す。"""
    pairs = "; ".join("@{n=%d; s=%d}" % (n, s) for n, s in sorted(FIGURE_SLIDES.items()))
    ps("""
$ErrorActionPreference = 'Stop'
$src  = '%s'
$dest = '%s'
$ppt = New-Object -ComObject PowerPoint.Application
foreach ($m in @(%s)) {
  $tmp = Join-Path $dest ('Figure' + $m.n + '.pptx')
  Copy-Item $src $tmp -Force
  $pres = $ppt.Presentations.Open($tmp, $false, $false, $false)
  for ($i = $pres.Slides.Count; $i -ge 1; $i--) {
    if ($i -ne $m.s) { $pres.Slides.Item($i).Delete() }
  }
  $pres.Save(); $pres.Close()
}
$ppt.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
""" % (MASTER, DEST, pairs))


def export_pngs():
    names = "', '".join("Figure%d" % n for n in sorted(FIGURE_SLIDES))
    ps("""
$ErrorActionPreference = 'Stop'
$dest = '%s'
$ppt = New-Object -ComObject PowerPoint.Application
foreach ($n in @('%s')) {
  $pres = $ppt.Presentations.Open((Join-Path $dest ($n + '.pptx')), $false, $false, $false)
  $pres.Slides.Item(1).Export((Join-Path $dest ($n + '.png')), 'PNG', %d, %d)
  $pres.Close()
}
$ppt.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
""" % (DEST, names, PNG_W, PNG_H))


def crop(path):
    im = Image.open(path).convert("RGB")
    bb = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    if not bb:
        return
    box = (max(0, bb[0] - MARGIN), max(0, bb[1] - MARGIN),
           min(im.width, bb[2] + MARGIN), min(im.height, bb[3] + MARGIN))
    im.crop(box).save(path)


# ------------------------------------------------------------ マスターの修正
def _chart(slide, key):
    for sh in slide.shapes:
        if getattr(sh, "has_chart", False) and sh.chart.has_title \
                and key in sh.chart.chart_title.text_frame.text:
            return sh.chart
    raise KeyError(key)


def _set_axis_numfmt(chart, code="0"):
    """replace_data で系列の書式が軸ラベルに波及する（100.0 等）のを戻す。"""
    for ax in chart._chartSpace.iter(qn("c:valAx")):
        nf = ax.find(qn("c:numFmt"))
        if nf is not None:
            nf.set("formatCode", code)
            nf.set("sourceLinked", "0")


def _drop_shapes_with_text(slide, needle):
    for sh in list(slide.shapes):
        if sh.has_text_frame and needle in sh.text_frame.text:
            sh._element.getparent().remove(sh._element)


def _axis_numfmt(chart):
    """replace_data の前に軸の表示形式を控える（後で戻すため）。"""
    return [ax.find(qn("c:numFmt")).get("formatCode")
            for ax in chart._chartSpace.iter(qn("c:valAx"))
            if ax.find(qn("c:numFmt")) is not None]


def _restore_axis_numfmt(chart, codes):
    for ax, code in zip(chart._chartSpace.iter(qn("c:valAx")), codes):
        nf = ax.find(qn("c:numFmt"))
        if nf is not None:
            nf.set("formatCode", code)
            nf.set("sourceLinked", "0")


def _ser_name(ser):
    """系列名。直値（c:tx/c:v。python-pptx が読めない）と参照（strCache）の両対応。"""
    v = ser._element.find(qn("c:tx")).find(qn("c:v"))
    return v.text if v is not None else ser.name


def _clear_axis_max(chart):
    """値軸の固定最大を外して自動に戻す（100+ を軸外に逃がすための設定だった）。"""
    for ax in chart._chartSpace.iter(qn("c:valAx")):
        sc = ax.find(qn("c:scaling"))
        old = sc.find(qn("c:max"))
        if old is not None:
            sc.remove(old)


def _replace_note(slide, chart, text):
    """グラフ直下の "Whiskers…" 注記を差し替える（マスターが書いた Off scale 付きのもの）。"""
    gf = [x for x in slide.shapes if getattr(x, "has_chart", False) and x.chart is chart][0]
    for sh in list(slide.shapes):
        if sh.has_text_frame and sh.text_frame.text.startswith("Whiskers") \
                and abs(sh.top - (gf.top + gf.height)) < gf.height * 0.2:
            sh._element.getparent().remove(sh._element)
    tb = slide.shapes.add_textbox(gf.left + int(gf.width * 0.06), gf.top + gf.height + 40000,
                                  int(gf.width * 0.92), 500000)
    tb.text_frame.word_wrap = True
    tb.text_frame.text = text
    for para in tb.text_frame.paragraphs:
        for run in para.runs:
            run.font.size = Pt(12)
            run.font.name = "Arial"


def _drop_100plus(slide, chart, series_bounds, note):
    """グラフから 100歳以上の階級を落とす（識別区間が広すぎて情報が無いため）。

    100歳以上は人口分母が 88,000 人と小さく、セルの57%が秘匿されるため区間幅が
    +1,264%（Fig 1A）〜+4,442%（Fig 2 男性）になる。ひげが軸外まで伸びて図が読めず、
    棒・点も推定値として解釈できない。数値は Table 2・Suppl Table に区間つきで残す。
    Fig 5B で既に同じ理由で除外しており、それに揃える。

    series_bounds: 系列名 -> {カテゴリ: (下限, 上限)}（ひげを付け直すため）
    """
    plot = chart.plots[0]
    cats = [str(c) for c in plot.categories]
    if not cats or cats[-1] != "100+":
        return False                       # 再実行時は何もしない
    codes = _axis_numfmt(chart)
    names = [_ser_name(ser) for ser in plot.series]
    values = [list(ser.values)[:-1] for ser in plot.series]
    cd = CategoryChartData()
    cd.categories = cats[:-1]
    for name, vals in zip(names, values):
        cd.add_series(name, vals)
    chart.replace_data(cd)
    _restore_axis_numfmt(chart, codes)
    _clear_axis_max(chart)
    for ser, name in zip(chart.plots[0].series, names):
        b = series_bounds[name]
        add_error_bars(ser, [max(float(b[c][1]) - float(b[c][0]), 0.0) for c in cats[:-1]])
    _replace_note(slide, chart, note)
    return True


def _fig1_bounds(kind):
    """Fig 1A / 1B の (系列名 -> {カテゴリ: (下限, 上限)})。"""
    if kind == "1A":
        r = list(csv.DictReader(open(os.path.join(
            CSV, "Fig1_age_sex_profile_bounds__Fig1A_TOP3.csv"), encoding="utf-8-sig")))
        return {None: {x["Age Group"]: (x["per100k_lower"], x["per100k_upper"]) for x in r}}
    out = {}
    for drug in FIG1B_DRUGS:
        r = list(csv.DictReader(open(os.path.join(
            CSV, "Fig1_age_sex_profile_bounds__Fig1B_%s.csv" % drug), encoding="utf-8-sig")))
        out[drug] = {x["Age Group"]: (x["Total_lower"], x["Total_upper"]) for x in r}
    return out


# 100+ を外した理由の注記。3成分計の100+の数値は Table 2 に残るが、薬剤別（Fig 1B）の
# 100+ は投稿用ファイルには入らない（論文図表/csv/…Fig1B_*.csv にある）ので参照先を書かない。
_NOTE = ("Whiskers: upper bound of the identification interval "
         "(%s = lower bound = published value). "
         "Age 100+ is omitted because its identification interval is uninformative "
         "(more than tenfold the lower bound)%s.")
NOTE_1A = _NOTE % ("bars", "; see Table 2 for the numbers")
NOTE_1B = _NOTE % ("points", "")
NOTE_2 = NOTE_1A


def fix_figure1():
    """Fig 1A・1B から100歳以上を外す（識別区間が +1,264%〜+2,709% で情報が無いため）。"""
    p = os.path.join(DEST, "Figure1.pptx")
    prs = Presentation(p)
    s = prs.slides[0]
    ch = _chart(s, "Fig 1A")
    b = _fig1_bounds("1A")
    _drop_100plus(s, ch, {_ser_name(ch.plots[0].series[0]): b[None]}, NOTE_1A)
    _drop_100plus(s, _chart(s, "Fig 1B"), _fig1_bounds("1B"), NOTE_1B)
    prs.save(p)


def fix_figure2():
    """図中タイトルの旧番号「Fig 1B.」を直し、100歳以上を外す（区間 +4,442%）。"""
    p = os.path.join(DEST, "Figure2.pptx")
    prs = Presentation(p)
    s = prs.slides[0]
    ch = _chart(s, "Sex-specific")
    tf = ch.chart_title.text_frame
    for para in tf.paragraphs:
        for run in para.runs:
            if "Fig 1B." in run.text:
                run.text = run.text.replace("Fig 1B.", "Fig 2.")
    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig1_age_sex_profile_bounds__Fig1B_TOP3.csv"), encoding="utf-8-sig")))
    bounds = {sx: {x["Age Group"]: (x["%s_lower" % sx], x["%s_upper" % sx]) for x in r}
              for sx in ("Male", "Female")}
    _drop_100plus(s, ch, bounds, NOTE_2)
    prs.save(p)


def fix_figure5():
    """Fig 5B から100歳以上を外す（標準0.05%製剤が秘匿で見かけ上100%になるため）。"""
    p = os.path.join(DEST, "Figure5.pptx")
    prs = Presentation(p)
    s = prs.slides[0]
    _drop_shapes_with_text(s, "100+のデータは削除")
    ch = _chart(s, "Fig 5B")
    rows = [r for r in csv.DictReader(open(os.path.join(
        CSV, "Fig5_ge_formulation_bounds__Fig5B_LX_share_by_age_bounds.csv"),
        encoding="utf-8-sig"))
        if r["Year"] == "2024" and r["Age Group"] != "100+"]
    cd = CategoryChartData()
    cd.categories = [r["Age Group"] for r in rows]
    cd.add_series("0.1% share (%)", [round(float(r["LX_pct_published"]), 2) for r in rows])
    ch.replace_data(cd)
    _set_axis_numfmt(ch)
    # 識別区間（割合なので上下とも公表値からずれうる）
    pub = [float(r["LX_pct_published"]) for r in rows]
    add_error_bars(ch.plots[0].series[0],
                   plus=[max(float(r["LX_pct_upper"]) - v, 0.0) for r, v in zip(rows, pub)],
                   minus=[max(v - float(r["LX_pct_lower"]), 0.0) for r, v in zip(rows, pub)])
    for sh in s.shapes:      # 注記（グラフ枠の直下）
        if sh.has_text_frame and sh.text_frame.text.startswith("Whiskers"):
            sh._element.getparent().remove(sh._element)
    gf = [x for x in s.shapes if getattr(x, "has_chart", False) and x.chart is ch][0]
    tb = s.shapes.add_textbox(gf.left + int(gf.width * 0.06), gf.top + gf.height + 40000,
                              int(gf.width * 0.92), 500000)
    tb.text_frame.word_wrap = True
    tb.text_frame.text = ("Whiskers: identification interval of the share "
                          "(points = published value; 100+ excluded, see legend).")
    for para in tb.text_frame.paragraphs:
        for run in para.runs:
            run.font.size = Pt(12)
            run.font.name = "Arial"
    prs.save(p)


def fix_figure6():
    """Fig 6A を2015年度起点にする（2014年度はレボカバスチン後発品が足切りで非掲載）。"""
    p = os.path.join(DEST, "Figure6.pptx")
    prs = Presentation(p)
    s = prs.slides[0]
    _drop_shapes_with_text(s, "2015年度からにする")
    ch = _chart(s, "Fig 6A")
    want = {"EPINASTINE": "Epinastine GE%", "OLOPATADINE": "Olopatadine GE%",
            "LEVOCASTINE": "Levocabastine GE%"}
    data = {v: {} for v in want.values()}
    for r in csv.DictReader(open(os.path.join(GE_DIR, "brand_generic_share.csv"),
                                 encoding="utf-8-sig")):
        if r["category"] in want:
            data[want[r["category"]]][int(r["year"])] = round(float(r["share_pct_generic"]), 1)
    years = list(range(2015, 2025))
    cd = XyChartData()
    for name in want.values():
        ser = cd.add_series(name)
        for y in years:
            ser.add_data_point(y, data[name].get(y, 0.0))
    ch.replace_data(cd)
    _set_axis_numfmt(ch)
    for ax in ch._chartSpace.iter(qn("c:valAx")):
        if "Fiscal year" in "".join(t.text or "" for t in ax.iter(qn("a:t"))):
            sc = ax.find(qn("c:scaling"))
            for tag in ("c:max", "c:min"):
                old = sc.find(qn(tag))
                if old is not None:
                    sc.remove(old)
            orient = sc.find(qn("c:orientation"))
            mn = etree.SubElement(sc, qn("c:min"))
            mn.set("val", "2015")
            mx = etree.SubElement(sc, qn("c:max"))
            mx.set("val", "2024")
            sc.remove(mn)
            sc.remove(mx)
            orient.addnext(mn)
            mn.addnext(mx)
    prs.save(p)


FIGURE_FIXES = {1: fix_figure1, 2: fix_figure2, 5: fix_figure5, 6: fix_figure6}


# ------------------------------------------------------------ データCSV
def _pct(num, den):
    return "" if not den else "%.4f" % (num / den * 100)


def _by_value(pairs):
    """公表値（下限）で対応づけるルックアップ。県名が英語で一致しない Fig 3A 用。

    build_fig_bounds_master.fig3a のひげと同じ対応づけ（47県の下限は全て異なる）。
    """
    def f(v):
        lo, hi = min(pairs, key=lambda p: abs(p[0] - float(v)))
        if abs(lo - float(v)) > max(abs(lo), 1e-9) * 1e-4:
            raise RuntimeError("Fig 3A: 値 %r に対応する県が見つかりません" % v)
        return lo, hi
    return f


def bounds_lookup():
    """(figure, panel, series) -> {category: (lower, upper)}。図に描いた値に対応する識別区間。

    数量の panel では下限＝描いた値（公表値）。割合の panel（5A・5B・6A・6B）は
    描いた値が公表値どうしの比なので、下限は公表値より小さくなりうる。
    値が dict ではなく関数のときは、カテゴリ名ではなく描いた値で引く（Fig 3A）。
    """
    up = {}
    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig1_age_sex_profile_bounds__Fig1A_TOP3.csv"), encoding="utf-8-sig")))
    up[(1, "1A", None)] = {x["Age Group"]: (x["per100k_lower"], x["per100k_upper"]) for x in r}

    # Fig 1B: pptx の系列名が空なので、下限を突き合わせて成分名を決める（_resolve_series）
    for drug in FIG1B_DRUGS:
        r = list(csv.DictReader(open(os.path.join(
            CSV, "Fig1_age_sex_profile_bounds__Fig1B_%s.csv" % drug), encoding="utf-8-sig")))
        up[(1, "1B", drug)] = {x["Age Group"]: (x["Total_lower"], x["Total_upper"]) for x in r}

    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig1_age_sex_profile_bounds__Fig1B_TOP3.csv"), encoding="utf-8-sig")))
    up[(2, "2", "Male")] = {x["Age Group"]: (x["Male_lower"], x["Male_upper"]) for x in r}
    up[(2, "2", "Female")] = {x["Age Group"]: (x["Female_lower"], x["Female_upper"]) for x in r}

    # Fig 3A: 図の県名が英語で CSV の県名と一致しないため、描いた値（下限）で対応づける
    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig3_prefecture_map_bounds__Fig3_2024_per100k.csv"), encoding="utf-8-sig")))
    up[(3, "3A", None)] = _by_value([(float(x["TOP3_lower"]), float(x["TOP3_upper"]))
                                     for x in r])

    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig4_trends_shares_bounds__Fig4A_per100k.csv"), encoding="utf-8-sig")))
    for label in ("Top 3 total", "Epinastine", "Olopatadine", "Levocabastine"):
        up[(4, "4A", label)] = {x["Year"]: (x[label + "_lower"], x[label + "_upper"]) for x in r}

    # Fig 4B・Fig 1C: 構成比。Table 1・Table 3・Suppl Table S8 と同じ式（build_share_bounds）
    for label in FIG1B_DRUGS:
        up[(4, "4B", label)] = {}
    for x in r:
        lo = {d: float(x[d + "_lower"]) for d in FIG1B_DRUGS}
        hi = {d: float(x[d + "_upper"]) for d in FIG1B_DRUGS}
        for d, (s_lo, s_hi) in share_bounds(lo, hi).items():
            up[(4, "4B", d)][x["Year"]] = ("%.4f" % s_lo, "%.4f" % s_hi)

    age = {}
    for drug in FIG1B_DRUGS:
        up[(1, "1C", drug)] = {}
        for x in csv.DictReader(open(os.path.join(
                CSV, "Fig1_age_sex_profile_bounds__Fig1B_%s.csv" % drug), encoding="utf-8-sig")):
            age.setdefault(x["Age Group"], {})[drug] = (float(x["Total_lower"]),
                                                        float(x["Total_upper"]))
    for a, d in age.items():
        lo = {k: v[0] for k, v in d.items()}
        hi = {k: v[1] for k, v in d.items()}
        for k, (s_lo, s_hi) in share_bounds(lo, hi).items():
            up[(1, "1C", k)][a] = ("%.4f" % s_lo, "%.4f" % s_hi)

    # Fig 5A: 0.1%(LX)/0.05% の割合。区間は [自下限/(自下限+他上限), 自上限/(自上限+他下限)]
    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig5_ge_formulation_bounds__Fig5A_epinastine_LX.csv"), encoding="utf-8-sig")))
    f = lambda v: float(v) if v not in ("", None) else 0.0  # noqa: E731
    lx, st = {}, {}
    for x in r:
        a_lo, a_hi = f(x["LX_lower"]), f(x["LX_upper"])
        b_lo, b_hi = f(x["Standard+GE_lower"]), f(x["Standard+GE_upper"])
        lx[x["Year"]] = (_pct(a_lo, a_lo + b_hi), _pct(a_hi, a_hi + b_lo))
        st[x["Year"]] = (_pct(b_lo, b_lo + a_hi), _pct(b_hi, b_hi + a_lo))
    up[(5, "5A", "0.1% share (%)")] = lx
    up[(5, "5A", "0.05% share (%)")] = st

    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig5_ge_formulation_bounds__Fig5B_LX_share_by_age_bounds.csv"),
        encoding="utf-8-sig")))
    up[(5, "5B", None)] = {x["Age Group"]: (x["LX_pct_lower"], x["LX_pct_upper"])
                           for x in r if x["Year"] == "2024"}

    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig5_ge_formulation_bounds__Fig5B_GE_share_bounds.csv"), encoding="utf-8-sig")))
    for code, label in (("EPINASTINE", "Epinastine GE%"),
                        ("OLOPATADINE", "Olopatadine GE%"),
                        ("LEVOCASTINE", "Levocabastine GE%")):
        up[(6, "6A", label)] = {x["Year"]: (x["share_pct_generic_lower"],
                                            x["share_pct_generic_upper"])
                                for x in r if x["code"] == code}

    r = list(csv.DictReader(open(os.path.join(
        CSV, "Fig5_ge_formulation_bounds__Fig6B_epinastine_formulation_bounds.csv"),
        encoding="utf-8-sig")))
    for col, label in (("LX_0.1pct_brand", "0.1% brand (%)"),
                       ("LX_0.1pct_generic", "0.1% generic (%)"),
                       ("standard_0.05pct_brand", "0.05% brand (%)"),
                       ("standard_0.05pct_generic", "0.05% generic (%)")):
        up[(6, "6B", label)] = {x["Year"]: (x[col + "_pct_lower"], x[col + "_pct_upper"])
                                for x in r}
    return up


def _x_values(series):
    """XY散布図の x 値（c:xVal のキャッシュ）を文字列で返す。"""
    xs = []
    for xval in series._element.iter(qn("c:xVal")):
        for pt in xval.iter(qn("c:pt")):
            v = pt.find(qn("c:v"))
            if v is not None and v.text is not None:
                t = v.text
                xs.append(t[:-2] if t.endswith(".0") else t)
    return xs


def _resolve_series(n, panel, cats, vals, upper):
    """系列名が空のとき（Fig 1B）、下限テーブルと値を突き合わせて系列名を決める。"""
    for (fn, pn, name), m in upper.items():
        if (fn, pn) != (n, panel) or name is None or callable(m):
            continue
        try:
            ref = [float(m[c][0]) for c in cats]
        except KeyError:
            continue
        if all(v is not None and abs(v - x) <= max(abs(x), 1e-9) * 1e-4
               for v, x in zip(vals, ref)):
            return name
    raise RuntimeError("Fig %s: 系列を同定できません" % panel)


def build_data_rows(n, upper):
    """図に描いた値そのものを long 形式で組み立てる（panel名 -> 図タイトル も返す）。"""
    prs = Presentation(os.path.join(DEST, "Figure%d.pptx" % n))
    rows, titles = [], {}
    for sh in prs.slides[0].shapes:
        if not getattr(sh, "has_chart", False):
            continue
        ch = sh.chart
        title = ch.chart_title.text_frame.text if ch.has_title else ""
        panel = title.split(".")[0].replace("Fig", "").strip() or "?"
        titles[panel] = title.split(".", 1)[-1].strip()
        plot = ch.plots[0]
        try:
            cats = [str(c) for c in plot.categories]
        except Exception:
            cats = []
        for ser in plot.series:
            vals = list(ser.values)
            cs = cats if len(cats) == len(vals) else _x_values(ser)
            if len(cs) != len(vals):
                cs = [""] * len(vals)
            name = ser.name or _resolve_series(n, panel, cs, vals, upper)
            umap = upper.get((n, panel, name)) or upper.get((n, panel, None)) or {}
            for c, v in zip(cs, vals):
                lo, hi = umap(v) if callable(umap) else umap.get(c, ("", ""))
                rows.append((panel, name, c, "" if v is None else v, lo, hi))
    return rows, titles


def write_data_csv(n, rows):
    p = os.path.join(DEST, "Figure%d_data.csv" % n)
    head = ("panel", "series", "category", "value_plotted", "value_lower", "value_upper")
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows([head] + rows)
    return len(rows)


def write_data_xlsx(n, rows, titles):
    """同じ内容を panel ごとのシートに横持ちで並べた Excel（査読者が読む用）。

    列は系列ごとに「下限｜図の値｜上限」の3列組。CSV（long形式）が機械可読版、
    こちらが人間可読版で、値は同じもの。
    """
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    fill = PatternFill("solid", fgColor="DDEBF7")
    for panel in sorted({r[0] for r in rows}):
        sub = [r for r in rows if r[0] == panel]
        series, cats = [], []
        for _, s, c, _v, _lo, _hi in sub:      # 出現順を保つ
            if s not in series:
                series.append(s)
            if c not in cats:
                cats.append(c)
        ws = wb.create_sheet("Fig %s" % panel)
        ws["A1"] = "Fig %s. %s" % (panel, titles.get(panel, ""))
        ws["A1"].font = Font(bold=True, size=12)
        ws["A2"] = ("下限＝図の棒・点（公表値）、上限＝ひげの先。統計的な信頼区間ではなく、"
                    "セル秘匿を考慮した識別区間（真値が必ず入る範囲）。計算式は "
                    "識別区間の計算式.xlsx を参照。")
        ws["A2"].font = Font(size=9)
        val = {(s, c): (v, lo, hi) for _, s, c, v, lo, hi in sub}
        ws.cell(row=4, column=1, value="category").font = Font(bold=True)
        ws.cell(row=4, column=1).fill = fill
        ws.column_dimensions["A"].width = 16
        for j, s in enumerate(series):
            col = 2 + j * 3
            ws.merge_cells(start_row=4, start_column=col, end_row=4, end_column=col + 2)
            c = ws.cell(row=4, column=col, value=s.replace("\n", " "))
            c.font = Font(bold=True)
            c.alignment = Alignment(horizontal="center")
            for k, lab in enumerate(("lower", "plotted", "upper")):
                h = ws.cell(row=5, column=col + k, value=lab)
                h.font = Font(bold=True)
                h.fill = fill
                ws.column_dimensions[get_column_letter(col + k)].width = 14
        for i, cat in enumerate(cats):
            ws.cell(row=6 + i, column=1, value=cat)
            for j, s in enumerate(series):
                v, lo, hi = val.get((s, cat), ("", "", ""))
                for k, x in enumerate((lo, v, hi)):
                    cell = ws.cell(row=6 + i, column=2 + j * 3 + k,
                                   value=float(x) if x != "" else None)
                    cell.number_format = "#,##0.000"
        ws.freeze_panes = "B6"
    add_native_charts(wb)   # 各シートに pptx と同構成の Excel ネイティブグラフを埋め込む
    p = os.path.join(DEST, "Figure%d_data.xlsx" % n)
    wb.save(p)
    return p


# ------------------------------------------------------------ コピー対象
ITEMS = [
    ("Table1.csv", os.path.join(CSV, "Tables_123_bounds__Table1_FY2024.csv"),
     "2024年度 成分別 処方量・人口10万対・後発品比率（区間つき）",
     "9成分中シェア列は原稿本文の表で算出（本CSVには無い）"),
    ("Table2.csv", os.path.join(CSV, "Tables_123_bounds__Table2_MF_ratio.csv"),
     "2024年度 主要3成分合計の年齢階級×性別 人口10万対と男/女比（区間つき）",
     "Figure 2 の数値版。本文表は実数（mL）と人口10万対の双方を載せる"),
    ("Table3.csv", os.path.join(CSV, "Table3_share_2022_2024.csv"),
     "2022〜2024年度 9成分合計に占める成分別シェア（区間つき）", ""),

    ("SupplTableS1.csv", os.path.join(FIG, "unit_conversion_audit.csv"),
     "対象品目一覧（品目名・成分・単位・mL換算係数・根拠）",
     "先頭にREADME行があるため読込時は comment='#'"),
    ("SupplTableS2.csv", os.path.join(OUT, "unlisted_products_inventory.csv"),
     "成分×年度の未収載品目数（下限）の内訳", ""),
    ("SupplTableS3.csv", os.path.join(OUT, "unlisted_sensitivity.csv"),
     "未収載品目まで拡張した感度分析（順位ベース上限・逆推計上限）",
     "先頭にREADME行があるため読込時は comment='#'"),
    ("SupplTableS4.csv", os.path.join(OUT, "trend_identification_table.csv"),
     "増減が識別できるかの判定表（起点年 2014/2015/2022 × 成分・集計単位）", ""),
    ("SupplTableS5.csv",
     os.path.join(CSV, "SupplTable_annual_totals_bounds__SupplTable_annual_mL.csv"),
     "成分×年度の全国処方量 2014〜2024（区間つき）",
     "本文の上限は `_upper` 列。`_upper_published_items` は未収載品目を含まない上限"),
    ("SupplTableS6.csv", os.path.join(OUT, "top3_full_range_2014_2024.csv"),
     "主要3成分の公表総量・下限・上限（順位ベース／逆推計）の内訳",
     "先頭にREADME行があるため読込時は comment='#'"),
    ("SupplTableS7.csv", os.path.join(CSV, "SupplTable_S7_prefecture_2024.csv"),
     "2024年度 都道府県別 人口10万対（主要3成分・9成分、区間つき）と下限基準の順位",
     "Figure 3 の数値版"),
    ("SupplTableS8.xlsx", os.path.join(CSV, "SupplTable_S8_share_bounds.xlsx"),
     "構成比（シェア）の識別区間（Table 1 の9成分／Fig 4B／Fig 1C）",
     "`build_share_bounds.py`。Fig 4B・Fig 1C の数値版"),

    ("SupplFigureS1.png", os.path.join(FIG, "SupplFig_missingness_schema.png"),
     "欠測3層構造（セル秘匿・総計秘匿・品目非掲載）と識別区間の導出の模式図", "参照用"),
    ("SupplFigureS1.pptx", os.path.join(FIG, "SupplFig_missingness_schema.pptx"),
     "同上（PowerPointで編集可能）", ""),
    ("SupplFigureS2.png", os.path.join(FIG, "SupplFig_GE_share.png"),
     "9成分の後発品比率（全期間、比較不能年度は白抜き）とエピナスチンの製剤別処方量（mL）",
     "本文 Fig 6A・Fig 5A の親figure"),
    ("SupplFigureS3.png", os.path.join(FIG, "Fig_MF_ratio_forest.png"),
     "主要3成分合計の男/女比 2024年度（年齢階級別、フォレスト風、点推定なし）",
     "v7までの本文 Figure 2。参照用"),
    ("SupplFigureS3.xlsx", os.path.join(FIG, "Fig_bounds_charts_editable.xlsx"),
     "同上（Excelネイティブグラフ）",
     "コピー時に候補図シートを削除し Fig3_MF_ratio のみ残す。比=1基準線は手動追加"),
    ("SupplFigureS4.png", os.path.join(FIG, "Fig1_trend_bounds.png"),
     "全国処方量（mL）の推移と識別区間 2014〜2024（A: 主要3成分別、B: 3成分計・9成分計、対数軸）",
     "v7までの本文 Figure 1。参照用"),
    ("SupplFigureS4.xlsx", os.path.join(FIG, "Fig1_trend_bounds_editable.xlsx"),
     "同上（Excelネイティブ折れ線＋エラーバー）", "縦破線は手動追加が必要"),
    ("SupplFigureS4_data.csv", os.path.join(CSV, "Fig1_trend_bounds_data.csv"),
     "Suppl Fig S4 の下限・上限データ", ""),
    ("SupplFigureS5.png", os.path.join(OUT, "Fig_unlisted_sensitivity.png"),
     "品目非掲載を含む識別区間の年次推移（成分別、対数軸）", ""),

    ("識別区間の計算式.xlsx", os.path.join(FIG, "識別区間の計算式.xlsx"),
     "下限・上限の計算式（生データ→区間→図の値の突き合わせ。セルはExcel数式）",
     "`build_bounds_formula_workbook.py`。図表ではなく査読対応用の監査資料"),
]

KEEP_SHEETS = {"SupplFigureS3.xlsx": ["Fig3_MF_ratio"]}


def main(data_only=False):
    """data_only=True: PowerPoint COM を使わず、既存の投稿用 pptx からデータ版と
    コピー対象だけを作り直す（図そのものを変えていないときの再実行用）。"""
    if not os.path.exists(MASTER):
        raise SystemExit("マスターが見つかりません: %s" % MASTER)
    os.makedirs(DEST, exist_ok=True)
    if not data_only:
        for f in os.listdir(DEST):          # 旧番号のファイルを残さない
            if f != "README.md":
                os.remove(os.path.join(DEST, f))

        print("Figure 1〜6 を切り出し中...")
        export_figures()
        for n in sorted(FIGURE_FIXES):
            FIGURE_FIXES[n]()
            print("  Figure%d にマスター修正を適用" % n)
        print("PNG を書き出し中...")
        export_pngs()
    upper = bounds_lookup()
    for n in sorted(FIGURE_SLIDES):
        if not data_only:
            crop(os.path.join(DEST, "Figure%d.png" % n))
        rows, titles = build_data_rows(n, upper)
        k = write_data_csv(n, rows)
        write_data_xlsx(n, rows, titles)
        print("  Figure%d.pptx / .png / _data.csv / _data.xlsx (%d行)" % (n, k))

    lines = ["# 投稿用ファイル 対応表（原稿 draft v8）",
             "",
             "`build_submission_files.py` が自動生成する。**このフォルダのファイルは直接編集しないこと**",
             "（コピー元を直して再実行する）。原稿は `../論文下書き_総量2014_シェア2022_区間解析.md`。",
             "",
             "本文 **Figure 1〜6**・**Table 1〜3**、補遺 **Suppl Table S1〜S8**・**Suppl Fig S1〜S5**。",
             "legend は原稿§8。英訳時は図中の日本語（`Fig. 1` 等のラベル）を削除し legend へ移すこと。",
             "",
             "## 本文 Figure（`figureまとめnew.pptx` スライド1〜6 から生成）",
             "",
             "| ファイル | 内容 |",
             "|---|---|"]
    for n in sorted(FIGURE_SLIDES):
        lines.append("| `Figure%d.pptx` / `Figure%d.png` / `Figure%d_data.csv` / "
                     "`Figure%d_data.xlsx` | %s |" % (n, n, n, n, FIGURE_DESC[n]))
    lines += ["",
              "- `.pptx` は Excel ネイティブグラフ入りで編集可能（マスターのスライドを切り出したもの）。",
              "- `.png` は 3000×4000 px で書き出し、余白を自動トリミングしたもの（参照用）。",
              "- `_data.csv` は**図に描いた値そのもの**（long形式: panel, series, category,",
              "  value_plotted, value_lower, value_upper）。`value_plotted` は図に描いた公表値、",
              "  `value_lower`/`value_upper` はセル秘匿を考慮した識別区間。数量の panel",
              "  （Fig 1A・1B・2・3A・4A）では下限＝公表値。割合の panel（Fig 1C・4B・5A・5B・6A・6B）は",
              "  公表値どうしの比を描いているため、描いた値は下限と上限の中間に位置する。",
              "  全 panel に区間列が入る（構成比 Fig 1C・4B の数値版は Suppl Table S8）。",
              "- Fig 1A・1B・1C・2 は100歳以上を除外している（区間が広すぎて解釈できないため。"
              "Fig 5B と同じ扱い）。3成分計の100歳以上の数値は `Table2.csv` に区間つきで残っている。"
              "薬剤別（Fig 1B）の100歳以上は投稿用ファイルには無い"
              "（`論文図表/csv/Fig1_age_sex_profile_bounds__Fig1B_*.csv`）。",
              "- `_data.xlsx` は同じ値を panel ごとのシートに横持ち（系列ごとに",
              "  lower / plotted / upper の3列）で並べた人間可読版。値は CSV と同一。",
              "  各シートには本文の図と同構成の Excel ネイティブグラフを埋め込んである",
              "  （値は plotted 列、ひげは右側の err+ / err- 数式列を参照。編集可能）。",
              "- 下限・上限の**計算式**は `識別区間の計算式.xlsx`（生データ→区間→図の値までを",
              "  Excel 数式で組み、投稿用ファイルの値との差が 0 になることを示す監査ブック）。",
              "",
              "## マスターに対して本スクリプトが適用している修正",
              "",
              "マスター `figureまとめnew.pptx` のスライド5・6 には赤字の未処理メモが残っている。",
              "投稿用コピーには以下を適用済み（**マスターは書き換えていない**）。",
              "",
              "| 図 | マスターのメモ | 適用した修正 |",
              "|---|---|---|",
              "| Fig 1A・1B | （なし） | 100歳以上を除外（識別区間が +1,264%〜+2,709% で情報が無く、"
              "ひげが軸外まで伸びるため）。値軸の固定最大も解除 |",
              "| Fig 2 | （なし） | 図中タイトルが旧番号「Fig 1B.」のままだったため「Fig 2.」に修正。"
              "あわせて100歳以上を除外（区間 +4,442%）し、値軸の固定最大を解除 |",
              "| Fig 5B | 「100+のデータは削除」 | 100歳以上の階級を除外（標準0.05%製剤が秘匿されており見かけ上100%になるアーティファクトのため）。赤字メモも削除 |",
              "| Fig 6A | 「2015年度からにする」 | 2015年度起点に変更（2014年度はレボカバスチンの後発品が足切りで非掲載）。x軸を2015–2024に固定、赤字メモも削除 |",
              "",
              "マスター側を直したら `FIGURE_FIXES` を外すこと。",
              "",
              "## Table・Supplementary（コピー）",
              "",
              "| 投稿用ファイル | 内容 | コピー元 | 備考 |",
              "|---|---|---|---|"]
    missing = []
    for name, src, desc, note in ITEMS:
        if not os.path.exists(src):
            missing.append((name, src))
            continue
        dst = os.path.join(DEST, name)
        shutil.copy2(src, dst)
        if name in KEEP_SHEETS:
            wb = openpyxl.load_workbook(dst)
            for ws in [w for w in wb.worksheets if w.title not in KEEP_SHEETS[name]]:
                wb.remove(ws)
            wb.save(dst)
        rel = os.path.relpath(src, OUT).replace("\\", "/")
        lines.append("| `%s` | %s | `%s` | %s |" % (name, desc, rel, note))
        print("  %-26s <- %s" % (name, rel))
    lines += ["", "## 注意", "",
              "- 本文の Figure は棒・点＝下限（公表値）、ひげ＝識別区間の上限（原稿§2.8）。",
              "  Fig 1A・1B・2・3A・4A のひげは `build_fig_bounds_master.py` がマスターに、",
              "  構成比の Fig 1C・4B（上下ひげ）は `build_fig1c_fig4b.py` がマスターに、",
              "  Fig 5B のひげは本スクリプトが投稿用コピーに付ける。Fig 3B のハッチングは",
              "  `build_fig3_map.py`。Fig 5A・6A・6B は区間幅<0.01pt のためひげなし。",
              "- `SupplFigureS3.xlsx` は `Fig3_MF_ratio` の1シートのみ（コピー元の候補図2シート",
              "  `Fig_agesex_bounds`／`Fig_pref_bounds` は本スクリプトが削除している）。",
              "- `SupplTableS5.csv` の上限は `_upper` 列（未収載品目を含む本文の識別区間）。",
              "  `_upper_published_items` 列は公表品目のみの上限で、本文では引用しない。",
              "- `SupplTableS3.csv` は全年度で未収載加算を行う感度分析のため、2022年度以降の",
              "  上限が本文（`SupplTableS5.csv`）とわずかに異なる（原稿§8のS3脚注）。",
              "- Figure 5B・6B の区間つき一次データは `論文図表/Fig5_ge_formulation_bounds.xlsx` の",
              "  `Fig5B_LX_share_by_age_bounds`・`Fig6B_epinastine_formulation_bounds` シート",
              "  （`build_paper_figures_bounds.py`）。Fig 6A の公表値は",
              "  `03_解析結果/後発品_剤形/brand_generic_share.csv`（同じ新パイプライン）。",
              "- `論文図表/` の内部名ファイルとの対応は `../論文図表/README.md` を見ること。"]
    if missing:
        lines += ["", "## コピー元が見つからなかったファイル", ""]
        for name, src in missing:
            lines.append("- `%s` <- `%s`" % (name, src))
            print("  ★見つかりません: %s <- %s" % (name, src))
    p = os.path.join(DEST, "README.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("-> %s" % p)
    print("   Figure %d 点 / コピー %d 件 / 欠落 %d 件"
          % (len(FIGURE_SLIDES), len(ITEMS) - len(missing), len(missing)))


if __name__ == "__main__":
    main(data_only="--data-only" in sys.argv)
