# -*- coding: utf-8 -*-
"""
s03: 部分識別（bounds analysis）
秘匿セル（区間[1,9]）に 1 / 9 を代入した場合の Gini係数・CV・APC の
到達可能な上下限を計算する。指標の単調性は代入値に対して自明でないため、
下界・上界は {全て1, 全て9, 0補完, 5補完} の組合せではなく
1代入・9代入それぞれで指標を計算し min/max を取る保守的な範囲として報告する。
"""
import os
import numpy as np
import pandas as pd
from scipy import stats

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return np.nan
    cum = np.cumsum(x)
    return (n + 1 - 2 * (cum / cum[-1]).sum()) / n


def cv(x):
    x = np.asarray(x, dtype=float)
    return x.std(ddof=1) / x.mean() if x.mean() > 0 else np.nan


def apc(years, counts):
    """対数線形回帰によるAPC(%)。counts>0 の年のみ使用。"""
    y = np.asarray(counts, dtype=float)
    t = np.asarray(years, dtype=float)
    mask = y > 0
    if mask.sum() < 3:
        return np.nan
    slope = stats.linregress(t[mask], np.log(y[mask])).slope
    return (np.exp(slope) - 1) * 100


def run():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from structural import clean_structural

    df = pd.read_csv(os.path.join(OUT_DIR, "cells_with_censoring_flag.csv"))
    # 構造的欠測（全県秘匿の層・層数が異なる年）をコード別に除外
    df = pd.concat(
        [clean_structural(dc, label=code) for code, dc in df.groupby("code")],
        ignore_index=True,
    )
    # 同一 code×year×prefecture の複数層（外来/入院）は合算。
    # 秘匿セルの合算は代入値の合算として扱う。
    rows = []
    for imput in (1, 9):
        d = df.copy()
        d["count"] = d["count"].fillna(imput)
        g = d.groupby(["code", "year", "prefecture"], as_index=False)["count"].sum()
        g["imput"] = imput
        rows.append(g)
    panel = pd.concat(rows, ignore_index=True)

    # --- Gini / CV の bounds（code×year） ---
    disp = (
        panel.groupby(["code", "year", "imput"])["count"]
        .agg([gini, cv])
        .reset_index()
        .pivot_table(index=["code", "year"], columns="imput", values=["gini", "cv"])
    )
    disp.columns = [f"{m}_imput{i}" for m, i in disp.columns]
    for m in ("gini", "cv"):
        disp[f"{m}_lower"] = disp[[f"{m}_imput1", f"{m}_imput9"]].min(axis=1)
        disp[f"{m}_upper"] = disp[[f"{m}_imput1", f"{m}_imput9"]].max(axis=1)
        disp[f"{m}_width"] = disp[f"{m}_upper"] - disp[f"{m}_lower"]
    disp = disp.round(3)
    disp.to_csv(os.path.join(OUT_DIR, "bounds_disparity.csv"), encoding="utf-8-sig")

    # --- 全国合計APCの bounds（code） ---
    apc_rows = []
    for code, dc in panel.groupby("code"):
        rec = {"code": code}
        for imput in (1, 9):
            nat = dc[dc["imput"] == imput].groupby("year")["count"].sum()
            rec[f"apc_imput{imput}"] = apc(nat.index, nat.values)
        vals = [rec["apc_imput1"], rec["apc_imput9"]]
        rec["apc_lower"], rec["apc_upper"] = np.nanmin(vals), np.nanmax(vals)
        rec["apc_width"] = rec["apc_upper"] - rec["apc_lower"]
        apc_rows.append(rec)
    apc_df = pd.DataFrame(apc_rows).round(3)
    apc_df.to_csv(os.path.join(OUT_DIR, "bounds_apc.csv"), index=False, encoding="utf-8-sig")

    print("=== Gini識別区間の幅（コード別平均, 降順） ===")
    print(disp.groupby("code")["gini_width"].mean().sort_values(ascending=False).round(3).to_string())
    print("\n=== APC bounds（コード別） ===")
    print(apc_df.to_string(index=False))


if __name__ == "__main__":
    run()
