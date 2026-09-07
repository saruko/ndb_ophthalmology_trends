# -*- coding: utf-8 -*-
"""生Excel（公費含まない基準）から9成分の品目別データを抽出してCSVに落とす。

以降のレポート生成（build_censoring_reports.py / build_ge_series.py）は
すべてこのCSVを入力とし、Excelを読み直さない。

出力（都道府県ファイル）:
  01_抽出データ/product_level_censoring.csv  品目×年度×シート（秘匿情報つき）
  01_抽出データ/product_pref_long.csv        品目×年度×シート×都道府県（縦持ち）
  01_抽出データ/eye_product_counts.csv       薬効分類131の公開品目数（足切り検証用）

出力（年齢性別ファイル）:
  01_抽出データ/product_agesex_censoring.csv 品目×年度×シート（秘匿情報つき、42セル単位）
  01_抽出データ/product_agesex_long.csv      品目×年度×シート×性別×年齢階級（縦持ち）
"""
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

import ndb_reader as R                                     # noqa: E402
import units as U                                          # noqa: E402
from drug_master import classify_drug, product_type        # noqa: E402
from paths import INPUT_DIR, ensure, raw_file_map          # noqa: E402


def normalize_units(recs, label):
    """単位を補完し、mL換算係数（ml_factor）と total_ml を付与する。

    9成分の単位は ｍＬ／瓶（5mL）／個（0.35mL）が混在しており、
    正規化せずに成分をまたいで合算すると値が成立しない。詳細は src/units.py。
    """
    filled, unresolved = U.backfill_units(recs)
    unconv = U.annotate(recs)
    print(f"  [{label}] 単位補完: {filled} 行（2014〜2015年度は単位列が無いため）")
    if unresolved:
        print(f"  [{label}] ★単位を補完できなかった品目: {sorted(unresolved)}")
    if unconv:
        print(f"  [{label}] ★mL換算できなかった品目: {sorted(unconv)}")
    return recs


def extract_pref(files):
    rows, long_rows, count_rows = [], [], []
    all_recs = []
    for year in sorted(files):
        path = files[year]
        print(f"  {year}年度: {os.path.basename(path)}")
        all_recs += R.read_year(path, year, classify_drug, product_type)
        c = R.count_eye_products(path)
        for kind, d in c["by_sheet"].items():
            count_rows.append({"year": year, "sheet": kind,
                               "n_products_by_name": d["names"],
                               "n_products_by_code": d["codes"],
                               "min_total": d["min_total"]})
        count_rows.append({"year": year, "sheet": "全シート通算（ユニーク）",
                           "n_products_by_name": c["unique_names"],
                           "n_products_by_code": c["unique_codes"],
                           "min_total": None})

    # 単位の補完・mL換算は全年度を読み終えてから行う
    # （2014〜2015年度の単位を後年度から引き当てるため）。
    normalize_units(all_recs, "都道府県")

    for rec in all_recs:
        rows.append({k: v for k, v in rec.items()
                     if k not in ("censored_prefs", "disclosed")}
                    | {"censored_prefs": "|".join(rec["censored_prefs"])})
        f = rec["ml_factor"]
        for pref in R.PREFECTURES:
            v = rec["disclosed"].get(pref)
            long_rows.append({
                "year": rec["year"], "sheet": rec["sheet"], "code": rec["code"],
                "product_name": rec["product_name"],
                "product_type": rec["product_type"],
                "prefecture": pref, "value": v, "censored": v is None,
                "ml_factor": f,
                "value_ml": None if (v is None or f is None) else v * f,
            })
    return rows, long_rows, count_rows


def extract_agesex(files):
    """年齢性別ファイルを抽出する。

    2014〜2015年度は19年齢階級（90歳以上はまとめて1区分）、2016年度以降は
    21年齢階級（90〜94/95〜99/100歳以上に細分化）とセル構成が異なるため、
    縦持ちは行ごとに実際検出されたセル（disclosed＋censored_cells）から
    再構成する。固定リストは使わない。
    """
    rows, long_rows = [], []
    all_recs = []
    for year in sorted(files):
        path = files[year]
        print(f"  {year}年度: {os.path.basename(path)}")
        all_recs += R.read_agesex_year(path, year, classify_drug, product_type)

    normalize_units(all_recs, "年齢性別")

    for rec in all_recs:
        rows.append({k: v for k, v in rec.items()
                     if k not in ("censored_cells", "disclosed")}
                    | {"censored_cells": "|".join(rec["censored_cells"])})
        f = rec["ml_factor"]
        base = {"year": rec["year"], "sheet": rec["sheet"], "code": rec["code"],
                "product_name": rec["product_name"],
                "product_type": rec["product_type"], "ml_factor": f}
        for key, v in rec["disclosed"].items():
            long_rows.append(base | {
                "sex": key[0], "age_group": key[1:],
                "value": v, "censored": False,
                "value_ml": None if f is None else v * f,
            })
        for key in rec["censored_cells"]:
            long_rows.append(base | {
                "sex": key[0], "age_group": key[1:],
                "value": None, "censored": True, "value_ml": None,
            })
    return rows, long_rows


def _save(df, name):
    p = os.path.join(INPUT_DIR, name)
    df.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {name} ({len(df)} rows)")


def main():
    ensure(INPUT_DIR)

    print("=== 都道府県ファイル ===")
    files = raw_file_map("ndb_gaiyo")
    rows, long_rows, count_rows = extract_pref(files)
    _save(pd.DataFrame(rows), "product_level_censoring.csv")
    _save(pd.DataFrame(long_rows), "product_pref_long.csv")
    _save(pd.DataFrame(count_rows), "eye_product_counts.csv")

    print()
    print("=== 年齢性別ファイル ===")
    files_as = raw_file_map("ndb_gaiyo_agesex", agesex=True)
    rows_as, long_rows_as = extract_agesex(files_as)
    _save(pd.DataFrame(rows_as), "product_agesex_censoring.csv")
    _save(pd.DataFrame(long_rows_as), "product_agesex_long.csv")


if __name__ == "__main__":
    main()
