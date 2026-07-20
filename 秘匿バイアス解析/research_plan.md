# 研究計画: NDBオープンデータにおける小セル秘匿がトレンド・地域格差推定に与えるバイアスの定量化

**（既存の眼科診療トレンド解析とは独立した方法論研究）**

## 背景と新規性

NDBオープンデータは10件未満のセルを秘匿する（値は区間 [1, 9] にあることのみ既知＝区間打ち切り）。
既存のNDB研究のほぼ全てが 0補完・5補完・秘匿多数コードの除外というアドホック処理を採用しており、
その処理が APC（年平均変化率）や地域格差指標（Gini係数・CV）の推定に与えるバイアスは定量化されていない。

本研究の統計的貢献:

1. **秘匿実態の記述**: コード×年度×都道府県別の秘匿率の全数調査（除外された K281 を含む）
2. **部分識別（bounds analysis）**: 秘匿セルに 1 / 9 を代入した際の Gini・CV・APC の上下限
   （Manski 流の partial identification を医療オープンデータの格差指標に適用）
3. **人工秘匿実験**: 秘匿のない大件数コード（K282）を binomial thinning で縮小し人工的に
   10未満秘匿を施し、真値既知の下で各補完法の推定誤差を実測
4. **打ち切り尤度による推定**: 秘匿セルの尤度を P(1≤Y≤9) とする区間打ち切り
   ポアソン/負の二項モデルで K281 を「除外せずに」推定

## 検証可能なステップ

- [x] Step 1: 秘匿セルの特定（zero/five補完出力の差分） → 検証: 秘匿フラグ付き統合CSVが生成される
- [x] Step 2: 秘匿率センサス → 検証: code×year別秘匿率テーブル・K281の秘匿率が出力される
- [x] Step 3: bounds analysis → 検証: 各code×yearのGini/CVの[下限,上限]と幅が出力される
- [x] Step 4: 人工秘匿実験 → 検証: thinning率×補完法別のAPC/Giniバイアス表が出力される
- [x] Step 5: 打ち切り尤度MLE（K281等に適用、Poisson/NB） → 検証: `censored_mle_apc.csv`
- [x] Step 6: 人工秘匿実験にMLEを追加し優越性を検証 → 検証: `experiment_mle_summary.csv`
- [x] 追加知見: "-" は常に区間[1,9]ではない（全県秘匿＝項目レベル非公表）。
      構造的欠測の除外ルールを `scripts/structural.py` として共通化。
- [x] Step 7: 論文用図表（秘匿率ヒートマップ・Gini識別区間・手法別RMSE） → `s07_figures.py`
- [x] Step 8: 原稿ドラフト → `manuscript_draft.md`（IMRAD、限界の明示、再現性セクション付き）
- [x] 補強: βのSEを完全な観測情報行列（数値ヘッセ逆行列）から算出に変更、
      人工秘匿実験にNB版MLEを追加、秘匿率×人口の相関を検証（ρ=−0.855, p<10⁻¹³）
- [x] Step 9: シャープ識別区間 → `s08_sharp_bounds.py`（APCは年別最適代入による厳密解、
      Giniは座標降下）。端点代入区間が識別幅を最大2桁過小評価し、符号識別が失われる
      コードが4つ存在することを発見（`sharp_bounds_apc.csv`）
- [x] Step 10: 多重代入によるGini不確実性伝播 → `s09_bayes_mi.py`（MLE漸近分布×切断NB
      サンプリング、M=500、`bayes_mi_gini.csv`）

## ディレクトリ

```
秘匿バイアス解析/
├── research_plan.md          # 本ファイル
├── manuscript_draft.md       # 論文ドラフト（IMRAD）
├── RESULTS.md                # 実行結果サマリー
├── run_censoring_pipeline.py # 一括実行
├── scripts/
│   ├── s01_extract_censored.py   # 秘匿フラグ付きデータ抽出（K281含む、層情報付き）
│   ├── s02_censoring_census.py   # 秘匿率の記述統計
│   ├── s03_bounds_analysis.py    # Gini/CV/APC の端点代入区間
│   ├── s04_artificial_censoring.py # 人工秘匿実験（単一代入3法、200反復）
│   ├── s05_censored_mle.py       # 区間打ち切りPoisson/NB回帰（実データ適用）
│   ├── s06_experiment_mle.py     # 人工秘匿実験へのMLE追加比較（50反復）
│   ├── s07_figures.py            # 論文用図表
│   └── structural.py             # 構造的欠測の除外ルール（共通）
└── processed/                # 出力（plots/ に図）
```

## 実行

```bash
cd 秘匿バイアス解析
python run_censoring_pipeline.py
```
