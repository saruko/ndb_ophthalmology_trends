"""
build_paper_figures_xlsx.py
抗VEGF薬論文用のFigureデータシート＋Excelチャートを生成する。
出力: 公費含まない/04_図表/antivegf_paper_figures.xlsx

前半（Fig1A〜SupplFig）: 解析結果mdの「論文用Figure一覧」に対応
後半（P01〜P10）: 04_図表/plots/*.png（visualization_antivegf.py の出力）を
                  Excelのグラフ機能で再現したもの

依存: openpyxl, pandas
"""

import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.chart import (
    BarChart, LineChart, AreaChart, Reference
)
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart.layout import Layout, ManualLayout

BASE = Path(__file__).parent
ROOT = BASE / "公費含まない"
OUT = ROOT / "04_図表" / "antivegf_paper_figures.xlsx"


class _CsvLocator:
    """フォルダ再編後もファイル名だけでCSVを引けるようにする。"""

    def __init__(self, root):
        self._index = {}
        for p in root.rglob("*.csv"):
            self._index.setdefault(p.name, p)

    def __truediv__(self, name):
        try:
            return self._index[name]
        except KeyError:
            raise FileNotFoundError(f"{name} が {ROOT} 配下に見つかりません")


PROC = _CsvLocator(ROOT)

# 年齢群の正しいソート順
AGE_ORDER = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳",
    "25～29歳", "30～34歳", "35～39歳", "40～44歳", "45～49歳",
    "50～54歳", "55～59歳", "60～64歳", "65～69歳", "70～74歳",
    "75～79歳", "80～84歳", "85～89歳", "90歳以上",
]

# 年齢群（公開粒度21区分用）
AGE_ORDER_21 = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳",
    "25～29歳", "30～34歳", "35～39歳", "40～44歳", "45～49歳",
    "50～54歳", "55～59歳", "60～64歳", "65～69歳", "70～74歳",
    "75～79歳", "80～84歳", "85～89歳", "90～94歳", "95～99歳", "100歳以上",
]


def write_df(ws, df, start_row=1):
    """DataFrameをワークシートに書き込む"""
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start_row):
        for c_idx, val in enumerate(row, 1):
            ws.cell(row=r_idx, column=c_idx, value=val)
    return start_row + len(df)  # 次の空行


def build_fig1a(wb):
    """Fig 1A: 年齢群別 処方数量（2024年度、男女合算）"""
    ws = wb.create_sheet("Fig1A_data")
    df = pd.read_csv(PROC / "agesex_distribution_published_antivegf.csv")
    df2024 = df[df["year"] == 2024].copy()

    # 男女合算
    both = df2024.groupby("age_group_detail")["quantity"].sum().reset_index()
    both.rename(columns={"age_group_detail": "age_group"}, inplace=True)

    # age_orderに基づいてソート（21区分）
    order = [a for a in AGE_ORDER_21 if a in both["age_group"].values]
    both["age_group"] = pd.Categorical(both["age_group"], categories=order, ordered=True)
    both = both.sort_values("age_group").reset_index(drop=True)

    write_df(ws, both)

    # チャート: 棒グラフ
    chart = BarChart()
    chart.type = "col"
    chart.title = "Fig 1A: 年齢群別 処方数量（2024年度）"
    chart.y_axis.title = "処方数量（本）"
    chart.x_axis.title = "年齢群"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    data = Reference(ws, min_col=2, min_row=1, max_row=len(both) + 1)
    cats = Reference(ws, min_col=1, min_row=2, max_row=len(both) + 1)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape = 4
    chart.legend = None

    ws.add_chart(chart, "D2")


def build_fig1b(wb):
    """Fig 1B: 性別×年齢群（2024年度、男女2系列）"""
    ws = wb.create_sheet("Fig1B_data")
    df = pd.read_csv(PROC / "agesex_distribution_published_antivegf.csv")
    df2024 = df[df["year"] == 2024].copy()

    # ピボット
    pivot = df2024.pivot_table(index="age_group_detail", columns="sex", values="quantity", aggfunc="sum").reset_index()
    pivot.rename(columns={"age_group_detail": "age_group"}, inplace=True)

    order = [a for a in AGE_ORDER_21 if a in pivot["age_group"].values]
    pivot["age_group"] = pd.Categorical(pivot["age_group"], categories=order, ordered=True)
    pivot = pivot.sort_values("age_group").reset_index(drop=True)

    # 列名整理
    cols = ["age_group"]
    if "男" in pivot.columns:
        cols.append("男")
    if "女" in pivot.columns:
        cols.append("女")
    pivot = pivot[cols]
    pivot["age_group"] = pivot["age_group"].astype(str)
    pivot = pivot.fillna(0)

    write_df(ws, pivot)

    # チャート: 折れ線
    chart = LineChart()
    chart.title = "Fig 1B: 性別×年齢群 処方数量（2024年度）"
    chart.y_axis.title = "処方数量（本）"
    chart.x_axis.title = "年齢群"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    for i, col_name in enumerate(cols[1:], 2):
        data = Reference(ws, min_col=i, min_row=1, max_row=len(pivot) + 1)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=len(pivot) + 1)
    chart.set_categories(cats)

    ws.add_chart(chart, "D2")


def build_fig1c(wb):
    """Fig 1C: 年齢分布の経年シフト（2014 vs 2024）"""
    ws = wb.create_sheet("Fig1C_data")
    df = pd.read_csv(PROC / "agesex_distribution_comparable_antivegf.csv")

    # 男女合算
    both = df.groupby(["year", "age_group"])["quantity"].sum().reset_index()
    # 各年度の合計に対するshare
    totals = both.groupby("year")["quantity"].transform("sum")
    both["share_pct"] = both["quantity"] / totals * 100

    # 2014と2024のみ
    pivot = both[both["year"].isin([2014, 2024])].pivot_table(
        index="age_group", columns="year", values="share_pct"
    ).reset_index()

    order = [a for a in AGE_ORDER if a in pivot["age_group"].values]
    pivot["age_group"] = pd.Categorical(pivot["age_group"], categories=order, ordered=True)
    pivot = pivot.sort_values("age_group").reset_index(drop=True)
    pivot.columns = ["age_group", "2014年度_share_pct", "2024年度_share_pct"]

    write_df(ws, pivot)

    # チャート: 棒グラフ（2系列並列）
    chart = BarChart()
    chart.type = "col"
    chart.title = "Fig 1C: 年齢分布の経年シフト（2014→2024）"
    chart.y_axis.title = "構成比（%）"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    data = Reference(ws, min_col=2, max_col=3, min_row=1, max_row=len(pivot) + 1)
    cats = Reference(ws, min_col=1, min_row=2, max_row=len(pivot) + 1)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)

    ws.add_chart(chart, "E2")


def build_fig2a(wb):
    """Fig 2A: 近似平均年齢・75歳以上比率・男性比率の推移"""
    ws = wb.create_sheet("Fig2A_data")
    df = pd.read_csv(PROC / "agesex_summary_antivegf.csv")
    df = df.rename(columns={
        "mean_age_approx": "近似平均年齢",
        "share_75plus_pct": "75歳以上比率(%)",
        "male_share_pct": "男性比率(%)"
    })
    df["year"] = df["year"].astype(int)

    write_df(ws, df)

    # チャート: 2軸折れ線（左軸=年齢、右軸=%）
    chart = LineChart()
    chart.title = "Fig 2A: 近似平均年齢・75歳以上比率・男性比率の推移"
    chart.style = 10
    chart.width = 28
    chart.height = 15
    chart.y_axis.title = "年齢（歳）"

    n = len(df) + 1

    # 近似平均年齢（左軸）
    data1 = Reference(ws, min_col=2, min_row=1, max_row=n)
    chart.add_data(data1, titles_from_data=True)

    # 75歳以上比率（右軸）
    data2 = Reference(ws, min_col=3, min_row=1, max_row=n)
    chart.add_data(data2, titles_from_data=True)

    # 男性比率（右軸）
    data3 = Reference(ws, min_col=4, min_row=1, max_row=n)
    chart.add_data(data3, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    # 2軸設定
    from openpyxl.chart import LineChart as LC2
    chart2 = LC2()
    chart2.y_axis.title = "割合（%）"
    chart2.y_axis.axId = 200

    # 75歳以上比率と男性比率を右軸に
    s1 = chart.series[1]
    s2 = chart.series[2]
    chart.series.pop(2)
    chart.series.pop(1)
    chart2.series.append(s1)
    chart2.series.append(s2)

    chart.y_axis.crosses = "min"
    chart2.y_axis.crosses = "max"
    chart += chart2

    ws.add_chart(chart, "F2")


def build_fig2b(wb):
    """Fig 2B: 外来/入院比率の推移"""
    ws = wb.create_sheet("Fig2B_data")
    df = pd.read_csv(PROC / "product_by_setting_antivegf.csv")

    # 年度×setting で合算
    setting_total = df.groupby(["year", "setting"])["quantity"].sum().reset_index()
    pivot = setting_total.pivot_table(index="year", columns="setting", values="quantity").reset_index().fillna(0)

    # 入院比率を計算
    if "入院" in pivot.columns and "外来(院内)" in pivot.columns:
        pivot["合計"] = pivot["入院"] + pivot["外来(院内)"]
        pivot["入院比率(%)"] = pivot["入院"] / pivot["合計"] * 100
    else:
        pivot["合計"] = 0
        pivot["入院比率(%)"] = 0

    out = pivot[["year", "外来(院内)", "入院", "合計", "入院比率(%)"]].copy()
    out.columns = ["年度", "外来（院内）", "入院", "合計", "入院比率(%)"]
    out["年度"] = out["年度"].astype(int)

    write_df(ws, out)

    # チャート: 2軸（左=数量棒、右=入院比率%折れ線）
    chart = BarChart()
    chart.type = "col"
    chart.title = "Fig 2B: 外来/入院の推移"
    chart.y_axis.title = "処方数量（本）"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(out) + 1

    # 外来
    d1 = Reference(ws, min_col=2, min_row=1, max_row=n)
    chart.add_data(d1, titles_from_data=True)
    # 入院
    d2 = Reference(ws, min_col=3, min_row=1, max_row=n)
    chart.add_data(d2, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    # 入院比率を右軸折れ線
    line = LineChart()
    line.y_axis.title = "入院比率（%）"
    line.y_axis.axId = 200

    d3 = Reference(ws, min_col=5, min_row=1, max_row=n)
    line.add_data(d3, titles_from_data=True)
    line.set_categories(cats)

    chart.y_axis.crosses = "min"
    line.y_axis.crosses = "max"
    chart += line

    ws.add_chart(chart, "G2")


def build_fig3a(wb):
    """Fig 3A: 都道府県別ランキング（2024年度、横棒）"""
    ws = wb.create_sheet("Fig3A_data")
    df = pd.read_csv(PROC / "prefecture_per_capita_ranking_antivegf.csv")

    # 2024年度のデータ
    out = df[["prefecture", "2024年度_人口10万対", "2024年度_順位"]].copy()
    out = out.sort_values("2024年度_順位", ascending=True).reset_index(drop=True)
    out.columns = ["都道府県", "人口10万対", "順位"]

    write_df(ws, out)

    # 横棒グラフ
    chart = BarChart()
    chart.type = "bar"
    chart.title = "Fig 3A: 都道府県別 人口10万対処方数量（2024年度）"
    chart.x_axis.title = "人口10万対（本）"
    chart.style = 10
    chart.width = 20
    chart.height = 35  # 47県分なので縦長

    n = len(out) + 1
    data = Reference(ws, min_col=2, min_row=1, max_row=n)
    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.legend = None

    # 順位の低い県が上に来るように反転
    chart.x_axis.scaling.orientation = "maxMin"

    ws.add_chart(chart, "E2")


def build_fig3b(wb):
    """Fig 3B: Gini・CVの経年推移"""
    ws = wb.create_sheet("Fig3B_data")
    df = pd.read_csv(PROC / "geographic_disparity_antivegf.csv")
    total = df[df["code"] == "ANTI_VEGF_TOTAL"][["year", "gini", "cv", "max_to_min_ratio", "p90_to_p10_ratio"]].copy()
    total = total.sort_values("year").reset_index(drop=True)
    total.columns = ["年度", "Gini", "CV", "最大/最小比", "P90/P10比"]
    total["年度"] = total["年度"].astype(int)

    write_df(ws, total)

    # 折れ線
    chart = LineChart()
    chart.title = "Fig 3B: 地域格差指標の推移（抗VEGF薬合計）"
    chart.y_axis.title = "指標値"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(total) + 1
    for col_idx in range(2, 6):
        data = Reference(ws, min_col=col_idx, min_row=1, max_row=n)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    ws.add_chart(chart, "G2")


def build_fig4a(wb):
    """Fig 4A: 成分別 処方数量推移（人口10万対）"""
    ws = wb.create_sheet("Fig4A_data")
    df = pd.read_csv(PROC / "national_trends_antivegf.csv")

    # 成分コードをグループ化（AFLIBERCEPT_ALL相当にまとめる）
    # year × code の count_per_100k をピボット
    # 主要4成分+合計
    codes_of_interest = {
        "AFLIBERCEPT": "アフリベルセプト2mg",
        "AFLIBERCEPT_8MG": "アフリベルセプト8mg",
        "BROLUCIZUMAB": "ブロルシズマブ",
        "FARICIMAB": "ファリシマブ",
        "RANIBIZUMAB_ORIG": "ラニビズマブ先発",
        "RANIBIZUMAB_BS": "ラニビズマブBS",
        "PEGAPTANIB": "ペガプタニブ",
    }

    df_filtered = df[df["code"].isin(codes_of_interest.keys())].copy()
    df_filtered["label"] = df_filtered["code"].map(codes_of_interest)

    pivot = df_filtered.pivot_table(
        index="year", columns="label", values="count_per_100k", aggfunc="sum"
    ).reset_index().fillna("")

    # 合計行を追加
    total_by_year = df_filtered.groupby("year")["count_per_100k"].sum().reset_index()
    total_by_year.columns = ["year", "抗VEGF薬合計"]
    pivot = pivot.merge(total_by_year, on="year", how="left")

    # 列順を整理
    col_order = ["year", "抗VEGF薬合計", "アフリベルセプト2mg", "アフリベルセプト8mg",
                 "ファリシマブ", "ラニビズマブ先発", "ラニビズマブBS", "ブロルシズマブ", "ペガプタニブ"]
    col_order = [c for c in col_order if c in pivot.columns]
    pivot = pivot[col_order]
    pivot.rename(columns={"year": "年度"}, inplace=True)
    pivot["年度"] = pivot["年度"].astype(int)

    write_df(ws, pivot)

    # 折れ線チャート
    chart = LineChart()
    chart.title = "Fig 4A: 成分別 処方数量推移（人口10万対）"
    chart.y_axis.title = "人口10万対（本）"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(pivot) + 1
    for col_idx in range(2, len(col_order) + 1):
        data = Reference(ws, min_col=col_idx, min_row=1, max_row=n)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    ws.add_chart(chart, "K2")


def build_fig4b(wb):
    """Fig 4B: 成分別シェア推移（積み上げ面）"""
    ws = wb.create_sheet("Fig4B_data")
    df = pd.read_csv(PROC / "national_trends_antivegf.csv")

    codes_of_interest = {
        "AFLIBERCEPT": "アフリベルセプト2mg",
        "AFLIBERCEPT_8MG": "アフリベルセプト8mg",
        "BROLUCIZUMAB": "ブロルシズマブ",
        "FARICIMAB": "ファリシマブ",
        "RANIBIZUMAB_ORIG": "ラニビズマブ先発",
        "RANIBIZUMAB_BS": "ラニビズマブBS",
        "PEGAPTANIB": "ペガプタニブ",
    }

    df_filtered = df[df["code"].isin(codes_of_interest.keys())].copy()
    df_filtered["label"] = df_filtered["code"].map(codes_of_interest)

    pivot = df_filtered.pivot_table(
        index="year", columns="label", values="share_of_antivegf_pct", aggfunc="sum"
    ).reset_index().fillna(0)

    col_order = ["year", "アフリベルセプト2mg", "アフリベルセプト8mg",
                 "ファリシマブ", "ラニビズマブ先発", "ラニビズマブBS", "ブロルシズマブ", "ペガプタニブ"]
    col_order = [c for c in col_order if c in pivot.columns]
    pivot = pivot[col_order]
    pivot.rename(columns={"year": "年度"}, inplace=True)
    pivot["年度"] = pivot["年度"].astype(int)

    write_df(ws, pivot)

    # 積み上げ面グラフ
    chart = AreaChart()
    chart.grouping = "stacked"
    chart.title = "Fig 4B: 成分別シェア推移"
    chart.y_axis.title = "シェア（%）"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(pivot) + 1
    for col_idx in range(2, len(col_order) + 1):
        data = Reference(ws, min_col=col_idx, min_row=1, max_row=n)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    ws.add_chart(chart, "K2")


def build_fig5a(wb):
    """Fig 5A: 剤形比率の推移（注射液 vs キット）"""
    ws = wb.create_sheet("Fig5A_data")
    df = pd.read_csv(PROC / "formulation_total_antivegf.csv")
    pivot = df.pivot_table(
        index="year", columns="formulation", values="share_pct"
    ).reset_index().fillna(0)
    pivot.rename(columns={"year": "年度"}, inplace=True)
    pivot["年度"] = pivot["年度"].astype(int)

    # 列順: 注射液, キット
    cols = ["年度"]
    if "注射液" in pivot.columns:
        cols.append("注射液")
    if "キット" in pivot.columns:
        cols.append("キット")
    pivot = pivot[cols]

    write_df(ws, pivot)

    # 積み上げ棒
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "stacked"
    chart.title = "Fig 5A: 剤形比率の推移（注射液 vs キット）"
    chart.y_axis.title = "シェア（%）"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(pivot) + 1
    for col_idx in range(2, len(cols) + 1):
        data = Reference(ws, min_col=col_idx, min_row=1, max_row=n)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    ws.add_chart(chart, "E2")


def build_fig5b(wb):
    """Fig 5B: バイオシミラーシェア推移"""
    ws = wb.create_sheet("Fig5B_data")
    df = pd.read_csv(PROC / "biosimilar_national_share.csv")
    pivot = df.pivot_table(
        index="year", columns="brand_type", values="share_pct"
    ).reset_index().fillna(0)
    pivot.rename(columns={"year": "年度"}, inplace=True)
    pivot["年度"] = pivot["年度"].astype(int)

    cols = ["年度"]
    if "先発" in pivot.columns:
        cols.append("先発")
    if "バイオシミラー" in pivot.columns:
        cols.append("バイオシミラー")
    pivot = pivot[cols]

    write_df(ws, pivot)

    # 積み上げ面グラフ
    chart = AreaChart()
    chart.grouping = "stacked"
    chart.title = "Fig 5B: ラニビズマブ 先発 vs バイオシミラー シェア推移"
    chart.y_axis.title = "シェア（%）"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(pivot) + 1
    for col_idx in range(2, len(cols) + 1):
        data = Reference(ws, min_col=col_idx, min_row=1, max_row=n)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    ws.add_chart(chart, "E2")


def build_fig5c(wb):
    """Fig 5C: 薬剤費推移と構成（製品別積み上げ棒）"""
    ws = wb.create_sheet("Fig5C_data")
    df = pd.read_csv(PROC / "product_trends_antivegf.csv")

    # 製品名×年度で薬剤費を億円に
    df["cost_oku"] = df["cost"] / 1e8

    pivot = df.pivot_table(
        index="year", columns="product_name", values="cost_oku", aggfunc="sum"
    ).reset_index().fillna(0)
    pivot.rename(columns={"year": "年度"}, inplace=True)
    pivot["年度"] = pivot["年度"].astype(int)

    write_df(ws, pivot)

    # 積み上げ棒グラフ
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "stacked"
    chart.title = "Fig 5C: 薬剤費推移と構成（億円）"
    chart.y_axis.title = "薬剤費（億円）"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(pivot) + 1
    ncols = len(pivot.columns)
    for col_idx in range(2, ncols + 1):
        data = Reference(ws, min_col=col_idx, min_row=1, max_row=n)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    ws.add_chart(chart, f"{chr(64 + ncols + 2)}2")


def build_suppl(wb):
    """Suppl Fig: G016算定回数 vs 抗VEGF薬数量"""
    ws = wb.create_sheet("SuppFig_data")
    df = pd.read_csv(PROC / "g016_vs_drug_validation.csv")
    out = df[["year", "g016_procedures", "antivegf_vials", "antivegf_per_g016_pct"]].copy()
    out.columns = ["年度", "G016算定回数", "抗VEGF薬数量", "抗VEGF/G016(%)"]
    out["年度"] = out["年度"].astype(int)

    write_df(ws, out)

    # 2軸：左=数量（棒2本）、右=比率%（折れ線）
    chart = BarChart()
    chart.type = "col"
    chart.title = "Suppl Fig: G016算定回数 vs 抗VEGF薬数量"
    chart.y_axis.title = "件数/本数"
    chart.style = 10
    chart.width = 28
    chart.height = 15

    n = len(out) + 1
    d1 = Reference(ws, min_col=2, min_row=1, max_row=n)
    d2 = Reference(ws, min_col=3, min_row=1, max_row=n)
    chart.add_data(d1, titles_from_data=True)
    chart.add_data(d2, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n)
    chart.set_categories(cats)

    # 右軸に比率
    line = LineChart()
    line.y_axis.title = "抗VEGF/G016（%）"
    line.y_axis.axId = 200
    d3 = Reference(ws, min_col=4, min_row=1, max_row=n)
    line.add_data(d3, titles_from_data=True)
    line.set_categories(cats)

    chart.y_axis.crosses = "min"
    line.y_axis.crosses = "max"
    chart += line

    ws.add_chart(chart, "F2")


# ---------------------------------------------------------------------------
# 04_図表/plots/*.png の再現（P01〜P10）
# ---------------------------------------------------------------------------

# 公開粒度（2015年度以降は90歳以上が3区分に細分化）— visualization_antivegf.py と同一
AGE_ORDER_PUBLISHED = AGE_ORDER[:-1] + ["90～94歳", "95～99歳", "100歳以上", "90歳以上"]


def _note(ws, text, row=1):
    """シート先頭に元PNGの対応を書く。データは row+2 行目から。"""
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(bold=True)


def _year_pivot(df, columns, values, aggfunc="sum"):
    """year × columns のピボットを「年度」始まりの表に整える。"""
    piv = df.pivot_table(index="year", columns=columns, values=values,
                         aggfunc=aggfunc).fillna(0).reset_index()
    piv.rename(columns={"year": "年度"}, inplace=True)
    piv["年度"] = piv["年度"].astype(int)
    piv.columns = [str(c) for c in piv.columns]
    return piv


def _series_chart(ws, chart, df, first_row, anchor):
    """1列目=カテゴリ、2列目以降=系列としてチャートに流し込む。"""
    n_last = first_row + len(df)
    for col_idx in range(2, len(df.columns) + 1):
        chart.add_data(Reference(ws, min_col=col_idx, min_row=first_row, max_row=n_last),
                       titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=first_row + 1, max_row=n_last))
    chart.style = 10
    ws.add_chart(chart, anchor)


def build_p01(wb):
    """P01: product_trends.png — 製品別 処方数量の推移（折れ線）"""
    ws = wb.create_sheet("P01_product_trends")
    _note(ws, "plots/product_trends.png の再現（product_trends_antivegf.csv / year × product_name × quantity）")
    df = pd.read_csv(PROC / "product_trends_antivegf.csv")
    piv = _year_pivot(df, "product_name", "quantity")
    write_df(ws, piv, start_row=3)

    chart = LineChart()
    chart.title = "抗VEGF薬 製品別 処方数量の推移（全国・外来＋入院）"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "処方数量（バイアル・シリンジ本数）"
    chart.width = 28
    chart.height = 15
    _series_chart(ws, chart, piv, 3, f"{get_column_letter(len(piv.columns) + 2)}3")


def build_p02(wb):
    """P02: product_share_stacked.png — 製品別シェアの積み上げ面"""
    ws = wb.create_sheet("P02_product_share_stacked")
    _note(ws, "plots/product_share_stacked.png の再現（product_trends_antivegf.csv / share_pct）")
    df = pd.read_csv(PROC / "product_trends_antivegf.csv")
    piv = _year_pivot(df, "product_name", "share_pct", aggfunc="mean")
    write_df(ws, piv, start_row=3)

    chart = AreaChart()
    chart.grouping = "stacked"
    chart.overlap = 100
    chart.title = "抗VEGF薬 製品別シェアの推移（%）"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "シェア（%）"
    chart.y_axis.scaling.min = 0
    chart.y_axis.scaling.max = 100
    chart.width = 28
    chart.height = 15
    _series_chart(ws, chart, piv, 3, f"{get_column_letter(len(piv.columns) + 2)}3")


def build_p03(wb):
    """P03: formulation_share_total.png — 剤形比率（積み上げ棒）"""
    ws = wb.create_sheet("P03_formulation_share_total")
    _note(ws, "plots/formulation_share_total.png の再現（formulation_total_antivegf.csv / share_pct）")
    df = pd.read_csv(PROC / "formulation_total_antivegf.csv")
    piv = _year_pivot(df, "formulation", "share_pct")
    cols = ["年度"] + [c for c in ["注射液", "キット"] if c in piv.columns]
    piv = piv[cols]
    write_df(ws, piv, start_row=3)

    chart = BarChart()
    chart.type = "col"
    chart.grouping = "stacked"
    chart.overlap = 100
    chart.title = "抗VEGF薬全体の剤形比率（注射液 vs キット）"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "シェア（%）"
    chart.width = 24
    chart.height = 13
    _series_chart(ws, chart, piv, 3, "F3")


def build_p04(wb):
    """P04: formulation_kit_share_by_molecule.png — 成分別キット比率（折れ線）"""
    ws = wb.create_sheet("P04_formulation_kit_share_mol")
    _note(ws, "plots/formulation_kit_share_by_molecule.png の再現"
              "（formulation_by_molecule_antivegf.csv / has_both_formulations=True かつ formulation=キット）")
    df = pd.read_csv(PROC / "formulation_by_molecule_antivegf.csv")
    df = df[df["has_both_formulations"] & (df["formulation"] == "キット")]
    piv = _year_pivot(df, "molecule_name", "share_within_molecule_pct", aggfunc="mean")
    write_df(ws, piv, start_row=3)

    chart = LineChart()
    chart.title = "成分別 キット製剤の比率"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "キット比率（%）"
    chart.y_axis.scaling.min = 0
    chart.y_axis.scaling.max = 100
    chart.width = 24
    chart.height = 13
    _series_chart(ws, chart, piv, 3, f"{get_column_letter(len(piv.columns) + 2)}3")


def build_p05(wb):
    """P05: biosimilar_share.png — 左:数量積み上げ棒 / 右:シェア折れ線（2パネル）"""
    ws = wb.create_sheet("P05_biosimilar_share")
    _note(ws, "plots/biosimilar_share.png の再現（biosimilar_national_share.csv / 左=quantity, 右=share_pct）")
    df = pd.read_csv(PROC / "biosimilar_national_share.csv")

    qty = _year_pivot(df, "brand_type", "quantity")
    shr = _year_pivot(df, "brand_type", "share_pct")
    order = [c for c in ["先発", "バイオシミラー"] if c in qty.columns]
    qty = qty[["年度"] + order]
    shr = shr[["年度"] + order]

    ws.cell(row=3, column=1, value="【左パネル】処方数量").font = Font(bold=True)
    write_df(ws, qty, start_row=4)
    start2 = 4 + len(qty) + 3
    ws.cell(row=start2 - 1, column=1, value="【右パネル】シェア（%）").font = Font(bold=True)
    write_df(ws, shr, start_row=start2)

    c1 = BarChart()
    c1.type = "col"
    c1.grouping = "stacked"
    c1.overlap = 100
    c1.title = "ラニビズマブ 処方数量（先発 vs BS）"
    c1.x_axis.title = "年度"
    c1.y_axis.title = "処方数量"
    c1.width = 16
    c1.height = 11
    _series_chart(ws, c1, qty, 4, "F3")

    c2 = LineChart()
    c2.title = "ラニビズマブ シェア推移（%）"
    c2.x_axis.title = "年度"
    c2.y_axis.title = "シェア（%）"
    c2.y_axis.scaling.min = 0
    c2.y_axis.scaling.max = 100
    c2.width = 16
    c2.height = 11
    _series_chart(ws, c2, shr, start2, "R3")


def build_p06(wb):
    """P06: agesex_pyramid_latest.png — 年齢階級・性別ピラミッド（最新年度）"""
    ws = wb.create_sheet("P06_agesex_pyramid_latest")
    df = pd.read_csv(PROC / "agesex_distribution_published_antivegf.csv")
    latest_year = int(df["year"].max())
    _note(ws, f"plots/agesex_pyramid_latest.png の再現"
              f"（agesex_distribution_published_antivegf.csv / year={latest_year}）"
              "　※「男（描画用）」は左向き描画のため符号を反転した列で、実数は「男」列")

    latest = df[df["year"] == latest_year]
    piv = latest.pivot_table(index="age_group_detail", columns="sex",
                             values="quantity", aggfunc="sum").fillna(0)
    order = [a for a in AGE_ORDER_PUBLISHED if a in piv.index]
    piv = piv.reindex(order).reset_index()
    piv.rename(columns={"age_group_detail": "年齢階級"}, inplace=True)
    for s in ["男", "女"]:
        if s not in piv.columns:
            piv[s] = 0
    out = piv[["年齢階級", "男", "女"]].copy()
    out["男（描画用）"] = -out["男"]
    write_df(ws, out, start_row=3)

    chart = BarChart()
    chart.type = "bar"
    chart.grouping = "stacked"
    chart.overlap = 100
    chart.title = f"抗VEGF薬 年齢階級・性別分布（{latest_year}年度）"
    chart.x_axis.title = "処方数量（左：男 / 右：女）"
    chart.width = 20
    chart.height = 16
    n_last = 3 + len(out)
    for col_idx in (4, 3):  # 男（描画用）→ 左、女 → 右
        chart.add_data(Reference(ws, min_col=col_idx, min_row=3, max_row=n_last),
                       titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=4, max_row=n_last))
    chart.x_axis.tickLblPos = "low"  # 目盛ラベルを軸の外側へ（棒と重ねない）
    chart.style = 10
    ws.add_chart(chart, "F3")


def build_p07(wb):
    """P07: age_distribution_heatmap.png — 年齢構成比の推移（条件付き書式のカラースケール）"""
    ws = wb.create_sheet("P07_age_distribution_heatmap")
    _note(ws, "plots/age_distribution_heatmap.png の再現"
              "（agesex_distribution_comparable_antivegf.csv / 男女計の年度内構成比%）"
              "　※Excelにヒートマップのグラフ種別が無いため、条件付き書式のカラースケールで再現")
    df = pd.read_csv(PROC / "agesex_distribution_comparable_antivegf.csv")
    age = df.groupby(["year", "age_group"], as_index=False)["quantity"].sum()
    age["share"] = age.groupby("year")["quantity"].transform(lambda s: s / s.sum() * 100)
    piv = age.pivot_table(index="age_group", columns="year", values="share")
    piv = piv.reindex([a for a in AGE_ORDER if a in piv.index]).reset_index()
    piv.rename(columns={"age_group": "年齢階級"}, inplace=True)
    piv.columns = ["年齢階級"] + [f"{int(c)}年度" for c in piv.columns[1:]]
    write_df(ws, piv, start_row=3)

    last_col = get_column_letter(len(piv.columns))
    ws.conditional_formatting.add(
        f"B4:{last_col}{3 + len(piv)}",
        ColorScaleRule(start_type="min", start_color="FFFFE5",
                       mid_type="percentile", mid_value=50, mid_color="FEB24C",
                       end_type="max", end_color="BD0026"),
    )
    for col in range(2, len(piv.columns) + 1):
        for row in range(4, 4 + len(piv)):
            ws.cell(row=row, column=col).number_format = "0.0"

    # 同じ行列を転置し、Excelのグラフ（100%積み上げ縦棒）でも構成比の推移を描く
    trans = piv.set_index("年齢階級").T.reset_index()
    trans.rename(columns={"index": "年度"}, inplace=True)
    start2 = 3 + len(piv) + 3
    ws.cell(row=start2 - 1, column=1,
            value="【グラフ用】上表を転置（年度×年齢階級）").font = Font(bold=True)
    write_df(ws, trans, start_row=start2)

    chart = BarChart()
    chart.type = "col"
    chart.grouping = "percentStacked"
    chart.overlap = 100
    chart.title = "抗VEGF薬 年齢構成比の推移（%）"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "構成比（%）"
    chart.width = 28
    chart.height = 15
    _series_chart(ws, chart, trans, start2, f"{get_column_letter(len(piv.columns) + 2)}3")


def build_p08(wb):
    """P08: prefecture_ranking_latest.png — 都道府県別 人口10万対（最新年度、横棒）"""
    ws = wb.create_sheet("P08_prefecture_ranking_latest")
    panel = pd.read_csv(PROC / "panel_zero.csv")
    latest_year = int(panel["year"].max())
    _note(ws, f"plots/prefecture_ranking_latest.png の再現"
              f"（panel_zero.csv / code=ANTI_VEGF_TOTAL, year={latest_year}）")

    total = panel[(panel["code"] == "ANTI_VEGF_TOTAL") & (panel["year"] == latest_year)]
    out = total[["prefecture", "count_per_100k"]].sort_values(
        "count_per_100k", ascending=False).reset_index(drop=True)
    out.columns = ["都道府県", "人口10万対 処方数量"]
    write_df(ws, out, start_row=3)

    chart = BarChart()
    chart.type = "bar"
    chart.title = f"抗VEGF薬 都道府県別 人口10万対処方数量（{latest_year}年度）"
    chart.x_axis.title = "人口10万対 処方数量"
    chart.width = 18
    chart.height = 32
    chart.legend = None
    _series_chart(ws, chart, out, 3, "D3")
    chart.x_axis.scaling.orientation = "maxMin"  # 上位が上に来るよう反転


def build_p09(wb):
    """P09: gini_trends.png — 主要解析単位のGini係数推移（折れ線）"""
    ws = wb.create_sheet("P09_gini_trends")
    _note(ws, "plots/gini_trends.png の再現（geographic_disparity_antivegf.csv / "
              "code=ANTI_VEGF_TOTAL, AFLIBERCEPT, RANIBIZUMAB_ALL, FARICIMAB, RANIBIZUMAB_BS）")
    df = pd.read_csv(PROC / "geographic_disparity_antivegf.csv")
    codes = ["ANTI_VEGF_TOTAL", "AFLIBERCEPT", "RANIBIZUMAB_ALL", "FARICIMAB", "RANIBIZUMAB_BS"]
    sub = df[df["code"].isin(codes)]
    piv = _year_pivot(sub, "name", "gini", aggfunc="mean")
    write_df(ws, piv, start_row=3)

    chart = LineChart()
    chart.title = "都道府県間格差（Gini係数）の推移"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "Gini係数"
    chart.width = 24
    chart.height = 13
    _series_chart(ws, chart, piv, 3, f"{get_column_letter(len(piv.columns) + 2)}3")


def build_p10(wb):
    """P10: cost_trends.png — 製品別 薬剤費の推移（積み上げ面、億円）"""
    ws = wb.create_sheet("P10_cost_trends")
    _note(ws, "plots/cost_trends.png の再現（product_trends_antivegf.csv / cost を億円換算）")
    df = pd.read_csv(PROC / "product_trends_antivegf.csv")
    df = df.assign(cost_oku=df["cost"] / 1e8)
    piv = _year_pivot(df, "product_name", "cost_oku")
    write_df(ws, piv, start_row=3)

    chart = AreaChart()
    chart.grouping = "stacked"
    chart.overlap = 100
    chart.title = "抗VEGF薬 薬剤費の推移（薬価×処方数量）"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "薬剤費（億円）"
    chart.width = 28
    chart.height = 15
    _series_chart(ws, chart, piv, 3, f"{get_column_letter(len(piv.columns) + 2)}3")


# ---------------------------------------------------------------------------
# 年齢階級別 男女差（S1〜S5）
# ---------------------------------------------------------------------------

SETTINGS = {
    "外来のみ": ["外来(院内)"],
    "外来＋入院": ["外来(院内)", "入院"],
}


def _load_agesex(settings):
    """秘匿セルを0で補完した年齢性別データ（抗VEGF薬のみ）を読む。"""
    df = pd.read_csv(PROC / "processed_agesex_zero.csv")
    df = df[(df["category"] == "ANTI_VEGF") & (df["setting"].isin(settings))]
    return df.copy()


def _sex_diff_table(df, keys):
    """keys（年度・成分など）×年齢階級で男女差の指標を組み立てる。

    quantity は秘匿セルを0で補完した値。masked/cells で秘匿の程度を併記する。
    """
    g = df.groupby(keys + ["age_group", "sex"]).agg(
        qty=("quantity", "sum"), masked=("masked", "sum"), cells=("masked", "size")
    ).reset_index()

    wide = g.pivot_table(index=keys + ["age_group"], columns="sex",
                         values=["qty", "masked", "cells"], fill_value=0)
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    for col in ["qty_男", "qty_女", "masked_男", "masked_女", "cells_男", "cells_女"]:
        if col not in wide.columns:
            wide[col] = 0

    wide["男−女"] = wide["qty_男"] - wide["qty_女"]
    wide["男/女比"] = [m / f if f > 0 else None
                    for m, f in zip(wide["qty_男"], wide["qty_女"])]
    # 性別内構成比: その集計単位・その性別の総量に占める当該年齢階級の割合
    for s in ["男", "女"]:
        tot = wide.groupby(keys)[f"qty_{s}"].transform("sum")
        wide[f"{s}_構成比%"] = [q / t * 100 if t > 0 else None
                             for q, t in zip(wide[f"qty_{s}"], tot)]
    wide["男性比率%"] = [m / (m + f) * 100 if (m + f) > 0 else None
                     for m, f in zip(wide["qty_男"], wide["qty_女"])]
    wide["秘匿セル数"] = wide["masked_男"] + wide["masked_女"]
    wide["全セル数"] = wide["cells_男"] + wide["cells_女"]
    wide["秘匿率%"] = wide["秘匿セル数"] / wide["全セル数"] * 100

    order = {a: i for i, a in enumerate(AGE_ORDER)}
    wide["_o"] = wide["age_group"].map(order)
    wide = wide.sort_values(keys + ["_o"]).drop(columns=["_o"])

    out = wide[keys + ["age_group", "qty_男", "qty_女", "男−女", "男/女比",
                       "男_構成比%", "女_構成比%", "男性比率%",
                       "秘匿セル数", "全セル数", "秘匿率%"]].copy()
    out.columns = keys + ["年齢階級", "男", "女", "男−女", "男/女比",
                          "男_構成比%", "女_構成比%", "男性比率%",
                          "秘匿セル数", "全セル数", "秘匿率%"]
    return out


def _write_block(ws, df, start_row, caption):
    ws.cell(row=start_row - 1, column=1, value=caption).font = Font(bold=True)
    write_df(ws, df, start_row=start_row)
    return start_row + len(df) + 3


def _fmt(ws, first_row, n_rows, col_formats):
    for col, fmt in col_formats.items():
        for r in range(first_row + 1, first_row + 1 + n_rows):
            ws.cell(row=r, column=col).number_format = fmt


def _build_sexdiff_total(wb, sheet_name, label, settings):
    """S1/S2: 抗VEGF薬合計の年齢階級別 男女差。"""
    ws = wb.create_sheet(sheet_name)
    _note(ws, f"抗VEGF薬合計 × 年齢階級 × 性別（{label}）"
              "　※秘匿セル（NDB原表記「-」＝10未満）は0で補完済み。"
              "「秘匿セル数／全セル数」列で各行の信頼度を確認すること")
    df = _load_agesex(settings)
    tbl = _sex_diff_table(df, ["year"])
    tbl = tbl.rename(columns={"year": "年度"})
    tbl["年度"] = tbl["年度"].astype(int)

    row = _write_block(ws, tbl, 4, f"【明細】年度×年齢階級（{label}）")
    _fmt(ws, 4, len(tbl), {4: "#,##0.0", 5: "#,##0.0", 6: "#,##0.0",
                           7: "0.000", 8: "0.00", 9: "0.00", 10: "0.00", 13: "0.0"})

    # グラフ用ピボット（年齢階級 × 年度）
    def _piv(value):
        p = tbl.pivot_table(index="年齢階級", columns="年度", values=value)
        p = p.reindex([a for a in AGE_ORDER if a in p.index]).reset_index()
        p.columns = ["年齢階級"] + [f"{int(c)}年度" for c in p.columns[1:]]
        return p

    blocks = [
        ("男性比率%", "【グラフ1】年齢階級別 男性比率（%）の推移",
         "年齢階級別 男性比率（%）の推移", "男性比率（%）"),
        ("男−女", "【グラフ2】年齢階級別 男女差（男−女、本）の推移",
         "年齢階級別 男女差（男−女、本）の推移", "男−女（本）"),
    ]
    anchor_col = get_column_letter(len(tbl.columns) + 2)
    anchor_row = 3
    for value, caption, title, ytitle in blocks:
        p = _piv(value)
        start = row
        row = _write_block(ws, p, start, caption)
        chart = LineChart()
        chart.title = f"{title}（{label}）"
        chart.x_axis.title = "年齢階級"
        chart.y_axis.title = ytitle
        chart.width = 28
        chart.height = 14
        _series_chart(ws, chart, p, start, f"{anchor_col}{anchor_row}")
        anchor_row += 29

    # 性別内構成比（最新年度）
    latest = int(tbl["年度"].max())
    comp = tbl[tbl["年度"] == latest][["年齢階級", "男_構成比%", "女_構成比%"]].reset_index(drop=True)
    start = row
    row = _write_block(ws, comp, start, f"【グラフ3】{latest}年度 性別内 年齢構成比（%）")
    chart = LineChart()
    chart.title = f"{latest}年度 性別内 年齢構成比（%）（{label}）"
    chart.x_axis.title = "年齢階級"
    chart.y_axis.title = "構成比（%）"
    chart.width = 28
    chart.height = 14
    _series_chart(ws, chart, comp, start, f"{anchor_col}{anchor_row}")


def _build_sexdiff_molecule(wb, sheet_name, label, settings):
    """S3/S4: 成分別の年齢階級別 男女差。"""
    ws = wb.create_sheet(sheet_name)
    _note(ws, f"成分別 × 年齢階級 × 性別（{label}）"
              "　※秘匿セルは0で補完済み。ペガプタニブは全年度・全セル秘匿のため実質データなし")
    df = _load_agesex(settings)
    tbl = _sex_diff_table(df, ["year", "molecule_name"])
    tbl = tbl.rename(columns={"year": "年度", "molecule_name": "成分"})
    tbl["年度"] = tbl["年度"].astype(int)

    row = _write_block(ws, tbl, 4, f"【明細】年度×成分×年齢階級（{label}）")
    _fmt(ws, 4, len(tbl), {5: "#,##0.0", 6: "#,##0.0", 7: "#,##0.0",
                           8: "0.000", 9: "0.00", 10: "0.00", 11: "0.00", 14: "0.0"})

    anchor_col = get_column_letter(len(tbl.columns) + 2)

    # グラフ1: 成分別 男性比率（%）の推移（全年齢計）
    tot = df.groupby(["year", "molecule_name", "sex"])["quantity"].sum().reset_index()
    tot = tot.pivot_table(index=["year", "molecule_name"], columns="sex",
                          values="quantity", fill_value=0).reset_index()
    for s in ["男", "女"]:
        if s not in tot.columns:
            tot[s] = 0
    tot["男性比率%"] = [m / (m + f) * 100 if (m + f) > 0 else None
                    for m, f in zip(tot["男"], tot["女"])]
    p1 = tot.pivot_table(index="year", columns="molecule_name",
                         values="男性比率%").reset_index()
    p1.rename(columns={"year": "年度"}, inplace=True)
    p1["年度"] = p1["年度"].astype(int)
    p1.columns = [str(c) for c in p1.columns]
    start = row
    row = _write_block(ws, p1, start, "【グラフ1】成分別 男性比率（%）の推移（全年齢計）")
    chart = LineChart()
    chart.title = f"成分別 男性比率（%）の推移（{label}）"
    chart.x_axis.title = "年度"
    chart.y_axis.title = "男性比率（%）"
    chart.width = 26
    chart.height = 14
    _series_chart(ws, chart, p1, start, f"{anchor_col}3")

    # グラフ2: 最新年度の成分別・年齢階級別 男性比率（%）
    latest = int(tbl["年度"].max())
    p2 = tbl[tbl["年度"] == latest].pivot_table(index="年齢階級", columns="成分",
                                              values="男性比率%")
    p2 = p2.reindex([a for a in AGE_ORDER if a in p2.index]).reset_index()
    p2.columns = [str(c) for c in p2.columns]
    start = row
    row = _write_block(ws, p2, start, f"【グラフ2】{latest}年度 成分別・年齢階級別 男性比率（%）")
    chart = LineChart()
    chart.title = f"{latest}年度 成分別・年齢階級別 男性比率（%）（{label}）"
    chart.x_axis.title = "年齢階級"
    chart.y_axis.title = "男性比率（%）"
    chart.width = 26
    chart.height = 14
    _series_chart(ws, chart, p2, start, f"{anchor_col}32")


def build_s5_masking(wb):
    """S5: S1〜S4で使った年齢性別データの秘匿状況サマリ。"""
    ws = wb.create_sheet("S5_秘匿状況")
    _note(ws, "S1〜S4の元データ（processed_agesex_zero.csv）の秘匿状況。"
              "捕捉率＝年齢性別内訳の合計÷公表総計。公表総計は秘匿なしの値")

    raw = pd.read_csv(PROC / "ophthalmic_injection_agesex.csv", dtype=str)
    raw["医薬品コード"] = raw["医薬品コード"].astype(str)
    zero = pd.read_csv(PROC / "processed_agesex_zero.csv")
    zero = zero[zero["category"] == "ANTI_VEGF"]  # マキュエイド・ビスダインを除く
    av_codes = set(zero["drug_code"].astype(str))
    raw = raw[raw["医薬品コード"].isin(av_codes)].copy()
    raw["masked"] = raw["秘匿フラグ"].astype(int)
    raw["val"] = pd.to_numeric(raw["処方数量"], errors="coerce").fillna(0.0)
    raw["総計"] = pd.to_numeric(raw["総計_処方数量"], errors="coerce")
    raw["年度"] = raw["年度"].astype(int)
    name = dict(zip(zero["drug_code"].astype(str), zero["molecule_name"]))
    raw["成分"] = raw["医薬品コード"].map(name)

    row = 4
    for label, settings in SETTINGS.items():
        sub = raw[raw["区分"].isin(settings)]
        num = sub.groupby("年度")["val"].sum()
        den = sub.drop_duplicates(["年度", "医薬品コード", "区分"]).groupby("年度")["総計"].sum()
        cell = sub.groupby("年度")["masked"].agg(["size", "sum"])
        t = pd.DataFrame({
            "年度": num.index.astype(int),
            "内訳合計": num.values,
            "公表総計": den.values,
            "欠落": (den - num).values,
            "捕捉率%": (num / den * 100).values,
            "全セル数": cell["size"].values,
            "秘匿セル数": cell["sum"].values,
            "セル秘匿率%": (cell["sum"] / cell["size"] * 100).values,
        })
        start = row
        row = _write_block(ws, t, start, f"【1】抗VEGF薬合計の捕捉率（{label}）")
        _fmt(ws, start, len(t), {2: "#,##0.0", 3: "#,##0.0", 4: "#,##0.0",
                                 5: "0.00", 8: "0.0"})
        c = LineChart()
        c.add_data(Reference(ws, min_col=5, min_row=start,
                             max_row=start + len(t)), titles_from_data=True)
        c.set_categories(Reference(ws, min_col=1, min_row=start + 1,
                                   max_row=start + len(t)))
        c.title = f"抗VEGF薬合計 年齢性別内訳の捕捉率（%）（{label}）"
        c.x_axis.title = "年度"
        c.y_axis.title = "捕捉率（%）"
        c.width, c.height, c.style = 22, 12, 10
        ws.add_chart(c, f"K{start}")

    # 成分別の捕捉率
    for label, settings in SETTINGS.items():
        sub = raw[raw["区分"].isin(settings)]
        num = sub.groupby(["成分", "年度"])["val"].sum()
        den = sub.drop_duplicates(["年度", "医薬品コード", "区分"]).groupby(
            ["成分", "年度"])["総計"].sum()
        t = (num / den * 100).unstack().reset_index()
        t.columns = ["成分"] + [f"{int(c)}年度" for c in t.columns[1:]]
        start = row
        row = _write_block(ws, t, start, f"【2】成分別 捕捉率%（{label}）")
        _fmt(ws, start, len(t), {c: "0.0" for c in range(2, len(t.columns) + 1)})


def main():
    wb = Workbook()
    # デフォルトシートを削除
    wb.remove(wb.active)

    print("Building Fig 1A...")
    build_fig1a(wb)
    print("Building Fig 1B...")
    build_fig1b(wb)
    print("Building Fig 1C...")
    build_fig1c(wb)
    print("Building Fig 2A...")
    build_fig2a(wb)
    print("Building Fig 2B...")
    build_fig2b(wb)
    print("Building Fig 3A...")
    build_fig3a(wb)
    print("Building Fig 3B...")
    build_fig3b(wb)
    print("Building Fig 4A...")
    build_fig4a(wb)
    print("Building Fig 4B...")
    build_fig4b(wb)
    print("Building Fig 5A...")
    build_fig5a(wb)
    print("Building Fig 5B...")
    build_fig5b(wb)
    print("Building Fig 5C...")
    build_fig5c(wb)
    print("Building Suppl Fig...")
    build_suppl(wb)

    for name, fn in [
        ("P01 product_trends", build_p01),
        ("P02 product_share_stacked", build_p02),
        ("P03 formulation_share_total", build_p03),
        ("P04 formulation_kit_share_by_molecule", build_p04),
        ("P05 biosimilar_share", build_p05),
        ("P06 agesex_pyramid_latest", build_p06),
        ("P07 age_distribution_heatmap", build_p07),
        ("P08 prefecture_ranking_latest", build_p08),
        ("P09 gini_trends", build_p09),
        ("P10 cost_trends", build_p10),
    ]:
        print(f"Building {name}...")
        fn(wb)

    print("Building S1 男女差 合計 外来のみ...")
    _build_sexdiff_total(wb, "S1_男女差_合計_外来のみ", "外来のみ", SETTINGS["外来のみ"])
    print("Building S2 男女差 合計 外来＋入院...")
    _build_sexdiff_total(wb, "S2_男女差_合計_外来入院", "外来＋入院", SETTINGS["外来＋入院"])
    print("Building S3 男女差 成分別 外来のみ...")
    _build_sexdiff_molecule(wb, "S3_男女差_成分別_外来のみ", "外来のみ", SETTINGS["外来のみ"])
    print("Building S4 男女差 成分別 外来＋入院...")
    _build_sexdiff_molecule(wb, "S4_男女差_成分別_外来入院", "外来＋入院", SETTINGS["外来＋入院"])
    print("Building S5 秘匿状況...")
    build_s5_masking(wb)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(OUT))
    print(f"\nSaved: {OUT}")
    print(f"Sheets: {wb.sheetnames}")


if __name__ == "__main__":
    main()
