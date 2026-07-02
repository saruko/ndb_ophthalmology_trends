# 花粉飛散量集計システム

都道府県別・年度別の花粉飛散量（スギ・ヒノキ）を集計し、統一されたフォーマットのCSVとして出力するシステムです。
以下の3つの手段を用いてデータを収集・抽出します。

1. **NPO法人花粉情報協会の公開データ** (Excelファイルをダウンロードしてパース)
2. **環境省の報道発表資料** (Excelリンクをパース、またはPDF報告書からテーブル構造を抽出してパース)
3. **各都道府県の公開データ** (代表例として、東京都健康安全研究センターのZIP/CSVデータをダウンロードして合算)

---

## 依存ライブラリ
実行には以下のライブラリが必要です。

```bash
pip install pandas pypdf pdfplumber openpyxl requests beautifulsoup4 lxml
```

---

## ファイル構成

* **`collect_pollen.py`**: 全データソースから一括して花粉データを収集・統合するメインスクリプト。
* **`npo_pollen.py`**: NPO法人花粉情報協会（pollen-net.com）の公開Excelデータのパーサー。
* **`env_pollen.py`**: 環境省の過去飛散結果のExcelデータのパーサー、およびPDF報道発表資料からのテーブル抽出パーサー。
* **`local_pollen.py`**: 東京都健康安全研究センターのZIP/CSVデータのパーサー。
* **`utils.py`**: 都道府県名の正規化（表記揺れ吸収）を行う共通関数群。

---

## 使用方法

### 1. 一括集計（推奨）
すべてのデータソースから指定年度のスギ・ヒノキ花粉データを収集し、統合されたCSVを出力します。

```bash
python collect_pollen.py --year 2024 --out output/pollen_summary_standard.csv
```

* `--year`: 収集対象の西暦年度（デフォルト: `2024`）
* `--out`: 出力先CSVパス（デフォルト: `output/pollen_summary_standard.csv`）

### 2. 個別データソースの実行
各モジュールを個別に実行し、`tmp/` ディレクトリに中間CSVを出力することも可能です。

#### NPO法人花粉情報協会データの集計
```bash
python npo_pollen.py --year 2024 --type sugi
```

#### 環境省データの集計
Excelがあれば自動でExcelを使用し、なければPDFから抽出します。`--pdf`でPDFからの抽出を強制できます。
```bash
python env_pollen.py --year 2024 --type sugi
python env_pollen.py --year 2024 --type sugi --pdf
```

#### 東京都データの集計
```bash
python local_pollen.py --year 2024 --type sugi
```

---

## 出力CSVフォーマット (`pollen_summary_standard.csv`)

| カラム名 | 説明 | 例 |
| :--- | :--- | :--- |
| `year` | 観測年度（西暦） | `2024` |
| `source` | データソース（`NPO` / `MOE` (環境省) / `Tokyo`） | `MOE` |
| `prefecture` | 正規化された都道府県名 | `東京都` |
| `station` | 観測地点名 | `千代田区` |
| `pollen_type` | 花粉の種別（`スギ` / `ヒノキ`） | `スギ` |
| `total_scattering` | 期間中の総飛散数（単位：個/cm²） | `4370.7` |

---

## 留意点（東京都以外の自治体について）
* 東京都以外の多くの地方自治体（衛生研究所・林業試験場など）では、データの提供形式がPDF、HTMLテーブル、Excelなどに分かれており、一貫したCSV形式でのデータ提供は限られています。
* 各自治体でURL設計やDOM構造、ファイルのデータフォーマットが毎年変更されるため、47都道府県すべてを網羅する個別の自動パーサーを保守することは現実的ではありません。
* 全国集計を行う場合は、全国の代表地点のデータをあらかじめ一括集計して統一フォーマットで公開している **NPOデータ** または **環境省データ** を利用してください。
