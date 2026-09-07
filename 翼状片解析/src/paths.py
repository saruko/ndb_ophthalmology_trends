"""翼状片解析の入出力フォルダ構成。

抽出データ・中間データ・解析結果・図表が同じ階層に混在しないよう、
下記の構成で管理する（抗VEGF薬解析/src/paths.py と同じ方針）。

    翼状片解析/
      01_抽出データ/   生Excelから抽出した縦持ちCSV（解析の入力）
      02_中間データ/   人口10万対換算まで済ませたデータ
      03_解析結果/     解析アウトプット（テーマ別サブフォルダ）
      04_図表/plots/   図（png）・Excel
      05_紫外線データ/ 紫外線・日射量の収集データと元画像

解析スクリプトは従来どおり processed/ に出力してよい。
出力後に organize_outputs.py を実行すると上記の構成へ振り分けられる。
読み込みは find() を使うことで、整理後でも整理前でも同じコードで解決できる。
"""

import os

INPUT_SUBDIR = "01_抽出データ"
INTERIM_SUBDIR = "02_中間データ"
RESULT_SUBDIR = "03_解析結果"
FIGURE_SUBDIR = "04_図表"
UV_SUBDIR = "05_紫外線データ"

# 03_解析結果 の下のテーマ別サブフォルダ
RESULT_CATEGORIES = [
    "全国トレンド",
    "都道府県_地域格差",
    "紫外線相関",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find(filename, base=None):
    """base 配下から filename を探す。

    整理前（processed/ 直下）でも整理後（01_抽出データ/ 等）でも
    同じコードで読み込めるようにするためのヘルパー。
    見つからない場合は processed/ 直下のパスを返す（呼び出し側でエラーになる）。
    """
    base = base or BASE_DIR
    processed = os.path.join(base, "processed", filename)
    if os.path.exists(processed):
        return processed
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
        if filename in files:
            return os.path.join(dirpath, filename)
    return processed


def uv_path(filename, base=None):
    """紫外線データのパスを解決する（05_紫外線データ/ を優先し、無ければ直下）。"""
    base = base or BASE_DIR
    p = os.path.join(base, UV_SUBDIR, filename)
    return p if os.path.exists(p) else os.path.join(base, filename)


def output_dir(base=None, create=True):
    """解析スクリプトの一次出力先（processed/）を返す。"""
    base = base or BASE_DIR
    d = os.path.join(base, "processed")
    if create:
        os.makedirs(d, exist_ok=True)
    return d
