# 免疫抑制点眼薬（シクロスポリン／タクロリムス）サブ解析

**Prescription profile of immunosuppressive eye drops using NDB Open Data (2014–2024)**

抗アレルギー点眼薬解析のサブ解析。重症アレルギー性結膜疾患に用いる免疫抑制点眼薬
（パピロックミニ®＝シクロスポリン、タリムス®＝タクロリムス）の処方プロファイル・
地域格差・年齢性別分布を扱う。**次回の論文で使用する。**

---

## 1. データと定義

- **全年度で公費レセプトを含まないデータ**を使用する（2024年度は
  `data/raw/ndb_2024_nokouhi/` のファイルに自動で差し替わる）。
  本体の主解析と定義が揃っている。
- 秘匿セルは主解析でゼロ補完、感度分析で999補完（識別区間の上限）。
  外用薬の秘匿閾値は処方数量1,000未満。
- 人口分母は本体の `../02_中間データ/population_age_sex.csv` を参照するため、
  **本体パイプラインを先に実行しておく必要がある**。

収録期間の制約: タクロリムスは2022年度以降のみ収録（3年分）。
シクロスポリンは2015年度以降。詳細は [../README.md](../README.md) §2.2 を参照。

---

## 2. フォルダ構成

解析スクリプトはフォルダ直下へ出力し、`organize_outputs.py` で下記へ振り分ける
（何度実行しても同じ結果になる。ファイルは削除しない）。

```text
シクロスポリンとタクロリムス/
├── 01_抽出データ/   prefecture_immuno.csv
├── 03_解析結果/
│   ├── 全国トレンド/       national_trends_immuno.csv / apc_immuno.csv
│   ├── 都道府県_地域格差/  prefecture_per_capita_pivot_immuno.csv /
│   │                       prefecture_ranking_2024_immuno.csv /
│   │                       geographic_disparity_immuno.csv /
│   │                       covariate_correlation_immuno.csv /
│   │                       panel_regression_summary_immuno.csv /
│   │                       panel_regression_{CYCLOSPORINE,TACROLIMUS,IMMUNO_ML}_report.txt
│   ├── 年齢性別/           age_distribution_immuno.csv / age_sex_rates_immuno.csv /
│   │                       mf_ratio_by_age_immuno.csv / weighted_mean_age_immuno.csv
│   └── 品質管理_感度分析/  censoring_sensitivity_immuno.csv /
│                           censoring_sensitivity_disparity_immuno.csv
├── 04_図表/         immunosuppressant_figures_tables.xlsx（＋backup） /
│                    免疫抑制点眼薬_処方プロファイル_論文原稿.docx
├── immunosuppressant_paper_draft.md      論文ドラフト
├── immunosuppressant_subanalysis.md      サブ解析の設計メモ
└── 使用データファイル一覧.md              使用データの一覧
```

---

## 3. 実行方法

```bash
python allergy解析/シクロスポリンとタクロリムス/build_immunosuppressant_analysis.py
```

```bash
python allergy解析/シクロスポリンとタクロリムス/organize_outputs.py
```

```bash
python allergy解析/シクロスポリンとタクロリムス/build_xlsx.py
```

`build_xlsx.py` は整理前（フォルダ直下）・整理後（`03_解析結果/…`）のどちらでも
CSVを見つけられる（`_find()` で再帰探索する）。

---

## 4. 注意事項

- `immunosuppressant_figures_tables_backup_20260728.xlsx` は手作業編集前のバックアップ。
  `build_xlsx.py` を再実行すると `immunosuppressant_figures_tables.xlsx` は再生成されるので、
  手で加えた編集が必要な場合はバックアップから戻すこと。
- タクロリムスは観測3年のためAPC・地域格差は参考値として扱う。
- NDBオープンデータには処方科の情報がないが、免疫抑制点眼薬は事実上すべて眼科での処方である。
  ただし眼科医療資源との関連付けは生態学的（ecological）な関連にとどまり、因果は主張できない。
