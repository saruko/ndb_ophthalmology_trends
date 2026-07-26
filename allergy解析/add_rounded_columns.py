# -*- coding: utf-8 -*-
"""
論文用CSVを processed/ から更新し、丸め済み列を併記する。

対象: 論文に使うCSV/ と 論文に使うファイルたち/
各数値列 X の直後に X_rounded を追加する。実データ（X）はそのまま保持し、
論文表記に用いる丸め値（X_rounded）を並べて確認できるようにする。
p値のみ、生値を保持したうえで表示用文字列 p_value_display を併記する
（3桁に丸めると p=1e-8 が 0.000 となり有意性情報が失われるため）。

既存の _rounded / _display 列は毎回作り直すため、再実行しても重複しない。

丸め規則（解析スクリプト統一規則に準拠）:
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
import os
import shutil
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
PROCESSED = os.path.join(BASE, "processed")
TARGET_DIRS = [os.path.join(BASE, "論文に使うCSV"),
               os.path.join(BASE, "論文に使うファイルたち")]

# 列名の完全一致で決まるもの
DIGITS_EXACT = {
    "share": 3, "share_top3": 3,
    "mf_ratio_count": 3, "mf_ratio_rate": 3, "max_to_min_ratio": 3,
    "cv": 3, "gini": 3,
    "coefficient": 3, "std_err": 3, "t_stat": 3,
    "apc": 2, "apc_low": 2, "apc_high": 2,
    "r2": 4, "r2_within": 4,
    "weighted_mean_age": 1, "start_year": 1, "end_year": 1,
    "mean_rate_per_100k": 0, "min_rate": 0, "max_rate": 0,
}


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
        "total", "total_count", "LX_0.1pct", "standard_0.05pct",
        "LX_0.1pct_brand", "LX_0.1pct_generic",
        "standard_0.05pct_brand", "standard_0.05pct_generic",
    ):
        return 0
    return None


def process(path):
    df = pd.read_csv(path)
    df = df[[c for c in df.columns
             if not c.endswith("_rounded") and c != "p_value_display"]]

    cols, added = [], []
    for c in df.columns:
        cols.append(c)
        if c == "p_value":
            df["p_value_display"] = df[c].map(fmt_p)
            cols.append("p_value_display")
            added.append("p_value->表示用(3桁/<0.001)")
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
    for out_dir in TARGET_DIRS:
        print(f"\n### {os.path.basename(out_dir)} ###")
        for name in sorted(f for f in os.listdir(out_dir) if f.endswith(".csv")):
            dst = os.path.join(out_dir, name)
            src = os.path.join(PROCESSED, name)
            if os.path.exists(src):
                shutil.copyfile(src, dst)  # processed/ の最新データで更新
            added = process(dst)
            print(f"  {name}: {len(added)}列追加")


if __name__ == "__main__":
    main()
