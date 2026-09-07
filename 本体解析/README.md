# 本体解析: 主要眼科手術・処置のトレンドと地域格差

NDBオープンデータ（第1回〜第11回: 2014〜2024年度）から、主要な眼科診療行為の
時系列トレンド・地域格差・その要因を解析するパイプライン。

## 1. 分析対象の診療行為

1. **J039-2: 抗VEGF薬注射（薬剤数量代替による補完分析）**
   * NDBの処置データでは非公表であるため、「注射薬（個別品目）」から主要な眼科用抗VEGF薬（アイリーア、ルセンティス、バビースモ等）の電算処理用医薬品コード（Yコード）を検索し、都道府県別数量を合算して代替指標として統合している。
   * ※本値は投与回数そのものではなく薬剤数量に基づく代替推計値。
2. **K282: 水晶体再建術（白内障手術）**
   * 主解析として眼内レンズを挿入する場合（その他のもの: K282_ro）。追加解析として「縫着レンズを挿入するもの（K282_i）」との合算（K282_total）。
3. **K280: 硝子体茎顕微鏡下離断術（硝子体手術）**
   * 「網膜付着組織を含むもの（K280_1）」と「その他のもの（K280_2）」の合算。サブ解析で内訳を区別した比較・パネルOLSを実行。
4. **K268: 緑内障手術（合算）**
   * 観血的緑内障手術に関連する全8種の電算処理コードを合算。サブグループとして「濾過手術」「流出路再建術」「デバイス挿入術」「白内障併用ドレーン（iStent等）」の4分類を作成し内訳の推移を可視化。
5. **K259: 角膜移植術**
   * 電算処理コード 150086210 のみ。K259-2（自家培養口腔粘膜等）は除外。

> **除外コード: K281（増殖性硝子体網膜症手術）**
> 秘匿閾値（10件未満非公開）により大半の都道府県・年度で秘匿されているため除外。

## 2. フォルダ構成

```text
本体解析/
├── run_pipeline.py             # 前処理・統計解析・作図の一括実行
├── build_real_covariates.py    # e-Stat から共変量を構築
├── generate_summary_report.py  # 解析結果のテキストサマリー
├── generate_manuscript_docx.py # 論文ドラフト（Word）を結果CSVから生成
├── export_excel_figures.py     # Excelグラフ用データの出力
├── organize_outputs.py         # data/processed/ 直下の出力を振り分ける
├── src/
│   ├── paths.py                # 出力フォルダ構成の一元管理・find()
│   ├── preprocess.py           # 前処理・クレンジング・マージ・秘匿値補完
│   ├── analysis.py             # APC、ジニ係数/CV、相関、固定効果パネル回帰
│   └── visualization.py        # 作図
└── 05_論文成果物/               # 論文原稿（JP/EN docx）・骨子・研究計画書
```

**出力先は `data/processed/`（リポジトリ直下）であり、本フォルダの中ではない。**
`.gitignore` が `data/` を「NDB・患者データの流出防止」目的で丸ごと除外しているため、
解析結果を `data/` の外へ出すとこの保護が外れる。他テーマと構成が違うのはこの理由による。

```text
data/processed/
  01_中間データ/    前処理済みの統合データ（ndb_processed_*.csv 等）
  02_解析結果/      全国トレンド / 都道府県_地域格差 / 論文図表データ
  03_図表/plots/    図（png）・Excel
  sub_analysis/     K280・K268・K282 のサブ解析（親と同名のCSVがあるので分離を維持）
```

## 3. 実行手順

**すべてリポジトリ直下から実行する。** `run_pipeline.py` と `build_real_covariates.py` は
`data/raw` などをカレントディレクトリ相対で参照する。

```bash
python 本体解析/run_pipeline.py --imputation zero    # 0補完（既定）
python 本体解析/run_pipeline.py --imputation five    # 5補完
python 本体解析/run_pipeline.py --imputation random  # 1〜9の一様乱数補完
```

```bash
python 本体解析/generate_summary_report.py
python 本体解析/export_excel_figures.py
python 本体解析/generate_manuscript_docx.py
python 本体解析/organize_outputs.py
```

`organize_outputs.py` は**下流スクリプトまで走らせた後に最後に1回**実行する。
`generate_summary_report.py` と `export_excel_figures.py` も `data/processed/` 直下へ出力するため、
パイプライン直後に整理すると、その後の7ファイル（`analysis_summary_report.txt` と `fig1〜fig6_*.csv`）が
直下に取り残される。何度実行しても同じ結果になる。ファイルは削除しない。
読み込み側は `src/paths.py` の `find()` を使うので、整理前でも整理後でも動く。

共変量の再構築（e-Stat からダウンロード）:

```bash
python 本体解析/build_real_covariates.py
```

> **⚠️ 年齢・性別別パーサーが現存しない**
> `src/preprocess_age_sex.py`（年齢・性別別データのパーサー）はリポジトリ内に存在しない。
> 生成済みCSV（`data/processed/ndb_age_sex_zero.csv`）は残っており下流解析は動作するが、
> 生データからの再生成にはパーサーの再実装が必要。

## 4. 出力ファイル一覧（`data/processed/`）

| ファイル名 | 内容 | 主な列 | 対応する図 |
|---|---|---|---|
| `ndb_processed_zero.csv` | **全データの統合テーブル** | year, prefecture, code, count, count_per_100k, aging_rate, docs_per_100k, … | （全図の基礎データ） |
| `national_trends.csv` | **全国集計の経年トレンド** | year, code, count, count_per_100k, count_per_100k_65plus | Figure 1 |
| `national_apc_linear.csv` | **APC（年平均変化率）** 対数線形回帰 | code, apc, apc_low, apc_high, p_value, r2 | Table 2 |
| `national_apc_joinpoint.csv` | **Joinpoint分析結果** | code, segment, start_year, end_year, apc | Figure 2, Table 2 |
| `geographic_disparity.csv` | **地域格差指標の推移** Gini・CV・最大最小比 | year, code, cv, gini, max_to_min_ratio, min_prefecture, max_prefecture | Figure 3 |
| `covariates_correlation.csv` | **Spearman相関係数** | year, code, spearman_rho_aging, p_value_aging, spearman_rho_docs, … | Figure 5 |
| `panel_regression_summary.csv` | **パネル回帰の係数一覧** | code, variable, coefficient, std_err, t_stat, p_value, r2_within | Table 5 |
| `panel_regression_*_report.txt` | パネル回帰の詳細レポート（コード別） | — | 補足資料 |
| `analysis_summary_report.txt` | 全解析結果のまとめ（人間が読む用） | — | 確認・報告用 |
| `panel_regression_summary_sensitivity_survey_years.csv` | **感度分析** 共変量が実測値の調査年のみ | 主解析と同一構造 | Table S1 |
| `sub_analysis/` | K280・K268・K282 の内訳別パネル回帰と感度分析 | — | — |

### 年齢・性別別解析（追加解析）

NDB年齢別ファイル（`data/raw/ndb_age_sex/`）を用いた追加解析。

| ファイル | 内容 | 主な列 |
|---|---|---|
| `data/processed/ndb_age_sex_zero.csv` | 眼科手術（K282・K268・K280等）および抗VEGF薬の年齢・性別別件数（2014〜2024年） | year, code, procedure_name, sex, age_group, count |

抗アレルギー点眼薬の年齢別分布は `抗アレルギー点眼解析/` を参照。

## 5. 公費レセプトの取り扱い（本体解析への影響）

2024年度（第11回）のみ公費レセプトを含む集計を用いているため、J039-2 / K259 / K268 / K280 / K282 の
2024年度の算定回数は約 +3.4% 上振れている。詳細と Limitations 記載文はルートの README を参照。
`data/raw/ndb_2024_nokouhi/ndb_chusha_2024_nokouhi.xlsx` があるので J039-2 は「含まない」版へ切り替え可能。
手術系の「含まない」版は未入手。
