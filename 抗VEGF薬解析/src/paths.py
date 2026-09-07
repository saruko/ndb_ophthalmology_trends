"""抗VEGF薬解析の入出力フォルダ構成。

抽出データ・中間データ・解析結果・図表が同じ階層に混在しないよう、
下記の構成で管理する。

    <データフォルダ>/
      01_抽出データ/        生Excelから抽出したCSV（解析の入力）
      02_中間データ/        前処理済みデータ・パネルデータ
      03_解析結果/          解析アウトプット（テーマ別サブフォルダ）
      04_図表/              図（png）・Excel・Word
      05_先行研究再現_Kabata/ Kabata et al. (2026) 再現用の表

解析スクリプトは従来どおり processed/ に出力してよい。
出力後に organize_outputs.py を実行すると上記の構成へ振り分けられる。
入力の読み込みは input_path() を使うことで、整理後（01_抽出データ/）でも
整理前（フォルダ直下）でも同じコードで解決できる。
"""

import os

INPUT_SUBDIR = "01_抽出データ"
INTERIM_SUBDIR = "02_中間データ"
RESULT_SUBDIR = "03_解析結果"
FIGURE_SUBDIR = "04_図表"
KABATA_SUBDIR = "05_先行研究再現_Kabata"

# 03_解析結果 の下のテーマ別サブフォルダ
RESULT_CATEGORIES = [
    "全国トレンド",
    "製品_剤形_バイオシミラー",
    "医療費",
    "年齢性別",
    "都道府県_地域格差",
    "G016硝子体内注射",
    "品質管理_感度分析",
]

ANTIVEGF_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ANTIVEGF_DIR)
COVARIATES = os.path.join(PROJECT_ROOT, "data", "covariates",
                          "prefecture_covariates.csv")


def input_path(base, filename):
    """入力CSVのパスを解決する（01_抽出データ/ を優先し、無ければ直下）。"""
    p = os.path.join(base, INPUT_SUBDIR, filename)
    return p if os.path.exists(p) else os.path.join(base, filename)


def input_dir(base, create=True):
    """抽出データの出力先を返す。"""
    d = os.path.join(base, INPUT_SUBDIR)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def find(base, filename):
    """base 配下から filename を探す。

    整理前（processed/ 直下）でも整理後（03_解析結果/テーマ別/）でも
    同じコードで読み込めるようにするためのヘルパー。

    「公費含まない」は同名・別内容のファイルを持つ独立したデータセットなので、
    親フォルダからの走査では必ず除外する（混ざると解析結果が静かに壊れる）。
    見つからない場合は base 直下のパスを返す（呼び出し側でエラーになる）。
    """
    direct = os.path.join(base, filename)
    if os.path.exists(direct):
        return direct
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", ".git", "公費含まない")]
        if filename in files:
            return os.path.join(dirpath, filename)
    return direct
