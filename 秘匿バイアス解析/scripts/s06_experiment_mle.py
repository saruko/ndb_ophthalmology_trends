# -*- coding: utf-8 -*-
"""
s06: 人工秘匿実験への打ち切りMLEの追加
s04 と同一の binomial thinning 実験に、第4の手法として
区間打ち切りポアソンMLE（s05）を投入し、単一代入法との推定誤差を比較する。
- APC: モデルの beta から直接推定（補完を経由しない）
- Gini: 秘匿セルを条件付き期待値 E[Y|1<=Y<=9, mu] で置換して算出
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")

from s03_bounds_analysis import gini, apc  # noqa: E402
from s04_artificial_censoring import impute, THINNING  # noqa: E402
from s05_censored_mle import fit_censored, conditional_expectation  # noqa: E402

RNG = np.random.default_rng(20260712)
N_REP = 50


def run():
    df = pd.read_csv(os.path.join(OUT_DIR, "cells_with_censoring_flag.csv"))
    base = (
        df[(df["code"].str.startswith("K282")) & (~df["is_censored"])]
        .groupby(["year", "prefecture"], as_index=False)["count"].sum()
    )
    base["stratum"] = 0

    results = []
    for p in THINNING:
        for rep in range(N_REP):
            thinned = base.copy()
            thinned["count"] = RNG.binomial(base["count"].astype(int), p)
            true_gini = thinned.groupby("year")["count"].apply(gini).mean()
            nat = thinned.groupby("year")["count"].sum()
            true_apc = apc(nat.index, nat.values)
            mask = (thinned["count"] > 0) & (thinned["count"] < 10)

            # --- 単一代入 3法 ---
            for strat in ("zero", "five", "random"):
                c, _ = impute(thinned["count"].values, strat)
                t2 = thinned.assign(count=c)
                est_gini = t2.groupby("year")["count"].apply(gini).mean()
                nat2 = t2.groupby("year")["count"].sum()
                results.append({
                    "thinning": p, "rep": rep, "strategy": strat,
                    "censoring_rate": mask.mean(),
                    "gini_bias": est_gini - true_gini,
                    "apc_bias": apc(nat2.index, nat2.values) - true_apc,
                })

            # --- 打ち切りMLE（Poisson / NB） ---
            obs = thinned.copy()
            obs["is_censored"] = mask
            obs.loc[mask, "count"] = np.nan
            for family in ("poisson", "nb"):
                fit = fit_censored(obs, family=family, compute_se=False)
                k = np.exp(fit.get("log_disp", 0.0)) if family == "nb" else None
                c = obs["count"].values.astype(float).copy()
                c[mask.values] = conditional_expectation(
                    fit["mu"][mask.values], family, k=k)
                t2 = thinned.assign(count=c)
                est_gini = t2.groupby("year")["count"].apply(gini).mean()
                results.append({
                    "thinning": p, "rep": rep, "strategy": f"censored_mle_{family}",
                    "censoring_rate": mask.mean(),
                    "gini_bias": est_gini - true_gini,
                    "apc_bias": fit["apc"] - true_apc,
                })
        print(f"thinning={p} done")

    res = pd.DataFrame(results)
    res.to_csv(os.path.join(OUT_DIR, "experiment_mle_raw.csv"), index=False, encoding="utf-8-sig")
    summ = (
        res.groupby(["thinning", "strategy"])
        .agg(censoring_rate=("censoring_rate", "mean"),
             gini_bias_mean=("gini_bias", "mean"),
             gini_rmse=("gini_bias", lambda x: np.sqrt((x ** 2).mean())),
             apc_bias_mean=("apc_bias", "mean"),
             apc_rmse=("apc_bias", lambda x: np.sqrt((x ** 2).mean())))
        .round(3)
    )
    summ.to_csv(os.path.join(OUT_DIR, "experiment_mle_summary.csv"), encoding="utf-8-sig")
    print(summ.to_string())


if __name__ == "__main__":
    run()
