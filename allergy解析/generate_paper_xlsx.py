#!/usr/bin/env python3
"""
generate_paper_xlsx.py
論文 Fig/Table 用の .xlsx ファイル（データ＋Excelグラフ埋め込み）を生成する。

出力先: allergy解析/論文に使うファイルたち/

生成ファイル:
  - Fig1_age_sex_profile.xlsx   (Fig 1A + 1B)
  - Fig2_age_distribution.xlsx  (Fig 2: 年齢分布シフト + 加重平均年齢)
  - Fig3_prefecture_map.xlsx    (Fig 3: 都道府県別ランキング)
  - Fig4_trends_shares.xlsx     (Fig 4: 11年トレンド + 市場シェア)
  - Tables_all.xlsx             (Table 1–5 をまとめて)
"""
import os
import sys
import csv

import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.chart import (
    BarChart, LineChart, Reference, BarChart3D
)
from openpyxl.chart.series import DataPoint
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.layout import Layout, ManualLayout
from openpyxl.chart.legend import Legend
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers

# ── パス設定 ──
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))
from paths import nokouhi_from_argv, output_dir  # noqa: E402

# generate_paper_csvs.py が出したステージングのCSVを読み、同じ場所にxlsxを出す
DATA_DIR = os.environ.get("PAPER_CSV_OUT_DIR") or os.path.join(
    output_dir(nokouhi_from_argv()), "論文用CSV")
OUT_DIR = DATA_DIR  # 同じフォルダに出力

# 年齢グループのソート順
AGE_ORDER = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80-84", "85-89", "90-94", "95-99", "100+", "90+",
]

# 論文で使う主要薬剤（グラフ表示用）
MAIN_DRUGS = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
MAIN_DRUG_NAMES = {
    "EPINASTINE": "Epinastine",
    "OLOPATADINE": "Olopatadine",
    "LEVOCASTINE": "Levocabastine",
    "ALLERGY_EYE_TOTAL": "Total",
    "ANTI_HIST": "Antihistamines",
    "MED_RELEASE": "Mast cell stabilizers",
    "IMMUNO": "Immunosuppressants",
    "CROMOGLICATE": "Cromoglicate",
    "TRANILAST": "Tranilast",
    "CYCLOSPORINE": "Cyclosporine",
    "TACROLIMUS": "Tacrolimus",
    "TOP3_TOTAL": "Top 3 total",
    "KETOTIFEN": "Ketotifen",
    "ACITAZANOLAST": "Acitazanolast",
    "PEMIROLAST": "Pemirolast",
    "IBUDILAST": "Ibudilast",
}

DRUG_CLASS_EN = {
    "小計/合計": "Subtotal/Total",
    "抗ヒスタミン薬": "Antihistamines",
    "メディエーター遊離抑制薬": "Mast cell stabilizers",
    "免疫抑制薬": "Immunosuppressants",
}

PROCEDURE_NAME_EN = {
    "抗アレルギー点眼薬（全体合計）": "All anti-allergic eye drops (total)",
    "抗ヒスタミン点眼薬（合計）": "Antihistamine eye drops (subtotal)",
    "メディエーター遊離抑制点眼薬（合計）": "Mast cell stabilizer eye drops (subtotal)",
    "免疫抑制点眼薬（合計）": "Immunosuppressant eye drops (subtotal)",
    "エピナスチン点眼（アレジオン系）": "Epinastine (Alejon)",
    "オロパタジン点眼（パタノール系）": "Olopatadine (Patanol)",
    "レボカバスチン点眼（リボスチン系）": "Levocabastine (Livostin)",
    "ケトチフェン点眼（ザジテン系）": "Ketotifen (Zaditen)",
    "トラニラスト点眼（リザベン系）": "Tranilast (Rizaben)",
    "アシタザノラスト点眼（ゼペリン）": "Acitazanolast (Zepelin)",
    "クロモグリク酸点眼（インタール系）": "Cromoglicate (Intal)",
    "ペミロラスト点眼（アレギサール系）": "Pemirolast (Alegysal)",
    "イブジラスト点眼（ケタス）": "Ibudilast (Ketas)",
    "シクロスポリン点眼（パピロック）": "Cyclosporine (Papilock)",
    "タクロリムス点眼（タリムス）": "Tacrolimus (Talymus)",
}

PREF_EN = {
    "北海道": "Hokkaido", "青森県": "Aomori", "岩手県": "Iwate",
    "宮城県": "Miyagi", "秋田県": "Akita", "山形県": "Yamagata",
    "福島県": "Fukushima", "茨城県": "Ibaraki", "栃木県": "Tochigi",
    "群馬県": "Gunma", "埼玉県": "Saitama", "千葉県": "Chiba",
    "東京都": "Tokyo", "神奈川県": "Kanagawa", "新潟県": "Niigata",
    "富山県": "Toyama", "石川県": "Ishikawa", "福井県": "Fukui",
    "山梨県": "Yamanashi", "長野県": "Nagano", "岐阜県": "Gifu",
    "静岡県": "Shizuoka", "愛知県": "Aichi", "三重県": "Mie",
    "滋賀県": "Shiga", "京都府": "Kyoto", "大阪府": "Osaka",
    "兵庫県": "Hyogo", "奈良県": "Nara", "和歌山県": "Wakayama",
    "鳥取県": "Tottori", "島根県": "Shimane", "岡山県": "Okayama",
    "広島県": "Hiroshima", "山口県": "Yamaguchi", "徳島県": "Tokushima",
    "香川県": "Kagawa", "愛媛県": "Ehime", "高知県": "Kochi",
    "福岡県": "Fukuoka", "佐賀県": "Saga", "長崎県": "Nagasaki",
    "熊本県": "Kumamoto", "大分県": "Oita", "宮崎県": "Miyazaki",
    "鹿児島県": "Kagoshima", "沖縄県": "Okinawa",
}

VARIABLE_EN = {
    "aging_rate": "Aging rate",
    "docs_per_100k": "Physicians per 100k",
    "facilities_per_100k": "Facilities per 100k",
}

# 配色
COLORS = {
    "ALLERGY_EYE_TOTAL": "333333",
    "ANTI_HIST": "2166AC",
    "EPINASTINE": "D62728",
    "OLOPATADINE": "1F77B4",
    "LEVOCASTINE": "FF7F0E",
    "KETOTIFEN": "9467BD",
    "MED_RELEASE": "2CA02C",
    "CROMOGLICATE": "8C564B",
    "TRANILAST": "E377C2",
    "IMMUNO": "7F7F7F",
    "CYCLOSPORINE": "BCBD22",
    "TACROLIMUS": "17BECF",
    "male": "4472C4",
    "female": "ED7D31",
    "year2014": "7F7F7F",
    "year2024": "D62728",
    "TOP3_TOTAL": "2CA02C",
}


def _sort_age(df, col="age_group"):
    unknown = sorted(set(df[col].astype(str)) - set(AGE_ORDER))
    if unknown:
        raise ValueError(
            f"未知の age_group ラベルがあります（ExcelでCSVを保存し日付に化けた可能性）: {unknown}"
        )
    order_map = {ag: i for i, ag in enumerate(AGE_ORDER)}
    df = df.copy()
    df["_sort"] = df[col].map(order_map)
    df = df.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)
    return df


def _write_data_ws(wb, ws_name, df):
    """DataFrameをワークシートに書き込み、ヘッダに書式を設定"""
    ws = wb.create_sheet(ws_name)
    header_font = Font(bold=True, size=10)
    header_fill = PatternFill("solid", fgColor="D9E2F3")
    thin_border = Border(
        bottom=Side(style="thin", color="999999")
    )

    # ヘッダ
    for c_idx, col_name in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=c_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center")

    # データ
    for r_idx, row in enumerate(df.itertuples(index=False), 2):
        for c_idx, val in enumerate(row, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            # 数値フォーマット
            if isinstance(val, float):
                cell.number_format = '#,##0.0'

    # 列幅自動調整（簡易）
    for c_idx, col_name in enumerate(df.columns, 1):
        max_len = max(len(str(col_name)), 10)
        ws.column_dimensions[get_column_letter(c_idx)].width = max_len + 2

    return ws


def _set_chart_style(chart, title, x_label, y_label, width=20, height=12):
    """グラフの共通スタイルを設定"""
    chart.title = title
    chart.x_axis.title = x_label
    chart.y_axis.title = y_label
    chart.width = width
    chart.height = height
    chart.style = 2
    if chart.legend:
        chart.legend.position = 'b'


# ========================================================
# Fig 1: Age and Sex Profile
# ========================================================
def generate_fig1():
    print("=== Fig 1: Age & Sex Profile ===")
    wb = Workbook()
    wb.remove(wb.active)

    # --- Fig 1A: 年齢群別 人口10万対処方量（全体合計、2024年度、both）---
    df1a = pd.read_csv(os.path.join(DATA_DIR, "fig1a_age_profile_2024.csv"))
    total = df1a[df1a["code"] == "ALLERGY_EYE_TOTAL"].copy()
    total = _sort_age(total)

    # データシート
    ws_data = wb.create_sheet("Fig1A_data")
    ws_data.cell(1, 1, value="Age Group").font = Font(bold=True)
    ws_data.cell(1, 2, value="Prescription volume\nper 100,000 population").font = Font(bold=True)
    for i, row in enumerate(total.itertuples(), 2):
        ws_data.cell(i, 1, value=row.age_group)
        ws_data.cell(i, 2, value=round(row.count_per_100k, 1))
        ws_data.cell(i, 2).number_format = '#,##0.0'

    n_rows = len(total) + 1

    # グラフ
    chart = BarChart()
    _set_chart_style(chart,
                     "Fig 1A. Age-specific prescription volume per 100,000 population (FY2024)",
                     "Age group (years)", "Prescription volume per 100,000 (mL)")
    chart.legend = None

    data_ref = Reference(ws_data, min_col=2, min_row=1, max_row=n_rows)
    cats_ref = Reference(ws_data, min_col=1, min_row=2, max_row=n_rows)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.shape = 4

    # 色設定
    series = chart.series[0]
    series.graphicalProperties.solidFill = "4472C4"

    chart.width = 24
    chart.height = 13
    chart.x_axis.tickLblPos = "low"

    ws_chart = wb.create_sheet("Fig1A")
    ws_chart.add_chart(chart, "A1")

    # --- Fig 1B: 性別×年齢群 人口10万対処方量 ---
    df1b = pd.read_csv(os.path.join(DATA_DIR, "fig1b_age_sex_profile_2024.csv"))
    total_1b = df1b[df1b["code"] == "ALLERGY_EYE_TOTAL"].copy()

    # ピボット: 年齢 × 性別
    pivot = total_1b.pivot_table(
        index="age_group", columns="sex", values="count_per_100k"
    ).reset_index()
    pivot = _sort_age(pivot)

    ws_data2 = wb.create_sheet("Fig1B_data")
    ws_data2.cell(1, 1, value="Age Group").font = Font(bold=True)
    ws_data2.cell(1, 2, value="Male").font = Font(bold=True)
    ws_data2.cell(1, 3, value="Female").font = Font(bold=True)
    for i, row in enumerate(pivot.itertuples(), 2):
        ws_data2.cell(i, 1, value=row.age_group)
        ws_data2.cell(i, 2, value=round(row.male, 1))
        ws_data2.cell(i, 3, value=round(row.female, 1))
        ws_data2.cell(i, 2).number_format = '#,##0.0'
        ws_data2.cell(i, 3).number_format = '#,##0.0'

    n_rows2 = len(pivot) + 1

    chart2 = BarChart()
    _set_chart_style(chart2,
                     "Fig 1B. Sex-specific prescription volume per 100,000 population (FY2024)",
                     "Age group (years)", "Prescription volume per 100,000 (mL)")

    data_ref2 = Reference(ws_data2, min_col=2, max_col=3, min_row=1, max_row=n_rows2)
    cats_ref2 = Reference(ws_data2, min_col=1, min_row=2, max_row=n_rows2)
    chart2.add_data(data_ref2, titles_from_data=True)
    chart2.set_categories(cats_ref2)

    chart2.series[0].graphicalProperties.solidFill = COLORS["male"]
    chart2.series[1].graphicalProperties.solidFill = COLORS["female"]

    chart2.width = 24
    chart2.height = 13
    chart2.x_axis.tickLblPos = "low"

    ws_chart2 = wb.create_sheet("Fig1B")
    ws_chart2.add_chart(chart2, "A1")

    # --- Fig 1B 追加: 主要薬剤別（エピナスチン、オロパタジン、レボカバスチン）---
    for drug_code in MAIN_DRUGS:
        drug_data = df1b[df1b["code"] == drug_code].copy()
        if drug_data.empty:
            continue
        drug_pivot = drug_data.pivot_table(
            index="age_group", columns="sex", values="count_per_100k"
        ).reset_index()
        drug_pivot = _sort_age(drug_pivot)
        drug_name = MAIN_DRUG_NAMES.get(drug_code, drug_code)

        ws_d = wb.create_sheet(f"Fig1B_{drug_name}_data")
        ws_d.cell(1, 1, value="Age Group").font = Font(bold=True)
        ws_d.cell(1, 2, value="Male").font = Font(bold=True)
        ws_d.cell(1, 3, value="Female").font = Font(bold=True)
        for i, row in enumerate(drug_pivot.itertuples(), 2):
            ws_d.cell(i, 1, value=row.age_group)
            male_val = getattr(row, 'male', 0) or 0
            female_val = getattr(row, 'female', 0) or 0
            ws_d.cell(i, 2, value=round(male_val, 1))
            ws_d.cell(i, 3, value=round(female_val, 1))

        n_d = len(drug_pivot) + 1
        ch = BarChart()
        _set_chart_style(ch,
                         f"Fig 1B-{drug_name}. Sex-specific profile (FY2024)",
                         "Age group (years)", "per 100,000 (mL)")
        data_d = Reference(ws_d, min_col=2, max_col=3, min_row=1, max_row=n_d)
        cats_d = Reference(ws_d, min_col=1, min_row=2, max_row=n_d)
        ch.add_data(data_d, titles_from_data=True)
        ch.set_categories(cats_d)
        ch.series[0].graphicalProperties.solidFill = COLORS["male"]
        ch.series[1].graphicalProperties.solidFill = COLORS["female"]
        ch.width = 24
        ch.height = 13

        ws_ch = wb.create_sheet(f"Fig1B_{drug_name}")
        ws_ch.add_chart(ch, "A1")

    out_path = os.path.join(OUT_DIR, "Fig1_age_sex_profile.xlsx")
    wb.save(out_path)
    print(f"  → {out_path}")


# ========================================================
# Fig 2: Age Distribution Shift
# ========================================================
def generate_fig2():
    print("\n=== Fig 2: Age Distribution Shift ===")
    wb = Workbook()
    wb.remove(wb.active)

    # --- Fig 2A: 年齢分布シェア 2014 vs 2024 (ALLERGY_EYE_TOTAL) ---
    df = pd.read_csv(os.path.join(DATA_DIR, "fig2_age_distribution_shift.csv"))
    total = df[df["code"] == "ALLERGY_EYE_TOTAL"].copy()

    # 2014と2024
    d14 = total[total["year"] == 2014].copy()
    d24 = total[total["year"] == 2024].copy()
    d14 = _sort_age(d14)
    d24 = _sort_age(d24)

    # 2014は19区分(90+)、2024は21区分(90-94, 95-99, 100+) → 統一
    # 2024の90-94, 95-99, 100+を90+に統合
    d24_90plus = d24[d24["age_group"].isin(["90-94", "95-99", "100+"])]
    d24_main = d24[~d24["age_group"].isin(["90-94", "95-99", "100+"])].copy()
    if not d24_90plus.empty:
        row_90 = pd.DataFrame({
            "age_group": ["90+"],
            "share_pct": [d24_90plus["share_pct"].sum()],
            "count": [d24_90plus["count"].sum()],
            "year": [2024],
            "code": ["ALLERGY_EYE_TOTAL"],
            "procedure_name": ["抗アレルギー点眼薬（全体合計）"]
        })
        d24_unified = pd.concat([d24_main, row_90], ignore_index=True)
    else:
        d24_unified = d24_main
    d24_unified = _sort_age(d24_unified)

    # データシート
    ws_data = wb.create_sheet("Fig2A_data")
    ws_data.cell(1, 1, value="Age Group").font = Font(bold=True)
    ws_data.cell(1, 2, value="FY2014 (%)").font = Font(bold=True)
    ws_data.cell(1, 3, value="FY2024 (%)").font = Font(bold=True)

    age_groups_19 = d14["age_group"].tolist()
    share_24_dict = dict(zip(d24_unified["age_group"], d24_unified["share_pct"]))

    for i, ag in enumerate(age_groups_19, 2):
        ws_data.cell(i, 1, value=ag)
        val14 = d14[d14["age_group"] == ag]["share_pct"].values
        ws_data.cell(i, 2, value=round(val14[0], 1) if len(val14) > 0 else 0)
        ws_data.cell(i, 3, value=round(share_24_dict.get(ag, 0), 1))

    n_rows = len(age_groups_19) + 1

    chart = BarChart()
    _set_chart_style(chart,
                     "Fig 2A. Age distribution of prescription volume: FY2014 vs FY2024",
                     "Age group (years)", "Share (%)")

    data_ref = Reference(ws_data, min_col=2, max_col=3, min_row=1, max_row=n_rows)
    cats_ref = Reference(ws_data, min_col=1, min_row=2, max_row=n_rows)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)

    chart.series[0].graphicalProperties.solidFill = COLORS["year2014"]
    chart.series[1].graphicalProperties.solidFill = COLORS["year2024"]
    chart.width = 24
    chart.height = 13

    ws_ch = wb.create_sheet("Fig2A")
    ws_ch.add_chart(chart, "A1")

    # --- Fig 2B: 加重平均処方年齢の推移 ---
    wma = pd.read_csv(os.path.join(DATA_DIR, "fig2_weighted_mean_age.csv"))
    # 主要薬剤のみ
    target_codes = ["ALLERGY_EYE_TOTAL", "EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
    wma_main = wma[wma["code"].isin(target_codes)].copy()
    wma_pivot = wma_main.pivot_table(
        index="year", columns="code", values="weighted_mean_age"
    ).reset_index()
    # 列順を揃える
    cols = ["year"] + [c for c in target_codes if c in wma_pivot.columns]
    wma_pivot = wma_pivot[cols]

    ws_data2 = wb.create_sheet("Fig2B_data")
    headers = ["Year"] + [MAIN_DRUG_NAMES.get(c, c) for c in cols[1:]]
    for c_idx, h in enumerate(headers, 1):
        ws_data2.cell(1, c_idx, value=h).font = Font(bold=True)

    for r_idx, row in enumerate(wma_pivot.itertuples(index=False), 2):
        for c_idx, val in enumerate(row, 1):
            cell = ws_data2.cell(r_idx, c_idx, value=round(val, 2) if isinstance(val, float) else val)
            if isinstance(val, float):
                cell.number_format = '0.0'

    n_rows2 = len(wma_pivot) + 1
    n_cols2 = len(cols)

    chart2 = LineChart()
    _set_chart_style(chart2,
                     "Fig 2B. Weighted mean prescription age by drug (FY2014–2024)",
                     "Fiscal year", "Weighted mean age (years)")

    data_ref2 = Reference(ws_data2, min_col=2, max_col=n_cols2, min_row=1, max_row=n_rows2)
    cats_ref2 = Reference(ws_data2, min_col=1, min_row=2, max_row=n_rows2)
    chart2.add_data(data_ref2, titles_from_data=True)
    chart2.set_categories(cats_ref2)

    color_list = [COLORS.get(c, "333333") for c in cols[1:]]
    for idx, s in enumerate(chart2.series):
        s.graphicalProperties.line.solidFill = color_list[idx]
        s.graphicalProperties.line.width = 22000  # EMUs, ~2pt
        s.smooth = False

    chart2.y_axis.scaling.min = 40
    chart2.y_axis.scaling.max = 60
    chart2.width = 20
    chart2.height = 12

    ws_ch2 = wb.create_sheet("Fig2B")
    ws_ch2.add_chart(chart2, "A1")

    # --- Fig 2C: 薬剤別年齢分布比較（2024年度）---
    d24_drugs = df[(df["year"] == 2024) & (df["code"].isin(MAIN_DRUGS))].copy()
    drug_pivot = d24_drugs.pivot_table(
        index="age_group", columns="code", values="share_pct"
    ).reset_index()
    drug_pivot = _sort_age(drug_pivot)

    ws_data3 = wb.create_sheet("Fig2C_data")
    d_cols = ["age_group"] + [c for c in MAIN_DRUGS if c in drug_pivot.columns]
    d_headers = ["Age Group"] + [MAIN_DRUG_NAMES.get(c, c) for c in d_cols[1:]]
    for c_idx, h in enumerate(d_headers, 1):
        ws_data3.cell(1, c_idx, value=h).font = Font(bold=True)

    for r_idx, row_data in enumerate(drug_pivot[d_cols].itertuples(index=False), 2):
        for c_idx, val in enumerate(row_data, 1):
            cell = ws_data3.cell(r_idx, c_idx, value=round(val, 1) if isinstance(val, float) else val)

    n_rows3 = len(drug_pivot) + 1
    n_cols3 = len(d_cols)

    chart3 = LineChart()
    _set_chart_style(chart3,
                     "Fig 2C. Drug-specific age distribution (FY2024)",
                     "Age group (years)", "Share (%)")

    data_ref3 = Reference(ws_data3, min_col=2, max_col=n_cols3, min_row=1, max_row=n_rows3)
    cats_ref3 = Reference(ws_data3, min_col=1, min_row=2, max_row=n_rows3)
    chart3.add_data(data_ref3, titles_from_data=True)
    chart3.set_categories(cats_ref3)

    drug_colors = [COLORS.get(c, "333333") for c in d_cols[1:]]
    for idx, s in enumerate(chart3.series):
        s.graphicalProperties.line.solidFill = drug_colors[idx]
        s.graphicalProperties.line.width = 22000
        s.smooth = False

    chart3.width = 24
    chart3.height = 13

    ws_ch3 = wb.create_sheet("Fig2C")
    ws_ch3.add_chart(chart3, "A1")

    # --- Fig 2A_top3: 上位3剤合計の年齢分布シェア 2014 vs 2024 ---
    top3 = df[df["code"] == "TOP3_TOTAL"].copy()
    t3_14 = top3[top3["year"] == 2014].copy()
    t3_24 = top3[top3["year"] == 2024].copy()
    t3_14 = _sort_age(t3_14)
    t3_24 = _sort_age(t3_24)

    t3_24_90plus = t3_24[t3_24["age_group"].isin(["90-94", "95-99", "100+"])]
    t3_24_main = t3_24[~t3_24["age_group"].isin(["90-94", "95-99", "100+"])].copy()
    if not t3_24_90plus.empty:
        row_90 = pd.DataFrame({
            "age_group": ["90+"],
            "share_pct": [t3_24_90plus["share_pct"].sum()],
            "count": [t3_24_90plus["count"].sum()],
            "year": [2024],
            "code": ["TOP3_TOTAL"],
        })
        t3_24_unified = pd.concat([t3_24_main, row_90], ignore_index=True)
    else:
        t3_24_unified = t3_24_main
    t3_24_unified = _sort_age(t3_24_unified)

    ws_t3a = wb.create_sheet("Fig2A_top3_data")
    ws_t3a.cell(1, 1, value="Age Group").font = Font(bold=True)
    ws_t3a.cell(1, 2, value="FY2014 (%)").font = Font(bold=True)
    ws_t3a.cell(1, 3, value="FY2024 (%)").font = Font(bold=True)

    age_groups_t3 = t3_14["age_group"].tolist()
    share_t3_24 = dict(zip(t3_24_unified["age_group"], t3_24_unified["share_pct"]))
    for i, ag in enumerate(age_groups_t3, 2):
        ws_t3a.cell(i, 1, value=ag)
        val14 = t3_14[t3_14["age_group"] == ag]["share_pct"].values
        ws_t3a.cell(i, 2, value=round(val14[0], 1) if len(val14) > 0 else 0)
        ws_t3a.cell(i, 3, value=round(share_t3_24.get(ag, 0), 1))

    n_t3a = len(age_groups_t3) + 1
    chart_t3a = BarChart()
    _set_chart_style(chart_t3a,
                     "Fig 2A (Top 3). Age distribution: FY2014 vs FY2024 (Epinastine + Olopatadine + Levocabastine)",
                     "Age group (years)", "Share (%)")
    data_t3a = Reference(ws_t3a, min_col=2, max_col=3, min_row=1, max_row=n_t3a)
    cats_t3a = Reference(ws_t3a, min_col=1, min_row=2, max_row=n_t3a)
    chart_t3a.add_data(data_t3a, titles_from_data=True)
    chart_t3a.set_categories(cats_t3a)
    chart_t3a.series[0].graphicalProperties.solidFill = COLORS["year2014"]
    chart_t3a.series[1].graphicalProperties.solidFill = COLORS["year2024"]
    chart_t3a.width = 24
    chart_t3a.height = 13
    ws_t3a_ch = wb.create_sheet("Fig2A_top3")
    ws_t3a_ch.add_chart(chart_t3a, "A1")

    # --- Fig 2B_top3: 上位3剤の加重平均処方年齢推移（TOP3_TOTAL + 個別3剤）---
    wma = pd.read_csv(os.path.join(DATA_DIR, "fig2_weighted_mean_age.csv"))
    t3b_codes = ["TOP3_TOTAL", "EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
    wma_t3 = wma[wma["code"].isin(t3b_codes)].copy()
    wma_t3_pivot = wma_t3.pivot_table(
        index="year", columns="code", values="weighted_mean_age"
    ).reset_index()
    t3b_cols = ["year"] + [c for c in t3b_codes if c in wma_t3_pivot.columns]
    wma_t3_pivot = wma_t3_pivot[t3b_cols]

    ws_t3b = wb.create_sheet("Fig2B_top3_data")
    t3b_headers = ["Year"] + [MAIN_DRUG_NAMES.get(c, c) for c in t3b_cols[1:]]
    for c_idx, h in enumerate(t3b_headers, 1):
        ws_t3b.cell(1, c_idx, value=h).font = Font(bold=True)
    for r_idx, row in enumerate(wma_t3_pivot.itertuples(index=False), 2):
        for c_idx, val in enumerate(row, 1):
            cell = ws_t3b.cell(r_idx, c_idx, value=round(val, 2) if isinstance(val, float) else val)
            if isinstance(val, float):
                cell.number_format = '0.0'

    n_t3b = len(wma_t3_pivot) + 1
    n_t3b_cols = len(t3b_cols)
    chart_t3b = LineChart()
    _set_chart_style(chart_t3b,
                     "Fig 2B (Top 3). Weighted mean prescription age (FY2014–2024)",
                     "Fiscal year", "Weighted mean age (years)")
    data_t3b = Reference(ws_t3b, min_col=2, max_col=n_t3b_cols, min_row=1, max_row=n_t3b)
    cats_t3b = Reference(ws_t3b, min_col=1, min_row=2, max_row=n_t3b)
    chart_t3b.add_data(data_t3b, titles_from_data=True)
    chart_t3b.set_categories(cats_t3b)
    t3b_colors = [COLORS.get(c, "333333") for c in t3b_cols[1:]]
    for idx, s in enumerate(chart_t3b.series):
        s.graphicalProperties.line.solidFill = t3b_colors[idx]
        s.graphicalProperties.line.width = 22000
        s.smooth = False
    chart_t3b.y_axis.scaling.min = 40
    chart_t3b.y_axis.scaling.max = 60
    chart_t3b.width = 20
    chart_t3b.height = 12
    ws_t3b_ch = wb.create_sheet("Fig2B_top3")
    ws_t3b_ch.add_chart(chart_t3b, "A1")

    out_path = os.path.join(OUT_DIR, "Fig2_age_distribution.xlsx")
    wb.save(out_path)
    print(f"  → {out_path}")


# ========================================================
# Fig 3: Prefecture Ranking
# ========================================================
def generate_fig3():
    print("\n=== Fig 3: Prefecture Ranking ===")
    wb = Workbook()
    wb.remove(wb.active)

    df = pd.read_csv(os.path.join(DATA_DIR, "fig3_prefecture_ranking.csv"),
                     encoding="utf-8-sig")
    # 列名を確認して2024年の列を特定
    cols = df.columns.tolist()
    col_2024 = [c for c in cols if "2024" in c and "順位" not in c and "rank" not in c.lower()]
    col_rank = [c for c in cols if "順位" in c or "rank" in c.lower()]

    if not col_2024:
        print("  ⚠ 2024年の列が見つかりません")
        return

    rate_col = col_2024[0]
    pref_col = cols[0]  # prefecture

    # 2024年の値でソート（降順）
    df_sorted = df.sort_values(rate_col, ascending=True).copy()  # 横棒グラフ用に昇順

    ws_data = wb.create_sheet("Fig3_data")
    ws_data.cell(1, 1, value="Prefecture").font = Font(bold=True)
    ws_data.cell(1, 2, value="Prescription volume per 100,000 (FY2024)").font = Font(bold=True)

    for i, (_, row) in enumerate(df_sorted.iterrows(), 2):
        ws_data.cell(i, 1, value=row[pref_col])
        ws_data.cell(i, 2, value=round(float(row[rate_col]), 1))
        ws_data.cell(i, 2).number_format = '#,##0.0'

    n_rows = len(df_sorted) + 1

    chart = BarChart()
    chart.type = "bar"  # 横棒
    _set_chart_style(chart,
                     "Fig 3. Prefecture-level prescription volume per 100,000 population (FY2024)",
                     "Prescription volume per 100,000 (mL)", "")
    chart.legend = None

    data_ref = Reference(ws_data, min_col=2, min_row=1, max_row=n_rows)
    cats_ref = Reference(ws_data, min_col=1, min_row=2, max_row=n_rows)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)

    chart.series[0].graphicalProperties.solidFill = "4472C4"

    chart.width = 22
    chart.height = 28  # 47都道府県なので縦長

    ws_ch = wb.create_sheet("Fig3")
    ws_ch.add_chart(chart, "A1")

    # --- 11年間の推移テーブル（参考用データシート）---
    year_cols = [c for c in cols if "人口10万対" in c]
    df_rank = df.sort_values(rate_col, ascending=False)
    ws_full = _write_data_ws(wb, "Fig3_full_data", df_rank[[pref_col] + year_cols])

    # --- Fig 3 (Top 3): 上位3剤合計の都道府県ランキング ---
    top3_path = os.path.join(DATA_DIR, "fig3_prefecture_ranking_top3.csv")
    if os.path.exists(top3_path):
        df_t3 = pd.read_csv(top3_path, encoding="utf-8-sig")
        t3_cols = df_t3.columns.tolist()
        t3_col_2024 = [c for c in t3_cols if "2024" in c and "順位" not in c]
        if t3_col_2024:
            t3_rate = t3_col_2024[0]
            t3_pref = t3_cols[0]
            df_t3_sorted = df_t3.sort_values(t3_rate, ascending=True).copy()

            ws_t3 = wb.create_sheet("Fig3_top3_data")
            ws_t3.cell(1, 1, value="Prefecture").font = Font(bold=True)
            ws_t3.cell(1, 2, value="Top 3 drugs per 100,000 (FY2024)").font = Font(bold=True)
            for i, (_, row) in enumerate(df_t3_sorted.iterrows(), 2):
                ws_t3.cell(i, 1, value=row[t3_pref])
                ws_t3.cell(i, 2, value=round(float(row[t3_rate]), 1))
                ws_t3.cell(i, 2).number_format = '#,##0.0'

            n_t3 = len(df_t3_sorted) + 1
            chart_t3 = BarChart()
            chart_t3.type = "bar"
            _set_chart_style(chart_t3,
                             "Fig 3 (Top 3). Prefecture ranking (Epinastine + Olopatadine + Levocabastine, FY2024)",
                             "Prescription volume per 100,000 (mL)", "")
            chart_t3.legend = None
            data_t3 = Reference(ws_t3, min_col=2, min_row=1, max_row=n_t3)
            cats_t3 = Reference(ws_t3, min_col=1, min_row=2, max_row=n_t3)
            chart_t3.add_data(data_t3, titles_from_data=True)
            chart_t3.set_categories(cats_t3)
            chart_t3.series[0].graphicalProperties.solidFill = "2CA02C"
            chart_t3.width = 22
            chart_t3.height = 28
            ws_t3_ch = wb.create_sheet("Fig3_top3")
            ws_t3_ch.add_chart(chart_t3, "A1")

            # 11年推移データシート
            t3_year_cols = [c for c in t3_cols if "人口10万対" in c]
            df_t3_rank = df_t3.sort_values(t3_rate, ascending=False)
            _write_data_ws(wb, "Fig3_top3_full", df_t3_rank[[t3_pref] + t3_year_cols])

    # --- 個別薬剤の都道府県ランキング（2024年度）---
    pbd_path = os.path.join(DATA_DIR, "fig3_prefecture_by_drug.csv")
    if os.path.exists(pbd_path):
        pbd = pd.read_csv(pbd_path, encoding="utf-8-sig")
        pbd_pref_col = pbd.columns[0]
        pbd_year_cols = [c for c in pbd.columns if "人口10万対" in c]
        pbd_col_2024 = [c for c in pbd_year_cols if "2024" in c]
        if pbd_col_2024:
            pbd_rate = pbd_col_2024[0]
            drug_map = {
                "エピナスチン点眼（アレジオン系）": ("Epinastine", COLORS["EPINASTINE"]),
                "オロパタジン点眼（パタノール系）": ("Olopatadine", COLORS["OLOPATADINE"]),
                "レボカバスチン点眼（リボスチン系）": ("Levocabastine", COLORS["LEVOCASTINE"]),
            }
            for proc_name, (eng_name, color) in drug_map.items():
                drug_df = pbd[pbd["procedure_name"] == proc_name].copy()
                if drug_df.empty:
                    continue
                drug_sorted = drug_df.sort_values(pbd_rate, ascending=True)

                tag = eng_name[:4]  # Epin, Olop, Levo
                ws_d = wb.create_sheet(f"Fig3_{tag}_data")
                ws_d.cell(1, 1, value="Prefecture").font = Font(bold=True)
                ws_d.cell(1, 2, value=f"{eng_name} per 100,000 (FY2024)").font = Font(bold=True)
                for i, (_, row) in enumerate(drug_sorted.iterrows(), 2):
                    ws_d.cell(i, 1, value=row[pbd_pref_col])
                    val = row[pbd_rate]
                    ws_d.cell(i, 2, value=round(float(val), 1) if pd.notna(val) else 0)
                    ws_d.cell(i, 2).number_format = '#,##0.0'

                n_d = len(drug_sorted) + 1
                ch_d = BarChart()
                ch_d.type = "bar"
                _set_chart_style(ch_d,
                                 f"Fig 3 ({eng_name}). Prefecture ranking (FY2024)",
                                 "Prescription volume per 100,000 (mL)", "")
                ch_d.legend = None
                data_d = Reference(ws_d, min_col=2, min_row=1, max_row=n_d)
                cats_d = Reference(ws_d, min_col=1, min_row=2, max_row=n_d)
                ch_d.add_data(data_d, titles_from_data=True)
                ch_d.set_categories(cats_d)
                ch_d.series[0].graphicalProperties.solidFill = color
                ch_d.width = 22
                ch_d.height = 28
                ws_d_ch = wb.create_sheet(f"Fig3_{tag}")
                ws_d_ch.add_chart(ch_d, "A1")

    out_path = os.path.join(OUT_DIR, "Fig3_prefecture_map.xlsx")
    wb.save(out_path)
    print(f"  → {out_path}")


# ========================================================
# Fig 4: Trends and Market Shares
# ========================================================
def generate_fig4():
    print("\n=== Fig 4: Trends & Shares ===")
    wb = Workbook()
    wb.remove(wb.active)

    # --- Fig 4A: 人口10万対処方量の推移（主要薬剤）---
    trends = pd.read_csv(os.path.join(DATA_DIR, "fig4_national_trends.csv"))
    target = ["ALLERGY_EYE_TOTAL", "EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
    t_main = trends[trends["code"].isin(target)].copy()

    pivot = t_main.pivot_table(index="year", columns="code", values="count_per_100k").reset_index()
    cols_order = ["year"] + [c for c in target if c in pivot.columns]
    pivot = pivot[cols_order]

    ws_data = wb.create_sheet("Fig4A_data")
    headers = ["Year"] + [MAIN_DRUG_NAMES.get(c, c) for c in cols_order[1:]]
    for c_idx, h in enumerate(headers, 1):
        ws_data.cell(1, c_idx, value=h).font = Font(bold=True)

    for r_idx, row in enumerate(pivot.itertuples(index=False), 2):
        for c_idx, val in enumerate(row, 1):
            cell = ws_data.cell(r_idx, c_idx, value=round(val, 1) if isinstance(val, float) else val)
            if isinstance(val, float):
                cell.number_format = '#,##0.0'

    n_rows = len(pivot) + 1
    n_cols = len(cols_order)

    chart = LineChart()
    _set_chart_style(chart,
                     "Fig 4A. National trends in prescription volume per 100,000 population (FY2014–2024)",
                     "Fiscal year", "Prescription volume per 100,000 (mL)")

    data_ref = Reference(ws_data, min_col=2, max_col=n_cols, min_row=1, max_row=n_rows)
    cats_ref = Reference(ws_data, min_col=1, min_row=2, max_row=n_rows)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)

    color_list = [COLORS.get(c, "333333") for c in cols_order[1:]]
    for idx, s in enumerate(chart.series):
        s.graphicalProperties.line.solidFill = color_list[idx]
        s.graphicalProperties.line.width = 25000
        s.smooth = False

    chart.width = 22
    chart.height = 13

    ws_ch = wb.create_sheet("Fig4A")
    ws_ch.add_chart(chart, "A1")

    # --- Fig 4B: 市場シェア推移（積み上げ面グラフ風 → 折れ線で代替）---
    shares = pd.read_csv(os.path.join(DATA_DIR, "fig4_market_shares.csv"))
    # 個別薬剤のみ（合計カテゴリ除外）
    individual_drugs = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE",
                        "CROMOGLICATE", "TRANILAST", "CYCLOSPORINE",
                        "TACROLIMUS", "ACITAZANOLAST", "KETOTIFEN",
                        "PEMIROLAST", "IBUDILAST"]
    s_main = shares[shares["code"].isin(individual_drugs)].copy()
    s_main["share_pct"] = s_main["share"] * 100

    s_pivot = s_main.pivot_table(index="year", columns="code", values="share_pct").reset_index()
    # 主要薬剤を先に、残りを後に
    priority = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
    remaining = [c for c in s_pivot.columns if c not in ["year"] + priority and c in individual_drugs]
    s_cols = ["year"] + priority + remaining
    s_cols = [c for c in s_cols if c in s_pivot.columns]
    s_pivot = s_pivot[s_cols].fillna(0)

    ws_data2 = wb.create_sheet("Fig4B_data")
    s_headers = ["Year"] + [MAIN_DRUG_NAMES.get(c, c) for c in s_cols[1:]]
    for c_idx, h in enumerate(s_headers, 1):
        ws_data2.cell(1, c_idx, value=h).font = Font(bold=True)

    for r_idx, row in enumerate(s_pivot.itertuples(index=False), 2):
        for c_idx, val in enumerate(row, 1):
            cell = ws_data2.cell(r_idx, c_idx, value=round(val, 1) if isinstance(val, float) else val)
            if isinstance(val, float):
                cell.number_format = '0.0'

    n_rows2 = len(s_pivot) + 1
    n_cols2 = len(s_cols)

    from openpyxl.chart import AreaChart
    chart2 = AreaChart()
    chart2.grouping = "stacked"
    _set_chart_style(chart2,
                     "Fig 4B. Market share trends by drug (FY2014–2024)",
                     "Fiscal year", "Market share (%)")

    data_ref2 = Reference(ws_data2, min_col=2, max_col=n_cols2, min_row=1, max_row=n_rows2)
    cats_ref2 = Reference(ws_data2, min_col=1, min_row=2, max_row=n_rows2)
    chart2.add_data(data_ref2, titles_from_data=True)
    chart2.set_categories(cats_ref2)

    share_colors = [COLORS.get(c, "AAAAAA") for c in s_cols[1:]]
    for idx, s in enumerate(chart2.series):
        s.graphicalProperties.solidFill = share_colors[idx]

    chart2.y_axis.scaling.max = 100
    chart2.width = 22
    chart2.height = 13

    ws_ch2 = wb.create_sheet("Fig4B")
    ws_ch2.add_chart(chart2, "A1")

    # --- Fig 4A (Top 3): TOP3_TOTAL + 個別3剤のトレンド ---
    t3_target = ["TOP3_TOTAL", "EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
    t3_main = trends[trends["code"].isin(t3_target)].copy()
    if not t3_main.empty:
        t3_pivot = t3_main.pivot_table(
            index="year", columns="code", values="count_per_100k"
        ).reset_index()
        t3_cols_order = ["year"] + [c for c in t3_target if c in t3_pivot.columns]
        t3_pivot = t3_pivot[t3_cols_order]

        ws_t3a = wb.create_sheet("Fig4A_top3_data")
        t3a_headers = ["Year"] + [MAIN_DRUG_NAMES.get(c, c) for c in t3_cols_order[1:]]
        for c_idx, h in enumerate(t3a_headers, 1):
            ws_t3a.cell(1, c_idx, value=h).font = Font(bold=True)
        for r_idx, row in enumerate(t3_pivot.itertuples(index=False), 2):
            for c_idx, val in enumerate(row, 1):
                cell = ws_t3a.cell(r_idx, c_idx,
                                  value=round(val, 1) if isinstance(val, float) else val)
                if isinstance(val, float):
                    cell.number_format = '#,##0.0'

        n_t3a = len(t3_pivot) + 1
        n_t3a_cols = len(t3_cols_order)
        chart_t3a = LineChart()
        _set_chart_style(chart_t3a,
                         "Fig 4A (Top 3). Prescription volume per 100,000 (FY2014–2024)",
                         "Fiscal year", "Prescription volume per 100,000 (mL)")
        data_t3a = Reference(ws_t3a, min_col=2, max_col=n_t3a_cols,
                             min_row=1, max_row=n_t3a)
        cats_t3a = Reference(ws_t3a, min_col=1, min_row=2, max_row=n_t3a)
        chart_t3a.add_data(data_t3a, titles_from_data=True)
        chart_t3a.set_categories(cats_t3a)
        t3a_colors = [COLORS.get(c, "333333") for c in t3_cols_order[1:]]
        for idx, s in enumerate(chart_t3a.series):
            s.graphicalProperties.line.solidFill = t3a_colors[idx]
            s.graphicalProperties.line.width = 25000
            s.smooth = False
        chart_t3a.width = 22
        chart_t3a.height = 13
        ws_t3a_ch = wb.create_sheet("Fig4A_top3")
        ws_t3a_ch.add_chart(chart_t3a, "A1")

    # --- Fig 4B (Top 3): 3剤合計基準のシェア推移 ---
    if "share_top3" in shares.columns:
        s_t3 = shares[shares["code"].isin(["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"])
                       & shares["share_top3"].notna()].copy()
        s_t3["share_top3_pct"] = s_t3["share_top3"] * 100

        s_t3_pivot = s_t3.pivot_table(
            index="year", columns="code", values="share_top3_pct"
        ).reset_index()
        t3b_order = ["year", "EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
        t3b_order = [c for c in t3b_order if c in s_t3_pivot.columns]
        s_t3_pivot = s_t3_pivot[t3b_order].fillna(0)

        ws_t3b = wb.create_sheet("Fig4B_top3_data")
        t3b_headers = ["Year"] + [MAIN_DRUG_NAMES.get(c, c) for c in t3b_order[1:]]
        for c_idx, h in enumerate(t3b_headers, 1):
            ws_t3b.cell(1, c_idx, value=h).font = Font(bold=True)
        for r_idx, row in enumerate(s_t3_pivot.itertuples(index=False), 2):
            for c_idx, val in enumerate(row, 1):
                cell = ws_t3b.cell(r_idx, c_idx,
                                   value=round(val, 1) if isinstance(val, float) else val)
                if isinstance(val, float):
                    cell.number_format = '0.0'

        n_t3b = len(s_t3_pivot) + 1
        n_t3b_cols = len(t3b_order)
        chart_t3b = AreaChart()
        chart_t3b.grouping = "stacked"
        _set_chart_style(chart_t3b,
                         "Fig 4B (Top 3). Market share within top 3 drugs (FY2014–2024)",
                         "Fiscal year", "Market share (%)")
        data_t3b = Reference(ws_t3b, min_col=2, max_col=n_t3b_cols,
                             min_row=1, max_row=n_t3b)
        cats_t3b = Reference(ws_t3b, min_col=1, min_row=2, max_row=n_t3b)
        chart_t3b.add_data(data_t3b, titles_from_data=True)
        chart_t3b.set_categories(cats_t3b)
        t3b_colors = [COLORS.get(c, "AAAAAA") for c in t3b_order[1:]]
        for idx, s in enumerate(chart_t3b.series):
            s.graphicalProperties.solidFill = t3b_colors[idx]
        chart_t3b.y_axis.scaling.max = 100
        chart_t3b.width = 22
        chart_t3b.height = 13
        ws_t3b_ch = wb.create_sheet("Fig4B_top3")
        ws_t3b_ch.add_chart(chart_t3b, "A1")

    out_path = os.path.join(OUT_DIR, "Fig4_trends_shares.xlsx")
    wb.save(out_path)
    print(f"  → {out_path}")


# ========================================================
# Tables 1–5
# ========================================================
def generate_tables():
    print("\n=== Tables 1-5 (English) ===")
    wb = Workbook()
    wb.remove(wb.active)

    header_font = Font(bold=True, size=10, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4472C4")
    subheader_fill = PatternFill("solid", fgColor="D6E4F0")

    def _en_proc(name):
        return PROCEDURE_NAME_EN.get(name, name)

    def _en_pref(name):
        return PREF_EN.get(name, name)

    def _en_class(name):
        return DRUG_CLASS_EN.get(name, name)

    def _en_var(name):
        return VARIABLE_EN.get(name, name)

    # --- Table 1: Drug prescriptions (FY2024, grand total basis) ---
    t1 = pd.read_csv(os.path.join(DATA_DIR, "table1_drug_summary_2024.csv"),
                     encoding="utf-8-sig")
    ws1 = wb.create_sheet("Table1")
    ws1.merge_cells("A1:F1")
    ws1.cell(1, 1, value="Table 1. Anti-allergic eye drop prescriptions by drug (FY2024)")
    ws1.cell(1, 1).font = Font(bold=True, size=12)

    t1_headers = ["Drug class", "Code", "Drug name", "Volume (mL)",
                  "Per 100,000", "Share (%)"]
    for c, h in enumerate(t1_headers, 1):
        cell = ws1.cell(3, c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for r, row in enumerate(t1.itertuples(), 4):
        drug_class_en = _en_class(row.drug_class)
        ws1.cell(r, 1, value=drug_class_en)
        ws1.cell(r, 2, value=row.code)
        ws1.cell(r, 3, value=_en_proc(row.procedure_name))
        ws1.cell(r, 4, value=round(row.count, 0))
        ws1.cell(r, 4).number_format = '#,##0'
        ws1.cell(r, 5, value=round(row.count_per_100k, 1))
        ws1.cell(r, 5).number_format = '#,##0.0'
        share_val = row.share_pct if not pd.isna(row.share_pct) else ""
        ws1.cell(r, 6, value=round(share_val, 1) if isinstance(share_val, (int, float)) else share_val)
        if isinstance(share_val, (int, float)):
            ws1.cell(r, 6).number_format = '0.0'

        if drug_class_en == "Subtotal/Total":
            for c in range(1, 7):
                ws1.cell(r, c).fill = subheader_fill
                ws1.cell(r, c).font = Font(bold=True)

    for c in [1, 2, 3, 4, 5, 6]:
        ws1.column_dimensions[get_column_letter(c)].width = [20, 18, 32, 16, 14, 10][c-1]

    # --- Table 2: M:F ratio (FY2024) ---
    t2 = pd.read_csv(os.path.join(DATA_DIR, "table2_mf_ratio_2024.csv"),
                     encoding="utf-8-sig")
    t2_total = t2[t2["code"] == "ALLERGY_EYE_TOTAL"].copy()
    t2_total = _sort_age(t2_total)

    ws2 = wb.create_sheet("Table2")
    ws2.merge_cells("A1:G1")
    ws2.cell(1, 1, value="Table 2. Male-to-female ratio by age group (FY2024, total anti-allergic eye drops)")
    ws2.cell(1, 1).font = Font(bold=True, size=12)

    t2_headers = ["Age Group", "Male (mL)", "Female (mL)",
                  "Male per 100k", "Female per 100k",
                  "M:F ratio (volume)", "M:F ratio (rate)"]
    for c, h in enumerate(t2_headers, 1):
        cell = ws2.cell(3, c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for r, row in enumerate(t2_total.itertuples(), 4):
        ws2.cell(r, 1, value=row.age_group)
        ws2.cell(r, 2, value=round(row.count_male, 0))
        ws2.cell(r, 2).number_format = '#,##0'
        ws2.cell(r, 3, value=round(row.count_female, 0))
        ws2.cell(r, 3).number_format = '#,##0'
        ws2.cell(r, 4, value=round(row.count_per_100k_male, 1))
        ws2.cell(r, 4).number_format = '#,##0.0'
        ws2.cell(r, 5, value=round(row.count_per_100k_female, 1))
        ws2.cell(r, 5).number_format = '#,##0.0'
        ws2.cell(r, 6, value=round(row.mf_ratio_count, 3))
        ws2.cell(r, 6).number_format = '0.000'
        ws2.cell(r, 7, value=round(row.mf_ratio_rate, 3))
        ws2.cell(r, 7).number_format = '0.000'

    for c in range(1, 8):
        ws2.column_dimensions[get_column_letter(c)].width = [12, 14, 14, 14, 14, 14, 14][c-1]

    # --- Table 3: Geographic disparity indices ---
    t3 = pd.read_csv(os.path.join(DATA_DIR, "supplementary_geographic_disparity.csv"),
                     encoding="utf-8-sig")
    t3["procedure_name"] = t3["procedure_name"].map(_en_proc)
    t3["min_prefecture"] = t3["min_prefecture"].map(_en_pref)
    t3["max_prefecture"] = t3["max_prefecture"].map(_en_pref)
    t3_cols = ["year", "code", "procedure_name", "mean_rate_per_100k", "cv",
               "gini", "min_prefecture", "min_rate", "max_prefecture", "max_rate",
               "max_to_min_ratio"]
    t3_display = t3[t3_cols].copy()
    t3_display.columns = ["Year", "Code", "Drug name", "Mean rate per 100k", "CV",
                          "Gini", "Min prefecture", "Min rate", "Max prefecture",
                          "Max rate", "Max/Min ratio"]
    ws3 = _write_data_ws(wb, "Table3", t3_display)
    ws3.insert_rows(1)
    ws3.merge_cells("A1:K1")
    ws3.cell(1, 1, value="Table 3. Geographic disparity indices by drug and year")
    ws3.cell(1, 1).font = Font(bold=True, size=12)

    # --- Table 4: APC ---
    t4 = pd.read_csv(os.path.join(DATA_DIR, "supplementary_apc_results.csv"),
                     encoding="utf-8-sig")
    ws4 = wb.create_sheet("Table4")
    ws4.merge_cells("A1:I1")
    ws4.cell(1, 1, value="Table 4. Annual percent change (APC) in prescription volume per 100,000 population")
    ws4.cell(1, 1).font = Font(bold=True, size=12)

    t4_headers = ["Drug code", "Drug name", "Period", "APC (%)",
                  "95% CI lower", "95% CI upper", "p-value", "R²"]
    for c, h in enumerate(t4_headers, 1):
        cell = ws4.cell(3, c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for r, row in enumerate(t4.itertuples(), 4):
        ws4.cell(r, 1, value=row.code)
        ws4.cell(r, 2, value=_en_proc(row.procedure_name))
        ws4.cell(r, 3, value=f"{row.start_year}-{row.end_year}")
        ws4.cell(r, 4, value=round(row.apc, 2))
        ws4.cell(r, 4).number_format = '0.00'
        ws4.cell(r, 5, value=round(row.apc_low, 2))
        ws4.cell(r, 5).number_format = '0.00'
        ws4.cell(r, 6, value=round(row.apc_high, 2))
        ws4.cell(r, 6).number_format = '0.00'
        p_val = row.p_value
        ws4.cell(r, 7, value=p_val)
        if p_val < 0.001:
            ws4.cell(r, 7).number_format = '0.00E+00'
        else:
            ws4.cell(r, 7).number_format = '0.000'
        ws4.cell(r, 8, value=round(row.r2, 4))
        ws4.cell(r, 8).number_format = '0.0000'

        if p_val < 0.05:
            for c in range(1, 9):
                ws4.cell(r, c).font = Font(bold=True)

    for c in range(1, 9):
        ws4.column_dimensions[get_column_letter(c)].width = [18, 32, 10, 10, 12, 12, 12, 10][c-1]

    # --- Table 5: Panel regression ---
    t5 = pd.read_csv(os.path.join(DATA_DIR, "supplementary_panel_regression.csv"),
                     encoding="utf-8-sig")
    ws5 = wb.create_sheet("Table5")
    ws5.merge_cells("A1:I1")
    ws5.cell(1, 1, value="Table 5. Fixed-effects panel regression results (prefecture FE + year FE)")
    ws5.cell(1, 1).font = Font(bold=True, size=12)

    t5_headers = ["Drug code", "Drug name", "Variable", "Coefficient", "Std. Error",
                  "t-stat", "p-value", "R² (within)", "N"]
    for c, h in enumerate(t5_headers, 1):
        cell = ws5.cell(3, c, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    for r, row in enumerate(t5.itertuples(), 4):
        ws5.cell(r, 1, value=row.code)
        ws5.cell(r, 2, value=_en_proc(row.procedure_name))
        ws5.cell(r, 3, value=_en_var(row.variable))
        ws5.cell(r, 4, value=round(row.coefficient, 3))
        ws5.cell(r, 4).number_format = '#,##0.000'
        ws5.cell(r, 5, value=round(row.std_err, 3))
        ws5.cell(r, 5).number_format = '#,##0.000'
        ws5.cell(r, 6, value=round(row.t_stat, 3))
        ws5.cell(r, 6).number_format = '0.000'
        p_val = row.p_value
        ws5.cell(r, 7, value=p_val)
        if p_val < 0.001:
            ws5.cell(r, 7).number_format = '0.00E+00'
        else:
            ws5.cell(r, 7).number_format = '0.000'
        ws5.cell(r, 8, value=round(row.r2_within, 4))
        ws5.cell(r, 8).number_format = '0.0000'
        ws5.cell(r, 9, value=int(row.n_obs))

        if p_val < 0.05:
            for c in range(1, 10):
                ws5.cell(r, c).font = Font(bold=True)

    for c in range(1, 10):
        ws5.column_dimensions[get_column_letter(c)].width = [18, 32, 20, 14, 12, 10, 12, 12, 8][c-1]

    out_path = os.path.join(OUT_DIR, "Tables_all.xlsx")
    wb.save(out_path)
    print(f"  -> {out_path}")


# ========================================================
# メイン
# ========================================================
# ========================================================
# Fig 5: Epinastine LX vs Standard / GE share / Cross-tab
# ========================================================
def generate_fig5():
    """
    Fig 5A: Epinastine LX 0.1% vs Standard 0.05% share (stacked bar)
    Fig 5B: Generic share trends for 3 drugs (line chart)
    Fig 5C: Epinastine brand/generic × LX/standard cross-tab (stacked bar)

    Source CSVs:
      - epinastine_lx_vs_standard.csv      (Fig 5A)
      - brand_generic_share.csv            (Fig 5B)
      - epinastine_lx_formulation_detail.csv (Fig 5C)
    """
    from openpyxl.chart import AreaChart

    print("\n=== Fig 5: LX/Standard, GE share, Cross-tab ===")
    wb = Workbook()
    wb.remove(wb.active)

    # ------ Fig 5A: LX vs Standard share ------
    lx_path = os.path.join(DATA_DIR, "epinastine_lx_vs_standard.csv")
    lx = pd.read_csv(lx_path, encoding="utf-8-sig")

    ws5a_d = wb.create_sheet("Fig5A_data")
    ws5a_d.cell(1, 1, value="Source: epinastine_lx_vs_standard.csv").font = Font(italic=True, color="888888")
    headers = ["Year", "LX 0.1% (mL)", "Standard 0.05% (mL)", "Total (mL)", "LX share (%)", "Std share (%)"]
    for c, h in enumerate(headers, 1):
        ws5a_d.cell(2, c, value=h).font = Font(bold=True)
    for i, (_, row) in enumerate(lx.iterrows(), 3):
        ws5a_d.cell(i, 1, value=int(row["year"]))
        ws5a_d.cell(i, 2, value=round(row["LX_0.1pct"], 1))
        ws5a_d.cell(i, 3, value=round(row["standard_0.05pct"], 1))
        ws5a_d.cell(i, 4, value=round(row["total"], 1))
        ws5a_d.cell(i, 5, value=round(row["LX_pct"], 1))
        ws5a_d.cell(i, 6, value=round(row["standard_pct"], 1))
    n5a = 2 + len(lx)

    ch5a = BarChart()
    ch5a.type = "col"
    ch5a.grouping = "stacked"
    _set_chart_style(ch5a,
                     "Fig 5A. Epinastine formulation share: LX 0.1% vs Standard 0.05%",
                     "", "Share (%)")
    cats = Reference(ws5a_d, min_col=1, min_row=3, max_row=n5a)
    d_lx = Reference(ws5a_d, min_col=5, min_row=2, max_row=n5a)
    d_std = Reference(ws5a_d, min_col=6, min_row=2, max_row=n5a)
    ch5a.add_data(d_lx, titles_from_data=True)
    ch5a.add_data(d_std, titles_from_data=True)
    ch5a.set_categories(cats)
    ch5a.series[0].graphicalProperties.solidFill = "C0392B"
    ch5a.series[1].graphicalProperties.solidFill = "BDC3C7"
    ch5a.y_axis.scaling.max = 100

    ws5a = wb.create_sheet("Fig5A")
    ws5a.add_chart(ch5a, "A1")

    # ------ Fig 5B: Generic share trends (3 drugs) ------
    ge_path = os.path.join(DATA_DIR, "brand_generic_share.csv")
    ge = pd.read_csv(ge_path, encoding="utf-8-sig")

    ws5b_d = wb.create_sheet("Fig5B_data")
    ws5b_d.cell(1, 1, value="Source: brand_generic_share.csv").font = Font(italic=True, color="888888")
    ws5b_d.cell(2, 1, value="Year").font = Font(bold=True)
    drug_order = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
    drug_labels = {"EPINASTINE": "Epinastine GE%", "OLOPATADINE": "Olopatadine GE%", "LEVOCASTINE": "Levocabastine GE%"}
    drug_colors = {"EPINASTINE": COLORS["EPINASTINE"], "OLOPATADINE": COLORS["OLOPATADINE"], "LEVOCASTINE": COLORS["LEVOCASTINE"]}
    for c, d in enumerate(drug_order, 2):
        ws5b_d.cell(2, c, value=drug_labels[d]).font = Font(bold=True)

    years = sorted(ge["year"].unique())
    for i, yr in enumerate(years, 3):
        ws5b_d.cell(i, 1, value=int(yr))
        for c, d in enumerate(drug_order, 2):
            row_match = ge[(ge["year"] == yr) & (ge["category"] == d)]
            val = row_match["share_pct_generic"].values[0] if len(row_match) else 0
            ws5b_d.cell(i, c, value=round(float(val), 1))
    n5b = 2 + len(years)

    ch5b = LineChart()
    _set_chart_style(ch5b,
                     "Fig 5B. Generic share trends by drug",
                     "", "Generic share (%)")
    cats_b = Reference(ws5b_d, min_col=1, min_row=3, max_row=n5b)
    for c, d in enumerate(drug_order, 2):
        data_ref = Reference(ws5b_d, min_col=c, min_row=2, max_row=n5b)
        ch5b.add_data(data_ref, titles_from_data=True)
    ch5b.set_categories(cats_b)
    for idx, d in enumerate(drug_order):
        ch5b.series[idx].graphicalProperties.line.solidFill = drug_colors[d]
        ch5b.series[idx].graphicalProperties.line.width = 25000
    ch5b.y_axis.scaling.max = 100
    ch5b.y_axis.scaling.min = 0

    ws5b = wb.create_sheet("Fig5B")
    ws5b.add_chart(ch5b, "A1")

    # ------ Fig 5C: Epinastine cross-tab (brand/GE × LX/standard) ------
    detail_path = os.path.join(DATA_DIR, "epinastine_lx_formulation_detail.csv")
    det = pd.read_csv(detail_path, encoding="utf-8-sig")

    ws5c_d = wb.create_sheet("Fig5C_data")
    ws5c_d.cell(1, 1, value="Source: epinastine_lx_formulation_detail.csv").font = Font(italic=True, color="888888")
    c_headers = ["Year", "LX brand (%)", "LX generic (%)", "Std brand (%)", "Std generic (%)"]
    for c, h in enumerate(c_headers, 1):
        ws5c_d.cell(2, c, value=h).font = Font(bold=True)
    for i, (_, row) in enumerate(det.iterrows(), 3):
        ws5c_d.cell(i, 1, value=int(row["year"]))
        ws5c_d.cell(i, 2, value=round(row["LX_0.1pct_brand_pct"], 1))
        ws5c_d.cell(i, 3, value=round(row["LX_0.1pct_generic_pct"], 1))
        ws5c_d.cell(i, 4, value=round(row["standard_0.05pct_brand_pct"], 1))
        ws5c_d.cell(i, 5, value=round(row["standard_0.05pct_generic_pct"], 1))
    n5c = 2 + len(det)

    ch5c = BarChart()
    ch5c.type = "col"
    ch5c.grouping = "stacked"
    _set_chart_style(ch5c,
                     "Fig 5C. Epinastine: brand/generic × LX/standard",
                     "", "Share (%)")
    cats_c = Reference(ws5c_d, min_col=1, min_row=3, max_row=n5c)
    colors_5c = ["C0392B", "E74C3C", "7F8C8D", "BDC3C7"]
    for c_idx in range(2, 6):
        data_ref = Reference(ws5c_d, min_col=c_idx, min_row=2, max_row=n5c)
        ch5c.add_data(data_ref, titles_from_data=True)
    ch5c.set_categories(cats_c)
    for idx, clr in enumerate(colors_5c):
        ch5c.series[idx].graphicalProperties.solidFill = clr
    ch5c.y_axis.scaling.max = 100

    ws5c = wb.create_sheet("Fig5C")
    ws5c.add_chart(ch5c, "A1")

    out_path = os.path.join(OUT_DIR, "Fig5_ge_formulation.xlsx")
    wb.save(out_path)
    print(f"  → {out_path}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("論文 Fig/Table .xlsx 生成（Excelグラフ埋め込み）")
    print("=" * 60)

    generate_fig1()
    generate_fig2()
    generate_fig3()
    generate_fig4()
    generate_fig5()
    generate_tables()

    print("\n" + "=" * 60)
    print(f"完了。出力先: {OUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
