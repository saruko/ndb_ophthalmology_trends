# -*- coding: utf-8 -*-
"""
Clinical Ophthalmology 投稿用 本文ドラフト (.docx) 生成スクリプト

使用方法:
    pip install python-docx
    python generate_manuscript_docx.py
"""

import os
import pandas as pd
import numpy as np
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "論文")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# =========================================================================
# CSVデータ読み込み・整形関数
# =========================================================================

def get_table1_data():
    csv_path = os.path.join(BASE_DIR, "data/processed/national_trends.csv")
    if not os.path.exists(csv_path):
        return []
    df = pd.read_csv(csv_path)
    # codeの順序
    codes = ["J039-2", "K280", "K282", "K282_total", "K268", "K259"]
    df_pivot = df.pivot(index="year", columns="code", values="count_per_100k")
    
    rows = []
    for yr in sorted(df_pivot.index):
        row = [str(yr)]
        for c in codes:
            if c in df_pivot.columns:
                val = df_pivot.loc[yr, c]
                row.append(f"{val:,.1f}")
            else:
                row.append("—")
        rows.append(row)
    return rows


def get_table2_data():
    df_lin_path = os.path.join(BASE_DIR, "data/processed/national_apc_linear.csv")
    df_jp_path = os.path.join(BASE_DIR, "data/processed/national_apc_joinpoint.csv")
    if not os.path.exists(df_lin_path) or not os.path.exists(df_jp_path):
        return []
    
    df_lin = pd.read_csv(df_lin_path)
    df_jp = pd.read_csv(df_jp_path)
    
    rows = []
    codes = ["J039-2", "K280", "K282", "K282_total", "K268", "K259"]
    code_names = {
        "J039-2": "J039-2 (抗VEGF)",
        "K280": "K280 (硝子体手術)",
        "K282": "K282 (白内障手術)",
        "K282_total": "K282_total (白内障合算)",
        "K268": "K268 (緑内障手術)",
        "K259": "K259 (角膜移植術)"
    }
    
    for c in codes:
        # 線形 APC
        lin_row = df_lin[df_lin["code"] == c]
        if not lin_row.empty:
            r = lin_row.iloc[0]
            sig = "*" if r["p_value"] < 0.05 else ""
            p_str = f"{r['p_value']:.4f}" if r["p_value"] >= 0.001 else "<0.001"
            rows.append([
                code_names.get(c, c), "線形", f"{int(r['start_year'])}–{int(r['end_year'])}",
                f"{r['apc']:+.2f}%{sig}", f"{r['apc_low']:+.2f}–{r['apc_high']:+.2f}",
                p_str, f"{r['r2']:.4f}"
            ])
        # Joinpoint APC
        jp_rows = df_jp[df_jp["code"] == c]
        for _, jp_r in jp_rows.iterrows():
            rows.append([
                "", f"Joinpoint (Seg {int(jp_r['segment'])})",
                f"{jp_r['start_year']:.1f}–{jp_r['end_year']:.1f}",
                f"{jp_r['apc']:+.2f}%", "—", "—", "—"
            ])
    return rows


def get_table3_data():
    csv_path = os.path.join(BASE_DIR, "data/processed/geographic_disparity.csv")
    if not os.path.exists(csv_path):
        return []
    df = pd.read_csv(csv_path)
    codes = ["J039-2", "K280", "K282", "K282_total", "K268", "K259"]
    code_names = {
        "J039-2": "J039-2",
        "K280": "K280",
        "K282": "K282",
        "K282_total": "K282_total",
        "K268": "K268",
        "K259": "K259"
    }
    
    rows = []
    for yr in [2014, 2023]:
        for c in codes:
            sub = df[(df["year"] == yr) & (df["code"] == c)]
            if not sub.empty:
                r = sub.iloc[0]
                ratio_str = f"{r['max_to_min_ratio']:.2f}" if not pd.isna(r['max_to_min_ratio']) else "—"
                rows.append([
                    str(yr), code_names.get(c, c), f"{r['gini']:.4f}", f"{r['cv']:.4f}",
                    f"{r['min_prefecture']} ({r['min_rate']:.2f})",
                    f"{r['max_prefecture']} ({r['max_rate']:.2f})",
                    ratio_str
                ])
    return rows


def get_table4_data():
    csv_path = os.path.join(BASE_DIR, "data/processed/covariates_correlation.csv")
    if not os.path.exists(csv_path):
        return []
    df = pd.read_csv(csv_path)
    df_2023 = df[df["year"] == 2023]
    codes = ["J039-2", "K280", "K282", "K282_total", "K268", "K259"]
    code_names = {
        "J039-2": "J039-2 (抗VEGF)",
        "K280": "K280 (硝子体)",
        "K282": "K282 (白内障)",
        "K282_total": "K282_total (合算)",
        "K268": "K268 (緑内障)",
        "K259": "K259 (角膜移植)"
    }
    
    rows = []
    for c in codes:
        sub = df_2023[df_2023["code"] == c]
        if not sub.empty:
            r = sub.iloc[0]
            p_aging = f"{r['p_value_aging']:.4f}" if r['p_value_aging'] >= 0.001 else "<0.001"
            p_docs = f"{r['p_value_docs']:.4f}" if r['p_value_docs'] >= 0.001 else "<0.001"
            p_facs = f"{r['p_value_facilities']:.4f}" if r['p_value_facilities'] >= 0.001 else "<0.001"
            rows.append([
                code_names.get(c, c),
                f"{r['spearman_rho_aging']:.4f}", p_aging,
                f"{r['spearman_rho_docs']:.4f}", p_docs,
                f"{r['spearman_rho_facilities']:.4f}", p_facs
            ])
    return rows


def get_table5_data():
    csv_path = os.path.join(BASE_DIR, "data/processed/panel_regression_summary.csv")
    if not os.path.exists(csv_path):
        return []
    df = pd.read_csv(csv_path)
    codes = ["J039-2", "K280", "K282", "K282_total", "K268", "K259"]
    code_names = {
        "J039-2": "J039-2",
        "K280": "K280",
        "K282": "K282",
        "K282_total": "K282_total",
        "K268": "K268",
        "K259": "K259"
    }
    var_map = {
        "aging_rate": "高齢化率",
        "docs_per_100k": "眼科医数",
        "facilities_per_100k": "施設数"
    }
    
    rows = []
    for c in codes:
        sub = df[df["code"] == c]
        if sub.empty:
            continue
        r2_w = sub.iloc[0]["r2_within"]
        r2_str = f"{r2_w:.4f}"
        for i, (_, r) in enumerate(sub.iterrows()):
            p_str = f"{r['p_value']:.4f}" if r['p_value'] >= 0.001 else "<0.001"
            sig = "*" if r["p_value"] < 0.05 else ""
            rows.append([
                code_names.get(c, c) if i == 0 else "",
                var_map.get(r["variable"], r["variable"]),
                f"{r['coefficient']:+.4f}{sig}",
                f"{r['std_err']:.4f}",
                f"{r['t_stat']:.4f}",
                p_str,
                r2_str if i == 0 else ""
            ])
    return rows


# =========================================================================
# Word ドキュメント構築用関数
# =========================================================================

def set_style(doc):
    style = doc.styles["Normal"]
    font = style.font
    font.name = "游明朝"
    font.size = Pt(10.5)
    style.paragraph_format.line_spacing = 2.0
    style.paragraph_format.space_after = Pt(0)


def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
    return h


def add_paragraph(doc, text, bold=False, italic=False, alignment=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    if alignment:
        p.alignment = alignment
    return p


def add_table_from_data(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True
                run.font.size = Pt(9)
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = str(val)
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(9)
    return table


def build_manuscript():
    doc = Document()
    set_style(doc)

    # =========================================================================
    # Title Page
    # =========================================================================
    add_paragraph(doc, "Original Research", bold=True,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()

    add_paragraph(
        doc,
        "NDBオープンデータを用いた日本の主要眼科手術および抗VEGF薬注射の"
        "経年トレンドと地域格差の解析：2014〜2023年度の全国悉皆データに基づく記述疫学研究",
        bold=True,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
    )
    doc.add_paragraph()
    add_paragraph(
        doc,
        "Trends and Geographic Disparities in Major Ophthalmic Procedures "
        "in Japan: A Nationwide Claims Database Study (2014–2023)",
        italic=True,
        alignment=WD_ALIGN_PARAGRAPH.CENTER,
    )
    doc.add_paragraph()

    add_paragraph(doc, "著者名: [著者名を記入]", alignment=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(doc, "所属: [所属を記入]", alignment=WD_ALIGN_PARAGRAPH.CENTER)
    add_paragraph(doc, "責任著者連絡先: [メールアドレス・住所]",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    add_paragraph(doc, "投稿先: Clinical Ophthalmology (Dove Press)",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER)

    doc.add_page_break()

    # =========================================================================
    # Abstract
    # =========================================================================
    add_heading(doc, "Abstract", level=1)

    add_paragraph(doc, "Purpose", bold=True)
    add_paragraph(
        doc,
        "本研究は、NDBオープンデータ（第1〜10回：2014〜2023年度）を用いて、"
        "日本の主要眼科手術（白内障手術、硝子体手術、緑内障手術、角膜移植術）および抗VEGF薬注射の"
        "全国施行トレンド、都道府県間の地域格差の推移、ならびにその構造的関連要因を"
        "明らかにすることを目的とした。"
    )

    add_paragraph(doc, "Methods", bold=True)
    add_paragraph(
        doc,
        "解析対象は白内障手術（K282）、硝子体手術（K280合算）、抗VEGF薬注射（J039-2；薬剤数量による代替推計）、"
        "緑内障手術（K268合算）、角膜移植術（K259；150086210のみ）の5手技とした。"
        "増殖性硝子体網膜症手術（K281）は秘匿閾値により除外した。"
        "トレンド指標として人口10万対施行率の年平均変化率（APC）を対数線形回帰で算出し、"
        "探索的Joinpoint回帰で変化点を同定した。"
        "地域格差はジニ係数および変動係数（CV）の経年推移で評価した。"
        "関連要因は47都道府県のSpearman順位相関（断面的分析）および"
        "two-way固定効果パネル回帰（都道府県＋年固定効果、"
        "都道府県クラスターロバスト標準誤差）で検討した。"
    )

    add_paragraph(doc, "Results", bold=True)
    add_paragraph(
        doc,
        "抗VEGF薬注射は10年間で約3.1倍に急増し（250.5→771.2/10万人；APC +12.2%、p<0.001）、"
        "Joinpoint回帰で2016.7年に成長減速の変化点を検出した（前半APC +25.0%、後半+8.4%）。"
        "緑内障手術は10年間で約4.6倍に急増し（22,098→101,011件；APC +17.7%、p=0.001）、"
        "Joinpoint回帰では2020.5年に変化点が同定され、後半セグメントのAPCは+68.9%に急加速した。"
        "白内障手術はAPC +4.1%（p=0.051）、硝子体手術はAPC +3.3%（p<0.001）で増加した。"
        "角膜移植術は年間約3,000件で推移し（APC -0.57%、p=0.525）、2020年のコロナ禍による一時的低下から回復した。"
        "地域格差は、角膜移植術において極めて高水準であり（Gini 0.40–0.47）、"
        "抗VEGF薬注射の格差は大幅に収斂し（Gini 0.254→0.108）、"
        "白内障手術は一貫して低格差であった（Gini≈0.07）。"
        "断面的相関では硝子体手術と眼科医数に一貫した正の相関を認めた（ρ≈0.58–0.62、p<0.001）。"
        "Two-way固定効果パネル回帰では、角膜移植術で標榜施設数が有意に関連していた（p=0.032）が、"
        "その他の手技では有意な共変量効果は認められず、全国共通の時間トレンド（time FE）との交絡が示唆された。"
    )

    add_paragraph(doc, "Conclusion", bold=True)
    add_paragraph(
        doc,
        "日本では抗VEGF薬注射に加え、低侵襲手術（MIGS）の普及を背景に緑内障手術が爆発的に増加している。"
        "高度な専門性を要する角膜移植は、高い地域偏在性を維持しつつ安定的に提供されている。"
        "施行率のトレンドは都道府県固有の構造的要因と全国共通の年次変化に大きく規定されており、"
        "高齢化率や眼科医数の経年変動の寄与は限定的であった。"
    )

    add_paragraph(doc, "Keywords", bold=True)
    add_paragraph(
        doc,
        "NDBオープンデータ、白内障手術、硝子体手術、抗VEGF薬注射、緑内障手術、角膜移植術、"
        "トレンド分析、地域格差、ジニ係数、パネル回帰"
    )

    doc.add_page_break()

    # =========================================================================
    # Introduction
    # =========================================================================
    add_heading(doc, "緒言 (Introduction)", level=1)

    add_paragraph(
        doc,
        "日本は世界で最も高齢化が進んだ国であり、65歳以上人口の割合は2023年時点で約29%に達している。"
        "加齢に伴い白内障、加齢黄斑変性（AMD）、糖尿病網膜症、緑内障、角膜変性などの"
        "眼疾患の有病率が上昇するため、これらの疾患に対する手術・薬物治療の需要は"
        "増大し続けていると推測される。しかし、全国レベルの悉皆データに基づいて"
        "眼科診療の長期トレンドや地域格差を定量的に検証した研究は限られている。"
    )

    add_paragraph(
        doc,
        "抗VEGF薬（血管内皮増殖因子阻害薬）の硝子体内注射は、AMDや糖尿病黄斑浮腫、"
        "網膜静脈閉塞症に伴う黄斑浮腫等に対する標準治療として確立されている。"
        "2012年以降のアフリベルセプトの適応拡大、さらに2020年のブロルシズマブ、"
        "2022年のファリシマブの承認により、治療選択肢は拡大し続けている。"
        "また、緑内障領域においては、2010年代後半から低侵襲緑内障手術（MIGS；Microinvasive Glaucoma Surgery）"
        "が登場し、特に2020年に保険収載された水晶体再建術併用眼内ドレーン（iStentなど）は、"
        "白内障手術と同時施行できるため、一般開業医を含め爆発的に普及した。"
        "一方で、角膜移植術などの高度専門的な外科的治療は、ドナー供給の制限や提供医療機関の偏在、"
        "アイバンクとの連携体制などにより、他の眼科手術とは異なるトレンドや地域格差を持つと推測される。"
    )

    add_paragraph(
        doc,
        "医療へのアクセスの地域格差は日本の医療政策上の主要課題の一つである。"
        "眼科領域においては、手術施設や専門医の地域偏在が施行率の格差を生じさせている"
        "可能性があるが、都道府県間の格差を定量的指標（ジニ係数や変動係数）で"
        "経年的に追跡した報告は極めて少ない。"
        "Shigaら(2026)はNDBオープンデータの2022年度単年を用いて眼科手術の"
        "都道府県間格差を報告しているが、格差の経時的変化は検討されていない。"
        "Kitazawaら(2023)は2014〜2020年のNDBデータで白内障手術と硝子体手術の"
        "トレンドを報告しているが、抗VEGF薬注射や緑内障手術、角膜移植術を対象に含まず、"
        "格差の定量的指標も用いていない。"
    )

    add_paragraph(
        doc,
        "NDBオープンデータ（厚生労働省）は、全保険診療のレセプト集計値を"
        "都道府県別・年齢階級別に公開しており、全国悉皆データに基づく"
        "眼科診療トレンド解析に適した唯一のデータソースである。"
        "2014年度の第1回公開から2023年度の第10回まで、10年分のデータが蓄積されている。"
    )

    add_paragraph(
        doc,
        "本研究の目的は以下の3点である。"
        "（1）主要眼科手術（白内障手術、硝子体手術、緑内障手術、角膜移植術）および抗VEGF薬注射の"
        "全国施行トレンドを年平均変化率（APC）およびJoinpoint回帰により定量化する。"
        "（2）都道府県間の地域格差の推移をジニ係数およびCVで追跡する。"
        "（3）施行率と構造的要因（高齢化率、眼科医数、眼科施設数）の関連を"
        "断面的相関分析およびtwo-way固定効果パネル回帰により評価する。"
    )

    doc.add_page_break()

    # =========================================================================
    # Methods
    # =========================================================================
    add_heading(doc, "方法 (Methods)", level=1)

    add_heading(doc, "研究デザインとデータソース", level=2)
    add_paragraph(
        doc,
        "後ろ向き横断反復調査（repeated cross-sectional study）による記述疫学研究である。"
        "データは厚生労働省NDBオープンデータ第1回〜第10回（2014〜2023年度）を使用した。"
        "NDBオープンデータは匿名化済み集計統計であり、"
        "個人の同意および倫理審査委員会の承認は不要である。"
    )

    add_heading(doc, "対象手技の定義", level=2)
    add_paragraph(
        doc,
        "解析対象は以下の5手技とした。"
    )
    add_paragraph(
        doc,
        "（1）白内障手術（K282）：水晶体再建術（眼内レンズを挿入する場合）（その他のもの）。"
        "レセプト電算処理コード150253010、190179210、190179310で特定した。"
        "主解析はK282単独（その他のもの）とし、"
        "追加解析として縫着レンズ（K282_i）との合算（K282_total）を実施した。"
    )
    add_paragraph(
        doc,
        "（2）硝子体手術（K280合算）：硝子体茎顕微鏡下離断術の"
        "「網膜付着組織を含むもの」（K280_1；150274010）と"
        "「その他のもの」（K280_2；150090610）を合算した。"
    )
    add_paragraph(
        doc,
        "（3）抗VEGF薬注射（J039-2；薬剤数量代替推計）：NDBオープンデータでは"
        "硝子体内注射の処置件数が直接公開されていないため、"
        "抗VEGF薬の個別品目の薬剤数量データを代替指標として使用した。"
        "対象はラニビズマブ（ルセンティス）、アフリベルセプト（アイリーア）、"
        "ブロルシズマブ（ベオビュ）、ファリシマブ（バビースモ）等の9品目のYコードを"
        "集計した（品目一覧はSupplementary Table S1に記載）。"
    )
    add_paragraph(
        doc,
        "（4）緑内障手術（K268合算）：緑内障手術（K268）および短手３（A400）の緑内障手術関連コードを含む、"
        "観血的緑内障手術に関連する全8種の電算処理コードを合算した。"
        "電算処理コードは 150335910（濾過手術）、150427310（濾過胞再建術）、150087510（虹彩切除術）、"
        "150356010（インプラント：プレートなし）、150373010（インプラント：プレートあり）、"
        "150427210（流出路再建術：その他）、150435810（流出路再建術：眼内法）、"
        "および 150395150（水晶体再建術併用眼内ドレーン）とした。"
        "なお、レーザー光凝固（K270等）は他術式との一貫性を保つため対象外とした。"
    )
    add_paragraph(
        doc,
        "（5）角膜移植術（K259）：角膜移植術の電算処理コード 150086210 のみを集計した。"
        "K259-2（自家培養口腔粘膜上皮細胞シート移植等）は臨床的背景が大きく異なるため除外した。"
    )
    add_paragraph(
        doc,
        "増殖性硝子体網膜症手術（K281）は、NDBオープンデータの秘匿閾値"
        "（各都道府県で10件未満は非公開）により大半の都道府県・年度で値が秘匿されており、"
        "安定した統計解析が困難なため解析対象から除外した。"
    )
    add_paragraph(
        doc,
        "秘匿値（10件未満で「-」表示）の補完については、主解析では0で補完した。"
        "感度分析として5補完および1〜9の一様乱数補完を実施した。"
    )

    add_heading(doc, "共変量", level=2)
    add_paragraph(
        doc,
        "以下の共変量をe-Stat（政府統計 of 統計局）より取得し、人口10万対の率に変換した。"
    )
    add_paragraph(
        doc,
        "・都道府県別人口および65歳以上人口：総務省統計局「人口推計」（各年10月1日現在）"
        "（※2015年は国勢調査確定値、2020年は人口推計補正人口の実数値をアンカーとして使用）\n"
        "・眼科医師数：厚生労働省「医師・歯科医師・薬剤師統計」（隔年調査；奇数年は隣接する調査年の線形補間）\n"
        "・眼科標榜施設数：厚生労働省「医療施設調査（静態調査）」（3年周期；中間年は線形補間）"
    )

    add_heading(doc, "統計解析", level=2)

    add_paragraph(doc, "全国トレンド（APC）", bold=True)
    add_paragraph(
        doc,
        "各手技の全国年度別人口10万対施行率について、"
        "対数線形回帰（log(rate) = β₀ + β₁ × year）を適合し、"
        "年平均変化率（APC = (exp(β₁) − 1) × 100 [%]）と95%信頼区間を算出した。"
        "探索的分析として、pwlf（piecewise linear fitting）ライブラリを用いた"
        "2セグメント固定のJoinpoint回帰を実施し、経年トレンドの変化点（ノット）を同定した。"
    )

    add_paragraph(doc, "地域格差", bold=True)
    add_paragraph(
        doc,
        "47都道府県の人口10万対施行率について、各年度・手技別に"
        "ジニ係数（0＝完全平等、1＝完全不平等）および変動係数"
        "（CV＝標準偏差/平均）を算出し、経年推移を評価した。"
    )

    add_paragraph(doc, "関連要因分析：断面的相関", bold=True)
    add_paragraph(
        doc,
        "各年度について、47都道府県の人口10万対施行率と共変量"
        "（高齢化率、眼科医数/10万人、眼科施設数/10万人）の"
        "Spearman順位相関係数を算出した。"
    )

    add_paragraph(doc, "関連要因分析：パネル回帰", bold=True)
    add_paragraph(
        doc,
        "47都道府県×10年度のパネルデータを構築し、"
        "two-way固定効果モデル（都道府県固定効果＋年固定効果）を適用した。"
        "目的変数は人口10万対施行率、説明変数は高齢化率、眼科医数/10万人、"
        "眼科施設数/10万人とした。"
        "都道府県クラスターロバスト標準誤差を使用し、"
        "都道府県内の系列相関に対して頑健な推定を行った。"
    )

    add_paragraph(doc, "感度分析", bold=True)
    add_paragraph(
        doc,
        "以下の感度分析を実施した。"
        "（a）共変量が実測値である調査実施年のみ"
        "（2014、2016、2018、2020、2022年度）のサブセットでパネル回帰を再推定した。"
        "（b）Entity FEのみ（年固定効果なし）のモデルを推定し、"
        "time FE追加前後の係数変化を比較した。"
        "（c）秘匿値の5補完および一様乱数補完による全解析の再実行を行った。"
    )

    doc.add_page_break()

    # =========================================================================
    # Results
    # =========================================================================
    add_heading(doc, "結果 (Results)", level=1)

    # --- 3.1 National Trends ---
    add_heading(doc, "全国トレンド", level=2)
    add_paragraph(
        doc,
        "2014〜2023年度の各手技の全国施行件数および人口10万対施行率の推移をTable 1に、"
        "全国トレンドの折れ線グラフをFigure 1に示す。"
    )

    add_paragraph(doc, "抗VEGF薬注射（J039-2）", bold=True)
    add_paragraph(
        doc,
        "人口10万対施行率は2014年度の250.5から2023年度の771.2へと10年間で約3.1倍に増加した。"
        "対数線形回帰によるAPCは+12.25%（95%CI 10.00–14.55、p<0.001、R²=0.94）であり、"
        "対象手技の中で最も急速な増加を示した（Table 2）。"
    )

    add_paragraph(doc, "緑内障手術（K268）", bold=True)
    add_paragraph(
        doc,
        "人口10万対施行率は2014年度の17.4から2023年度の81.2へと、10年間で約4.6倍に急増した。"
        "対数線形回帰によるAPCは+17.66%（95%CI 10.30–25.51、p=0.001、R²=0.75）であった。"
        "特に2021年度（28.5/10万人）から2022年度（69.0/10万人）にかけての急増が極めて顕著であった。"
    )

    add_paragraph(doc, "白内障手術（K282）および硝子体手術（K280）", bold=True)
    add_paragraph(
        doc,
        "白内障手術の人口10万対施行率は2014年度の1,099.3から2023年度の1,429.6へと増加した。"
        "APCは+4.10%（p=0.051、R²=0.40）であった。縫着レンズ含む合算（K282_total）でも"
        "APC +4.13%（p=0.048）であった。硝子体手術は2014年度の82.3から2023年度の117.6へと"
        "安定的に増加し、APCは+3.35%（p<0.001、R²=0.90）であった。"
    )

    add_paragraph(doc, "角膜移植術（K259）", bold=True)
    add_paragraph(
        doc,
        "角膜移植術は、2014年度の2,995件（2.36/10万人）から2023年度の3,008件（2.42/10万人）"
        "と、10年間を通じてほぼ横ばいで推移した。線形APCは-0.57%（p=0.525、R²=0.05）であり、"
        "統計的に有意な変化傾向は認められなかった。"
    )

    # --- 3.2 Joinpoint ---
    add_heading(doc, "Joinpoint分析", level=2)
    add_paragraph(
        doc,
        "探索的Joinpoint回帰の結果をTable 2（下段）およびFigure 2に示す。"
    )

    add_paragraph(
        doc,
        "抗VEGF薬注射では2016.7年に変化点が検出され、"
        "前半セグメント（2014–2016.7年）のAPCは+24.98%、"
        "後半セグメント（2016.7–2023年）のAPCは+8.43%であった。"
        "初期の急速な普及フェーズから、成熟した安定普及フェーズへの移行が示された。"
    )
    add_paragraph(
        doc,
        "緑内障手術では2020.5年に変化点が検出された。"
        "前半セグメント（2014–2020.5年）のAPCは+6.50%であったが、"
        "後半セグメント（2020.5–2023年）のAPCは**+68.92%**へと急加速していた。"
        "2020年以降に普及したMIGS（水晶体再建術併用眼内ドレーン）による構造変化が明確に捉えられた。"
    )
    add_paragraph(
        doc,
        "角膜移植術では2020.4年に変化点が同定され、"
        "前半セグメント（2014–2020.4年）はAPC -2.57%と緩やかな減少傾向であったが、"
        "後半セグメント（2020.4–2023年）はAPC +6.63%と、コロナ禍における"
        "一時的低下（2020年度は2,382件）からのV字回復のトレンドを反映していた。"
    )
    add_paragraph(
        doc,
        "白内障手術では2016.0年に変化点が検出され、"
        "前半（2014–2016年）はAPC −14.14%、後半（2016–2023年）はAPC +7.74%であった。"
        "硝子体手術は2021.7年に変化点を検出し、後半に増加ペースがやや加速した（前半+2.86%、後半+8.91%）。"
    )

    # --- 3.3 Geographic Disparity ---
    add_heading(doc, "地域格差の推移", level=2)
    add_paragraph(
        doc,
        "各手技の都道府県間地域格差指標（ジニ係数、CV、最大/最小比）の推移を"
        "Table 3およびFigure 3に示す。"
    )

    add_paragraph(doc, "角膜移植術（K259）", bold=True)
    add_paragraph(
        doc,
        "角膜移植術の地域格差は、全期間・全手技の中で極めて高い水準を維持した。"
        "ジニ係数は2014年度の0.405から2023年度の0.465へと上昇傾向にあり、"
        "CVも0.736から0.841へと拡大した。和歌山県が全期間を通じて最小値（0件、補完値0）"
        "であり、最高値は京都府（2014年）や石川県（2023年）などで、高度専門施設への高度な集中を示していた。"
    )

    add_paragraph(doc, "緑内障手術（K268）", bold=True)
    add_paragraph(
        doc,
        "緑内障手術の地域格差は緩やかな低下傾向を示した。"
        "ジニ係数は2014年度の0.254から2023年度の0.206へと低下し、"
        "CVも0.523から0.424へと低下した。最大/最小比は8.68倍から5.71倍へと縮小した。"
        "全期間を通じて島根県が一貫して最高率であった。"
    )

    add_paragraph(doc, "その他の手技", bold=True)
    add_paragraph(
        doc,
        "抗VEGF薬注射の地域格差は劇的に収斂した（Gini 0.254→0.108、CV 0.464→0.195）。"
        "白内障手術は一貫して極めて低い格差水準を維持し（Gini≈0.07）、"
        "硝子体手術の格差は概ね横ばい（Gini≈0.13）であった。"
    )

    # --- 3.4 Prefecture Ranking ---
    add_heading(doc, "都道府県別施行率", level=2)
    add_paragraph(
        doc,
        "2023年度の都道府県別施行率ランキングをFigure 4に示す。"
        "緑内障手術では島根県（225.4/10万人）が最高、秋田県（39.5/10万人）が最低であり、約5.7倍の開きがあった。"
        "角膜移植術では、石川県（6.94/10万人）が最高であり、和歌山県（0件）を含む複数の県で非常に低い施行率であった。"
        "抗VEGF薬注射では長崎県（1,168.8/10万人）が最高、沖縄県（383.9/10万人）が最低であった。"
    )

    # --- 3.5 Spearman Correlation ---
    add_heading(doc, "断面的相関分析", level=2)
    add_paragraph(
        doc,
        "各年度における47都道府県の施行率と共変量のSpearman順位相関係数をTable 4および"
        "Figure 5（2023年度の散布図）に示す。"
    )
    add_paragraph(
        doc,
        "緑内障手術（K268）と人口10万対眼科医数は、全年度で一貫して正の相関を示した"
        "（2023年度 ρ=0.423、p=0.003）。一方、高齢化率や施設数との相関は一貫して弱く、有意ではなかった。"
    )
    add_paragraph(
        doc,
        "角膜移植術（K259）の共変量との相関は一貫して非常に低く、いずれの年度においても"
        "高齢化率、医数、施設数との間に統計的有意な断面的相関は認められなかった（2023年高齢化率 ρ=0.101、p=0.499）。"
    )
    add_paragraph(
        doc,
        "硝子体手術と眼科医数には一貫して強い正の相関（ρ≈0.58）を認めた。白内障手術と高齢化率には"
        "中程度の正の相関（ρ≈0.20〜0.53）を認めた。抗VEGF薬注射と医師数には、近年（2021年以降）に"
        "有意な正の相関が認められるようになった。"
    )

    # --- 3.6 Panel Regression ---
    add_heading(doc, "パネル回帰分析", level=2)
    add_paragraph(
        doc,
        "Two-way固定効果パネル回帰の結果をTable 5に示す。"
    )

    add_paragraph(doc, "主解析（Two-way FE、全10年度）", bold=True)
    add_paragraph(
        doc,
        "角膜移植術（K259）において、人口10万対眼科施設数が施行率と有意な正の関連を示した"
        "（β=0.500, SE=0.232, p=0.032）。一方、高齢化率や眼科医数とは有意な関連はなかった。"
        "緑内障手術（K268）では、高齢化率、医師数、施設数のいずれも有意な効果を示さなかった"
        "（医師数 β=9.56, SE=5.19, p=0.066；R² within = -0.158）。"
        "白内障手術および抗VEGF薬注射、硝子体手術においても、主解析モデルでは有意な関連は認められなかった。"
    )

    add_paragraph(doc, "感度分析とロバストネスチェック", bold=True)
    add_paragraph(
        doc,
        "共変量が実測値である5年度に限定した感度分析でも、主解析とほぼ同方向の結果が得られた。"
        "年固定効果を除いたentity FEのみのモデルでは、全手技で高齢化率が高度に有意となったが（p<0.001）、"
        "time FEを追加した主解析ではこれらの効果は完全に消失した。これは、全国共通の時間トレンド（制度・技術変化）が"
        "高齢化率の見かけ上の経年変化と交絡（疑似相関）していたことを強く示している。"
    )

    doc.add_page_break()

    # =========================================================================
    # Discussion
    # =========================================================================
    add_heading(doc, "考察 (Discussion)", level=1)

    add_heading(doc, "主要知見の解釈", level=2)

    add_paragraph(doc, "緑内障手術の爆発的急増と技術革新", bold=True)
    add_paragraph(
        doc,
        "緑内障手術の10年間での4.6倍の増加、およびJoinpoint回帰による2020.5年を境とした"
        "後半セグメント（APC +68.9%）の急加速は、眼科臨床における技術革新のインパクトを劇的に示している。"
        "この急増の主因は、2020年に保険適用が拡大・整理されたiStent（水晶体再建術併用眼内ドレーン挿入術）"
        "をはじめとするMIGS（低侵襲緑内障手術）の爆発的普及である。"
        "MIGSは白内障手術と同時に施行可能であり、手術侵襲が極めて低いため、従来は専門施設でのみ行われていた"
        "緑内障手術を、一般開業医のレベルでも広く導入することを可能とした。"
        "ただし、2021→2022年の2.4倍という極端なジャンプは、2022年度の診療報酬改定および"
        "NDBオープンデータにおける集計定義のマイナーチェンジ（短期滞在手術等基本料3の改定に伴う"
        "コード抽出ロジックの影響など）が関与している可能性も否定できず、解釈には慎重さを要する。"
        "地域格差（ジニ係数0.25→0.21）が比較的低水準で推移していることは、このMIGS技術が全国の"
        "地域医療機関へ均一に浸透したことを意味する。"
    )

    add_paragraph(doc, "角膜移植術の横ばいトレンドと偏在性", bold=True)
    add_paragraph(
        doc,
        "角膜移植術が年間約3,000件で完全に横ばいで推移し、かつ極めて高い地域格差（Gini 0.40–0.47）"
        "を維持していることは、角膜移植医療の特殊な提供体制を反映している。"
        "第一に、角膜移植はドナー角膜の供給制約（アイバンクでの登録・提供体制）に強く依存しており、"
        "手術需要が高まっても施行件数が単純に増加しにくい構造的限界がある。"
        "Joinpoint分析で2020年に明確な落ち込み（コロナ禍によるアイバンク活動の停滞）と、"
        "その後の速やかな回復が検出されたことは、このドナー依存性を裏付けるものである。"
        "第二に、角膜移植は高度な顕微鏡手術技術と術後の複雑な拒絶反応管理を必要とするため、"
        "大学病院や角膜専門医が在籍する特定の高機能病院へ患者が高度に集中している。"
        "和歌山県などで施行数が極めて低く、石川県や京都府で高率である事実は、アイバンクの拠点配置と"
        "移植認定施設の地域分布と密接に関係している。"
        "パネル回帰において、一般の「標榜施設数」のみが有意な関連（p=0.032）を示したことは、"
        "地域における眼科医療インフラ全体の充実度が角膜移植の紹介・提供パイプラインとして寄与している可能性を示唆する。"
    )

    add_paragraph(doc, "抗VEGF薬注射・白内障手術の解釈", bold=True)
    add_paragraph(
        doc,
        "抗VEGF薬注射の10年間で3.1倍の増加と地域格差の大幅な収斂は、地方における網膜疾患治療への"
        "アクセス改善を示している。白内障手術の一貫した低格差（Gini≈0.07）は、日本の国民皆保険制度下で"
        "最も均等に提供されている手術アクセスの好例である。2016年度の白内障手術の一時的な落ち込みは、"
        "NDBの同一日複数回算定の重複計上ルール排除に伴う集計上の人工的な変動を反映している可能性が高い。"
    )

    add_heading(doc, "パネル回帰における方法論的含意", level=2)
    add_paragraph(
        doc,
        "Two-way固定効果パネル回帰で高齢化率などの効果が非有意となった（あるいはR² withinが負値になった）"
        "という事実は、方法論的に重要な示唆を与える。"
        "時間固定効果（time FE）を含めないモデルでは、全国的な時間トレンドと共変量が交絡し、"
        "「高齢化が手術施行率を増加させている」という見かけ上の疑似相関が検出されてしまう。"
        "本研究は、NDBを用いた長期的トレンド分析において、全国共通の年次ショック（制度改定や技術革新）を"
        "適切に吸収するtwo-way固定効果モデルの適用が必須であることを実証的に示した。"
    )

    add_heading(doc, "研究の限界", level=2)
    add_paragraph(
        doc,
        "本研究の主な限界は、NDBオープンデータ特有の秘匿閾値（10件未満非公開）に伴う影響である。"
        "これによりK281は解析対象から除外せざるを得ず、角膜移植術など件数の少ない術式では"
        "特定県での0補完による件数のわずかな過小評価が生じている可能性がある。"
        "また、抗VEGF薬注射は薬剤数量データに基づく代替指標であり、実際の施行件数そのものではない。"
        "さらに、本研究は都道府県レベルの集計データに基づく生態学的研究であり、"
        "個人レベルでの因果推論や、施設間・医師個人レベルのバイアス（エコロジカルバイアス）"
        "を排除できない点に留意が必要である。"
    )

    doc.add_page_break()

    # =========================================================================
    # Conclusion
    # =========================================================================
    add_heading(doc, "結論 (Conclusion)", level=1)
    add_paragraph(
        doc,
        "NDBオープンデータ全10回（2014〜2023年度）の解析から、"
        "日本において低侵襲手術（MIGS）の普及に伴い緑内障手術が10年間で約4.6倍へと爆発的に増加し、"
        "抗VEGF薬注射も3.1倍に急増して地域格差も大幅に改善したことが明らかになった。"
        "一方で、角膜移植術はドナー制約を背景に年間約3,000件で横ばいであり、"
        "提供施設への集中を反映して極めて高い地域格差を維持していた。"
        "Two-way固定効果パネル回帰の適用は、長期的トレンドの分析における疑似相関の排除と、"
        "年固定効果の包含の不可欠性を実証した。"
    )

    doc.add_page_break()

    # =========================================================================
    # References, Tables and save
    # =========================================================================
    add_heading(doc, "謝辞・利益相反 (Acknowledgments & Disclosure)", level=1)
    add_paragraph(doc, "著者に開示すべき利益相反はない。本研究で使用したNDBオープンデータおよび共変量データはすべて公的公開統計（e-Stat）より取得した。")
    doc.add_paragraph()

    add_heading(doc, "参考文献 (References)", level=1)
    refs = [
        "1. 厚生労働省. NDBオープンデータ 第1回〜第10回. https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000177182.html",
        "2. Kitazawa K, et al. Trends in cataract and vitreoretinal surgeries using a Japanese national database from fiscal years 2014 to 2020. Sci Rep. 2023;13:XXXXX.",
        "3. Shiga Y, et al. Regional disparities in ophthalmic surgical volumes across 47 prefectures in Japan: a cross-sectional analysis using National Database of Health Insurance Claims. PLOS ONE. 2026;21(4):eXXXXXX.",
        "4. [JJO 2026 anti-VEGF NDB study. 著者名・詳細を確認して追記]",
        "5. 総務省統計局. 人口推計. https://www.e-stat.go.jp/",
        "6. 厚生労働省. 医師・歯科医師・薬剤師統計. https://www.e-stat.go.jp/",
        "7. 厚生労働省. 医療施設調査. https://www.e-stat.go.jp/",
        "8. Kim HJ, Fay MP, Feuer EJ, Midthune DN. Permutation tests for joinpoint regression with applications to cancer rates. Stat Med. 2000;19(3):335-351.",
    ]
    for ref in refs:
        add_paragraph(doc, ref)

    doc.add_page_break()

    # Tables
    add_heading(doc, "Tables", level=1)

    add_heading(doc, "Table 1. 主要眼科手技の全国年次推移（人口10万対施行率）", level=2)
    t1_headers = ["年度", "J039-2\n(抗VEGF)", "K280\n(硝子体)", "K282\n(白内障)", "K282_total\n(合算)", "K268\n(緑内障)", "K259\n(角膜)"]
    t1_data = get_table1_data()
    if t1_data:
        add_table_from_data(doc, t1_headers, t1_data)
    add_paragraph(doc, "注：施行率は人口10万対。J039-2は薬剤数量による代替推計値。K268は8電算コード合算。K259は150086210のみ。", italic=True)
    doc.add_paragraph()

    add_heading(doc, "Table 2. 年平均変化率（APC）：線形回帰およびJoinpoint回帰", level=2)
    t2_headers = ["手技", "分析方法", "分析期間", "APC (%)", "95% CI", "p値", "R² (線形)"]
    t2_data = get_table2_data()
    if t2_data:
        add_table_from_data(doc, t2_headers, t2_data)
    add_paragraph(doc, "注：Joinpoint回帰はセグメント数2固定の探索的分析。*は線形APCでp<0.05で有意。", italic=True)
    doc.add_paragraph()

    add_heading(doc, "Table 3. 都道府県間の地域格差指標の推移", level=2)
    t3_headers = ["年度", "手技", "ジニ係数", "変動係数 (CV)", "最小率都道府県", "最大率都道府県", "最大/最小比"]
    t3_data = get_table3_data()
    if t3_data:
        add_table_from_data(doc, t3_headers, t3_data)
    add_paragraph(doc, "注：施行率ゼロの都道府県が存在する場合、比率は算出不能(—)となる。", italic=True)
    doc.add_paragraph()

    add_heading(doc, "Table 4. Spearmanの順位相関係数（2023年度）", level=2)
    t4_headers = ["手技", "高齢化率 (ρ)", "p値", "眼科医数 (ρ)", "p値", "施設数 (ρ)", "p値"]
    t4_data = get_table4_data()
    if t4_data:
        add_table_from_data(doc, t4_headers, t4_data)
    add_paragraph(doc, "注：ρは都道府県単位の断面的Spearman相関係数。n=47。", italic=True)
    doc.add_paragraph()

    add_heading(doc, "Table 5. Two-way固定効果パネル回帰モデルのパラメータ推定値", level=2)
    t5_headers = ["手技", "共変量", "回帰係数 β", "標準誤差 SE", "t統計量", "p値", "R² within"]
    t5_data = get_table5_data()
    if t5_data:
        add_table_from_data(doc, t5_headers, t5_data)
    add_paragraph(doc, "注：都道府県および年次固定効果モデル。*はp<0.05で有意。共変量は人口10万対（高齢化率は除く）。", italic=True)
    doc.add_paragraph()

    doc.add_page_break()

    # Figure Legends
    add_heading(doc, "Figure Legends", level=1)
    legends = [
        "Figure 1. 主要眼科手技の全国施行率の推移（2014〜2023年度）: 手技別の全国人口10万対施行率の年次変化。緑内障手術（K268）および抗VEGF薬注射は2020年以降に著明な普及を示した。",
        "Figure 2. Joinpoint回帰による変化点の適合結果: 対数施行率に対する2セグメント固定回帰。K268は2020.5年を境にAPCが+6.5%から+68.9%へと劇的に加速した。",
        "Figure 3. 都道府県間の地域格差指標（ジニ係数、変動係数）の経年推移: 角膜移植術（K259）が一貫して最高格差水準を維持し、抗VEGF薬注射（J039-2）は顕著に収斂した。",
        "Figure 4. 2023年度における都道府県別の施行率ランキング: 各手技別の施行率を降順で示す。全国平均を点線で示す。",
        "Figure 5. 2023年度の施行率と共変量（高齢化率、眼科医数）の相関散布図: 47都道府県の断面的散布図。硝子体手術と眼科医数との強い正の相関が示されている。",
        "Figure 6. パネル回帰係数の比較：Two-way FE vs Entity FEモデル: 年固定効果の追加による高齢化率の疑似相関の消失を示す棒グラフ（概念図）。"
    ]
    for leg in legends:
        add_paragraph(doc, leg)

    # Save
    output_path = os.path.join(OUTPUT_DIR, "NDB眼科トレンド論文ドラフト_ClinicalOphthalmology.docx")
    doc.save(output_path)
    print(f"Manuscript saved to: {output_path}")
    
    # ユーザー側の別の既存のdocxファイル名（NDB_JP_ClinicalOphthalmology.docx）にコピーする
    alt_output_path = os.path.join(OUTPUT_DIR, "NDB_JP_ClinicalOphthalmology.docx")
    doc.save(alt_output_path)
    print(f"Manuscript also saved to: {alt_output_path}")

    return output_path


if __name__ == "__main__":
    build_manuscript()
