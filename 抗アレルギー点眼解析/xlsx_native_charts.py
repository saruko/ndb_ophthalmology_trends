# -*- coding: utf-8 -*-
"""投稿用 FigureN_data.xlsx の各シートに Excel ネイティブグラフを埋め込む。

build_submission_files.write_data_xlsx が保存前に add_native_charts() を呼ぶ。
シート構造（write_data_xlsx が書く共通形式）: 行1=タイトル、行2=注記、
行4=系列名（3列組の先頭に記入）、行5=lower/plotted/upper、行6以降=データ、A列=カテゴリ。

グラフは FigureN.pptx の各 panel と同じ種類・系列・色で作り、値は plotted 列を参照する。
識別区間はエラーバーで示し、その値はデータ表の右側に追加する数式列
（err+ = upper - plotted, err- = plotted - lower）を参照する。
データを直せばグラフとひげも追従する。
"""
from openpyxl.chart import BarChart, LineChart, ScatterChart, Series, Reference
from openpyxl.chart.data_source import NumDataSource, NumRef
from openpyxl.chart.error_bar import ErrorBars
from openpyxl.chart.marker import Marker
from openpyxl.drawing.line import LineProperties
from openpyxl.utils import get_column_letter

# panel ごとのグラフ仕様（FigureN.pptx のグラフに合わせる）。
# kind: col=縦棒 / barh=横棒 / col_stacked=積み上げ縦棒 / line=折れ線 / scatter=散布図(線+マーカー)
CHART_SPEC = {
    "Fig 1A": dict(kind="col",  err=True,  colors=["595959"]),
    "Fig 1B": dict(kind="line", err=True,  colors=["E97132", "0070C0", "7030A0"],
                   symbols=["circle", "square", "triangle"]),
    "Fig 1C": dict(kind="line", err=True,  colors=["E97132", "0070C0", "7030A0"],
                   symbols=["circle", "square", "triangle"]),
    "Fig 2":  dict(kind="col",  err=True,  colors=["0070C0", "C00000"]),
    "Fig 3A": dict(kind="barh", err=True,  colors=["404040"], tall=True),
    "Fig 4A": dict(kind="line", err=True,  colors=["404040", "E97132", "0070C0", "7030A0"],
                   symbols=["circle", "circle", "circle", "circle"]),
    "Fig 4B": dict(kind="line", err=True,  colors=["E97132", "0070C0", "7030A0"],
                   symbols=["circle", "square", "triangle"]),
    "Fig 5A": dict(kind="col_stacked", err=False, colors=["E97132", "FFC000"]),
    "Fig 5B": dict(kind="line", err=True,  colors=["E97132"], symbols=["circle"]),
    "Fig 6A": dict(kind="scatter", err=False, colors=["E97132", "0070C0", "7030A0"]),
    "Fig 6B": dict(kind="col_stacked", err=False,
                   colors=["E97132", "F4B183", "FFC000", "FFE699"]),
}

DATA_START = 6   # 最初のデータ行


def _series_layout(ws):
    """行4の系列名から (name, col_lower, col_plotted, col_upper) を得る。"""
    out = []
    for col in range(2, ws.max_column + 1):
        name = ws.cell(row=4, column=col).value
        if name:
            out.append((str(name), col, col + 1, col + 2))
    return out


def _num_ref(ws, col, n):
    L = get_column_letter(col)
    return NumDataSource(NumRef(f="'%s'!$%s$%d:$%s$%d" % (ws.title, L, DATA_START, L, n)))


def _add_err_cols(ws, sers, n):
    """右側に err+ / err- の数式列を追加し、系列名 -> (plus列, minus列) を返す。"""
    base = ws.max_column + 2
    mapping = {}
    for i, (name, lo, pl, up) in enumerate(sers):
        cp, cm = base + i * 2, base + i * 2 + 1
        ws.cell(row=4, column=cp, value=name)
        ws.cell(row=5, column=cp, value="err+ (upper-plotted)")
        ws.cell(row=5, column=cm, value="err- (plotted-lower)")
        for r in range(DATA_START, n + 1):
            Lu, Lp, Ll = (get_column_letter(c) for c in (up, pl, lo))
            ws.cell(row=r, column=cp, value="=MAX(%s%d-%s%d,0)" % (Lu, r, Lp, r))
            ws.cell(row=r, column=cm, value="=MAX(%s%d-%s%d,0)" % (Lp, r, Ll, r))
        mapping[name] = (cp, cm)
    return mapping


def _build_chart(ws, spec):
    sers = _series_layout(ws)
    n = ws.max_row
    err_cols = _add_err_cols(ws, sers, n) if spec["err"] else {}

    kind = spec["kind"]
    if kind in ("col", "barh", "col_stacked"):
        ch = BarChart()
        ch.type = "bar" if kind == "barh" else "col"
        ch.grouping = "stacked" if kind == "col_stacked" else "clustered"
        if kind == "col_stacked":
            ch.overlap = 100
    elif kind == "line":
        ch = LineChart()
    else:
        ch = ScatterChart()
        ch.scatterStyle = "lineMarker"

    ch.title = ws.cell(row=1, column=1).value
    ch.y_axis.delete = False
    ch.x_axis.delete = False

    for i, (name, lo, pl, up) in enumerate(sers):
        vals = Reference(ws, min_col=pl, min_row=DATA_START, max_row=n)
        if kind == "scatter":
            xref = Reference(ws, min_col=1, min_row=DATA_START, max_row=n)
            ser = Series(vals, xvalues=xref, title=name)
        else:
            ser = Series(vals, title=name)
        color = spec["colors"][i % len(spec["colors"])]
        if kind in ("col", "barh", "col_stacked"):
            ser.graphicalProperties.solidFill = color
            ser.graphicalProperties.line.noFill = True
        else:
            ser.graphicalProperties.line = LineProperties(solidFill=color, w=28575)
            sym = (spec.get("symbols") or ["circle"])[i % len(spec.get("symbols", ["circle"]))]
            ser.marker = Marker(symbol=sym, size=6)
            ser.marker.graphicalProperties.solidFill = color
            ser.smooth = False
        if spec["err"]:
            cp, cm = err_cols[name]
            ser.errBars = ErrorBars(errBarType="both", errValType="cust",
                                    plus=_num_ref(ws, cp, n), minus=_num_ref(ws, cm, n),
                                    noEndCap=False)
        ch.series.append(ser)

    if kind != "scatter":
        ch.set_categories(Reference(ws, min_col=1, min_row=DATA_START, max_row=n))

    if spec.get("tall"):               # Fig 3A: 47都道府県の横棒は縦長に
        ch.width, ch.height = 18, 30
    else:
        ch.width, ch.height = 24, 12
    ws.add_chart(ch, "%s%d" % (get_column_letter(ws.max_column + 2), 4))


def add_native_charts(wb):
    """ワークブックの全シートにグラフを追加する（保存前に呼ぶ）。"""
    for ws in wb.worksheets:
        spec = CHART_SPEC.get(ws.title)
        if spec is None:
            print("  xlsx_native_charts: 仕様未定義のシートをスキップ: %s" % ws.title)
            continue
        ws._charts = []                # 再実行できるように既存グラフは消して作り直す
        _build_chart(ws, spec)
