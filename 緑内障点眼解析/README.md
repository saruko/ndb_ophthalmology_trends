# NDB緑内障点眼薬 解析パイプライン

NDBオープンデータ（第1〜11回, 2014〜2024年度）を用いた緑内障点眼薬の処方トレンド解析。
`allergy解析/` と同一の設計・同一の解析メニューを、対象薬剤を緑内障点眼薬に置き換えて実装したもの。

**本書はパイプラインと解析手法の説明。データの中身と結果は [解析結果まとめ.md](解析結果まとめ.md) を参照。**

---

## 1. 実行方法

### 1-1. 標準の実行順

```bash
python 緑内障点眼解析/run_glaucoma_pipeline.py
```

```bash
python 緑内障点眼解析/build_product_inventory.py
```

```bash
python 緑内障点眼解析/verify_coverage.py
```

```bash
python 緑内障点眼解析/run_paper_analyses.py
```

```bash
python 緑内障点眼解析/run_censoring_sensitivity.py
```

```bash
python 緑内障点眼解析/build_censoring_bounds_glaucoma.py
```

```bash
python 緑内障点眼解析/build_paper_outputs.py
```

```bash
python 緑内障点眼解析/organize_outputs.py
```

```bash
python 緑内障点眼解析/add_rounded_columns.py
```

| # | スクリプト | 役割 | 依存 |
|---|---|---|---|
| 1 | `run_glaucoma_pipeline.py` | 前処理から作図・サマリーまでの本体（下記1-3） | 生Excel |
| 2 | `build_product_inventory.py` | 品目マスタ（対象薬剤・先発後発・単位・秘匿状況） | 生Excel |
| 3 | `verify_coverage.py` | 収載カバレッジの検証と単位判定の妥当性検証 | 生Excel |
| 4 | `run_paper_analyses.py` | 主解析（2022–2024）・均衡パネル・成分内シェア・成分別年次系列・年齢調整 | 1・2の出力 |
| 5 | `run_censoring_sensitivity.py` | 秘匿補完の感度分析（zero / upper の識別区間） | 生Excel |
| 6 | `build_paper_outputs.py` | `05_論文成果物/` のTable・Fig・Suppl Tableを生成 | 1〜5の出力 |
| 7 | `organize_outputs.py` | `processed_nokouhi/` から `01_〜04_` へ振り分け | — |
| 8 | `add_rounded_columns.py` | `03_解析結果/` の全CSVに丸め列を付与 | 7の後 |

2・3・5は生Excelを直接走査するため各3〜10分かかる。1の結果には依存しないので1〜3・5は順不同。
4は1・2の出力を、6は1〜5の出力を必要とする。

### 1-2. 共通オプション

| オプション | 意味 |
|---|---|
| `--imputation zero\|upper\|five\|random` | 秘匿セル（処方数量1,000未満）の補完戦略。既定 `zero`（識別区間 [0,1000) の下限）。`upper` は上限999。`five`/`random` は閾値10を前提とした旧仕様で本データでは `zero` とほぼ同義 |
| `--nokouhi` / `--kouhi` | 公費レセプトを含まない（既定・主解析）／含む（参考） |
| `--output-dir` | 出力先の上書き（感度分析で主解析を上書きしないために使う） |
| `--skip-agesex` | 年齢性別集計をスキップ（`run_glaucoma_pipeline.py` のみ） |
| `--dry-run` | 移動せず一覧のみ表示（`organize_outputs.py` のみ） |
| `--dir` | 対象ディレクトリの上書き（`add_rounded_columns.py` のみ） |

**公費レセプトの扱い**: 第1〜10回（2014〜2023年度）は公費レセプトを含まない集計のみが公表されている。
2024年度だけ「含む」版を使うと時系列に定義の不連続が生じるため、主解析は公費含まない版とし、
2024年度は第11回の「処方薬 公費レセプトを含まないデータ」に差し替える。

### 1-3. `run_glaucoma_pipeline.py` の処理順

| # | 処理 | 実装 |
|---|---|---|
| 1 | 前処理（生Excel→解析用CSV、mL統一換算、共変量マージ） | `src/preprocess_glaucoma.py` |
| 2 | 全国トレンド・APC・地域格差・共変量相関・パネル回帰 | `src/analysis_glaucoma.py` |
| 3 | シェア・HHI・治療的代替・Theil・収束・専門性 | `src/analysis_substitution.py` |
| 4 | 作図（トレンド・格差推移・共変量散布図） | `src/visualization_glaucoma.py` |
| 5 | 薬効群（作用機序分類）の群間比較 | `src/analysis_group_comparison.py` |
| 6 | 成分別曝露量（配合剤を成分に分解）のトレンド・APC | `run_glaucoma_pipeline.py` 内 |
| 7 | 都道府県別ピボットCSV（4種） | `run_glaucoma_pipeline.py` 内 |
| 8 | 年齢性別集計と年齢階級別処方率 | `build_glaucoma_age_sex.py` → `src/analysis_age_sex_rates.py` |
| 9 | 人間可読サマリー `glaucoma_summary_report.txt` | `run_glaucoma_pipeline.py` 内 |

---

## 2. 入力データ

| 種別 | パス | 内容 |
|---|---|---|
| 都道府県別 外用薬 | `data/raw/ndb_gaiyo_YYYY.xlsx` | 2014〜2024年度。シート: 外用薬 外来(院内)/外来(院外)/入院 |
| 年齢性別 外用薬 | `data/raw/ndb_age_sex/ndb_gaiyo_agesex_YYYY.xlsx` | 同上の年齢×性別版 |
| 公費含まない版 | `data/raw/ndb_2024_nokouhi/ndb_gaiyo_2024_nokouhi.xlsx` ほか | 第11回 001711930.zip の展開先 |
| 都道府県共変量 | `data/covariates/prefecture_covariates.csv` | 人口・65歳以上人口・眼科医数・眼科施設数 |
| 年齢性別人口 | `02_中間データ/population_age_sex.csv` | allergy解析の `build_population_age_sex.py` 生成物を共用 |

Excelの列構成には年度差がある（2014年度は単位列なしで総計=col7、2015年度以降は単位列ありで総計=col8）。
`load_gaiyo_sheet()` は「総計」を含むヘッダセルを動的に探索し、その右隣47列を都道府県として解決するため
年度差を意識せず読める。

---

## 3. 対象薬剤の抽出ロジック

`src/preprocess_glaucoma.py` の `DRUG_CATEGORIES`。

1. 薬効分類コード（col0、`ffill` で補完）が **`131`（眼科用剤）** の行のみ対象
2. 医薬品名（col3）に **「点眼」** を含む行のみ対象（眼軟膏・原末を除外）
3. 品名のキーワード一致で薬剤カテゴリへ分類。**配合剤を先に判定する**
   （「ミケルナ」を「ミケラン」と部分一致で取り違えないため）
4. 3シート（外来院内・外来院外・入院）を都道府県×カテゴリで合算

抽出結果は `build_product_inventory.py` で全品目・全年度を一覧化して検証している
（11年度通算160品目）。分類漏れの確認は、131かつ「点眼」を含む未分類品目名を
全年度・両ファイル（都道府県別・年齢性別）で走査して行った（未分類365品目はすべて
抗菌薬・ステロイド・抗アレルギー薬・ドライアイ治療薬等の非緑内障薬である）。

> **配合剤の後発品はキーワードに先発品名を含まない。** ラタチモ（ザラカムの後発品）・
> トラチモ（デュオトラバの後発品）・タフチモ（タプコムの後発品）・ドルモロール
> （コソプトの後発品）は先発品名を一切含まない一般名で収載されるため、先発品名だけを
> キーワードにすると11品目・2024年度で26.4百万mL（全体の10.6%）が欠落する。
> 配合剤のキーワードには後発品の一般名も必ず含めること。

「ピロカルピン塩酸塩」（原末、単位g）は2023年度以降に131として収載されるが、
「点眼」を含まずmL換算もできないため対象外である（数量は全年度秘匿）。

2024年10月開始の長期収載品の選定療養により、同一銘柄が「通常分」と「（選）」の2行に
分割収載されている。品目の同一性は `base_name()` で「（選）」を除いた品名により判定し、
品目数・品目別数量では両者を合算する（合算しないと2024年度だけ品目数が増え数量が分散する）。

### 3-1. 薬効群の定義

**日本緑内障学会「緑内障診療ガイドライン（第5版）」第5章「緑内障治療薬」1.局所投与薬**
の分類（日眼会誌126巻2号, 令和4年2月10日）に準拠した9群。ガイドラインに記載のない
緑内障適応薬を「その他」としてまとめ計10群とする。
`GROUP_DEFS`（10群・互いに排他）と `SUBGROUP_DEFS`（下位分類・上位群と重複）で管理する。

| # | 群コード | 薬効群 | 下位分類 |
|---|---|---|---|
| 1 | `PGA` | プロスタノイド受容体関連薬 | `PGA_FP` / `PGA_EP2` |
| 2 | `BETA` | 交感神経β受容体遮断薬 | `BETA_NONSEL` / `BETA_B1SEL` / `BETA_A1B` |
| 3 | `CAI` | 炭酸脱水酵素阻害薬 | — |
| 4 | `ALPHA2` | 交感神経α2受容体作動薬 | — |
| 5 | `ROCK` | Rhoキナーゼ阻害薬 | — |
| 6 | `PARASYMPATHO` | 副交感神経作動薬 | — |
| 7 | `ALPHA1` | 交感神経α1受容体遮断薬 | — |
| 8 | `ION_CHANNEL` | イオンチャネル開口薬 | — |
| 9 | `FDC_TOTAL` | 配合点眼薬 | — |
| — | `OTHER_NON_GL` | その他（ガイドライン記載外） | — |
| | `GLAUCOMA_EYE_TOTAL` | 全体合計（上記10群の和） | — |

ガイドライン原典で確認した、間違えやすい点:

- **イソプロピル・ウノプロストンは「イオンチャネル開口薬」**（8群目）であり、
  プロスタノイド受容体関連薬には含まれない。
- **ニプラジロールは「交感神経β受容体遮断薬」の下位分類(3) α1β受容体遮断薬**であり、
  独立群ではない。
- **オミデネパグ・イソプロピルはプロスタノイド受容体関連薬の下位分類(2)**（EP2受容体
  選択性作動薬）。プロスタグランジン骨格を持たないがプロスタノイドとして分類される。
- **ジピベフリン・ジスチグミンはガイドラインの9群に記載がない**ため `OTHER_NON_GL` とした。
- **アプラクロニジン（アイオピジンUD）は全体合計に含めない**。ガイドライン第6章で
  レーザー術前後の一過性眼圧上昇予防薬として記載され、第5章の眼圧下降薬9群に含まれないため。
- **配合剤は単剤の薬効群と重複させない**。複数の薬効群にまたがるため独立群として扱う。
  これにより10群は排他となり、シェア・HHI・全体合計が整合する。

### 3-2. 成分ベースの曝露量（配合剤の分解）

配合剤を成分に分解した集計（`INGREDIENT_MAP`）。`ING_PGA` / `ING_BETA` / `ING_CAI` /
`ING_ALPHA2` / `ING_ROCK` の5系列で、群間で重複するため
**シェア・HHI・全体合計には使わず別ファイルに出力する**
（`ingredient_exposure_glaucoma_zero.csv` と `national_ingredient_*`）。

`ING_BETA` はニプラジロールを含む（`BETA_CODES` の下位分類 `BETA_A1B` として
既に含まれる）。

### 3-3. 先発品/後発品の判定

NDBオープンデータには先発後発を示す列がないため、`build_product_inventory.py` の
`drug_type()` が品名から3区分で判定する。

| 区分 | 判定 |
|---|---|
| 先発品 | 品名が `BRAND_PREFIXES` の先発品名で始まる |
| 後発品（銘柄別収載） | 品名にメーカー名「」が付く |
| 後発品（統一名収載） | メーカー名を持たない一般名表記 |

「（選）」付き品目は2024年10月開始の長期収載品の選定療養分であり、先発品として扱う
（allergy解析と同じ扱い）。品目としては親品目に名寄せする（§3 末尾）。

---

## 4. 処方数量のmL統一換算

NDBオープンデータの処方数量は品目ごとに単位（`ｍＬ` / `瓶` / `個`）が異なる。
allergy解析では単位を統一せず素合算していたが、**本解析ではすべてmLに統一換算する**。

- `count` : 公表値の素の合算（単位混在）。公表値との突合用に残している
- `count_ml` : mL統一換算後の数量。**人口10万対・トレンド・パネル回帰・シェアはすべてこちら**

### 4-1. 換算規則

`ml_per_unit()` が品名から換算係数を返す。

- 品名末尾に容量が明記されている（正規表現 `[　\s]([０-９．]+)ｍＬ` に一致）→ 容器単位。その容量をmL数とする
- 一致しない → `ｍＬ` 単位。係数1.0

### 4-2. 規則の検証

「単位」列はNDBオープンデータ第3回（2016年度分）以降にのみ存在する。
`verify_coverage.py` §1 が、単位列のある全年度・全行で品名ベースの判定と公表単位を照合する。

- 都道府県別ファイル: **1,706行で不一致0件**

単位列のない2014・2015年度も同一品名で整合するため、全11年度で換算できる。
換算対象となった9品目（サンピロ5品目＝瓶5mL、コソプトミニ＝個0.4mL、タプロスミニ・
エイベリスミニ＝個0.3mL、アイオピジンUD＝個0.1mL）は
[解析結果まとめ.md](解析結果まとめ.md) 第3節に一覧。

---

## 5. 秘匿セルの扱い

外用薬（処方薬）の秘匿閾値は**処方数量1,000未満**であり、該当セルは「-」で公表される。
真値は区間 [0, 1000) にあるため、補完戦略は識別区間の下限・上限に対応する。

| `--imputation` | 補完値 | 意味 |
|---|---:|---|
| `zero`（既定） | 0 | 識別区間の下限 |
| `upper` | 999 | 識別区間の上限 |
| `five` / `random` | 5 / 1〜9乱数 | 閾値10を前提とした旧仕様。本データでは `zero` とほぼ同義 |

秘匿の実態（年度別・成分別の秘匿率、数量ベースで失われた割合）は
`build_product_inventory.py` が `censoring_report_glaucoma.csv` と
`inventory_summary_glaucoma.txt` §3 に出力する。

> **⚠️ `upper`（999/セル）は識別区間の上限として機能しない（2026-08-07判明）。**
> NDBは補完的秘匿（complementary suppression）を行っており、実データでも部分秘匿の
> 品目×年度582行に単独秘匿は0行、`missing = 公表総計 − Σ開示セル` が
> 秘匿セル数×999×mL係数 を超える行が18行ある（閾値1,000超のセルが巻き添えで
> 伏せられている）。正しい上限は行ごとの `missing` から導く。
> `build_censoring_bounds_glaucoma.py` が missing ベースの識別区間
> （全国・都道府県別）と、未収載品目まで拡張した上限（2021年度以前）を
> `03_解析結果/品質管理_感度分析/` に出力する。識別区間はこちらを正とする
> （`zero` は下限として引き続き有効）。

`zero` と `upper` の両方で前処理をやり直し、公表値のみから到達可能な**識別区間**を求めるのが
`run_censoring_sensitivity.py` である。カテゴリ別の区間幅、シェア順位の入れ替わり、
都道府県ランキングのSpearman相関を評価し、主解析（zero）の結論が区間の中で変わらないかを判定する。

```bash
python 緑内障点眼解析/run_censoring_sensitivity.py
```

出力: `censoring_sensitivity_glaucoma.csv`（カテゴリ別）／
`censoring_sensitivity_prefecture.csv`（都道府県順位）／`censoring_sensitivity_report.txt`。

パイプライン全体を上限補完で流し直したい場合は次のようにする。

```bash
python 緑内障点眼解析/run_glaucoma_pipeline.py --imputation upper --output-dir 緑内障点眼解析/processed_upper
```

---

## 6. 解析手法

### 6-1. 全国トレンドとAPC（`src/analysis_glaucoma.py`）

- **APC（年平均変化率）**: 人口10万対処方数量(mL)の対数を年に回帰し、
  APC = (exp(β₁) − 1) × 100。95%CIは β₁ ± 1.96×SE を指数変換して算出
- **Joinpoint APC**: `pwlf` による2セグメントの折れ線対数線形回帰。データ点5以上の系列のみ。
  セグメント長1年未満は除外し、傾きは ±5 にクリップ

### 6-2. 地域格差（`src/analysis_glaucoma.py`, `src/analysis_substitution.py`）

- **変動係数 CV** = 標準偏差(ddof=1) / 平均（都道府県間）
- **ジニ係数**: ソート済み系列に対する標準的な定義
- **最大/最小比** と該当都道府県
- **Theil T index（GE(1)）** = mean((x/μ)·ln(x/μ))。県間成分のみ
  （NDBオープンデータには県内の下位地域データがないため分解不可）

### 6-3. 共変量との関連（`src/analysis_glaucoma.py`）

- **Spearman順位相関**: 人口10万対処方数量 vs 高齢化率・眼科医数(人口10万対)・眼科施設数(人口10万対)
- **固定効果パネル回帰**: `linearmodels.PanelOLS`

  ```
  rate_it = β₁·aging_rate_it + β₂·docs_per_100k_it + β₃·facilities_per_100k_it
            + 都道府県FE + 年度FE + ε_it
  ```

  Two-way FE、都道府県クラスター頑健標準誤差（`cov_type="clustered", cluster_entity=True`）。
  薬剤カテゴリごとに推定し、個別レポート `panel_regression_<CODE>_glaucoma_report.txt` を出力

### 6-4. 市場構造（`src/analysis_substitution.py`）

- **シェア** = 各カテゴリの `count_ml` / 全体合計。都道府県×年度で計算
- **HHI** = Σ(shareᵢ²)。1/N（完全均等）〜1（完全独占）。都道府県×年度で計算

### 6-5. 治療的代替（`src/analysis_substitution.py`）

シェアの1階差分どうしを Two-way FE パネル回帰し、**負の係数を代替の証拠**とする。

**モデル1: クラス内代替（PG関連薬のブランド間）**

```
ΔShare(LATANOPROST)_it = β₁ΔShare(TRAVOPROST)_it + β₂ΔShare(TAFLUPROST)_it
                        + β₃ΔShare(BIMATOPROST)_it + 県FE + 年FE + ε
```

**モデル2: クラス間代替（配合剤への移行）**

```
ΔShare(FDC_TOTAL)_it = β₁ΔShare(BETA単剤)_it + β₂ΔShare(PGA単剤)_it + 県FE + 年FE + ε
```

`FULL_PANEL_DRUGS` は2014年度から全年度で処方実績のある薬剤に限定している。

### 6-6. 収束分析（`src/analysis_substitution.py`）

- **σ収束**: 年ごとのCVを年に回帰し、傾きの符号と有意性を検定（負＝収束）
- **β収束**: log(rate_tN / rate_t0) = α + β·log(rate_t0) + ε。β<0＝初期値が低い県ほど成長率が高い＝収束

### 6-7. 専門性と格差の関係（`src/analysis_substitution.py`）

専門性スコア（= 1 / 平均人口10万対処方量、希少性の代理指標）とジニ係数のSpearman相関。
「稀にしか使われない薬ほど地域差が大きい」という構造を定量化する。

### 6-8. 薬効群の群間比較（`src/analysis_group_comparison.py`）

作用機序に基づく10群について、年度ごとに以下を並べて比較する。

- 全国数量(mL)・人口10万対(mL)・全体に占めるシェア
- 都道府県間の CV・ジニ・最大/最小比・最小県・最大県
- 群別APC（対数線形回帰・95%CI）
- 群×都道府県の人口10万対と順位（最新年度）

### 6-9. 解析期間の設計（`run_paper_analyses.py`）

NDBオープンデータは第10回（2022年度分）から外用薬の収録品目が大幅に増えた。収載品目数は
2021年度の33品目から2022年度の147品目へ増加しており、**2021年度以前と2022年度以降の
処方量は直接比較できない**。そこで論文用の解析を2系統に分けている。

**(a) 主解析: 2022〜2024年度に限定した薬剤間・薬効群間の比較**

`run_full_coverage_analysis()`。全品目が収載されたフルカバレッジ期間に限定することで、
薬剤間の量比較・シェア・地域差を収載バイアスなく比較できる。出力:

| ファイル | 内容 |
|---|---|
| `fullcov_summary_glaucoma.csv` | 年度×カテゴリの数量・人口10万対・シェア・CV・ジニ・最大最小 |
| `fullcov_change_2022_2024_glaucoma.csv` | 2022→2024の量・シェア変化と年平均変化率 |
| `fullcov_prefecture_ranking_glaucoma.csv` | 都道府県ランキング（3年平均、全体および薬効群） |

**(b) 長期解析: 収載品目を固定した均衡パネル**

`run_balanced_panel_analysis()`。全年度に連続収載された品目のみを追うことで、
収載拡大の影響を受けずに長期トレンドを評価する。

| パネル | 期間 | 品目数 | 内容 |
|---|---|---:|---|
| Panel A | 2014〜2024年度 | 6 | 11年度すべてに収載された品目（すべて先発品） |
| Panel B | 2015〜2024年度 | 20 | 10年度すべてに収載された品目 |

数量は各品目行の公表「総計」列を用いる（都道府県セルの合計ではない。秘匿の影響を受けにくく
全国トレンドの推定に適するため）。品目・カテゴリ・パネル合計の3水準でAPCを算出する。出力:
`balanced_panel_products_glaucoma.csv` / `balanced_panel_trends_glaucoma.csv` /
`balanced_panel_apc_glaucoma.csv`。

**解釈上の注意**: Panel A/B の減少は当該品目が後発品等に置換されたことを示すもので、
成分全体の使用量の減少ではない。この点は成果物の注記にも明記してある。

### 6-10. 同一成分内の品目別シェア（`run_paper_analyses.py`）

`run_within_agent_share()`。同一成分（カテゴリ）のなかで各品目が占める数量シェアを算出する。
先発品と各後発品の競争構造、成分内の集中度（HHI）を見るための集計。

数量は各品目行の公表「総計」列。2024年10月開始の選定療養により分割収載された「（選）」は
`build_product_inventory.py` の時点で親品目へ名寄せ済みである
（「（選）」は2024年度にのみ44品目出現し、2014〜2023年度には存在しない）。

出力: `within_agent_product_share_glaucoma.csv`（年度×成分×品目）／
`within_agent_summary_glaucoma.csv`（年度×成分の要約：品目数・先発後発比・首位品目シェア・HHI）。

### 6-11. 成分別の年次系列と薬効群シェアの推移（`src/analysis_agent_series.py`）

成分ごとに「いつから追跡できるか」を機械的に判定し、収載開始年度から最新年度までの
年次系列を出力する。収載開始が遅い理由には (a) 新規発売 と (b) 2022年度の収載拡大まで
NDBに載っていなかった、の2つがあり意味が違うため、2022年度初収載の成分については
初年度からの伸び（新規発売なら低値から急増、既存薬の可視化なら横ばい）を併記して
判別材料とする。

**収載の有無は品目マスタ（公表「総計」列）で判定する。** 都道府県セルの合計は秘匿の
影響を受け、収載されていても0になる成分（ジスチグミン等）があるため。

`continuous_since` は最新年度から途切れずに遡れる最初の年度で、最新年度に収載がない
成分（ジピベフリン）は None となる。APCはこの連続収載期間についてのみ算出する。

出力: `agent_annual_series_glaucoma.csv`（薬効群×成分×年度。未収載は空欄）／
`agent_traceability_glaucoma.csv`（成分ごとの追跡可能性の判定とAPC）／
`group_share_by_year_glaucoma.csv`（年度×薬効群および下位分類のシェア推移）。

### 6-12. 都道府県比較の年齢調整（`src/analysis_age_adjusted.py`）

処方量の77%が65歳以上に集中するため、都道府県の粗率（人口10万対）は年齢構成の差を
そのまま反映する。**間接標準化**により調整する。

```
期待値_p     = Σ_s ( 全国の年齢層別処方率_s × 都道府県pの年齢層s人口 )
SPR_p        = 観測値_p / 期待値_p          （1.0が全国平均）
年齢調整率_p = SPR_p × 全国粗率
```

**年齢層は 0–64歳 と 65歳以上 の2層**である。NDBオープンデータは都道府県別の年齢内訳を
公表しておらず、都道府県×年齢の人口として本リポジトリが保持しているのは人口推計の
年齢3区分に由来する総人口と65歳以上人口だけであるため。より細かい階級での調整には
都道府県×5歳階級人口の追加取得が必要である。直接法は都道府県別の年齢層別処方率を
必要とするため本データでは実施できない。

出力: `age_adjusted_prefecture_glaucoma.csv`（都道府県×年度×カテゴリの粗率・期待値・SPR・
年齢調整率・順位変動）／`age_adjusted_disparity_glaucoma.csv`（粗率と年齢調整率それぞれの
CV・ジニ・最大最小比の対比）。

### 6-13. 論文成果物の生成（`build_paper_outputs.py`）

上記の出力から `05_論文成果物/` にTable・Figure・Supplementary Tableを生成する。
Excelにはネイティブのグラフを埋め込んであり、データシートの値を編集すればグラフに反映される。
列見出しは英語、薬剤名は英語＋日本語を併記する（`src/labels.py` の対応表）。
生成物の一覧と本文中の配置は [解析結果まとめ.md](解析結果まとめ.md) 冒頭の図表一覧を参照。

### 6-14. 年齢×性別（`build_glaucoma_age_sex.py`, `src/analysis_age_sex_rates.py`）

年齢性別ファイルから同じ薬剤定義・mL換算で集計し、年齢階級別人口で除して
人口10万対処方数量を算出。男女比（M:F）は数量比と率比の両方を出力する。
年齢区分はその年度の公開粒度をそのまま保持する（2014年度は90+まで、2015年度以降は
90-94/95-99/100+ に細分化）。

---

## 7. 数値の丸め（`add_rounded_columns.py`）

allergy解析（`allergy解析/add_rounded_columns.py`）と**同一の規則**。
実データ列 `X` はそのまま保持し、直後に丸め列 `X_rounded` を併記する。
既存の `_rounded` / `_display` 列は毎回作り直すため再実行しても重複しない。

| 対象 | 桁数 |
|---|---|
| 処方数量・人口・人口10万対（率） | 整数 |
| 割合・シェア(%) | 小数1桁 |
| 割合（比率0–1）・シェア・HHI・Theil | 小数3桁 |
| 比（M:F・最大/最小） | 小数3桁 |
| CV・ジニ | 小数3桁 |
| 回帰係数・標準誤差・t値 | 小数3桁 |
| APC(%) | 小数2桁 |
| R² | 小数4桁 |
| 加重平均年齢・年 | 小数1桁 |
| p値 | 生値保持＋表示用 `p_value_display`（3桁、0.001未満は `<0.001`） |

p値のみ丸め列ではなく表示用文字列を併記する。3桁に丸めると p=1e-8 が 0.000 となり
有意性情報が失われるため。

---

## 8. フォルダ構成

allergy解析と同じ規約（`src/paths.py`）。解析スクリプトは一旦 `processed_nokouhi/` に出力し、
`organize_outputs.py` で下記へ振り分ける。読み込みは `find()` を使うため整理前後どちらでも動く。

```
緑内障点眼解析/
  01_抽出データ/
    ndb_processed_glaucoma_zero.csv        解析の主入力（都道府県×年度×カテゴリ）
    ingredient_exposure_glaucoma_zero.csv  成分ベース曝露量
  02_中間データ/
    ndb_glaucoma_age_sex_zero.csv          年齢×性別の集計
    population_age_sex.csv                 年齢性別人口（分母）
  03_解析結果/
    全国トレンド/        national_trends / national_apc_linear / national_apc_joinpoint /
                        national_shares / market_hhi / convergence_analysis
    都道府県_地域格差/   geographic_disparity / covariates_correlation / theil_index /
                        specialization_disparity / panel_regression_* / prefecture_* /
                        age_adjusted_*
    年齢性別/            age_sex_rates / mf_ratio_by_age
    薬効群比較/          group_comparison / group_apc / group_share_pivot /
                        group_prefecture_ranking / group_share_by_year /
                        agent_annual_series / agent_traceability
    期間別解析/          fullcov_*（2022–2024の主解析）/ balanced_panel_*（均衡パネル）
    配合剤_成分別/       national_ingredient_trends / national_ingredient_apc
    品目マスタ/          product_master / product_inventory / censoring_report /
                        inventory_summary / within_agent_*
    代替性分析/          substitution_regression / substitution_*_report
    品質管理_感度分析/   coverage_by_year / coverage_summary /
                        censoring_sensitivity_*
    glaucoma_summary_report.txt
  04_図表/plots/    national_trends_glaucoma.png（薬効群別）
                    national_trends_by_drug_glaucoma.png（薬剤別）
                    geographic_disparity_glaucoma.png
                    correlation_scatter_<CODE>_2024.png（11コード）
  05_論文成果物/    論文用のTable・Figure・Supplementary Table
                    （build_paper_outputs.py が生成。organize_outputs.py の対象外）
                    Table1〜7_*.csv / Tables_1to7.xlsx
                    Fig1〜9_*.xlsx（グラフ埋込済）
                    SupplTable1〜6_*.xlsx
  公費含む/         参考：公費レセプトを含むデータでの同一構成
  src/              paths / preprocess_glaucoma / analysis_glaucoma /
                    analysis_substitution / analysis_group_comparison /
                    visualization_glaucoma / analysis_age_sex_rates
  processed_nokouhi/  一次出力先
```

`organize_outputs.py` は**ファイルを一切削除しない**。移動先に同名ファイルが既にある場合、
`processed_nokouhi/` 由来（今回の実行の出力）なら置き換え、それ以外は元の場所に残して警告する。

---

## 9. 依存ライブラリ

`pandas` `numpy` `scipy` `statsmodels` `linearmodels` `pwlf` `matplotlib` `seaborn` `openpyxl`
（任意: `adjustText` — 散布図の都道府県ラベル重なり調整。未導入でも動作する）

日本語フォントは Windows 環境を想定して `MS Gothic` を指定している
（`src/visualization_glaucoma.py` 冒頭）。

---

## 10. allergy解析からの変更点

| 項目 | allergy解析 | 本解析 |
|---|---|---|
| 単位 | 統一せず素合算 | 全品目をmLに統一換算（`count_ml`）。判定規則を1,706行で検証 |
| 薬効分類 | 3クラス（抗ヒスタミン／メディエーター遊離抑制／免疫抑制） | 作用機序に基づく10群＋7下位分類 |
| 配合剤 | 対象外 | 独立群として扱い、成分ベース曝露量を別出力 |
| 注射薬 | DUPIXENT/ZOLEAIR を併せて解析 | 該当なし（緑内障の全身投与薬は内服CAIだがNDBの内服薬ファイルは未取得） |
| 代替モデル | エピナスチン←オロパタジン+レボカバスチン／抗ヒスタミン←メディエーター遊離抑制 | ラタノプロスト←他PG関連薬／配合剤←単剤β遮断+単剤PG |
| 後発品_剤形の解析 | あり（アレジオンLX等） | 品目マスタ（`build_product_inventory.py`）と配合剤_成分別に置き換え |
| カバレッジ検証 | README内に記述 | `verify_coverage.py` として自動化 |
| 品目一覧・秘匿の可視化 | なし | `build_product_inventory.py` として新設 |
| 群間比較 | なし | `src/analysis_group_comparison.py` として新設 |
| 丸め | `add_rounded_columns.py`（論文用CSVに適用） | 同一規則を `03_解析結果/` 全体に適用 |

---

## 11. 既知の制約

データ側の制約（収載カバレッジの不連続・秘匿・患者数が取れないこと等）は
[解析結果まとめ.md](解析結果まとめ.md) 第5節・第9節にまとめている。
**特に2021年度以前と2022年度以降の処方量は直接比較できない**点は、
トレンド・APCを解釈する前に必ず確認すること。

収載カバレッジの不連続には `run_paper_analyses.py` の2系統設計（§6-9）で対処している。

パイプライン側の未実装項目:

- 都道府県×5歳階級人口を用いた細かい年齢調整（現状は0–64歳／65歳以上の2層）
- 直接法による年齢調整（都道府県別の年齢層別処方率が公表されていないため実施不可）
