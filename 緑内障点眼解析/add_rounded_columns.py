# -*- coding: utf-8 -*-
"""解析結果CSVに丸め済み列を併記する。

allergy解析/add_rounded_columns.py と同一の丸め規則を用いる。実データ（X）は
そのまま保持し、表記に用いる丸め値（X_rounded）を並べて確認できるようにする。
p値のみ、生値を保持したうえで表示用文字列 p_value_display を併記する
（3桁に丸めると p=1e-8 が 0.000 となり有意性情報が失われるため）。

既存の _rounded / _display 列は毎回作り直すため、再実行しても重複しない。

    python 緑内障点眼解析/add_rounded_columns.py            # 03_解析結果/ 配下を更新
    python 緑内障点眼解析/add_rounded_columns.py --dir <path>

丸め規則（allergy解析と同一）:
  処方数量・人口     : 整数
  人口10万対（率）   : 整数
  割合・シェア(%)    : 小数1桁
  割合（比率0-1）    : 小数3桁（%換算で1桁相当）
  比（M:F・最大/最小）: 小数3桁
  CV・Gini           : 小数3桁
  回帰係数・標準誤差・t値 : 小数3桁
  APC(%)             : 小数2桁
  R²                 : 小数4桁
  加重平均年齢・年   : 小数1桁
  p値                : 生値保持＋表示用（3桁、0.001未満は<0.001）
"""
import argparse
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))
from paths import RESULT_SUBDIR, add_nokouhi_arg, data_root  # noqa: E402

# 列名の完全一致で決まるもの
DIGITS_EXACT = {
    "share": 3, "share_top3": 3, "hhi": 3, "theil_t": 3,
    "mf_ratio_count": 3, "mf_ratio_rate": 3, "max_to_min_ratio": 3,
    "cv": 3, "gini": 3, "cv_start": 3, "cv_end": 3,
    "coefficient": 3, "std_err": 3, "t_stat": 3,
    "sigma_slope": 3, "beta_coefficient": 3,
    "apc": 2, "apc_low": 2, "apc_high": 2,
    "r2": 4, "r2_within": 4, "beta_r2": 4,
    "spearman_rho_aging": 3, "spearman_rho_docs": 3, "spearman_rho_facilities": 3,
    "weighted_mean_age": 1, "start_year": 1, "end_year": 1,
    "mean_rate_per_100k": 0, "min_rate": 0, "max_rate": 0,
    "specialization_score": 6, "log_mean_rate": 3,
    "ml_per_unit": 1, "pref_censor_rate": 3, "pref_coverage_ratio": 3,
    "ml_lost_rate": 4,
}
# p値と同じ扱いをする列（生値保持＋表示用文字列）
P_COLUMNS = {"p_value", "p_value_aging", "p_value_docs", "p_value_facilities",
             "sigma_p_value", "beta_p_value"}


def fmt_p(p):
    if pd.isna(p):
        return ""
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def digits_for(col):
    """列名から丸め桁数を決定する。対象外なら None。"""
    if col in DIGITS_EXACT:
        return DIGITS_EXACT[col]
    if col.endswith("_pct") or col.startswith("share_pct"):
        return 1
    if "人口10万対" in col or col.startswith("count_per_100k"):
        return 0
    if col.startswith("count") or col.startswith("quantity") or col in (
        "total", "total_count", "population", "pref_sum_ml",
        "ml_lost_to_censoring",
    ):
        return 0
    if col.startswith("population_") or col.endswith("_ml"):
        return 0
    return None


def process(path):
    df = pd.read_csv(path)
    df = df[[c for c in df.columns
             if not c.endswith("_rounded") and not c.endswith("_display")]]

    cols, added = [], []
    for c in df.columns:
        cols.append(c)
        if c in P_COLUMNS:
            df[f"{c}_display"] = df[c].map(fmt_p)
            cols.append(f"{c}_display")
            added.append(f"{c}->表示用(3桁/<0.001)")
            continue
        d = digits_for(c)
        if d is not None and df[c].dtype.kind == "f":
            rc = f"{c}_rounded"
            df[rc] = df[c].round(d)
            if d == 0:
                df[rc] = df[rc].astype("Int64")
            cols.append(rc)
            added.append(f"{c}->{d}桁")
    df[cols].to_csv(path, index=False, encoding="utf-8-sig")
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None,
                    help="対象ディレクトリ（既定: 03_解析結果/ 配下を再帰的に処理）")
    add_nokouhi_arg(ap)
    args = ap.parse_args()

    root = args.dir or os.path.join(data_root(args.nokouhi), RESULT_SUBDIR)
    n = 0
    for dirpath, _, files in os.walk(root):
        for name in sorted(f for f in files if f.endswith(".csv")):
            added = process(os.path.join(dirpath, name))
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            print(f"  {rel}: {len(added)}列追加")
            n += 1
    print(f"\n{n} ファイルに丸め列を付与しました。")


if __name__ == "__main__":
    main()
