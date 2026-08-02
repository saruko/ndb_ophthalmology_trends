# NDB 抗VEGF薬（硝子体注射液）トレンド・地域格差解析

**Sub-analysis of intravitreal anti-VEGF agents using NDB Open Data (2014–2024)**

NDBオープンデータ（第1回〜第11回：2014年度〜2024年度）の**注射（chusha）**ファイルから、
**薬効分類131「眼科用剤」**を抽出し、抗VEGF薬の処方トレンド・製品構成・剤形・
バイオシミラー浸透・年齢性別分布・地域格差を定量化するパイプライン。

---

## 1. データフロー

```
data/raw/ndb_chusha_YYYY.xlsx              ─┐
data/raw/ndb_age_sex/ndb_chusha_agesex_*.xlsx ┤─► extract_ophthalmic_drugs.py
data/raw/ndb_g_chusha_koui/*.xlsx          ─┘   extract_g016.py
                                             │
                                    01_抽出データ/*.csv
                                             │
     run_antivegf_pipeline.py / analyze_g016.py / analyze_cost.py
     build_kabata_tables.py
                                             │
                                    processed/（一時出力）
                                             │
                                    organize_outputs.py
                                             │
   01_抽出データ / 02_中間データ / 03_解析結果 / 04_図表 / 05_先行研究再現_Kabata
```

## フォルダ構成

解析スクリプトは一旦 `processed/` に出力し、`organize_outputs.py` で下記へ振り分ける
（何度実行しても同じ結果になる）。

| フォルダ | 内容 |
|---|---|
| `01_抽出データ/` | 生Excelから抽出したCSV（解析の入力） |
| `02_中間データ/` | 前処理済みデータ・パネルデータ（補完戦略別） |
| `03_解析結果/` | 解析アウトプット。テーマ別に7サブフォルダ（全国トレンド／製品_剤形_バイオシミラー／医療費／年齢性別／都道府県_地域格差／G016硝子体内注射／品質管理_感度分析） |
| `04_図表/` | 図（`plots/`）・Excel・Word |
| `05_先行研究再現_Kabata/` | Kabata et al. (2026) の図表再現用データ |
| `公費含まない/` | 全年度を「公費レセプトを含まない」で統一した解析（同一構成）。**経年トレンドの評価にはこちらを使用する** |

### 実行方法

```bash
python 抗VEFG薬/extract_ophthalmic_drugs.py     # 生Excel → CSV抽出（初回のみ）
```

```bash
python 抗VEFG薬/extract_g016.py                 # G016算定回数の抽出（初回のみ）
```

```bash
python 抗VEFG薬/run_antivegf_pipeline.py        # zero補完で主解析＋感度分析
```

```bash
python 抗VEFG薬/analyze_g016.py                 # G016の解析
```

```bash
python 抗VEFG薬/analyze_cost.py                 # 医療費の要因分解・治療総額・反実仮想
```

> **`analyze_cost.py` は2026年8月に再実装したもの**（元のスクリプトが失われ、出力CSVだけが
> 残っていたため）。既存出力から手法を逆算し、6本中5本を数値まで完全再現できることを確認した
> （要因分解・治療総額・反実仮想・価格乖離感度は相対差 1e-9 未満）。
> 残る1本 `cost_biosimilar_regional_potential.csv` は、**旧出力に内部矛盾があった**ため
> 一致しない（下記 §3-7 の注記を参照）。
> なお同種のスクリプト欠落が他に2件ある: `src/preprocess_age_sex.py`（ルート）、
> `眼腫瘍手術トレンド_2014_2024.csv` の抽出スクリプト。

```bash
python 抗VEFG薬/build_kabata_tables.py --kouhi  # 先行研究の図表再現
```

```bash
python 抗VEFG薬/organize_outputs.py             # 出力をフォルダ構成へ振り分け
```

公費レセプトを含まない版を扱う場合は、各コマンドに `--nokouhi` を付ける
（`build_kabata_tables.py` は `--kouhi` を外すと公費含まない版になる）。

---

## 2. 対象薬剤

薬効分類131に収載された13製品のうち、**抗VEGF薬10製品（7成分）**を主解析対象とする。

| 成分コード | 成分（製品） | 製品数 | 剤形 | 収載期間 |
|---|---|---|---|---|
| AFLIBERCEPT | アフリベルセプト2mg（アイリーア） | 2 | 注射液・キット | 2014– |
| AFLIBERCEPT_8MG | アフリベルセプト8mg（アイリーア8mg） | 1 | 注射液 | 2024– |
| RANIBIZUMAB_ORIG | ラニビズマブ先発（ルセンティス） | 3 | 注射液・キット | 2014– |
| RANIBIZUMAB_BS | ラニビズマブBS | 1 | キット | 2021– |
| FARICIMAB | ファリシマブ（バビースモ） | 1 | 注射液 | 2022– |
| BROLUCIZUMAB | ブロルシズマブ（ベオビュ） | 1 | キット | 2020– |
| PEGAPTANIB | ペガプタニブ（マクジェン） | 1 | キット | 2014–2018 |

**参考（抗VEGF薬ではないため主解析から除外）**
- マキュエイド（トリアムシノロン）: ステロイド硝子体内注射。`category=REFERENCE`
- ビスダイン（ベルテポルフィン）: PDT用で**静注（全身投与）**。`category=SYSTEMIC`

薬剤の分類定義は [`src/drug_master.py`](src/drug_master.py) に集約している。
NDBの「後発品区分」列は本分類では全品目`0`のため、**先発/バイオシミラーの別は製品名ベースで定義**した。

---

## 3. 解析内容と出力ファイル

### 3-1. 製品毎（要望①）
| ファイル | 内容 |
|---|---|
| `product_trends_antivegf.csv` | 年度×製品の数量・シェア・薬価・薬剤費・薬剤費シェア |
| `product_quantity_pivot_antivegf.csv` | 製品×年度の数量ピボット |
| `product_share_pivot_antivegf.csv` | 製品×年度のシェア（%）ピボット |
| `product_cost_pivot_antivegf.csv` | 製品×年度の薬剤費ピボット |
| `product_price_table_antivegf.csv` | **製品×年度の薬価一覧（円）** |
| `product_by_setting_antivegf.csv` | 製品×年度の外来（院内）／入院内訳 |

### 3-2. 注射液・キットの割合（要望②）
| ファイル | 内容 |
|---|---|
| `formulation_by_molecule_antivegf.csv` | 成分×年度×剤形の数量・成分内シェア（両剤形併存フラグ付き） |
| `formulation_total_antivegf.csv` | 抗VEGF薬全体の剤形比率 |
| `formulation_kit_share_by_prefecture.csv` | 最新年度の都道府県別キット比率 |

### 3-3. 先発 vs 後発（ルセンティス／ラニビズマブBS）（要望③）
| ファイル | 内容 |
|---|---|
| `biosimilar_national_share.csv` | 年度別の先発・BS数量とシェア |
| `biosimilar_share_by_prefecture.csv` | 都道府県×年度のBSシェア（%） |
| `biosimilar_cost_impact.csv` | BS数量を先発薬価で換算した場合との薬剤費差 |

### 3-4. 年齢・性別
| ファイル | 内容 |
|---|---|
| `agesex_distribution_published_antivegf.csv` | 年度×性×年齢階級（その年度の公開粒度）の数量・年度内構成比 |
| `agesex_distribution_comparable_antivegf.csv` | 同上を経年比較用に90歳以上へ統合したもの |
| `agesex_by_molecule_antivegf.csv` | 上記を成分別に分解 |
| `agesex_summary_antivegf.csv` | 年度別の近似平均年齢・75歳以上比率・男性比率 |

### 3-5. 都道府県別・地域格差
| ファイル | 内容 |
|---|---|
| `prefecture_quantity_antivegf.csv` | 都道府県×年度の数量 |
| `prefecture_per_capita_ranking_antivegf.csv` | 人口10万対＋最新年度順位 |
| `prefecture_per_capita_by_drug_antivegf.csv` | 都道府県×成分×年度の人口10万対 |
| `geographic_disparity_antivegf.csv` | Gini・CV・最大最小比・P90/P10・0件県数 |
| `covariates_correlation_antivegf.csv` | 高齢化率・眼科医師数・眼科施設数とのSpearman相関 |
| `panel_regression_summary_antivegf.csv` | Two-way FEパネル回帰の係数一覧 |
| `panel_regression_<CODE>_report.txt` | 各解析単位の回帰出力 |

### 3-6. 全国トレンド・品質管理・感度分析
| ファイル | 内容 |
|---|---|
| `national_trends_antivegf.csv` | 年度×解析単位の数量・人口10万対・65歳以上10万対・抗VEGF内シェア |
| `national_apc_antivegf.csv` | 対数線形回帰による年平均変化率（APC）と95%CI |
| `masking_qc_antivegf.csv` | 公表総計に対する内訳合計の捕捉率・秘匿セル率 |
| `sensitivity_imputation_antivegf.csv` | zero/five/randomでのGini・順位相関の比較 |
| `antivegf_summary_report_zero.txt` | 上記すべてを統合したテキストレポート |

### 3-7. 医療費（`03_解析結果/医療費/`）
| ファイル | 内容 |
|---|---|
| `cost_decomposition_yearly.csv` | 費用変化の年次要因分解（数量効果・構成効果・価格効果） |
| `cost_decomposition_cumulative.csv` | 同上の累計 |
| `cost_total_with_procedure.csv` | 薬剤費＋手技料（G016算定回数×点数×10円）の治療総額 |
| `cost_counterfactual_scenarios.csv` | 反実仮想（バイオシミラー非参入／薬価据置） |
| `cost_biosimilar_regional_potential.csv` | BSシェアの地域差解消による追加削減余地 |
| `cost_price_gap_sensitivity.csv` | 実勢価格乖離（0/5/10%）を仮定した感度分析 |

要因分解は ΔC = 数量効果＋構成効果＋価格効果 として残差0で厳密に分解される。

| 項 | 定義 |
|---|---|
| 数量効果 | (Q<sub>当年</sub> − Q<sub>前年</sub>) × p̄<sub>前年</sub> |
| 構成効果 | Q<sub>当年</sub> × (Σ s<sub>i,当年</sub> p<sub>i,前年</sub> − p̄<sub>前年</sub>) |
| 価格効果 | Σ q<sub>i,当年</sub> × (p<sub>i,当年</sub> − p<sub>i,前年</sub>) |

新規収載薬は前年薬価が存在しないため当年薬価で代用し、参入の影響は構成効果に計上される。
薬価×数量は**薬価基準額**であり実際の償還額ではない。転帰データがないため費用対効果分析は算出できない。
手技料は G016算定回数 × 点数 × 10円。点数は年度で改定される（2015〜2023年度 580点、2024年度 600点）。

> **⚠️ `cost_biosimilar_regional_potential.csv` は2026年8月に値が変わっている**
> 旧出力は、`current_national_bs_share_pct`（シェア）と `additional_bs_switch_quantity`
> （追加切替数量）で**分母が食い違っていた**。
>
> | 年度 | シェア列が示す分母 | 数量列が示す分母 | 差 |
> |---|---:|---:|---:|
> | 2022 | 152,702 | 158,072 | +5,369 |
> | 2023 | 154,499 | 157,683 | +3,184 |
> | 2024 | 150,115 | 145,054 | −5,061 |
>
> 再実装では都道府県別集計の合計に統一した（県別シェアの分母と揃えるため）。
> その結果、追加切替数量と追加削減額が旧出力より **2022年度 −3.4% / 2023年度 −2.0% /
> 2024年度 +3.8%** 変わっている。シェア列（P90・全国シェア）は2021〜2023年度で旧出力と完全一致。
>
> BSとの単価差は**先発の最高薬価（ルセンティス注射液10mg/mL）**との差を用いている。
> BSはキット製剤なので、同じキットの先発と比べると単価差は約半分になる
> （2024年度: 46,069円 vs 23,228円）。削減額の解釈に注意すること。

### 3-8. G016 硝子体内注射（`03_解析結果/G016硝子体内注射/`）
| ファイル | 内容 |
|---|---|
| `g016_national_trends.csv` / `g016_apc.csv` | 全国算定回数・人口10万対・APC（外来／入院／合計） |
| `g016_prefecture_panel.csv` / `g016_prefecture_ranking.csv` | 都道府県別の算定回数・人口10万対・順位 |
| `g016_geographic_disparity.csv` | Gini・CV・最大最小比・P90/P10 |
| `g016_agesex_distribution.csv` / `g016_agesex_summary.csv` | 年齢階級×性別の分布と要約 |
| `g016_vs_drug_validation.csv` | 薬剤数量との突合（「1バイアル＝1注射」の検証） |

### 3-9. 図（`04_図表/plots/`）
`product_trends.png` / `product_share_stacked.png` / `formulation_share_total.png` /
`formulation_kit_share_by_molecule.png` / `biosimilar_share.png` /
`agesex_pyramid_latest.png` / `age_distribution_heatmap.png` /
`prefecture_ranking_latest.png` / `gini_trends.png` / `cost_trends.png`

---

## 4. 解析手法

- **人口10万対**: `data/covariates/prefecture_covariates.csv`（e-Stat由来の人口推計・医師統計・医療施設調査）を結合
- **APC**: 対数線形回帰 `log(rate) ~ year` の傾きから `(exp(β)-1)×100`。収載のある年度のみ使用
- **地域格差**: Gini係数、変動係数（CV）、最大最小比、P90/P10比
- **パネル回帰**: `PanelOLS`（都道府県＋年の二元固定効果、都道府県クラスター頑健SE）。
  説明変数は高齢化率・人口10万対眼科医師数・人口10万対眼科施設数
- **薬剤費**: 当該年度の薬価 × 処方数量（薬価改定を年度別に反映）

いずれも `allergy解析/src/analysis_allergy.py` と同一の実装方針。

---

## 5. データ上の重要な制限事項

### 5-1. 「処方数量」は注射手技件数ではない
NDB注射ファイルの値はバイアル・シリンジの**数量**である。抗VEGF薬は原則1バイアル＝1眼1回投与のため
実施件数の近似となるが、厳密には一致しない。ビスダインのみ全身投与のため件数換算の意味が異なる。

### 5-2. 秘匿（10未満）の影響が大きい
セル単位の秘匿率は都道府県版で約60%、年齢性別版で約57%（2024年度）。
ただし**公表総計に対する内訳合計の捕捉率は96%台**であり、量的には大半が捕捉できている
（秘匿されるのは少数例の県・年齢階級に偏るため）。
2024年度の抗VEGF薬10製品では、公表総計 1,101,476本に対し都道府県内訳合計は 1,072,010本（97.3%）。
つまり**約2.7%＝29,466本が秘匿により県に帰属できていない**。

補完戦略の感度分析（`sensitivity_imputation_antivegf.csv`）では、
抗VEGF薬合計・アフリベルセプトの県別順位相関は zero vs five/random で **ρ≥0.999** と頑健。
一方、**発売直後で症例数が少ない薬剤（例: ラニビズマブBS 2021年度）はGiniが0.979→0.368と大きく変動**するため、
発売初年度の地域格差指標は解釈しないこと。

### 5-3. zero補完による「0件の県」
zero補完では、その県の全セルが秘匿だと数量0となる。最大最小比が定義できなくなるため、
`p90_to_p10_ratio` と `n_zero_prefectures` を併記している。
2024年度のルセンティス先発は21県が0件扱いとなっており、Gini=0.608は過大評価である点に注意。

### 5-4. 「外来（院外）」に該当データなし
硝子体注射は院内投与のため、`外来(院外)`シートには薬効分類131の収載行が存在しない。
本解析の「合算」は**外来（院内）＋入院**である。

### 5-5. 年齢階級の年度間差異
2014年度は`90歳以上`が最上位階級だが、2015年度以降は`90～94歳`/`95～99歳`/`100歳以上`に細分化されている。
経年比較のため全年度を`90歳以上`に統合した（`age_group`）。原表記は`age_group_detail`に保持。

### 5-6. 診療科情報がない
NDBオープンデータには処方科の情報がない。抗VEGF薬硝子体注射は事実上すべて眼科での実施だが、
眼科医療資源との関連付けはあくまで生態学的（ecological）な関連であり、因果関係は主張できない。

---

## 6. 主要な結果（zero補完・2024年度）

全国値は公表総計ベース（§5-2参照）。本フォルダは2024年度のみ公費レセプトを含む。

- **抗VEGF薬合計 1,101,476本**（人口10万対889.7）、2014年度からのAPC **+11.39%/年**（p<0.001）
- 製品別シェア: アイリーア2mgキット37.3%、アイリーア2mg注射液18.5%、バビースモ15.2%、
  ラニビズマブBS 10.4%、アイリーア8mg 8.7%、ベオビュ5.7%
- **薬剤費は年間約1,519億円**（薬価×数量）。手技料を含めた治療総額は約1,532億円で、**その95.8%が薬剤費**
- **キット比率は2019年度17.8%→2022年度63.2%へ急伸**。2024年度は56.8%（注射液のみのアイリーア8mg参入による低下）
- **ラニビズマブBSは2021年度2.9%→2024年度70.7%**。先発薬価換算との累積差は約113億円
- 年齢: 近似平均年齢は74.8歳（2014）→75.6歳（2024）、75歳以上比率は51.9%→59.3%と高齢化。男性比率62.7%→58.0%
- 地域格差: 抗VEGF薬合計のGiniは0.254（2014）→0.109（2024）と縮小。2024年度は長崎県が最多、沖縄県が最少で2.98倍
- パネル回帰: 抗VEGF薬合計では有意な共変量なし。ラニビズマブ（先発＋BS）でのみ高齢化率が正で有意（p=0.032、within R²=0.233）
- 医療費の要因分解（2014→2024累計）: **数量効果 +1,038億円 / 価格効果 −200億円 / 構成効果 +6億円**。
  価格効果は2016年度（−112億円）と2022年度（−58億円）の薬価改定に集中。
  構成効果は累計ほぼ中立だが**2024年度に+37億円へ反転**（高薬価のアイリーア8mg・バビースモへのシフト）
