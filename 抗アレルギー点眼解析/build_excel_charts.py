# -*- coding: utf-8 -*-
"""ユーザーがレイアウトを編集できるExcelネイティブグラフを生成する。

出力: 05_論文成果物/公費含めない_new/論文図表/Fig_bounds_charts_editable.xlsx
  シート1 Fig3_MF_ratio      男/女比フォレスト風（横棒の浮動バー＝識別区間、対数軸）
  シート2 Fig_agesex_bounds  年齢階級×性別の人口10万対処方量（棒＝下限、エラーバー＝上限まで）
  シート3 Fig_pref_bounds    都道府県別の人口10万対処方量（棒＝下限、エラーバー＝上限まで）

いずれも2024年度・主要3成分合計（TOP3_TOTAL）。
棒の値は下限（=公表値。秘匿セルを0とみなした値）とし、
エラーバーのプラス側で上限（秘匿分をすべて加算した値）までを示す。
"""
import os

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference, Series
from openpyxl.chart.data_source import NumDataSource, NumRef
from openpyxl.chart.error_bar import ErrorBars

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "05_論文成果物", "公費含めない_new")
FIG_DIR = os.path.join(OUT_DIR, "論文図表")

AGE_ORDER = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
             "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
             "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+"]


def col_ref(ws, col, n):
    return Reference(ws, min_col=col, min_row=2, max_row=n + 1)


def num_src(ws, col, n):
    letter = ws.cell(row=1, column=col).column_letter
    return NumDataSource(NumRef(f=f"'{ws.title}'!${letter}$2:${letter}${n + 1}"))


def add_err_bars(ser, ws, plus_col, n):
    """プラス側のみのカスタムエラーバー（下限の棒 → 上限まで）。"""
    zeros = num_src(ws, plus_col + 1, n)   # minus用のゼロ列
    ser.errBars = ErrorBars(errBarType="both", errValType="cust",
                            plus=num_src(ws, plus_col, n), minus=zeros,
                            noEndCap=False)


# ----------------------------------------------------------------------
# シート1: 男/女比フォレスト風（浮動横棒）
# ----------------------------------------------------------------------
def sheet_mf(wb, t2):
    ws = wb.create_sheet("Fig3_MF_ratio")
    ws.append(["年齢階級", "比_下限", "区間幅(上限-下限)", "比_上限", "備考"])
    for _, r in t2.iterrows():
        lo, hi = r.MF_per100k_ratio_lower, r.MF_per100k_ratio_upper
        note = "判定不能（区間が1をまたぐ）" if lo < 1 < hi else (
            "女性優位" if hi < 1 else "男性優位")
        ws.append([r["Age Group"], lo, hi - lo, hi, note])
    n = len(t2)

    ch = BarChart()
    ch.type = "bar"          # 横棒
    ch.grouping = "stacked"
    ch.overlap = 100
    ch.title = "主要3成分合計の処方量 男/女比（2024年度）"
    # 系列1: 下限（塗りなし＝見えない下駄）、系列2: 区間幅（見える浮動バー）
    s1 = Series(col_ref(ws, 2, n), title="下限（非表示）")
    s1.graphicalProperties.noFill = True
    s2 = Series(col_ref(ws, 3, n), title="識別区間 [男下限/女上限, 男上限/女下限]")
    s2.graphicalProperties.solidFill = "4472C4"
    ch.series = [s1, s2]
    ch.set_categories(col_ref(ws, 1, n))
    ch.y_axis.title = "男/女比（人口10万対処方量）"
    ch.y_axis.scaling.logBase = 10
    ch.x_axis.title = "年齢階級"
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.height, ch.width = 16, 18
    # 凡例は上（既定の右端では95歳以上の長いバーを隠す）。Excelの凡例位置は
    # t/l/b/r/tr のみで、PNG版の「左上」に最も近い指定が t
    ch.legend.position = "t"
    ch.legend.overlay = False
    ws.add_chart(ch, "G2")
    ws["G26"] = "※比=1の基準線はExcel上で「系列の追加」または図形で任意に追加してください。"
    ws["G27"] = "※薄い下駄（下限系列）は塗りつぶしなし。バーの左端=下限、右端=上限。"


# ----------------------------------------------------------------------
# シート2: 年齢×性別 per100k（棒＋エラーバー）
# ----------------------------------------------------------------------
def sheet_agesex(wb, ag):
    ws = wb.create_sheet("Fig_agesex_bounds")
    ws.append(["年齢階級",
               "女性_下限", "女性_上乗せ(上限-下限)", "女性_上限",
               "男性_下限", "男性_上乗せ(上限-下限)", "男性_上限", "ゼロ"])
    d = ag.pivot_table(index="age_group", columns="sex",
                       values=["per100k_lower", "per100k_upper"])
    d = d.reindex(AGE_ORDER)
    for age, r in d.iterrows():
        flo = r[("per100k_lower", "female")]
        fhi = r[("per100k_upper", "female")]
        mlo = r[("per100k_lower", "male")]
        mhi = r[("per100k_upper", "male")]
        ws.append([age, flo, fhi - flo, fhi, mlo, mhi - mlo, mhi, 0.0])
    n = len(AGE_ORDER)

    ch = BarChart()
    ch.type = "col"
    ch.grouping = "clustered"
    ch.title = "主要3成分合計の人口10万対処方量（2024年度）\n棒=下限（公表値）、エラーバー=秘匿分を含む上限"
    sf = Series(col_ref(ws, 2, n), title="女性（下限）")
    sf.graphicalProperties.solidFill = "C0504D"
    add_err_bars(sf, ws, 3, n)
    sm = Series(col_ref(ws, 5, n), title="男性（下限）")
    sm.graphicalProperties.solidFill = "4472C4"
    add_err_bars(sm, ws, 6, n)
    ch.series = [sf, sm]
    ch.set_categories(col_ref(ws, 1, n))
    ch.y_axis.title = "人口10万対処方量（mL）"
    ch.x_axis.title = "年齢階級"
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.height, ch.width = 12, 30
    ws.add_chart(ch, "J2")
    ws["J20"] = "※エラーバー（プラス側のみ）はカスタム値: 上乗せ列（上限−下限）。マイナス側は0。"
    ws["J21"] = "※95歳以上は秘匿の影響で上限が極端に大きい（例: 男性100+は下限の約45倍）。"


# ----------------------------------------------------------------------
# シート3: 都道府県 per100k（棒＋エラーバー）
# ----------------------------------------------------------------------
def sheet_pref(wb, pr):
    ws = wb.create_sheet("Fig_pref_bounds")
    ws.append(["都道府県", "下限（公表値）", "上乗せ(上限-下限)", "上限", "区間幅%", "ゼロ"])
    pr = pr.sort_values("per100k_lower", ascending=False)
    for _, r in pr.iterrows():
        ws.append([r.prefecture, r.per100k_lower,
                   r.per100k_upper - r.per100k_lower, r.per100k_upper,
                   (r.per100k_upper - r.per100k_lower) / r.per100k_lower * 100,
                   0.0])
    n = len(pr)

    ch = BarChart()
    ch.type = "col"
    ch.title = "主要3成分合計の人口10万対処方量 都道府県別（2024年度）\n棒=下限（公表値）、エラーバー=秘匿分を含む上限"
    s = Series(col_ref(ws, 2, n), title="下限（公表値）")
    s.graphicalProperties.solidFill = "70AD47"
    # エラーバー: plus=上乗せ列(3), minus=ゼロ列(6)
    s.errBars = ErrorBars(errBarType="both", errValType="cust",
                          plus=num_src(ws, 3, n), minus=num_src(ws, 6, n),
                          noEndCap=False)
    ch.series = [s]
    ch.set_categories(col_ref(ws, 1, n))
    ch.y_axis.title = "人口10万対処方量（mL）"
    ch.x_axis.title = "都道府県（下限の降順）"
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.height, ch.width = 12, 34
    ws.add_chart(ch, "H2")
    ws["H20"] = "※上位県でも秘匿区間があるため順位は区間が重なる範囲で入れ替わりうる。"


def main():
    t2 = pd.read_csv(os.path.join(FIG_DIR, "csv",
                                  "Tables_123_bounds__Table2_MF_ratio.csv"))
    ag = pd.read_csv(os.path.join(OUT_DIR, "agesex_bounds.csv"))
    ag = ag[(ag.year == 2024) & (ag.code == "TOP3_TOTAL")]
    pr = pd.read_csv(os.path.join(OUT_DIR, "prefecture_per_capita_bounds.csv"))
    pr = pr[(pr.year == 2024) & (pr.code == "TOP3_TOTAL")]

    wb = Workbook()
    wb.remove(wb.active)
    sheet_mf(wb, t2)
    sheet_agesex(wb, ag)
    sheet_pref(wb, pr)
    path = os.path.join(FIG_DIR, "Fig_bounds_charts_editable.xlsx")
    wb.save(path)
    print(f"-> {path}")


if __name__ == "__main__":
    main()
