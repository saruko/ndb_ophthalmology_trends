# -*- coding: utf-8 -*-
"""抗アレルギー点眼解析 の入出力パス。

allergy解析/ とは独立した自己完結プロジェクトとして動く。生Excelだけは
プロジェクト共通の data/raw/ を参照する（読み取り専用）。

主解析は「公費レセプトを含まない」版に統一する。
第1回〜第10回（2014〜2023年度）は公費レセプトを含まない集計のみが公表されており、
2024年度だけ「含む」版を使うと時系列に定義の不連続が生じるため。
"""
import glob
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
RAW_AGESEX_DIR = os.path.join(RAW_DIR, "ndb_age_sex")
# 第11回NDBオープンデータ「処方薬 公費レセプトを含まないデータ」(001711930.zip) の展開先
RAW_NOKOUHI_DIR = os.path.join(RAW_DIR, "ndb_2024_nokouhi")
NOKOUHI_YEAR = 2024

COVARIATE_PATH = os.path.join(PROJECT_ROOT, "data", "covariates",
                              "prefecture_covariates.csv")

INPUT_DIR = os.path.join(BASE_DIR, "01_抽出データ")
INTERIM_DIR = os.path.join(BASE_DIR, "02_中間データ")
RESULT_DIR = os.path.join(BASE_DIR, "03_解析結果")
FIGURE_DIR = os.path.join(BASE_DIR, "04_図表")
PAPER_DIR = os.path.join(BASE_DIR, "05_論文成果物")

# 03_解析結果 の下のテーマ別サブフォルダ（既存の分類に合わせる）
RESULT_GE = os.path.join(RESULT_DIR, "後発品_剤形")
RESULT_QC = os.path.join(RESULT_DIR, "品質管理_感度分析")


def ensure(path):
    os.makedirs(path, exist_ok=True)
    return path


def raw_file(stem, year, agesex=False):
    """生Excelのパスを返す（2024年度は公費含まない版に差し替える）。

        stem: "ndb_gaiyo" / "ndb_gaiyo_agesex"
    """
    if year == NOKOUHI_YEAR:
        p = os.path.join(RAW_NOKOUHI_DIR, f"{stem}_{year}_nokouhi.xlsx")
        if os.path.exists(p):
            return p
        raise FileNotFoundError(
            f"公費含まない版の生データが見つかりません: {p}\n"
            f"第11回NDBオープンデータ 001711930.zip を {RAW_NOKOUHI_DIR} へ展開してください。")
    base = RAW_AGESEX_DIR if agesex else RAW_DIR
    return os.path.join(base, f"{stem}_{year}.xlsx")


def raw_file_map(stem, agesex=False):
    """年度 -> 生Excelパス の辞書（2024年度は公費含まない版に差し替え済み）。"""
    base = RAW_AGESEX_DIR if agesex else RAW_DIR
    files = {}
    for p in glob.glob(os.path.join(base, f"{stem}_*.xlsx")):
        m = re.fullmatch(rf"{re.escape(stem)}_(\d{{4}})\.xlsx", os.path.basename(p))
        if m:
            files[int(m.group(1))] = p
    if NOKOUHI_YEAR in files:
        files[NOKOUHI_YEAR] = raw_file(stem, NOKOUHI_YEAR, agesex)
    return files
