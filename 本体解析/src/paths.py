"""本体解析（眼科主要手術・処置）の入出力フォルダ構成。

解析結果が `data/processed/` 直下に平積みになるのを避け、テーマ別に分けて管理する。
**サブ解析と違い、番号付きフォルダは `data/` の中に置く。**
`.gitignore` が `data/` を「NDB・患者データの流出防止」目的で丸ごと除外しているため、
解析結果を `data/` の外へ出すとこの保護が外れてしまうからである。

    data/processed/
      01_中間データ/    前処理済みの統合データ（解析の入力）
      02_解析結果/      解析アウトプット（テーマ別サブフォルダ）
      03_図表/plots/    図（png）・Excel
      sub_analysis/     K280・K268のサブ解析
                        （親と同名のCSVを持つため、ばらさずフォルダごと維持する）

解析スクリプトは従来どおり `data/processed/` 直下に出力してよい。
出力後に organize_outputs.py を実行すると上記の構成へ振り分けられる。
読み込みは find() を使うことで、整理後でも整理前でも同じコードで解決できる。
"""

import os

INTERIM_SUBDIR = "01_中間データ"
RESULT_SUBDIR = "02_解析結果"
FIGURE_SUBDIR = "03_図表"
SUB_ANALYSIS_SUBDIR = "sub_analysis"

# 02_解析結果 の下のテーマ別サブフォルダ
RESULT_CATEGORIES = [
    "全国トレンド",
    "都道府県_地域格差",
    "論文図表データ",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # リポジトリルート（本体解析/src の2階層上）
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
COVARIATE_PATH = os.path.join(BASE_DIR, "data", "covariates",
                              "prefecture_covariates.csv")


def output_dir(create=True):
    """解析スクリプトの一次出力先（data/processed/）を返す。"""
    if create:
        os.makedirs(PROCESSED_DIR, exist_ok=True)
    return PROCESSED_DIR


def find(filename, base=None):
    """data/processed/ 配下から filename を探す。

    整理前（直下）でも整理後（02_解析結果/テーマ別/）でも同じコードで読み込める。
    sub_analysis/ には親と同名で内容の違うCSVがあるため、走査から除外する
    （サブ解析の結果が必要な場合は sub_analysis_path() を使う）。
    見つからない場合は直下のパスを返す（呼び出し側でエラーになる）。
    """
    base = base or PROCESSED_DIR
    direct = os.path.join(base, filename)
    if os.path.exists(direct):
        return direct
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", ".git", SUB_ANALYSIS_SUBDIR)]
        if filename in files:
            return os.path.join(dirpath, filename)
    return direct


def sub_analysis_path(filename, base=None):
    """K280・K268サブ解析の結果パスを返す。"""
    base = base or PROCESSED_DIR
    return os.path.join(base, SUB_ANALYSIS_SUBDIR, filename)
