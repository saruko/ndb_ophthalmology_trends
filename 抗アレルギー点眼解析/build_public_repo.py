# -*- coding: utf-8 -*-
"""Data availability 用の公開ツリーを切り出す。

研究フォルダ全体には**未公開の原稿ドラフト**（本論文の下書き11本、免疫抑制薬
サブ解析の別論文、学会抄録2本）や他解析（花粉量・学会案）が含まれるため、
丸ごと公開することはできない。本スクリプトは、論文の数値を再現するために
必要なコードと、原稿§9 が引用する方法・監査記録だけを別ツリーに複製する。

公開先は既存の公開リポジトリ `saruko/ndb_ophthalmology_trends`（眼科診療
トレンド解析の傘リポジトリ）の `抗アレルギー点眼解析/` サブツリー。ルートの
`requirements.txt`・`.gitignore` は既にあり内容も足りるため複製しない。
`src/paths.py` が `<repo>/data/raw/` を相対参照するので、ディレクトリ階層を
そのまま保てばコードを書き換えずに動く。

出力: ../公開用_ndb_allergy_eyedrops/抗アレルギー点眼解析/
    **.py        パイプライン
    *.md         方法・監査記録（原稿§9 が引用するもの）
    README.md    本スクリプトが生成
    LICENSE      MIT（このサブツリーに対して）

除外もれを防ぐため、複製後にファイル名を走査して原稿・抄録・他解析が
混ざっていないか検査し、見つかれば異常終了する。

実行: python build_public_repo.py
"""
import io
import os
import re
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))            # 抗アレルギー点眼解析
ROOT = os.path.dirname(BASE)                                 # 研究フォルダ＝リポジトリroot
PKG = "抗アレルギー点眼解析"
DEST = os.path.join(ROOT, "公開用_ndb_allergy_eyedrops")
OUT = os.path.join(DEST, PKG)
NEW = os.path.join("05_論文成果物", "公費含めない_new")

# --- 複製するもの -----------------------------------------------------------
# (BASE からの相対ディレクトリ, 拡張子) — そのディレクトリ直下のみ
CODE_DIRS = [
    ("", ".py"),
    ("src", ".py"),
    (os.path.join(NEW, "ジニ係数あり"), ".py"),
    (os.path.join(NEW, "投稿改定ver"), ".py"),
]

# 原稿§9「方法の詳細・監査記録」と、査読者が方法を追うために要る解説
DOCS = [
    "NDB公開構造と秘匿実態_9成分_統合版.md",
    "解析方針QA.md",
    os.path.join(NEW, "bounded_outputs_report.md"),
    os.path.join(NEW, "pipeline_audit_findings.md"),
    os.path.join(NEW, "censoring_treatment_audit.md"),
    os.path.join(NEW, "unlisted_sensitivity_report.md"),
    os.path.join("05_論文成果物", "秘匿閾値と識別区間の解説.md"),
]

# --- 複製しないもの ---------------------------------------------------------
EXCLUDE_FILES = {
    "apply_lecture_revisions_v9.py",        # 講演スライド用
    "build_submission_files_v7_backup.py",  # v7 のバックアップ
    "build_gini_cv_v10_backup.py",          # v10 のバックアップ
    "build_public_repo.py",                 # 本スクリプト自身
}
# 複製後の検査：原稿・抄録・他解析が混ざっていたら異常終了する
FORBIDDEN = re.compile(r"論文下書き|paper_draft|abstract_|演題|figure_legends|"
                       r"immunosuppressant|花粉量|学会案")

# docstring に残っている個人の絶対パス
PERSONAL_PATH = "C:\\\\Users\\\\goodt\\\\anaconda3\\\\python.exe"

LICENSE = """MIT License

Copyright (c) 2026 saruko

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

README = """# 抗アレルギー点眼薬の全国処方動向 2014-2024年度（NDBオープンデータ・部分識別解析）

Analysis code for *"National Prescription Trends for Anti-allergic Eye Drops in
Japan, 2014-2024: A Partial Identification Approach to Cell Suppression and
Item-Level Non-Listing in NDB Open Data"*.

論文の Data availability に対応するディレクトリで、**前処理・解析コード**と
**方法・監査記録**を収める。入力は公開データだけなので、下記の手順で第三者が
論文の数値を再現できる。原稿本文と図表そのものは論文および Supplementary
Material を参照のこと（本ディレクトリには含めない）。

## 入力データ（利用者が取得する）

いずれも公開データで、本リポジトリには含めない。配置先はリポジトリ root からの
相対パスで、定義は `src/paths.py` にある。

| データ | 取得元 | 置き場所 |
|---|---|---|
| NDBオープンデータ 第1〜11回（2014〜2024年度）の処方薬・薬効分類131（眼科用剤） | 厚生労働省 https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000177182.html | `data/raw/ndb_age_sex/` ほか |
| 第11回「処方薬 公費レセプトを含まないデータ」`001711930.zip` | 同上 | 展開先を `data/raw/ndb_2024_nokouhi/` |
| 人口推計（年齢階級別・性別・都道府県別） | 総務省統計局 e-Stat https://www.e-stat.go.jp/ | `data/covariates/` |

全11年度を通じて「公費レセプトを含まない」集計を用いる。第1〜10回は
含まない版のみが公表されており、2024年度だけ含む版を使うと時系列に定義の
不連続が生じるためである。

## 実行環境

```
pip install -r ../requirements.txt
```

Python 3.13 / pandas 2.3 / numpy 2.4 / openpyxl 3.1 で実行した。
投稿用の pptx・png を生成する `build_submission_v1*.py` と `build_v1*_folder.py`
だけは **Windows + PowerPoint** を要する（PNG 書き出しに PowerPoint COM を使う）。
論文の数値を再現するだけなら不要である。

## 実行順

```
python build_extract.py                # 生Excel -> 抽出データ
python build_bounded_outputs.py        # 識別区間の本体
python build_paper_figures_bounds.py   # Table 1・2、Suppl Table S5・S7
python build_top3_full_bounds.py       # Suppl Table S6
python build_unlisted_sensitivity.py   # Suppl Table S2・S3、Suppl Fig S4
python build_trend_identification.py   # Suppl Table S4、Suppl Fig S3
python build_share_table_ge_fig.py     # Table 3、Suppl Fig S1
python build_extra_figures.py          # Suppl Fig S2
python 05_論文成果物/公費含めない_new/ジニ係数あり/build_gini_cv.py        # Fig 7・Suppl Table S10
python 05_論文成果物/公費含めない_new/ジニ係数あり/build_gini_cv_figure.py
```

投稿用ファイル一式（Figure 1-7、Table 1-3、Supplementary）の組み立ては
`05_論文成果物/公費含めない_new/投稿改定ver/build_submission_v11.py` →
`build_submission_v12.py` → `build_v14_folder.py`、検証は `verify_v14.py`。
補遺図の番号は原稿 v14 で1つずつ繰り上がっている（旧 S2-S5 が現 S1-S4）。

## 再現性

v10 で全パイプラインを生データから再実行したところ、生成される **CSV はすべて
再実行前とバイト単位で一致**した（`.xlsx`・`.png` は openpyxl・matplotlib が
作成時刻を埋め込むためハッシュが変わるが、由来する CSV は同一）。

## 方法・監査記録

| ファイル | 内容 |
|---|---|
| `NDB公開構造と秘匿実態_9成分_統合版.md` | 公表仕様と秘匿の実態の突合 |
| `05_論文成果物/秘匿閾値と識別区間の解説.md` | 秘匿閾値と識別区間の解説 |
| `05_論文成果物/公費含めない_new/pipeline_audit_findings.md` | 「秘匿セル≦999」が成立しない証拠を含む監査 |
| `05_論文成果物/公費含めない_new/censoring_treatment_audit.md` | 秘匿の扱いの監査 |
| `05_論文成果物/公費含めない_new/bounded_outputs_report.md` | 識別区間の生成物の記録 |
| `05_論文成果物/公費含めない_new/unlisted_sensitivity_report.md` | 品目非掲載の感度分析 |
| `解析方針QA.md` | 解析方針の判断記録 |

## ライセンス

MIT License（`LICENSE`）。本ディレクトリ（`抗アレルギー点眼解析/`）に適用する。
"""


def copy_tree():
    n = 0
    for rel, ext in CODE_DIRS:
        src_dir = os.path.join(BASE, rel)
        if not os.path.isdir(src_dir):
            raise SystemExit("ディレクトリがない: %s" % src_dir)
        for f in sorted(os.listdir(src_dir)):
            if not f.endswith(ext) or f in EXCLUDE_FILES:
                continue
            src = os.path.join(src_dir, f)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(OUT, rel, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n += 1
    for rel in DOCS:
        src = os.path.join(BASE, rel)
        if not os.path.exists(src):
            raise SystemExit("ファイルがない: %s" % src)
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


def scrub():
    """docstring の「実行:」行に残っている個人の絶対パスを `python` に直す。

    複製先だけを直す（研究フォルダ側の原本は触らない）。
    """
    n = 0
    for dirpath, _, files in os.walk(OUT):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(dirpath, f)
            s = io.open(p, encoding="utf-8").read()
            if PERSONAL_PATH in s:
                io.open(p, "w", encoding="utf-8", newline="").write(
                    s.replace(PERSONAL_PATH, "python"))
                n += 1
    return n


def audit():
    """原稿・抄録・他解析が混ざっていないかを検査し、残った個人パスを返す。"""
    bad = [os.path.relpath(os.path.join(d, f), DEST)
           for d, _, fs in os.walk(DEST) for f in fs
           if FORBIDDEN.search(os.path.relpath(os.path.join(d, f), DEST))]
    if bad:
        raise SystemExit("公開してはいけないファイルが混ざっている:\n  "
                         + "\n  ".join(bad))
    leaks = []
    for d, _, fs in os.walk(DEST):
        for f in fs:
            if not f.endswith((".py", ".md")):
                continue
            p = os.path.join(d, f)
            s = io.open(p, encoding="utf-8", errors="ignore").read()
            leaks += [(os.path.relpath(p, DEST), m)
                      for m in re.findall(r"C:\\+Users\\+[^\\\s\"']+", s)]
    return leaks


def main():
    if os.path.exists(DEST):
        shutil.rmtree(DEST)
    n = copy_tree()
    io.open(os.path.join(OUT, "README.md"), "w",
            encoding="utf-8", newline="\n").write(README)
    io.open(os.path.join(OUT, "LICENSE"), "w",
            encoding="utf-8", newline="\n").write(LICENSE)
    k = scrub()
    leaks = audit()
    total = sum(len(fs) for _, _, fs in os.walk(DEST))
    size = sum(os.path.getsize(os.path.join(d, f))
               for d, _, fs in os.walk(DEST) for f in fs)
    print("-> %s" % OUT)
    print("   %d ファイル / %.1f MB（複製 %d ＋ README・LICENSE）"
          % (total, size / 1e6, n))
    print("   個人の絶対パスを %d ファイルで `python` に置換" % k)
    if leaks:
        print("   まだ個人の絶対パスが残っている（要修正）:")
        for rel, m in leaks:
            print("     %-30s %s" % (rel, m))
    else:
        print("   個人の絶対パスなし")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
