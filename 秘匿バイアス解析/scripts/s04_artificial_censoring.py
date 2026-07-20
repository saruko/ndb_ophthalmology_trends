# -*- coding: utf-8 -*-
"""
s04: 人工秘匿実験
秘匿のほぼ無い大件数コード（K282系）を binomial thinning で縮小して
小セルを人工的に発生させ、10未満秘匿を適用したうえで
各補完法（zero / five / random / midpoint=5と同値 / bounds）の
Gini・APC 推定誤差を真値と比較する。
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")

from s03_bounds_analysis import gini, apc  # noqa: E402

RNG = np.random.default_rng(20260712)
THINNING = [0.001, 0.0005, 0.0002, 0.0001]  # K282は年間十数万件規模のためこの範囲で小セルが発生
N_REP = 200


def impute(counts_true, strategy):
    """counts_true: 真の縮小後カウント。10未満を秘匿→補完した配列を返す。"""
    c = counts_true.astype(float).copy()
    mask = (c > 0) & (c < 10)
    if strategy == "zero":
        c[mask] = 0
    elif strategy == "five":
        c[mask] = 5
    elif strategy == "random":
        c[mask] = RNG.integers(1, 10, mask.sum())
    return c, mask


def run():
    df = pd.read_csv(os.path.join(OUT_DIR, "cells_with_censoring_flag.csv"))
    base = (
        df[(df["code"].str.startswith("K282")) & (~df["is_censored"])]
        .groupby(["year", "prefecture"], as_index=False)["count"].sum()
    )
    print(f"ベースデータ: K282 {len(base)} cells, 総件数 {base['count'].sum():,.0f}")

    results = []
    for p in THINNING:
        for rep in range(N_REP):
            thinned = base.copy()
            thinned["count"] = RNG.binomial(thinned["count"].astype(int), p)
            # 真値の指標
            true_gini = thinned.groupby("year")["count"].apply(gini).mean()
            nat = thinned.groupby("year")["count"].sum()
            true_apc = apc(nat.index, nat.values)
            cens_rate = ((thinned["count"] > 0) & (thinned["count"] < 10)).mean()
            for strat in ("zero", "five", "random"):
                c, _ = impute(thinned["count"].values, strat)
                t2 = thinned.assign(count=c)
                est_gini = t2.groupby("year")["count"].apply(gini).mean()
                nat2 = t2.groupby("year")["count"].sum()
                est_apc = apc(nat2.index, nat2.values)
                results.append({
                    "thinning": p, "rep": rep, "strategy": strat,
                    "censoring_rate": cens_rate,
                    "gini_bias": est_gini - true_gini,
                    "apc_bias": est_apc - true_apc,
                })

    res = pd.DataFrame(results)
    res.to_csv(os.path.join(OUT_DIR, "artificial_censoring_raw.csv"), index=False, encoding="utf-8-sig")

    summ = (
        res.groupby(["thinning", "strategy"])
        .agg(censoring_rate=("censoring_rate", "mean"),
             gini_bias_mean=("gini_bias", "mean"),
             gini_bias_sd=("gini_bias", "std"),
             apc_bias_mean=("apc_bias", "mean"),
             apc_bias_sd=("apc_bias", "std"))
        .round(4)
    )
    summ.to_csv(os.path.join(OUT_DIR, "artificial_censoring_summary.csv"), encoding="utf-8-sig")
    print(summ.to_string())


if __name__ == "__main__":
    run()
