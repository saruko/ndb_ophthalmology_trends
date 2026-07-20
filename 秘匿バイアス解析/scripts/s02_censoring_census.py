# -*- coding: utf-8 -*-
"""
s02: 秘匿率センサス
コード別・年度別・都道府県別の秘匿率を集計する（K281含む）。
"""
import os
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")


def run():
    df = pd.read_csv(os.path.join(OUT_DIR, "cells_with_censoring_flag.csv"))

    by_code = df.groupby("code")["is_censored"].agg(["mean", "sum", "count"])
    by_code.columns = ["censoring_rate", "n_censored", "n_cells"]
    by_code = by_code.sort_values("censoring_rate", ascending=False)
    by_code.to_csv(os.path.join(OUT_DIR, "census_by_code.csv"), encoding="utf-8-sig")

    by_code_year = (
        df.groupby(["code", "year"])["is_censored"].mean().unstack("year").round(3)
    )
    by_code_year.to_csv(os.path.join(OUT_DIR, "census_by_code_year.csv"), encoding="utf-8-sig")

    by_pref = df.groupby("prefecture")["is_censored"].mean().sort_values(ascending=False).round(3)
    by_pref.to_csv(os.path.join(OUT_DIR, "census_by_prefecture.csv"), encoding="utf-8-sig")

    print("=== 秘匿率（コード別、降順） ===")
    print(by_code.round(3).to_string())
    print("\n=== 秘匿率（都道府県別 上位10） ===")
    print(by_pref.head(10).to_string())
    return by_code


if __name__ == "__main__":
    run()
