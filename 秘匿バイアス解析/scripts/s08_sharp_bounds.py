# -*- coding: utf-8 -*-
"""
s08: シャープな識別区間
(1) APC: 厳密解。対数線形回帰の傾きは beta = sum_t c_t log S_t（c_t は年の中心化重み）で、
    log は単調なので、S_t を c_t > 0 の年は最大化（秘匿セル=9）、c_t < 0 の年は
    最小化（=1）すれば厳密な上限が得られる（下限は逆）。端点代入（全セル同値）と異なり
    年ごとに代入方向を変えるため、これは区間 [1,9]^m 上の真の最大・最小である。
(2) Gini: 目的関数がセル値に非単調のため厳密解は組合せ最適化になる。都道府県別の
    秘匿合計値（区間 [n_c, 9*n_c]）を座標とする座標降下（グリッド探索）を
    複数初期値から実行し、端点代入より広い改良区間を得る。局所解の可能性があるため
    厳密なシャープ区間の内側近似だが、端点代入区間を下回ることはない。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")

from s03_bounds_analysis import gini  # noqa: E402
from structural import clean_structural  # noqa: E402


def sharp_apc_bounds(dc):
    """厳密なAPCシャープ区間。dc: 単一コードのセルDF（構造的欠測除外済み）"""
    obs = dc.groupby("year").apply(
        lambda g: g.loc[~g["is_censored"], "count"].sum())
    ncen = dc.groupby("year")["is_censored"].sum()
    years = np.array(sorted(obs.index))
    t = years - years.mean()
    c = t / (t ** 2).sum()  # 回帰重み

    def slope(assign_hi_when_positive):
        s = np.array([
            obs[y] + ncen[y] * (9 if (c[i] > 0) == assign_hi_when_positive else 1)
            for i, y in enumerate(years)
        ], dtype=float)
        if (s <= 0).any():
            return np.nan
        return np.polyfit(t, np.log(s), 1)[0]

    b_hi, b_lo = slope(True), slope(False)
    return ((np.exp(b_lo) - 1) * 100, (np.exp(b_hi) - 1) * 100)


def gini_search(fixed, lo, hi, maximize, n_starts=5, grid=17, seed=0):
    """
    座標降下によるGiniの最大化/最小化。
    fixed: 各都道府県の観測部分合計, lo/hi: 秘匿合計の下限/上限（同順）
    """
    rng = np.random.default_rng(seed)
    m = len(fixed)
    free = hi > lo
    best_val, sign = -np.inf, (1 if maximize else -1)
    starts = [lo.copy(), hi.copy(), (lo + hi) / 2]
    for _ in range(n_starts - 3):
        starts.append(lo + (hi - lo) * rng.random(m))
    for x in starts:
        x = x.copy()
        improved = True
        while improved:
            improved = False
            for i in np.where(free)[0]:
                cand = np.linspace(lo[i], hi[i], grid)
                vals = []
                for v in cand:
                    x[i] = v
                    vals.append(sign * gini(fixed + x))
                j = int(np.argmax(vals))
                if vals[j] > sign * gini(fixed + x) - 1e-12:
                    x[i] = cand[j]
                cur = sign * gini(fixed + x)
                if cur > best_val + 1e-10:
                    improved = True
            best_val = max(best_val, sign * gini(fixed + x))
    return sign * best_val


def run():
    df = pd.read_csv(os.path.join(OUT_DIR, "cells_with_censoring_flag.csv"))
    df = pd.concat(
        [clean_structural(dc, verbose=False) for _, dc in df.groupby("code")],
        ignore_index=True)

    # --- (1) APC 厳密シャープ区間 ---
    ep = pd.read_csv(os.path.join(OUT_DIR, "bounds_apc.csv"))
    rows = []
    for code, dc in df.groupby("code"):
        try:
            lo, hi = sharp_apc_bounds(dc)
        except Exception:
            lo = hi = np.nan
        rows.append({"code": code, "apc_sharp_lower": lo, "apc_sharp_upper": hi})
    sharp = pd.DataFrame(rows).merge(
        ep[["code", "apc_lower", "apc_upper"]], on="code", how="left")
    sharp["sharp_width"] = sharp["apc_sharp_upper"] - sharp["apc_sharp_lower"]
    sharp["endpoint_width"] = sharp["apc_upper"] - sharp["apc_lower"]
    sharp = sharp.round(3)
    sharp.to_csv(os.path.join(OUT_DIR, "sharp_bounds_apc.csv"),
                 index=False, encoding="utf-8-sig")
    print("=== APC: 厳密シャープ区間 vs 端点代入区間 ===")
    print(sharp.to_string(index=False))

    # --- (2) Gini 座標降下区間 ---
    grows = []
    for (code, year), dc in df.groupby(["code", "year"]):
        g = dc.groupby("prefecture").apply(lambda x: pd.Series({
            "fixed": x.loc[~x["is_censored"], "count"].sum(),
            "ncen": x["is_censored"].sum()}))
        fixed = g["fixed"].values.astype(float)
        lo = g["ncen"].values.astype(float) * 1
        hi = g["ncen"].values.astype(float) * 9
        if (hi > lo).sum() == 0:
            gmin = gmax = gini(fixed + lo)
        else:
            gmin = gini_search(fixed, lo, hi, maximize=False)
            gmax = gini_search(fixed, lo, hi, maximize=True)
        grows.append({"code": code, "year": year,
                      "gini_sharp_lower": gmin, "gini_sharp_upper": gmax,
                      "gini_sharp_width": gmax - gmin})
    gdf = pd.DataFrame(grows).round(3)
    gdf.to_csv(os.path.join(OUT_DIR, "sharp_bounds_gini.csv"),
               index=False, encoding="utf-8-sig")
    ep_g = pd.read_csv(os.path.join(OUT_DIR, "bounds_disparity.csv"))
    cmp = gdf.merge(ep_g[["code", "year", "gini_width"]], on=["code", "year"])
    summary = cmp.groupby("code")[["gini_sharp_width", "gini_width"]].mean().round(3)
    print("\n=== Gini: 座標降下区間幅 vs 端点代入区間幅（コード平均） ===")
    print(summary.to_string())


if __name__ == "__main__":
    run()
