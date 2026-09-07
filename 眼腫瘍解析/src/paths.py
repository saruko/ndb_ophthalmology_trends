"""眼腫瘍解析の入出力フォルダ構成。

抽出データ・中間データ・解析結果・図表が同じ階層に混在しないよう、
下記の構成で管理する（抗VEGF薬解析/src/paths.py と同じ方針）。

    眼腫瘍解析/
      01_抽出データ/      NDB・人口推計から抽出したCSV（解析の入力）
      02_中間データ/      層別化・整合性チェック用の中間集計
      03_解析結果/        rate換算・Poisson trend testの結果
      04_図表/            Word・図
      99_旧版_2014_2023/  2023年度までで作成した旧版（参照用・再実行対象外）

解析スクリプトは一旦 processed/ に出力し、organize_outputs.py で上記へ振り分ける。
読み込みは find() を使うことで、整理後でも整理前でも同じコードで解決できる。
"""

import os

INPUT_SUBDIR = "01_抽出データ"
INTERIM_SUBDIR = "02_中間データ"
RESULT_SUBDIR = "03_解析結果"
FIGURE_SUBDIR = "04_図表"
ARCHIVE_SUBDIR = "99_旧版_2014_2023"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find(filename, base=None):
    """base 配下から filename を探す。

    整理前（processed/ 直下）でも整理後（01_抽出データ/ 等）でも
    同じコードで読み込めるようにするためのヘルパー。
    旧版フォルダは同名ではないため誤ヒットしないが、念のため走査から除外する。
    見つからない場合は processed/ 直下のパスを返す（呼び出し側でエラーになる）。
    """
    base = base or BASE_DIR
    processed = os.path.join(base, "processed", filename)
    if os.path.exists(processed):
        return processed
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = [d for d in dirnames
                       if d not in ("__pycache__", ".git", ARCHIVE_SUBDIR, "参考文献")]
        if filename in files:
            return os.path.join(dirpath, filename)
    return processed


def output_dir(base=None, create=True):
    """解析スクリプトの一次出力先（processed/）を返す。"""
    base = base or BASE_DIR
    d = os.path.join(base, "processed")
    if create:
        os.makedirs(d, exist_ok=True)
    return d
