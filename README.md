# NDBオープンデータを用いた日本の眼科診療トレンド解析
**Trend Analysis of Ophthalmic Care in Japan Using NDB Open Data**

本プロジェクトは、厚生労働省が公開する大規模レセプト統計「NDBオープンデータ（第1回〜第11回：2014年度〜2024年度）」を利用し、主要な眼科診療行為（白内障手術、硝子体手術、緑内障手術、角膜移植術）および非公開の「抗VEGF薬注射」の時系列トレンド、地域格差、およびその要因を明らかにするための統合解析パイプラインです。

---

## 1. 分析対象の診療行為

本パイプラインは以下の5つの診療行為コードを抽出し、解析します。

1. **J039-2: 抗VEGF薬注射（薬剤数量代替による補完分析）**
   * NDBの処置データでは非公表であるため、「注射薬（個別品目）」から主要な眼科用抗VEGF薬（アイリーア、ルセンティス、バビースモ等）の電算処理用医薬品コード（Yコード）を検索し、都道府県別数量を合算して代替指標として統合しています。
   * ※本値は投与回数そのものではなく薬剤数量に基づく代替推計値です。
2. **K282: 水晶体再建術（白内障手術）**
   * 主解析として眼内レンズを挿入する場合（その他のもの：K282_ro）。追加解析として「縫着レンズを挿入するもの（K282_i）」との合算（K282_total）。白内障手術の圧倒的多数はK282_roに該当し、合算値との差はごくわずかです。
3. **K280: 硝子体茎顕微鏡下離断術（硝子体手術）**
   * メイン解析として「網膜付着組織を含むもの（K280_1）」と「その他のもの（K280_2）」の合算で計算。サブ解析でこれら二つの内訳を区別した比較・パネルOLSを実行。
4. **K268: 緑内障手術（合算）**
   * 観血的緑内障手術に関連する主要な全8種の電算処理コードを合算して解析。サブグループとして「濾過手術」「流出路再建術」「デバイス挿入術」「白内障併用ドレーン（iStent等）」の4つの分類を作成し、内訳の推移を可視化（iStent等の低侵襲手術(MIGS)の爆発的普及を反映）。
5. **K259: 角膜移植術**
   * 電算処理コード 150086210（角膜移植術のみ）を対象。ドナー供給制約や特定高度医療施設への集中の影響を強く受ける高度専門医療のプロキシとして解析。K259-2（自家培養口腔粘膜等）は除外。

> **除外コード: K281（増殖性硝子体網膜症手術）**
> NDBオープンデータの秘匿閾値（10件未満非公開）により大半の都道府県・年度で値が秘匿されており、安定した統計解析が困難なため解析対象から除外しました。

---

## 2. ディレクトリ構成

```text
NDB_眼科診療トレンド解析_研究計画書/
├── run_pipeline.py         # パイプラインの一括実行スクリプト
├── build_real_covariates.py # 公的統計（e-Stat）からの共変量データの構築スクリプト
├── generate_summary_report.py # 解析結果をテキスト形式のサマリーにまとめるスクリプト
├── generate_mock_data.py   # テスト用ダミーデータおよび共変量データの生成
├── generate_manuscript_docx.py # 論文ドラフト（Word形式）を解析結果CSVから自動的に生成・更新するスクリプト
├── requirements.txt        # 依存ライブラリ一覧
├── README.md               # 本ドキュメント
├── revision_summary.md     # 改定内容および結果CSV利用ガイド
├── configs/
│   └── ndb_mapping.json    # 各年度ごとのExcelファイルの列名・シートマッピング定義
├── data/
│   ├── raw/                # 各回NDBの生データExcel (ndb_shujutsu_*.xlsx, ndb_chusha_*.xlsx等)
│   ├── covariates/         # 共変量データ (prefecture_covariates.csv: 実データ / _DUMMY.csv: テスト用)
│   ├── real_covariates/    # 公的統計の生ファイル (e-Statからダウンロードした元データ)
│   └── processed/          # 前処理および統計解析結果の出力先
│       ├── plots/          # 生成された可視化グラフ画像 (.png)
│       └── *.csv / *.txt   # 解析統計値 (APC, ジニ係数, パネル回帰レポート等)
├── allergy解析/            # サブ解析: 抗アレルギー点眼薬のトレンド・地域格差解析
│   ├── run_allergy_pipeline.py
│   ├── src/               # 前処理・解析・可視化モジュール
│   └── processed/         # 解析結果出力
├── 眼腫瘍解析/             # サブ解析: 眼腫瘍手術の年齢階級別・Poisson回帰解析
│   └── scripts/           # 年齢層別化・rate換算・trend testスクリプト
└── src/
    ├── preprocess.py       # データの前処理・クレンジング・マージ (縦持ち変換、秘匿値補完)
    ├── analysis.py         # 統計解析 (APC計算、ジニ係数/CV算出、相関分析、固定効果パネル回帰)
    └── visualization.py    # グラフ描画 (経年トレンド、格差指標推移、相関散布図、ランキング)
```

---

## 3. セットアップと実行手順

### 3.1 依存ライブラリのインストール
```bash
pip install -r requirements.txt
```

### 3.2 共変量データの準備
デフォルトでは公的統計から取得した実データ（`data/covariates/prefecture_covariates.csv`）を使用します。
実データのダウンロードおよび再構築を行う場合は、以下を実行してください:
```bash
python build_real_covariates.py
```

### 3.3 解析パイプラインの実行
生データから前処理・統計解析・グラフプロットまでを一括実行します。10件未満の秘匿データ（`-`等）に対する補完方法を `--imputation` オプションで指定できます。
```bash
# 0補完（デフォルト、最も安定的）
python run_pipeline.py --imputation zero

# 5補完
python run_pipeline.py --imputation five

# 1-9の一様乱数補完
python run_pipeline.py --imputation random
```

### 3.4 論文原稿（docx）の生成・更新
最新の解析結果CSVを自動的に読み込んで、Word形式の論文ドラフトを作成します。
```bash
python generate_manuscript_docx.py
```

---

## 4. 出力ファイル一覧と内容

### 4.1 解析結果CSV（`data/processed/` ディレクトリ）

| ファイル名 | 内容 | 主な列 | 対応する図 |
|---|---|---|---|
| `ndb_processed_zero.csv` | **全データの統合テーブル**。グラフや分析の元データ | year, prefecture, code, count, count_per_100k, aging_rate, docs_per_100k, … | （全図の基礎データ） |
| `national_trends.csv` | **全国集計の経年トレンド**。各年・各手術コードの全国件数と人口10万対件数 | year, code, count, count_per_100k, count_per_100k_65plus | Figure 1（トレンド折れ線） |
| `national_apc_linear.csv` | **APC（年平均変化率）**。対数線形回帰で算出したAPC・95%CI・p値・R² | code, apc, apc_low, apc_high, p_value, r2 | Table 2 (線形APC部分) |
| `national_apc_joinpoint.csv` | **Joinpoint分析結果**。変化点で区切った各セグメントのAPC | code, segment, start_year, end_year, apc | Figure 2（変化点折れ線）、Table 2 |
| `geographic_disparity.csv` | **地域格差指標の推移**。年度×手術コード別のGini係数・CV・最大最小比 | year, code, cv, gini, max_to_min_ratio, min_prefecture, max_prefecture | Figure 3（格差推移折れ線） |
| `covariates_correlation.csv` | **Spearman相関係数**。年度×コード別の施行率と共変量の相関ρ・p値 | year, code, spearman_rho_aging, p_value_aging, spearman_rho_docs, … | Figure 5（散布図・相関） |
| `panel_regression_summary.csv` | **パネル回帰の係数一覧**。コード×変数別の回帰係数・t値・p値・R²(within) | code, variable, coefficient, std_err, t_stat, p_value, r2_within | Table 5 |
| `panel_regression_*_report.txt` | **パネル回帰の詳細レポート**（テキスト形式、各コード別） | — | 論文補足資料 |
| `analysis_summary_report.txt` | **全解析結果のまとめ**（テキスト形式、人間が読む用） | — | 結果の確認・報告用 |
| `panel_regression_summary_sensitivity_survey_years.csv` | **感度分析**。共変量が実測値の調査年のみ（偶数年）で推定したパネル回帰 | 主解析と同一構造 | Table S1（補足） |

### 4.2 サブ解析ディレクトリ
- **`data/processed/sub_analysis/`**: K280・K268・K282の内訳別（サブグループ別）パネル回帰と感度分析の結果
- **`allergy解析/processed/`**: 抗アレルギー点眼薬の全解析結果（詳細は [allergy解析/README.md](allergy解析/README.md) 参照）
- **`眼腫瘍解析/`**: 眼腫瘍手術の年齢階級別・Poisson回帰解析（詳細は [眼腫瘍解析/scripts/README.md](眼腫瘍解析/scripts/README.md) 参照）

---

## 5. 共変量データの出典と構築手法

背景データ（人口、医師数、施設数）は、以下の公的統計から取得した実データです（[build_real_covariates.py](file:///f:/マイドライブ/NDB_眼科診療トレンド解析_研究計画書/build_real_covariates.py) で自動取得・加工）。
- **人口・高齢者人口**: 総務省統計局「人口推計」「国勢調査」（2015年・2020年は国勢調査実数値を使用。2024年は令和6年10月1日現在の年齢3区分統計（`statInfId=000040268919`）をe-Statより自動ダウンロードして統合。中間年は線形補間）
- **眼科医師数**: 厚生労働省「医師・歯科医師・薬剤師統計」（隔年調査；2024年は令和6年調査の主たる診療科別医師数（`statInfId=000040383787`）をe-Statより自動ダウンロードして統合。奇数年は隣接調査年の値から線形補間）
- **眼科標榜施設数**: 厚生労働省「医療施設調査 静態調査」（3年周期；2024年は静態調査の年ではないため、2023年調査の実数値から前方補完（f-fill）によって2024年の値を補完。中間年は線形補間）

---

## 6. 第11回NDB生データの取り扱い

第11回NDBオープンデータ（2024年度分）からは、従来の個別Excelファイルへの直接リンクが廃止され、大カテゴリ別のZIPファイルに統合されて提供されるようになりました。これに伴い、本プロジェクトでは以下の通りデータを取り扱っています。

### データソース
* **使用ファイル**: [001712211.zip](https://www.mhlw.go.jp/content/12400000/001712211.zip)（医科診療行為 算定回数・公費レセプト含む）
  * ※過去の時系列データとの整合性維持のため、第10回と同様に「公費レセプトを含む」データセットを使用しています。

### 抽出とリネームマッピング
ZIP解凍後、以下の通りファイルを抽出・リネームして [data/raw/](file:///f:/マイドライブ/NDB_眼科診療トレンド解析_研究計画書/data/raw) 配下に配置しています。

| ZIP内の元ファイルパス | 抽出・リネーム後の配置先パス | 用途 |
| :--- | :--- | :--- |
| `01_医科診療行為/G_注射/都道府県別算定回数(公費含む).xlsx` | `data/raw/ndb_chusha_2024.xlsx` | 抗VEGF薬注射（薬剤数量） |
| `01_医科診療行為/J_処置/都道府県別算定回数(公費含む).xlsx` | `data/raw/ndb_shochi_2024.xlsx` | 処置（K280-2等） |
| `01_医科診療行為/K_手術/款別都道府県別算定回数(公費含む).xlsx` | `data/raw/ndb_shujutsu_2024.xlsx` | 手術（白内障・緑内障等） |
| `01_医科診療行為/F_投薬/都道府県別算定回数(公費含む).xlsx` | `data/raw/ndb_gaiyo_2024.xlsx` | 外用薬（点眼薬） |
| `01_医科診療行為/K_手術/款別性年齢別算定回数(公費含む).xlsx` | `data/raw/ndb_age_sex/ndb_shujutsu_agesex_2024.xlsx` | 手術の年齢階級別（追加解析） |
| `01_医科診療行為/A_基本診療料/短期滞在手術等基本料_都道府県別算定回数(公費含む).xlsx` | `data/raw/a400/a400_pref_2024.xlsx` | 短期滞在手術等基本料（白内障） |
