import os
import pandas as pd
import numpy as np
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

# フォルダパスの定義
BASE_DIR = r"F:\マイドライブ\NDB_眼科診療トレンド解析_研究計画書\眼腫瘍解析"
OUTPUT_PATH = os.path.join(BASE_DIR, "文書1.docx")

def set_font(run, font_name_ascii="Century", font_name_east_asia="MS 明朝", size_pt=10.5, bold=False, italic=False, color_rgb=(0,0,0)):
    run.font.name = font_name_ascii
    rPr = run._r.get_or_add_rPr()
    rFonts = parse_xml(r'<w:rFonts %s w:ascii="%s" w:hAnsi="%s" w:eastAsia="%s"/>' % (nsdecls('w'), font_name_ascii, font_name_ascii, font_name_east_asia))
    rPr.append(rFonts)
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(*color_rgb)

def set_table_borders(table):
    # 三段表用の罫線設定
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        '<w:tblBorders %s>'
        '<w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="none"/>'
        '<w:insideV w:val="none"/>'
        '<w:left w:val="none"/>'
        '<w:right w:val="none"/>'
        '</w:tblBorders>' % nsdecls('w')
    )
    tblPr.append(borders)

def set_cell_border_bottom(cell, sz="6", val="single", color="000000"):
    # ヘッダー下線用
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        '<w:tcBorders %s>'
        '<w:bottom w:val="%s" w:sz="%s" w:space="0" w:color="%s"/>'
        '</w:tcBorders>' % (nsdecls('w'), val, sz, color)
    )
    tcPr.append(tcBorders)

def add_heading_styled(doc, text, level):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    
    if level == 1:
        set_font(run, font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=14, bold=True)
    elif level == 2:
        set_font(run, font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=12, bold=True)
    else:
        set_font(run, font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=11, bold=True)
    return p

def add_paragraph_styled(doc, text="", align=WD_ALIGN_PARAGRAPH.LEFT):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    if text:
        run = p.add_run(text)
        set_font(run)
    return p

def add_abstract_section(doc, title, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.right_indent = Inches(0.5)
    p.paragraph_format.space_after = Pt(4)
    run_title = p.add_run(f"【{title}】 ")
    set_font(run_title, font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=10, bold=True)
    run_text = p.add_run(text)
    set_font(run_text, font_name_ascii="Century", font_name_east_asia="MS 明朝", size_pt=10)

def main():
    doc = Document()
    
    # ページ設定 (余白)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # 1. 論文題目
    p_title = add_paragraph_styled(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    p_title.paragraph_format.space_before = Pt(24)
    p_title.paragraph_format.space_after = Pt(12)
    run_title = p_title.add_run("レセプト情報・特定健診等情報データベース（NDB）オープンデータを用いた日本における眼腫瘍関連手術の全国トレンド解析（2014〜2023年度）")
    set_font(run_title, font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=18, bold=True)

    p_title_en = add_paragraph_styled(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    p_title_en.paragraph_format.space_after = Pt(24)
    run_title_en = p_title_en.add_run("A Decade-Long Nationwide Trend Analysis of Ophthalmic Tumor Surgeries in Japan Using the National Database of Health Insurance Claims Open Data (2014–2023)")
    set_font(run_title_en, font_name_ascii="Arial", size_pt=14, bold=True, italic=True)

    # 2. 抄録
    p_abs_head = add_paragraph_styled(doc, align=WD_ALIGN_PARAGRAPH.CENTER)
    p_abs_head.paragraph_format.space_after = Pt(8)
    run_abs_head = p_abs_head.add_run("抄録（Abstract）")
    set_font(run_abs_head, font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=12, bold=True)

    add_abstract_section(doc, "背景", "日本の超高齢社会において、眼腫瘍手術の全国的トレンドや年齢層別動向は十分に明らかにされていない。本研究は、レセプト情報・特定健診等情報データベース（NDB）オープンデータを用いて、過去10年間の主要な眼腫瘍関連手術の動向を包括的に解釈することを目的とした。")
    add_abstract_section(doc, "方法", "2014〜2023年度のNDBオープンデータから、眼瞼結膜腫瘍、眼窩腫瘍、眼球摘出、眼内腫瘍に関する16の手術電算コードを抽出した。分母として総務省の全国人口を用い、全年齢の人口10万対粗算定率（Crude Rate）を算出した。年間パーセント変化（APC）および傾向検定は、対数人口をオフセット項としたPoisson回帰モデルを用いて算出した。")
    add_abstract_section(doc, "結果", "10年間で、眼瞼結膜悪性腫瘍手術（K216: APC = +3.80%, p < 0.001）や眼窩腫瘍摘出術（K234: APC = +7.13%, p < 0.001）は有意に増加した。一方、眼球摘出術（K241: APC = -3.08%, p = 0.00016）は有意な減少を示した。結膜腫瘍冷凍凝固術（K225）は2014〜2021年度にかけて急増していたが（APC = +10.58%, p < 0.001）、2022年度の「角結膜悪性腫瘍切除術（K225-4）」新設に伴い、2023年度に件数が73%減少（463件→123件）する構造的断絶が認められた。")
    add_abstract_section(doc, "結論", "日本国内の眼腫瘍手術トレンドは術式により対照的な動向を示した。眼球摘出の減少は低侵襲治療や眼球温存療法の普及を反映している可能性がある。また、NDB等の診療行為コードをベースとした分析においては、診療報酬改定（新規コード収載）がトレンドに及ぼす構造的な影響に十分留意する必要がある。")
    
    # 改ページ
    doc.add_page_break()

    # 3. 緒言 (Introduction)
    add_heading_styled(doc, "1. 緒言（Introduction）", level=1)
    
    p1 = add_paragraph_styled(doc)
    p1.add_run("眼腫瘍（眼瞼、結膜、眼球、眼窩など）は希少疾患であり、単一施設における症例報告や病理診断ベースの限定的な疫学調査はあるものの、日本国内全体における手術施行数の実態や経時的変化はこれまで報告されていない。")
    
    p2 = add_paragraph_styled(doc)
    p2.add_run("近年、厚生労働省が公表する「レセプト情報・特定健診等情報データベース（NDB）オープンデータ」を用いた診療行為の全国トレンド解析が複数の診療科および眼科他領域（白内障、緑内障など）で報告され、医療技術の普及や制度改定の影響評価に貢献している。例えば、AkadaらはNDBオープンデータを用いて日本国内の超高齢社会における加齢黄斑変性（neovascular age-related macular degeneration; nAMD）の有病率および抗VEGF薬による治療負担の急激な増加傾向を明らかにしており、マクロな医療実態を評価する手法としてのNDBの有効性を示している[1]。しかし、眼腫瘍手術の領域に関しては、希少性やコード分類の複雑さからこれまで解析が行われていなかった。")
    
    p3 = add_paragraph_styled(doc)
    p3.add_run("また、眼腫瘍の領域においては近年、眼球摘出を回避し視機能や外観を温存する治療法（眼球温存療法）や低侵襲な手術手技が発展してきている。さらに、超高齢社会に伴う悪性腫瘍の増加や、診療報酬改定による新たな診療行為コードの新設が、臨床現場における術式選択トレンドに大きな影響を与えていると考えられる。")
    
    p4 = add_paragraph_styled(doc)
    p4.add_run("本研究は、2014年度から2023年度までの10年間のNDBオープンデータを用いて、日本における主要な眼腫瘍関連手術の算定動向を体系的に明らかにし、人口動態および治療技術の進歩、診療報酬改定が与えた影響について多角的に考察することを目的とした。")

    # 4. 対象と方法 (Methods)
    add_heading_styled(doc, "2. 対象と方法（Methods）", level=1)
    
    p5 = add_paragraph_styled(doc)
    p5.add_run("本研究は、2014年度（第1回）から2023年度（第10回）までのNDBオープンデータにおける「手術（都道府県別）」および「手術（性・年齢階級別）」の集計ファイルを使用した。また、分母データとなる分母人口には、総務省統計局が公表している「人口推計（各年10月1日現在）」の全国男女別・各歳別人口データを用いた。なお、国勢調査実施年である2015年および2020年については、前後年のデータから線形補間した値を使用した。")
    
    p6 = add_paragraph_styled(doc)
    p6.add_run("対象とする術式コードとして、眼瞼結膜腫瘍、眼窩内腫瘍、眼球摘出、眼内腫瘍に関連する16の電算コード（14の術式グループ）を選択した（表1）。")
    
    p7 = add_paragraph_styled(doc)
    p7.add_run("年齢層別解析を行うため、NDBオープンデータで提供される5歳刻みの19区分データを、小児（0-14歳）、AYA（15-39歳）、成人（40-64歳）、高齢者（65歳以上）の4つの年齢群に集約した。  \nただし、NDBオープンデータの性・年齢階級別クロス集計ファイルは、患者プライバシー保護の観点から「各セルにおける年間算定回数が10件未満」の場合に値が秘匿（「-」）される仕様になっている。そのため、年間の全国算定件数がきわめて少ない低頻度術式では、年齢階級別の再合算値が元の真の全国合計値から大きく乖離し、多くのデータが欠測となる構造的限界が存在する。事前のデータ品質評価において、K265（虹彩腫瘍切除術）、K266（毛様体腫瘍切除術・脈絡膜腫瘍切除術）はほぼ全年度で全年齢階級が秘匿されており年齢別解析および信頼性のあるトレンド解析が不可能であったため、これらは解析対象から除外した。また、K233（眼窩内容除去術）、K236（眼窩悪性腫瘍手術）、K241（眼球摘出術）、K245（眼球摘出及び組織又は義眼台充填術）についても、多くの年度で年齢別のデータが30〜100%（K241では21〜58%）欠測していたため、年齢層別解析からは除外した（あるいは記述的な参考値としての提示に留めた）。比較的症例数の多い術式（K215-2など）であっても数%程度の秘匿累積による過小評価が生じるため、本研究では年齢層別データは絶対数としての提示を避け、構成比率（分布シェア）の経時的変化の記述的議論にのみ使用することとした。また、この秘匿セル問題の影響により年齢階級別の正確な分子（手術件数）が得られないことから、年齢調整率（Age-Standardized Rate）の算出は行わず、全年齢人口を分母とした粗算定率（Crude Rate）のみを用いてトレンド解析を行うこととした。")
    
    p8 = add_paragraph_styled(doc)
    p8.add_run("各術式の全国年間算定回数には、秘匿セルの影響を受けない「都道府県別」集計ファイルから算出された正確な真の全国合計値を使用した。粗算定率は人口10万対年次件数として算出した。統計解析には、年間算定回数を従属変数、カレンダーイヤー（連続変数）を独立変数、全年齢人口の対数値をオフセット項（offset = log(Population)）としたPoisson回帰モデル（Generalized Linear Model; GLM）を採用し、傾向検定（trend test）を実施した。これにより、年間パーセント変化（Annual Percent Change: APC）、その95%信頼区間（CI）、およびp値を算出した。統計的有意水準はp < 0.05とした。なお、結膜腫瘍冷凍凝凝固術（K225）については、2022年度の診療報酬改定で「角結膜悪性腫瘍切除術（K225-4）」が新設されたことにより、急激な症例再分類（構造的断絶）が生じていたため、改定前の2014〜2021年度の8年間に限定して傾向検定を実施した。")

    # 5. 結果 (Results)
    add_heading_styled(doc, "3. 結果（Results）", level=1)
    
    p9 = add_paragraph_styled(doc)
    p9.add_run("2014〜2023年度の10年間における各術式の統計的トレンドを解析した結果、術式によって動向が大きく異なることが示された（表1）。")

    # 表1の動的作成
    results_csv = os.path.join(BASE_DIR, "poisson_trend_test_results.csv")
    df_res = pd.read_csv(results_csv)
    
    # Kコードと術式名のマッピング
    code_names = {
        "K215-2": "眼瞼結膜腫瘍手術",
        "K216": "眼瞼結膜悪性腫瘍手術",
        "K225": "結膜腫瘍冷凍凝固術",
        "K225-2": "結膜腫瘍摘出術",
        "K225-3": "結膜肉芽腫摘除術",
        "K225-4": "角結膜悪性腫瘍切除術",
        "K233": "眼窩内容除去術",
        "K234": "眼窩内腫瘍摘出術（表在性）",
        "K235": "眼窩内腫瘍摘出術（深在性）",
        "K236": "眼窩悪性腫瘍手術",
        "K239": "眼球内容除去術",
        "K241": "眼球摘出術",
        "K245": "眼球摘出及び組織又は義眼台充填術",
        "K265": "虹彩腫瘍切除術",
        "K266": "毛様体腫瘍切除術・脈絡膜腫瘍切除術"
    }

    add_paragraph_styled(doc, "表1: 各術式のPoisson傾向検定結果（2014〜2023年度）", align=WD_ALIGN_PARAGRAPH.LEFT)
    
    # テーブル作成
    table1 = doc.add_table(rows=1, cols=6)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table1)
    
    headers1 = ["Kコード", "術式名", "解析年数", "年間パーセント変化 (APC) [95% CI]", "p値", "トレンド分類 / 備考"]
    hdr_cells = table1.rows[0].cells
    for i, title in enumerate(headers1):
        hdr_cells[i].text = title
        set_cell_border_bottom(hdr_cells[i], sz="12")
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.runs[0], font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=9.5, bold=True)

    # データの追加
    for _, row in df_res.iterrows():
        kcode = row['k_code_group']
        name = code_names.get(kcode, kcode)
        n_years = str(int(row['n_years'])) if not pd.isna(row['n_years']) else "--"
        
        if not pd.isna(row['apc_percent']):
            apc = f"{row['apc_percent']:.2f}%"
            ci = f"[{row['apc_ci_low']:.2f}%, {row['apc_ci_high']:.2f}%]"
            apc_ci = f"{apc} {ci}"
        else:
            apc_ci = "--"
            
        p_val = row['p_value']
        if pd.isna(p_val):
            p_str = "--"
        elif p_val < 0.001:
            p_str = "< 0.001"
        else:
            p_str = f"{p_val:.5f}"
            
        note = row['note'] if not pd.isna(row['note']) else ""
        
        # トレンド分類の自動決定
        if kcode in ["K265", "K266"]:
            trend_class = "分析対象外"
        elif kcode == "K225-4":
            trend_class = "対象外"
        else:
            p_val_num = float(p_val) if not pd.isna(p_val) else 1.0
            apc_num = float(row['apc_percent']) if not pd.isna(row['apc_percent']) else 0.0
            if p_val_num < 0.05:
                if apc_num > 0:
                    trend_class = "有意増加"
                else:
                    trend_class = "有意減少"
            else:
                trend_class = "横ばい"
        
        desc = f"{trend_class}。 {note}" if note else trend_class
        
        row_cells = table1.add_row().cells
        data_row = [kcode, name, n_years, apc_ci, p_str, desc]
        for i, val in enumerate(data_row):
            row_cells[i].text = val
            p = row_cells[i].paragraphs[0]
            # Kコードと数値系は右寄せまたは中央寄せ
            if i in [0, 2, 4]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif i == 3:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_font(p.runs[0], size_pt=9)

    add_paragraph_styled(doc, "") # スペース空け
    
    p10 = add_paragraph_styled(doc)
    p10.add_run("主要な術式における算定回数および人口10万対算定率の期首・期末の比較を表2に示す。眼瞼結膜悪性腫瘍手術（K216）は2014年度の397件（10万対0.31）から2023年度の543件（10万対0.44）へと有意に増加した。また、眼窩内腫瘍摘出術（表在性）（K234）は1,338件（10万対1.05）から2,423件（10万対1.95）へとほぼ倍増する極めて顕著な増加（APC = +7.13%, p < 0.001）を示した。")
    
    p11 = add_paragraph_styled(doc)
    p11.add_run("一方、眼球摘出術（K241）は200件（10万対0.16）から149件（10万対0.12）へと有意に減少した（APC = -3.08%, p = 0.00016）。また、結膜腫瘍冷凍凝固術（K225）は、2014年度の317件から2021年度には604件（10万対0.48）へと有意に増加（APC = +10.58%, p < 0.001）していたが、2022年度の「角結膜悪性腫瘍切除術（K225-4）」新設を経て、2023年度には123件へと急減（対2022年比73%減）する構造的断絶が確認された。")

    # 表2の作成
    add_paragraph_styled(doc, "表2: 主要術式の算定数と人口10万対算定率の推移（2014年度 vs 2023年度）", align=WD_ALIGN_PARAGRAPH.LEFT)
    
    table2 = doc.add_table(rows=1, cols=6)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table2)
    
    headers2 = ["Kコード", "術式名", "2014年度 算定数 (10万対率)", "2023年度 算定数 (10万対率)", "変化率 (%)", "備考"]
    hdr_cells2 = table2.rows[0].cells
    for i, title in enumerate(headers2):
        hdr_cells2[i].text = title
        set_cell_border_bottom(hdr_cells2[i], sz="12")
        p = hdr_cells2[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.runs[0], font_name_ascii="Arial", font_name_east_asia="MS ゴシック", size_pt=9.5, bold=True)

    # 主要術式データの抽出
    # 2014年と2023年の比較
    rates_csv = os.path.join(BASE_DIR, "rate_per_100k_national_trend.csv")
    df_rates = pd.read_csv(rates_csv)
    
    target_k = ["K215-2", "K216", "K225", "K225-2", "K225-3", "K234", "K241"]
    
    for tk in target_k:
        df_tk = df_rates[df_rates['k_code_group'] == tk]
        val_2014 = df_tk[df_tk['year'] == 2014].iloc[0]
        val_2023 = df_tk[df_tk['year'] == 2023].iloc[0]
        
        c_2014 = int(val_2014['count'])
        r_2014 = val_2014['count_per_100k']
        c_2023 = int(val_2023['count'])
        r_2023 = val_2023['count_per_100k']
        
        pct_change = ((c_2023 - c_2014) / c_2014) * 100
        
        t2_row = table2.add_row().cells
        t2_row[0].text = tk
        t2_row[1].text = code_names.get(tk, tk)
        t2_row[2].text = f"{c_2014:,} ({r_2014:.2f})"
        t2_row[3].text = f"{c_2023:,} ({r_2023:.2f})"
        t2_row[4].text = f"{pct_change:+.1f}%"
        
        if tk == "K225":
            val_2021 = df_tk[df_tk['year'] == 2021].iloc[0]
            c_2021 = int(val_2021['count'])
            r_2021 = val_2021['count_per_100k']
            t2_row[5].text = f"2021年: {c_2021} ({r_2021:.2f}) ※2022年以降はK225-4新設影響で急減"
        else:
            t2_row[5].text = ""
            
        for i in range(6):
            p = t2_row[i].paragraphs[0]
            if i in [0, 4]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            elif i in [2, 3]:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_font(p.runs[0], size_pt=9)

    add_paragraph_styled(doc, "") # スペース空け

    p12 = add_paragraph_styled(doc)
    p12.add_run("年齢層別の構成比（分布シェア）の経時的変化においては、術式ごとに顕著な特徴が見られた。眼瞼結膜悪性腫瘍手術（K216）では、全期間を通じて高齢者（65歳以上）の占める割合が88%〜100%（2021年度は100%）ときわめて高率であり、高齢者における眼瞼悪性腫瘍罹患の多さを裏付けた。一方で、結膜腫瘍冷凍凝固術（K225）では、算定回数の約63%〜80%（2023年度の異常値を除く2014〜2022年度）が一貫してAYA世代（15-39歳）に集中しているという特異な年齢偏向が観察された。また、眼球摘出術（K241）については、年齢階級別データセット内で復元できた範囲での参考値として、2023年度に復元された63件中41件（65.1%）が小児（0-14歳）によるものであった（ただしK241は後述の通り秘匿セルの影響により大幅な欠測を含んでおり、参考値としての提示に留まる）。")

    # 6. 考察 (Discussion)
    add_heading_styled(doc, "4. 考察（Discussion）", level=1)
    
    p13 = add_paragraph_styled(doc)
    p13.add_run("本研究は、日本全国の保険請求レセプトをほぼ網羅するNDBオープンデータを用いて、日本国内における眼腫瘍関連手術の算定動向を初めてマクロな視点から体系的に明らかにしたものである。本解析から、主要術式の算定動向は臨床現場における治療手技の進歩や社会構造の変化（高齢化）、さらには診療報酬改定の構造的影響を色濃く反映していることが見出された。")
    
    p14 = add_paragraph_styled(doc)
    p14.add_run("まず、眼球摘出術（K241）が10年間で有意に減少（APC = -3.08%, p < 0.001）している点は、臨床における眼球温存療法の普及を強く示唆している。特に小児の眼腫瘍（網膜芽細胞腫など）や成人の眼内腫瘍（脈絡膜悪性黒色腫など）に対して、従来は眼球摘出術が標準治療であったが、近年は放射線療法（小線源治療や重粒子線治療）、化学療法（超選択的眼動脈注入療法など）といった集学的治療の発展により、眼球や視機能を温存する選択率が高まっている。例えば、Abramsonらは、眼動脈注入化学療法（OAC）の導入により、進行性の片側性網膜芽細胞腫に対する一次眼球摘出率が95%以上から7.4%へと劇的に低下したことを単一施設の後方視的検討から実証している[2]。日本国内においても同様に、温存療法の普及が手術件数の減少というトレンドとしてマクロに現れていると解釈するのが合理的である。")
    
    p15 = add_paragraph_styled(doc)
    p15.add_run("次に、眼瞼結膜悪性腫瘍手術（K216）が有意な増加（APC = +3.80%, p < 0.001）を示したことは、日本の超高齢社会の進展と密接に関連している。眼瞼に発生する悪性腫瘍のうち、脂腺癌や基底細胞癌は高齢者に好発することが知られている。Satoらの日本国内における眼瞼悪性腫瘍の包括的なレビューによれば、本邦においては基底細胞癌に次いで脂腺癌の頻度が他国に比して高く、その多くが60歳以上の高齢者に発生する[3]。今回の年齢階級別解析において、K216の算定件数の88%〜100%が高齢者（65歳以上）で占められていた事実は、高齢人口の絶対的増加が悪性腫瘍手術件数の底上げにつながっている現状を明瞭に示している。")
    
    p16 = add_paragraph_styled(doc)
    p16.add_run("また、眼窩内腫瘍摘出術（表在性）（K234）が極めて著明な増加（APC = +7.13%, p < 0.001）を示した背景には、画像診断技術（高解像度MRIやCT）の普及・高度化による無症候性あるいは早期の眼窩腫瘍（涙腺腫瘍、海綿状血管腫など）の発見率向上があると考えられる。さらに、内視鏡手術手技や手術ナビゲーションシステムの臨床導入といった手術支援技術の向上により、以前は手術困難とされた深在性あるいは複雑な眼窩腫瘍に対しても安全にアプローチできるようになり、適応が拡大していることも算定件数の増加に寄与していると推察される。")
    
    p17 = add_paragraph_styled(doc)
    p17.add_run("方法論的および医療政策的な視点において最も興味深い知見は、結膜腫瘍冷凍凝固術（K225）に認められた急激な件数減少である。2014〜2021年度まで一貫して年約10.6%のペースで有意に増加していたK225は、2022年度の改定で「角結膜悪性腫瘍切除術（K225-4）」が新設されたのと同時期に、2023年度には対前年比-73%という極めて急激な減少を示した。これは、従来K225（冷凍凝固術）として算定されていた悪性腫瘍症例（扁平上皮癌やBowen病など）の切除手技が、より点数が高く術式記述の正確な新設コード「K225-4」へ移行した「症例再分類（coding migration）」の影響を強く受けている可能性が高い。この事象は、NDB等の診療行為コードをベースとした長期トレンド解析において、医療技術そのものの実態的変化と、制度設計の変更（新規コード収載）による影響を注意深く区別して解釈しなければならないという、本研究におけるきわめて重要な学術的・方法論的教訓を示している。")
    
    p18 = add_paragraph_styled(doc)
    p18.add_run("本研究の新規性として、従来の単一施設や特定の病理データベースをベースとした眼腫瘍の報告とは異なり、日本全国の網羅的レセプトデータを包含するNDBオープンデータを使用することで、日本全体における主要な眼腫瘍関連手術の診療実態をマクロな疫学データとして初めて可視化した点が挙げられる。この結果は、将来的な眼腫瘍診療体制の構築や、専門医師の配置、医療資源の効率的な分配を検討するための重要な基礎データを提供し得る。")
    
    p19 = add_paragraph_styled(doc)
    p19.add_run("本研究には以下の限界が存在する。第一に、NDBオープンデータの手術（性年齢別）集計における「10件未満の秘匿（マスク）処理」の存在である。このため、K265やK266のような非常に希少な術式の年齢層別詳細やトレンド解析は実行不可能であった。また、算定件数の多いコードであっても、マスク処理の累積によって年齢階級別の合算値が真の全国値よりも数%過小評価されるバイアスが不可避であるため、年齢階級別の絶対数の比較や、厳密な年齢調整率の算出が困難であった。第二に、NDBオープンデータの構造上、手術コード（Kコード）とレセプト上の主病名（傷病名コード）が個々の症例レベルで紐付いていないことである。このため、例えば眼瞼悪性腫瘍手術（K216）において、実際に切除された腫瘍の組織型（脂腺癌、基底細胞癌、扁平上皮癌など）ごとの詳細な内訳トレンドを評価することは不可能であった。今後、診断名と診療行為が紐付けられた個別受給者データ（NDBのオンサイト利用等）を用いた詳細な検証が期待される。")

    # 7. 結語 (Conclusion)
    add_heading_styled(doc, "5. 結語（Conclusion）", level=1)
    
    p20 = add_paragraph_styled(doc)
    p20.add_run("2014〜2023年度の10年間にわたるNDBオープンデータを用いた解析により、日本の眼腫瘍関連手術は、眼球温存療法の普及を反映した眼球摘出術の減少、高齢化に伴う眼瞼悪性腫瘍手術の増加、診断・手術支援技術の進歩を背景とした眼窩腫瘍手術の増加など、臨床現場の実態を色濃く映し出した多様な動向を示した。また、結膜腫瘍冷凍凝固術の推移が示すように、診療報酬点数表の改定（新規コード新設）に伴う症例再分類の影響を考慮する重要性が示された。これらのマクロデータは、今後のわが国における眼腫瘍診療体制の整備や医療政策の評価において、価値ある統計的エビデンスを提供するものである。")

    # 8. 参考文献 (References)
    add_heading_styled(doc, "参考文献", level=1)
    
    ref_list = [
        "Akada M, Ideyama M, Kido A, Miyata M, Ueda-Arakawa N, Tamura H, Ooto S, Miyake M, Tsujikawa A, Hata M. Age-Specific Increases in the Prevalence and Treatment Burden of Neovascular Age-Related Macular Degeneration in a Super-Aged Society. Invest Ophthalmol Vis Sci. 2026;67(4):19. doi: 10.1167/iovs.67.4.19.",
        "Abramson DH, Fabius AWM, Issa R, Francis JH, Marr BP, Dunkel IJ, Gobin YP. Advanced Unilateral Retinoblastoma: The Impact of Ophthalmic Artery Chemosurgery on Enucleation Rate and Patient Survival at MSKCC. PLoS ONE. 2015;10(12):e0145436. doi: 10.1371/journal.pone.0145436.",
        "Sato Y, Takahashi S, Toshiyasu T, Tsuji H, Hanai N, Homma A. Squamous cell carcinoma of the eyelid. Jpn J Clin Oncol. 2024;54(1):4-12. doi: 10.1093/jjco/hyad127."
    ]
    
    for i, ref in enumerate(ref_list, 1):
        p_ref = add_paragraph_styled(doc)
        p_ref.paragraph_format.left_indent = Inches(0.25)
        p_ref.paragraph_format.first_line_indent = Inches(-0.25)
        run_num = p_ref.add_run(f"[{i}] ")
        set_font(run_num, bold=True)
        run_text = p_ref.add_run(ref)
        set_font(run_text)

    # 保存
    doc.save(OUTPUT_PATH)
    print("Done generating docx")

if __name__ == "__main__":
    main()
