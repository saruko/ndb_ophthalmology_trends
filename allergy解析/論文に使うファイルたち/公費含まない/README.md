# 抗アレルギー点眼薬解析（公費レセプトを含まないデータ版）

親フォルダ（`論文に使うファイルたち/`）と同じ26本のCSVを、
**すべての年度で「公費レセプトを含まない」集計表**を用いて再実行したものです。
ファイル名・列構成は親フォルダと同一なので、そのまま差し替えて比較できます。

## 経緯

NDBオープンデータ第11回解説編 p.5:

> 第11回NDBオープンデータでは、…第10回以前との年次推移を観察しやすくするため、
> 第10回までと同様の公費レセプトを含まない集計表も公表した

**第1回〜第10回（2014〜2023年度）はすべて「公費レセプトを含まない」集計のみ**が公表されています。
親フォルダの結果は2024年度のみ「公費レセプトを含む」版を使っており、時系列に定義の不連続があります。
**経年トレンド解析にはこちらを使用してください。**

「公費レセプト」＝社会保険・国民健康保険による請求がなく、公費負担医療のみによる請求のレセプト
（同 p.52 用語の解説）。すなわち公費単独レセプトを指します。

## 差し替えたデータ

2024年度分のみ差し替え、2014〜2023年度は従来と同一ファイルです。

| 用途 | 使用ファイル |
|---|---|
| 外用薬（都道府県別） | `data/raw/ndb_2024_nokouhi/ndb_gaiyo_2024_nokouhi.xlsx` |
| 外用薬（年齢性別） | `data/raw/ndb_2024_nokouhi/ndb_gaiyo_agesex_2024_nokouhi.xlsx` |
| 注射薬（都道府県別） | `data/raw/ndb_2024_nokouhi/ndb_chusha_2024_nokouhi.xlsx` |
| 注射薬（年齢性別） | `data/raw/ndb_2024_nokouhi/ndb_chusha_agesex_2024_nokouhi.xlsx` |

出典: 第11回NDBオープンデータ「処方薬 公費レセプトを含まないデータ」`001711930.zip`

## 実行したスクリプト

親フォルダの結果を生成しているのと同じスクリプト群を、
2024年度だけ差し替えた生データに対して同じ順序で実行しました。

1. `run_allergy_pipeline.py --imputation zero`
2. `build_national_totals.py`
3. `build_brand_generic_formulation.py`
4. `build_allergy_age_sex.py` ← **新規作成**（後述）
5. `src/analysis_age_sex_rates.py`
6. `generate_paper_csvs.py`
7. `add_rounded_columns.py`

### build_allergy_age_sex.py について

中間ファイル `ndb_allergy_age_sex_zero.csv`（年齢性別集計）は、
リポジトリ内に生成スクリプトが残っていなかったため新規に作成しました。
`src/preprocess_allergy.py` の薬剤定義・秘匿補完ロジックをそのまま再利用しています。

**検証**: 元データ（公費含む2024年度）で実行したところ、
既存の `ndb_allergy_age_sex_zero.csv` を **5,094行すべて完全に再現**しました。
したがってこのスクリプトによる再構築は元の生成過程と等価です。

## 親フォルダとの差

**2014〜2023年度は全ファイル・全指標で差0**（完全一致）であり、
差は2024年度のみに限定されることを検証済みです。

| 指標 | 公費含む（親フォルダ） | 公費含まない（本フォルダ） | 差 |
|---|---:|---:|---:|
| 抗アレルギー点眼薬 総処方量 2024 | 214,173,368 | **208,090,121** | −2.84% |

主要な集計表の2024年度の差はおおむね2〜5%です。
シェアや順位など構成比の指標は影響が小さい一方、
処方量の少ない薬剤・県では相対差が大きくなる場合があります。

## 秘匿値の扱い

親フォルダと同一（zero補完）。外用薬（処方薬）の秘匿閾値は数量1,000未満です。
解説編 p.24 のとおり、秘匿（ハイフン）の位置は「含む」版と「含まない」版で相互に反映されており同一です。

## 収録ファイル（26本）

親フォルダと同名・同構成:
`fig1a_age_profile_2024` / `fig1b_age_sex_profile_2024` / `fig2_age_distribution_shift` /
`fig2_weighted_mean_age` / `fig3_prefecture_ranking` / `fig3_prefecture_by_drug` /
`fig3_prefecture_ranking_top3` / `fig4_national_trends` / `fig4_market_shares` /
`table1_drug_summary_2024` / `table2_mf_ratio_2024` / `table3_prefecture_ranking_top3` /
`supplementary_apc_results` / `supplementary_apc_joinpoint` /
`supplementary_geographic_disparity` / `supplementary_panel_regression` /
`age_sex_rates_allergy` / `mf_ratio_by_age_allergy` / `ndb_allergy_age_sex_zero` /
`national_trends_allergy` / `national_shares_allergy` /
`prefecture_per_capita_ranking_allergy` / `prefecture_per_capita_by_drug_allergy` /
`brand_generic_share` / `epinastine_lx_vs_standard` / `epinastine_lx_formulation_detail`
