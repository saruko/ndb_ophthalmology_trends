"""緑内障点眼薬解析の入出力フォルダ構成と、公費レセプトの有無の切り替え。

抽出データ・中間データ・解析結果・図表・論文成果物が同じ階層に混在しないよう、
下記の構成で管理する（allergy解析/src/paths.py と同じ方針）。

    緑内障点眼/
      01_抽出データ/    生Excelから抽出したCSV（解析の入力）
      02_中間データ/    前処理済みデータ・年齢性別集計・人口
      03_解析結果/      解析アウトプット（テーマ別サブフォルダ）
      04_図表/plots/    図（png）
      05_論文成果物/    論文原稿・Fig/Table用xlsx（凍結。organize_outputs.py の対象外）
      公費含む/         参考：公費レセプトを含むデータでの同一構成（01〜04）

**主解析は「公費レセプトを含まない」版**である（--nokouhi）。
第1回〜第10回（2014〜2023年度）は公費レセプトを含まない集計のみが公表されており、
2024年度だけ「含む」版を使うと時系列に定義の不連続が生じるため。

解析スクリプトは一旦 processed/（--nokouhi 時は processed_nokouhi/）に出力し、
organize_outputs.py で上記の構成へ振り分ける。
読み込みは find() を使うことで、整理後でも整理前でも同じコードで解決できる。
"""

import glob
import os
import re
import sys

INPUT_SUBDIR = "01_抽出データ"
INTERIM_SUBDIR = "02_中間データ"
RESULT_SUBDIR = "03_解析結果"
FIGURE_SUBDIR = "04_図表"
PAPER_SUBDIR = "05_論文成果物"
KOUHI_SUBDIR = "公費含む"
ARCHIVE_SUBDIR = "旧版"

# 03_解析結果 の下のテーマ別サブフォルダ
RESULT_CATEGORIES = [
    "全国トレンド",
    "都道府県_地域格差",
    "年齢性別",
    "薬効群比較",
    "期間別解析",
    "配合剤_成分別",
    "品目マスタ",
    "代替性分析",
    "品質管理_感度分析",
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
RAW_AGESEX_DIR = os.path.join(RAW_DIR, "ndb_age_sex")
# 第11回NDBオープンデータ「処方薬 公費レセプトを含まないデータ」(001711930.zip) の展開先
RAW_NOKOUHI_DIR = os.path.join(RAW_DIR, "ndb_2024_nokouhi")
NOKOUHI_YEAR = 2024

COVARIATE_PATH = os.path.join(PROJECT_ROOT, "data", "covariates", "prefecture_covariates.csv")


def data_root(nokouhi):
    """解析結果を置くルートを返す。

    主解析（公費含まない）は 緑内障点眼/ 直下、公費含む版は 公費含む/ の下。
    """
    return BASE_DIR if nokouhi else os.path.join(BASE_DIR, KOUHI_SUBDIR)


def output_dir(nokouhi, create=True):
    """解析スクリプトの一次出力先を返す。

    公費の有無で別フォルダに出し、主解析を誤って上書きしないようにする。
    """
    name = "processed_nokouhi" if nokouhi else "processed"
    d = os.path.join(BASE_DIR, name)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def raw_file(stem, year, nokouhi, agesex=False):
    """生Excelのパスを返す。

    公費含まない版として公表されているのは2024年度分のみのため、
    --nokouhi 指定時は2024年度だけ ndb_2024_nokouhi/ のファイルに差し替える
    （2014〜2023年度はもともと公費含まない集計であり、差し替え不要）。

        stem: "ndb_gaiyo" / "ndb_gaiyo_agesex"
    """
    if nokouhi and year == NOKOUHI_YEAR:
        p = os.path.join(RAW_NOKOUHI_DIR, f"{stem}_{year}_nokouhi.xlsx")
        if os.path.exists(p):
            return p
        raise FileNotFoundError(
            f"公費含まない版の生データが見つかりません: {p}\n"
            f"第11回NDBオープンデータ 001711930.zip を {RAW_NOKOUHI_DIR} へ展開してください。"
        )
    base = RAW_AGESEX_DIR if agesex else RAW_DIR
    return os.path.join(base, f"{stem}_{year}.xlsx")


def raw_file_map(stem, nokouhi, agesex=False):
    """年度 -> 生Excelパス の辞書を返す（--nokouhi 時は2024年度を差し替え済み）。"""
    base = RAW_AGESEX_DIR if agesex else RAW_DIR
    files = {}
    for p in glob.glob(os.path.join(base, f"{stem}_*.xlsx")):
        m = re.fullmatch(rf"{re.escape(stem)}_(\d{{4}})\.xlsx", os.path.basename(p))
        if m:
            files[int(m.group(1))] = p
    if nokouhi and NOKOUHI_YEAR in files:
        files[NOKOUHI_YEAR] = raw_file(stem, NOKOUHI_YEAR, nokouhi, agesex)
    return files


def find(filename, nokouhi, base=None):
    """データルート配下から filename を探す。

    整理前（processed*/ 直下）でも整理後（01_抽出データ/ 等）でも同じコードで
    読み込めるようにするためのヘルパー。旧版・論文成果物は凍結された別世代の
    同名ファイルを含むため、走査から除外する。
    見つからない場合は一次出力先のパスを返す（呼び出し側でエラーになる）。
    """
    out = os.path.join(output_dir(nokouhi, create=False), filename)
    if os.path.exists(out):
        return out
    root = base or data_root(nokouhi)
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in
                       ("__pycache__", ".git", PAPER_SUBDIR, ARCHIVE_SUBDIR,
                        KOUHI_SUBDIR if nokouhi else "")]
        if filename in files:
            return os.path.join(dirpath, filename)
    return out


def nokouhi_from_argv(argv=None):
    """コマンドラインから公費の有無を判定する（既定は主解析＝公費含まない）。

    各スクリプトはモジュール冒頭で出力先などの定数を決めており、argparse の
    解析を待たずに値が要る。そのため sys.argv を直接見る軽量な判定を用意する。
    argparse 側にも add_nokouhi_arg() で同じオプションを登録し、--help や
    未知オプションのエラーが正しく出るようにしておくこと。
    """
    argv = sys.argv if argv is None else argv
    return "--kouhi" not in argv


def add_nokouhi_arg(parser):
    """各スクリプトに共通の --nokouhi / --kouhi オプションを足す。

    主解析は公費含まないため既定を --nokouhi とし、公費含む版は明示指定させる。
    """
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--nokouhi", dest="nokouhi", action="store_true", default=True,
                   help="公費レセプトを含まないデータで解析する（既定・主解析）")
    g.add_argument("--kouhi", dest="nokouhi", action="store_false",
                   help="公費レセプトを含むデータで解析する（参考）")
    return parser
