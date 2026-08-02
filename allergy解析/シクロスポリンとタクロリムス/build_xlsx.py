import pandas as pd
import os

from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.marker import Marker

target_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(target_dir, "immunosuppressant_figures_tables.xlsx")


def _find(filename):
    """整理前（フォルダ直下）でも整理後（03_解析結果/…）でも同じコードで読めるようにする。"""
    direct = os.path.join(target_dir, filename)
    if os.path.exists(direct):
        return direct
    for dirpath, dirnames, files in os.walk(target_dir):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        if filename in files:
            return os.path.join(dirpath, filename)
    return direct

# 年齢群の表示順（build_immunosuppressant_analysis.py の AGE_ORDER と同一）
# ※ pandas の pivot は文字列を辞書順に並べるため、明示的に並べ替える必要がある
#   （そのままだと "0-4", "10-14", "100+", "15-19", ... となる）
AGE_ORDER = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80-84", "85-89", "90+", "90-94", "95-99", "100+",
]

# 薬剤の表示順: シクロスポリン → タクロリムス → 2剤合計
CODE_ORDER = ["CYCLOSPORINE", "TACROLIMUS", "IMMUNO_ML"]

# 都道府県の表示順（都道府県コード順: 北海道=01 〜 沖縄県=47）
# ※ 既定では Unicode 順（三重県, 京都府, 佐賀県, …）になり不自然なため明示する
PREFECTURE_ORDER = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


# --- 論文Figure用のグラフ設定 ---------------------------------------------
# 凡例・軸ラベルは英語（本稿は英文タイトル・Keywordsを持つ国際誌想定）。
# 配色は色覚多様性を考慮した検証済みの2色（青・橙）。年齢帯は順序尺度なので
# 単一色相の5段ランプを用いる（カテゴリ色を年齢に割り当てない）。
SERIES_BLUE = "2A78D6"
SERIES_ORANGE = "EB6834"
AGE_BAND_RAMP = ["86B6EF", "5598E7", "2A78D6", "1C5CAB", "104281"]
SURFACE = "FCFCFB"  # 棒の間に入れる隙間の色（背景と同色の細い枠線）
PT = 12700  # 1pt = 12700 EMU

# 剤名の表示ラベル。NDB上の数量単位が剤ごとに異なる（シクロスポリン=個(0.4mL)、
# タクロリムス=瓶(5mL)）ため、凡例に単位を明記して誤読を防ぐ。
DISPLAY_NAME = {
    "CYCLOSPORINE": "Ciclosporin",
    "TACROLIMUS": "Tacrolimus",
    "IMMUNO_ML": "Combined (mL)",
}
DISPLAY_NAME_WITH_UNIT = {
    "CYCLOSPORINE": "Ciclosporin (0.4-mL units)",
    "TACROLIMUS": "Tacrolimus (5-mL bottles)",
}

# 年齢帯（Fig 2 用）。5歳刻みのままでは系列が22本になり判読できないため集約する。
# 収録年度により 90+ と 90-94/95-99/100+ が混在するが、65+ に集約すれば整合する。
AGE_BANDS = [
    ("0-9", ["0-4", "5-9"]),
    ("10-19", ["10-14", "15-19"]),
    ("20-39", ["20-24", "25-29", "30-34", "35-39"]),
    ("40-64", ["40-44", "45-49", "50-54", "55-59", "60-64"]),
    ("65+", ["65-69", "70-74", "75-79", "80-84", "85-89",
             "90+", "90-94", "95-99", "100+"]),
]

PREFECTURE_EN = {
    "北海道": "Hokkaido", "青森県": "Aomori", "岩手県": "Iwate", "宮城県": "Miyagi",
    "秋田県": "Akita", "山形県": "Yamagata", "福島県": "Fukushima", "茨城県": "Ibaraki",
    "栃木県": "Tochigi", "群馬県": "Gunma", "埼玉県": "Saitama", "千葉県": "Chiba",
    "東京都": "Tokyo", "神奈川県": "Kanagawa", "新潟県": "Niigata", "富山県": "Toyama",
    "石川県": "Ishikawa", "福井県": "Fukui", "山梨県": "Yamanashi", "長野県": "Nagano",
    "岐阜県": "Gifu", "静岡県": "Shizuoka", "愛知県": "Aichi", "三重県": "Mie",
    "滋賀県": "Shiga", "京都府": "Kyoto", "大阪府": "Osaka", "兵庫県": "Hyogo",
    "奈良県": "Nara", "和歌山県": "Wakayama", "鳥取県": "Tottori", "島根県": "Shimane",
    "岡山県": "Okayama", "広島県": "Hiroshima", "山口県": "Yamaguchi", "徳島県": "Tokushima",
    "香川県": "Kagawa", "愛媛県": "Ehime", "高知県": "Kochi", "福岡県": "Fukuoka",
    "佐賀県": "Saga", "長崎県": "Nagasaki", "熊本県": "Kumamoto", "大分県": "Oita",
    "宮崎県": "Miyazaki", "鹿児島県": "Kagoshima", "沖縄県": "Okinawa",
}


def style_axes(chart, x_title, y_title, width, height):
    """論文用の共通体裁: 目盛線を消し、軸を明示し、サイズをcmで固定する。"""
    chart.x_axis.title = x_title
    chart.y_axis.title = y_title
    chart.width = width
    chart.height = height
    chart.y_axis.majorGridlines = None
    # openpyxl は既定で軸を非表示にすることがあるため明示的に描画させる
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    # overlay を明示しないと Excel がタイトルをプロット領域に重ねて描画し、
    # 軸ラベルと文字が重なって読めなくなる
    for title in (chart.title, chart.x_axis.title, chart.y_axis.title):
        if title is not None:
            title.overlay = False
    if chart.legend is not None:
        chart.legend.position = "b"
        chart.legend.overlay = False


def paint_bar(series, fill):
    """棒に単色を塗り、隣接する棒の間に背景色の細い隙間を作る。"""
    series.graphicalProperties.solidFill = fill
    series.graphicalProperties.line.solidFill = SURFACE
    series.graphicalProperties.line.width = int(0.75 * PT)


def paint_line(series, fill):
    """折れ線は2pt・マーカー付き（色だけに依存させないため）。"""
    series.graphicalProperties.line.solidFill = fill
    series.graphicalProperties.line.width = 2 * PT
    series.marker = Marker(symbol="circle", size=7)
    series.marker.graphicalProperties.solidFill = fill
    series.marker.graphicalProperties.line.solidFill = fill
    series.smooth = False


def load_csv(filename):
    return pd.read_csv(_find(filename))


def _order(values, order):
    """order の順に、実際に存在するものだけを返す。"""
    return [v for v in order if v in list(values)]


def sort_age_index(df):
    return df.reindex(_order(df.index, AGE_ORDER))


def sort_age_columns(df):
    return df[_order(df.columns, AGE_ORDER)]


def sort_code_columns(df):
    """列が code、または (code, sex) の MultiIndex の場合に薬剤順で並べ替える。"""
    if isinstance(df.columns, pd.MultiIndex):
        cols = [c for code in CODE_ORDER for c in df.columns if c[0] == code]
        return df[cols]
    return df[_order(df.columns, CODE_ORDER)]


def sort_code_rows(df):
    """code 列を持つ行方向のデータを薬剤順で並べ替える（他列の順序は保つ）。"""
    key = pd.Categorical(df["code"], categories=CODE_ORDER, ordered=True)
    return df.assign(_o=key).sort_values("_o", kind="stable").drop(columns="_o")


def sort_code_then_prefecture_rows(df):
    """薬剤順 → 都道府県コード順（北海道〜沖縄県）で並べ替える。"""
    return (df.assign(
                _c=pd.Categorical(df["code"], categories=CODE_ORDER, ordered=True),
                _p=pd.Categorical(df["prefecture"], categories=PREFECTURE_ORDER, ordered=True))
              .sort_values(["_c", "_p"], kind="stable")
              .drop(columns=["_c", "_p"]))


with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    # Fig 1A
    df_1a = load_csv("age_sex_rates_immuno.csv")
    df_1a = df_1a[(df_1a['year'] == 2024) & (df_1a['sex'] == 'both')]
    df_1a = df_1a[['code', 'age_group', 'count_per_100k']]
    df_1a_pivot = df_1a.pivot(index='age_group', columns='code', values='count_per_100k')
    df_1a_pivot = sort_code_columns(sort_age_index(df_1a_pivot))
    df_1a_pivot = df_1a_pivot.rename(columns=DISPLAY_NAME_WITH_UNIT)
    df_1a_pivot.to_excel(writer, sheet_name='Fig 1A')

    ws = writer.sheets['Fig 1A']
    n = len(df_1a_pivot) + 1  # ヘッダ行を含む最終行
    ch = BarChart()
    ch.type = "col"
    ch.grouping = "clustered"
    ch.gapWidth = 60
    ch.overlap = -10
    ch.title = "Age-specific prescription rate, FY2024"
    ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=1, max_row=n), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n))
    paint_bar(ch.series[0], SERIES_BLUE)
    paint_bar(ch.series[1], SERIES_ORANGE)
    style_axes(ch, "Age group (years)", "Prescriptions per 100,000 population", 18, 10)
    ws.add_chart(ch, "E2")

    # Fig 1B
    df_1b = load_csv("age_sex_rates_immuno.csv")
    df_1b = df_1b[(df_1b['year'] == 2024) & (df_1b['sex'].isin(['male', 'female']))]
    df_1b = df_1b[['code', 'sex', 'age_group', 'count_per_100k']]
    df_1b_pivot = df_1b.pivot_table(index='age_group', columns=['code', 'sex'], values='count_per_100k')
    df_1b_pivot = sort_code_columns(sort_age_index(df_1b_pivot))
    # 2段ヘッダのままでは pandas が空行を挟み、グラフの参照範囲も分かりにくくなるため
    # 「剤名, 性別」の1段ヘッダに平坦化する。
    df_1b_pivot.columns = [f"{DISPLAY_NAME[c]}, {s}" for c, s in df_1b_pivot.columns]
    df_1b_pivot.to_excel(writer, sheet_name='Fig 1B')

    # 4系列を1枚に混ぜると剤の違いと性別の違いが同じ色チャンネルを奪い合うため、
    # 剤ごとに2枚（各2系列）に分ける。
    ws = writer.sheets['Fig 1B']
    n = len(df_1b_pivot) + 1
    for i, (code, anchor) in enumerate([("CYCLOSPORINE", "G2"), ("TACROLIMUS", "G22")]):
        first = 2 + i * 2  # B,C = シクロスポリン / D,E = タクロリムス
        ch = BarChart()
        ch.type = "col"
        ch.grouping = "clustered"
        ch.gapWidth = 60
        ch.overlap = -10
        ch.title = f"{DISPLAY_NAME[code]}: age-specific rate by sex, FY2024"
        ch.add_data(Reference(ws, min_col=first, max_col=first + 1, min_row=1, max_row=n),
                    titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n))
        paint_bar(ch.series[0], SERIES_BLUE)
        paint_bar(ch.series[1], SERIES_ORANGE)
        style_axes(ch, "Age group (years)", "Prescriptions per 100,000 population", 18, 10)
        ws.add_chart(ch, anchor)

    # Fig 2
    df_2 = load_csv("age_distribution_immuno.csv")
    df_2 = df_2[df_2['code'] == 'CYCLOSPORINE']
    df_2 = df_2[['year', 'age_group', 'share_pct']]
    df_2_pivot = df_2.pivot(index='year', columns='age_group', values='share_pct')
    df_2_pivot = sort_age_columns(df_2_pivot)
    df_2_pivot.to_excel(writer, sheet_name='Fig 2')

    # 5歳刻み22列のままでは積み上げ系列が多すぎて図として読めないため、
    # グラフ用に年齢帯へ集約した表を右側（Y列以降）に併記する。
    df_2_band = pd.DataFrame({
        label: df_2_pivot[[c for c in members if c in df_2_pivot.columns]].sum(axis=1)
        for label, members in AGE_BANDS
    })
    band_start = len(df_2_pivot.columns) + 3  # 詳細表の右に2列あける
    df_2_band.to_excel(writer, sheet_name='Fig 2', startcol=band_start - 1)

    ws = writer.sheets['Fig 2']
    n = len(df_2_band) + 1
    ch = BarChart()
    ch.type = "col"
    ch.grouping = "stacked"
    ch.overlap = 100
    ch.gapWidth = 60
    ch.title = "Ciclosporin: age composition of prescribed volume by fiscal year"
    ch.add_data(Reference(ws, min_col=band_start + 1, max_col=band_start + len(AGE_BANDS),
                          min_row=1, max_row=n), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=band_start, min_row=2, max_row=n))
    for ser, fill in zip(ch.series, AGE_BAND_RAMP):
        paint_bar(ser, fill)
    style_axes(ch, "Fiscal year", "Share of prescribed volume (%)", 16, 10)
    ch.y_axis.scaling.max = 100  # 構成比なので120まで伸ばさない
    ws.add_chart(ch, f"A{len(df_2_pivot) + 4}")

    # Fig 2 補助
    df_2_sub = load_csv("weighted_mean_age_immuno.csv")
    df_2_sub = df_2_sub[['code', 'year', 'weighted_mean_age']]
    df_2_sub_pivot = df_2_sub.pivot(index='year', columns='code', values='weighted_mean_age')
    df_2_sub_pivot = sort_code_columns(df_2_sub_pivot)
    df_2_sub_pivot = df_2_sub_pivot.rename(columns=DISPLAY_NAME)
    df_2_sub_pivot.to_excel(writer, sheet_name='Fig 2 補助')

    ws = writer.sheets['Fig 2 補助']
    n = len(df_2_sub_pivot) + 1
    ch = LineChart()
    ch.title = "Volume-weighted mean age at prescription"
    ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=1, max_row=n), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n))
    paint_line(ch.series[0], SERIES_BLUE)
    paint_line(ch.series[1], SERIES_ORANGE)
    style_axes(ch, "Fiscal year", "Weighted mean age (years)", 14, 9)
    ws.add_chart(ch, "E2")

    def write_prefecture_sheet(df, sheet_name, title):
        """都道府県の横棒グラフ（1系列なので凡例は不要、単色で塗る）。"""
        # 図の軸ラベルを英語にするため英語表記の列を添える
        df = df.assign(prefecture_en=df['prefecture'].map(PREFECTURE_EN))
        df = df[['prefecture', 'prefecture_en', 'count_ml_per_100k']]
        df.to_excel(writer, sheet_name=sheet_name, index=False)

        ws = writer.sheets[sheet_name]
        n = len(df) + 1
        ch = BarChart()
        ch.type = "col"          # 降順に左→右で読ませる（横棒だと軸の反転が必要になる）
        ch.gapWidth = 40
        ch.title = title
        ch.add_data(Reference(ws, min_col=3, min_row=1, max_row=n), titles_from_data=True)
        ch.set_categories(Reference(ws, min_col=2, min_row=2, max_row=n))
        paint_bar(ch.series[0], SERIES_BLUE)
        style_axes(ch, "Prefecture (descending order)", "mL per 100,000 population", 24, 11)
        ch.legend = None         # 1系列のためタイトルが系列名を兼ねる
        ws.add_chart(ch, "E2")

    # Fig 3A
    df_3a = load_csv("prefecture_immuno.csv")
    df_3a = df_3a[(df_3a['code'] == 'CYCLOSPORINE') & (df_3a['year'] == 2023)]
    df_3a = df_3a[['prefecture', 'count_ml_per_100k']].sort_values('count_ml_per_100k', ascending=False)
    write_prefecture_sheet(df_3a, 'Fig 3A', "Ciclosporin by prefecture, FY2023")

    # Fig 3B
    df_3b = load_csv("prefecture_immuno.csv")
    df_3b = df_3b[(df_3b['code'] == 'TACROLIMUS') & (df_3b['year'] == 2024)]
    df_3b = df_3b[['prefecture', 'count_ml_per_100k']].sort_values('count_ml_per_100k', ascending=False)
    write_prefecture_sheet(df_3b, 'Fig 3B', "Tacrolimus by prefecture, FY2024")

    # Fig 3 補助
    df_3_sub = load_csv("prefecture_per_capita_pivot_immuno.csv")
    df_3_sub = sort_code_then_prefecture_rows(df_3_sub)
    df_3_sub.to_excel(writer, sheet_name='Fig 3 補助', index=False)

    # Fig 4
    df_4 = load_csv("national_trends_immuno.csv")
    df_4_codes = df_4[df_4['code'] != 'IMMUNO_ML'][['year', 'code', 'count_per_100k']]
    df_4_ml = df_4[df_4['code'] == 'IMMUNO_ML'][['year', 'code', 'count_ml_per_100k']]
    df_4_pivot_codes = df_4_codes.pivot(index='year', columns='code', values='count_per_100k')
    df_4_pivot_ml = df_4_ml.pivot(index='year', columns='code', values='count_ml_per_100k')
    df_4_combined = df_4_pivot_codes.join(df_4_pivot_ml, how='outer')
    df_4_combined = sort_code_columns(df_4_combined)
    df_4_combined = df_4_combined.rename(columns=DISPLAY_NAME)
    df_4_combined.to_excel(writer, sheet_name='Fig 4')

    # 剤別（個・瓶）と2剤合計（mL換算）は単位が異なる。第2軸で1枚に重ねると
    # 目盛の取り方次第で見かけの大小が変わるため、2枚に分ける。
    ws = writer.sheets['Fig 4']
    n = len(df_4_combined) + 1
    ch = LineChart()
    ch.title = "Prescription volume by drug (native NDB units)"
    ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=1, max_row=n), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n))
    paint_line(ch.series[0], SERIES_BLUE)
    paint_line(ch.series[1], SERIES_ORANGE)
    style_axes(ch, "Fiscal year", "Units or bottles per 100,000 population", 14, 9)
    ws.add_chart(ch, "F2")

    ch = LineChart()
    ch.title = "Combined volume of the two drugs (mL-converted)"
    ch.add_data(Reference(ws, min_col=4, min_row=1, max_row=n), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=n))
    paint_line(ch.series[0], SERIES_BLUE)
    style_axes(ch, "Fiscal year", "mL per 100,000 population", 14, 9)
    ch.legend = None
    ws.add_chart(ch, "F20")

    # Table 1
    df_t1 = load_csv("national_trends_immuno.csv")
    df_t1 = df_t1[df_t1['year'] == 2024]
    cols = ['code', 'unit', 'count_published', 'count_ml', 'count_per_100k', 'count_ml_per_100k']
    cols = [c for c in cols if c in df_t1.columns]
    df_t1 = sort_code_rows(df_t1)[cols]
    df_t1.to_excel(writer, sheet_name='Table 1', index=False)

    # Table 2
    df_t2 = load_csv("mf_ratio_by_age_immuno.csv")
    df_t2 = df_t2[df_t2['year'] == 2024]
    df_t2 = df_t2[['code', 'age_group', 'mf_ratio_rate']]
    df_t2_pivot = df_t2.pivot(index='age_group', columns='code', values='mf_ratio_rate')
    df_t2_pivot = sort_code_columns(sort_age_index(df_t2_pivot))
    df_t2_pivot.to_excel(writer, sheet_name='Table 2')

    # Table 3
    df_t3 = load_csv("prefecture_ranking_2024_immuno.csv")
    cols_t3 = [c for c in df_t3.columns if c in ['prefecture', 'code', 'count_ml_per_100k', 'rank_2024'] or 'rank' in c or 'count' in c]
    df_t3 = sort_code_rows(df_t3)[cols_t3]
    df_t3.to_excel(writer, sheet_name='Table 3', index=False)

    # Suppl. 1
    df_s1 = load_csv("geographic_disparity_immuno.csv")
    df_s1 = df_s1[df_s1['metric'] == 'count_ml_per_100k']
    df_s1 = sort_code_rows(df_s1)
    df_s1.to_excel(writer, sheet_name='Suppl. 1', index=False)

    # Suppl. 2
    df_s2 = load_csv("censoring_sensitivity_immuno.csv")
    cols_s2 = [c for c in df_s2.columns if 'interval_width' in c or 'capture_rate' in c or c in ['year', 'code']]
    df_s2 = sort_code_rows(df_s2)[cols_s2]
    df_s2.to_excel(writer, sheet_name='Suppl. 2', index=False)

    # Suppl. 3
    df_s3 = load_csv("censoring_sensitivity_disparity_immuno.csv")
    cols_s3 = [c for c in df_s3.columns if 'zero' in c or 'upper' in c or c in ['year', 'code', 'metric']]
    df_s3 = sort_code_rows(df_s3)[cols_s3]
    df_s3.to_excel(writer, sheet_name='Suppl. 3', index=False)

    # Suppl. 4
    df_s4 = load_csv("apc_immuno.csv")
    cols_s4 = ['code', 'metric', 'apc', 'apc_low', 'apc_high', 'p_value', 'years_observed']
    cols_s4 = [c for c in cols_s4 if c in df_s4.columns]
    df_s4 = sort_code_rows(df_s4)[cols_s4]
    df_s4.to_excel(writer, sheet_name='Suppl. 4', index=False)

    # Suppl. 5
    df_s5 = load_csv("covariate_correlation_immuno.csv")
    cols_s5 = [c for c in df_s5.columns if 'rho' in c or 'p_' in c or c in ['year', 'code', 'metric']]
    df_s5 = sort_code_rows(df_s5)[cols_s5]
    df_s5.to_excel(writer, sheet_name='Suppl. 5', index=False)

    # Suppl. 6
    # 共変量名の列は 'variable'（'covariate' ではない）。指定が誤っていたため
    # どの共変量の係数か分からない表になっていたので修正した。
    df_s6 = load_csv("panel_regression_summary_immuno.csv")
    cols_s6 = ['code', 'dependent_variable', 'variable', 'coefficient', 'p_value', 'r2_within']
    cols_s6 = [c for c in cols_s6 if c in df_s6.columns]
    df_s6 = sort_code_rows(df_s6)[cols_s6]
    df_s6.to_excel(writer, sheet_name='Suppl. 6', index=False)

print("XLSX generated successfully.")
