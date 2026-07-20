# -*- coding: utf-8 -*-
"""
s09: 多重代入によるGini係数への不確実性伝播
打ち切りNB-MLEの漸近分布 N(theta_hat, Sigma_hat) からパラメータを M 回抽出し、
各抽出でのモデル下の切断分布（1<=Y<=9）から秘匿セル値をサンプリングして
Gini係数を再計算する。これによりパラメータ不確実性と秘匿セルの残余不確実性の
双方を反映した年度別Giniの95%区間を得る（plug-in条件付き期待値置換の上位互換）。
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")

from s03_bounds_analysis import gini  # noqa: E402
from s05_censored_mle import fit_censored, TARGET_CODES  # noqa: E402
from structural import clean_structural  # noqa: E402

M = 500
RNG = np.random.default_rng(20260712)


def truncated_nb_sample(mu, k, rng):
    """区間[1,9]で切断したNBからのサンプル（pmf正規化による逆変換）"""
    ks = np.arange(1, 10)
    pnb = k / (k + mu[:, None])
    pmf = stats.nbinom.pmf(ks[None, :], k, pnb)
    pmf = pmf / pmf.sum(axis=1, keepdims=True)
    u = rng.random(len(mu))
    return ks[(pmf.cumsum(axis=1) < u[:, None]).sum(axis=1).clip(0, 8)]


def run():
    df = pd.read_csv(os.path.join(OUT_DIR, "cells_with_censoring_flag.csv"))
    all_rows = []
    for code in TARGET_CODES:
        dc = df[df["code"] == code].copy()
        if dc.empty:
            continue
        dc = clean_structural(dc, verbose=False)
        dc.loc[dc["is_censored"], "count"] = np.nan
        dc = dc.reset_index(drop=True)
        fit = fit_censored(dc, family="nb", compute_se=True)
        if fit["cov"] is None:
            print(f"{code}: 共分散行列が特異のためスキップ")
            continue
        theta, cov, n_pref = fit["params"], fit["cov"], fit["n_pref"]
        # 共分散行列を対称化し、最近接の半正定値行列に射影
        cov = (cov + cov.T) / 2
        w, V = np.linalg.eigh(cov)
        cov = V @ np.diag(np.clip(w, 1e-12, None)) @ V.T

        cens = dc["is_censored"].values.astype(bool)
        y_obs = dc["count"].values.astype(float)
        ginis = []  # M × 年度平均Gini
        draws = RNG.multivariate_normal(theta, cov, size=M)
        for d in draws:
            mu = np.exp(np.clip(d[fit["pidx"]] + d[n_pref] * fit["t"], -20, 20))
            k = np.exp(np.clip(d[n_pref + 1], -10, 10))
            y = y_obs.copy()
            y[cens] = truncated_nb_sample(mu[cens], k, RNG)
            t2 = dc.assign(count=y)
            pref_year = t2.groupby(["year", "prefecture"])["count"].sum()
            ginis.append(pref_year.groupby("year").apply(gini).mean())
        ginis = np.array(ginis)
        # 比較: plug-in（条件付き期待値置換, 点推定パラメータ）
        all_rows.append({
            "code": code, "n_imputation": M,
            "gini_mi_mean": ginis.mean(),
            "gini_mi_2.5": np.percentile(ginis, 2.5),
            "gini_mi_97.5": np.percentile(ginis, 97.5),
            "gini_mi_sd": ginis.std(ddof=1),
        })
        print(f"{code}: Gini(年度平均) = {ginis.mean():.4f} "
              f"[{np.percentile(ginis,2.5):.4f}, {np.percentile(ginis,97.5):.4f}]")

    out = pd.DataFrame(all_rows).round(4)
    out.to_csv(os.path.join(OUT_DIR, "bayes_mi_gini.csv"),
               index=False, encoding="utf-8-sig")
    print("saved: bayes_mi_gini.csv")


if __name__ == "__main__":
    run()
