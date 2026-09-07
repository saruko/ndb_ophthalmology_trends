# -*- coding: utf-8 -*-
"""python-pptx のグラフに識別区間を Excel ネイティブのエラーバー（カスタム値）として付ける補助。

build_fig_bounds_master.py（マスター pptx の Fig 1A・1B・2・3A・4A）と
build_submission_files.py（投稿用コピーの Fig 5B）から使う。
"""
from lxml import etree
from pptx.oxml.ns import qn

NSMAP = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
         "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


def _num_lit(values):
    lit = etree.SubElement(etree.Element("dummy"), qn("c:numLit"))
    fc = etree.SubElement(lit, qn("c:formatCode"))
    fc.text = "General"
    etree.SubElement(lit, qn("c:ptCount")).set("val", str(len(values)))
    for i, v in enumerate(values):
        pt = etree.SubElement(lit, qn("c:pt"))
        pt.set("idx", str(i))
        etree.SubElement(pt, qn("c:v")).text = repr(float(v))
    return lit


def add_error_bars(series, plus, minus=None, color="595959", width_pt=1.5, no_end_cap=False):
    """series（python-pptx の series オブジェクト）に上下カスタムのエラーバーを付ける。

    plus / minus は描いた値からの差分（非負）の配列。minus を省くと上側のみ。
    既存の c:errBars は先に消す（再実行しても二重に入らない）。
    """
    ser = series._element
    for old in ser.findall(qn("c:errBars")):
        ser.remove(old)
    eb = etree.Element(qn("c:errBars"))
    etree.SubElement(eb, qn("c:errBarType")).set("val", "both" if minus is not None else "plus")
    etree.SubElement(eb, qn("c:errValType")).set("val", "cust")
    etree.SubElement(eb, qn("c:noEndCap")).set("val", "1" if no_end_cap else "0")
    p = etree.SubElement(eb, qn("c:plus"))
    p.append(_num_lit(plus))
    if minus is not None:
        m = etree.SubElement(eb, qn("c:minus"))
        m.append(_num_lit(minus))
    sp = etree.SubElement(eb, qn("c:spPr"))
    ln = etree.SubElement(sp, qn("a:ln"))
    ln.set("w", str(int(width_pt * 12700)))
    ln.set("cap", "flat")
    sf = etree.SubElement(ln, qn("a:solidFill"))
    etree.SubElement(sf, qn("a:srgbClr")).set("val", color)
    # スキーマ順: … dLbls, trendline*, errBars*, cat/xVal, val/yVal …
    anchor = None
    for tag in ("c:cat", "c:xVal", "c:val", "c:yVal", "c:smooth", "c:shape"):
        anchor = ser.find(qn(tag))
        if anchor is not None:
            break
    if anchor is not None:
        anchor.addprevious(eb)
    else:
        ser.append(eb)
    return eb


def set_value_axis_max(chart, vmax, vmin=None):
    """値軸の最大（・最小）を固定する。"""
    for ax in chart._chartSpace.iter(qn("c:valAx")):
        sc = ax.find(qn("c:scaling"))
        for tag in ("c:max", "c:min"):
            old = sc.find(qn(tag))
            if old is not None:
                sc.remove(old)
        orient = sc.find(qn("c:orientation"))
        mx = etree.Element(qn("c:max"))
        mx.set("val", repr(float(vmax)))
        orient.addnext(mx)
        if vmin is not None:
            mn = etree.Element(qn("c:min"))
            mn.set("val", repr(float(vmin)))
            mx.addnext(mn)
