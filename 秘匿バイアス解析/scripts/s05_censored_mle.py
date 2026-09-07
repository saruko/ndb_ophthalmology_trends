# -*- coding: utf-8 -*-
"""
s05: 区間打ち切り尤度による最尤推定
モデル: log mu_it = alpha_i (都道府県固定効果) + beta * (year - year0)
尤度:   観測セル → Poisson pmf / 秘匿セル → P(1 <= Y <= 9) = F(9) - F(0)
APC は beta から直接 (exp(beta)-1)*100 として得られ、補完を経由しない。
秘匿セルの点推定が必要な場合は条件付き期待値 E[Y | 1<=Y<=9, mu] を用いる。
過分散対応として負の二項版（dispersion 共通）も推定する。
"""
import os
import numpy as np
import pandas as pd
from scipy import stats, optimize, special

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "processed")

TARGET_CODES = ["K281", "K281-2", "K268_iridectomy", "K268_device_plate", "K259", "K280-2"]


def _design(df):
    """観測単位（prefecture×stratum）のダミーインデックスと中心化した年を返す"""
    df = df.assign(unit=df["prefecture"].astype(str) + "_s" + df["stratum"].astype(str))
    prefs = sorted(df["unit"].unique())
    pidx = df["unit"].map({p: i for i, p in enumerate(prefs)}).values
    t = (df["year"] - df["year"].min()).values.astype(float)
    return prefs, pidx, t


def _neg_loglik_poisson(params, pidx, t, y, cens, n_pref):
    alpha, beta = params[:n_pref], params[n_pref]
    log_mu = alpha[pidx] + beta * t
    mu = np.exp(np.clip(log_mu, -20, 20))
    ll = 0.0
    if (~cens).any():
        yo, mo = y[~cens], mu[~cens]
        ll += np.sum(yo * np.log(mo) - mo - special.gammaln(yo + 1))
    if cens.any():
        mc = mu[cens]
        p = stats.poisson.cdf(9, mc) - stats.poisson.cdf(0, mc)
        ll += np.sum(np.log(np.clip(p, 1e-300, None)))
    return -ll


def _neg_loglik_nb(params, pidx, t, y, cens, n_pref):
    alpha, beta = params[:n_pref], params[n_pref]
    log_disp = params[n_pref + 1]
    k = np.exp(np.clip(log_disp, -10, 10))  # size parameter
    log_mu = alpha[pidx] + beta * t
    mu = np.exp(np.clip(log_mu, -20, 20))
    pnb = k / (k + mu)
    ll = 0.0
    if (~cens).any():
        ll += np.sum(stats.nbinom.logpmf(y[~cens], k, pnb[~cens]))
    if cens.any():
        p = stats.nbinom.cdf(9, k, pnb[cens]) - stats.nbinom.cdf(0, k, pnb[cens])
        ll += np.sum(np.log(np.clip(p, 1e-300, None)))
    return -ll


def _covariance(fun, xhat, args, eps=1e-4):
    """負の対数尤度のフルヘッセ行列（中心差分）の逆行列＝漸近共分散行列"""
    n = len(xhat)
    H = np.zeros((n, n))
    f0 = fun(xhat, *args)
    steps = eps * np.maximum(np.abs(xhat), 1.0)
    fp = np.zeros(n)
    fm = np.zeros(n)
    for i in range(n):
        xp = xhat.copy(); xp[i] += steps[i]
        xm = xhat.copy(); xm[i] -= steps[i]
        fp[i], fm[i] = fun(xp, *args), fun(xm, *args)
        H[i, i] = (fp[i] - 2 * f0 + fm[i]) / steps[i] ** 2
    for i in range(n):
        for j in range(i + 1, n):
            xpp = xhat.copy(); xpp[i] += steps[i]; xpp[j] += steps[j]
            fpp = fun(xpp, *args)
            H[i, j] = H[j, i] = (
                fpp - fp[i] - fp[j] + f0
            ) / (steps[i] * steps[j])
    try:
        return np.linalg.inv(H)
    except np.linalg.LinAlgError:
        return None


def fit_censored(df, family="poisson", compute_se=True):
    """
    df: columns [year, prefecture, stratum, count, is_censored]（countは秘匿セルでNaN可）
    returns dict(beta, apc, se_beta, converged, fitted mu array, prefs)
    """
    prefs, pidx, t = _design(df)
    n_pref = len(prefs)
    y = df["count"].fillna(0).values.astype(float)
    cens = df["is_censored"].values.astype(bool)

    # 初期値: 秘匿=5 とした都道府県平均の対数
    y_init = np.where(cens, 5.0, y)
    alpha0 = np.array([
        np.log(max(y_init[pidx == i].mean(), 0.5)) for i in range(n_pref)
    ])
    if family == "poisson":
        x0 = np.append(alpha0, 0.0)
        fun = _neg_loglik_poisson
    else:
        x0 = np.append(alpha0, [0.0, 0.0])
        fun = _neg_loglik_nb

    res = optimize.minimize(fun, x0, args=(pidx, t, y, cens, n_pref), method="L-BFGS-B")
    beta = res.x[n_pref]
    cov = _covariance(fun, res.x, (pidx, t, y, cens, n_pref)) if compute_se else None
    se = np.nan
    if cov is not None and cov[n_pref, n_pref] > 0:
        se = np.sqrt(cov[n_pref, n_pref])

    mu = np.exp(res.x[pidx] + beta * t)
    return {
        "beta": beta, "se_beta": se,
        "apc": (np.exp(beta) - 1) * 100,
        "apc_low": (np.exp(beta - 1.96 * se) - 1) * 100 if np.isfinite(se) else np.nan,
        "apc_high": (np.exp(beta + 1.96 * se) - 1) * 100 if np.isfinite(se) else np.nan,
        "converged": bool(res.success), "mu": mu, "prefs": prefs,
        "loglik": -res.fun, "family": family,
        "log_disp": res.x[n_pref + 1] if family == "nb" else np.nan,
        "params": res.x, "cov": cov, "n_pref": n_pref,
        "pidx": pidx, "t": t,
    }


def conditional_expectation(mu, family="poisson", k=None):
    """E[Y | 1<=Y<=9, mu]（秘匿セルのモデルベース補完値）"""
    ks = np.arange(1, 10)
    if family == "poisson":
        pmf = np.array([stats.poisson.pmf(j, mu) for j in ks])
    else:
        pnb = k / (k + mu)
        pmf = np.array([stats.nbinom.pmf(j, k, pnb) for j in ks])
    denom = pmf.sum(axis=0)
    return (ks[:, None] * pmf).sum(axis=0) / np.clip(denom, 1e-300, None)


def run():
    df = pd.read_csv(os.path.join(OUT_DIR, "cells_with_censoring_flag.csv"))
    # 観測単位はセル（year×prefecture×stratum）。stratum はシート由来（外来/入院）で、
    # 各セルの秘匿は独立に区間 [1,9]。年によって層数が異なる場合（例: 総計のみの年）は
    # 層構造が最頻値と一致する年のみを使用する。
    from structural import clean_structural
    rows = []
    for code in TARGET_CODES:
        dc = df[df["code"] == code].copy()
        if dc.empty:
            continue
        dc = clean_structural(dc, label=code)
        dc.loc[dc["is_censored"], "count"] = np.nan
        for family in ("poisson", "nb"):
            r = fit_censored(dc, family)
            rows.append({
                "code": code, "family": family, "n_cells": len(dc),
                "censoring_rate": dc["is_censored"].mean(),
                "apc": r["apc"], "apc_low": r["apc_low"], "apc_high": r["apc_high"],
                "converged": r["converged"], "loglik": r["loglik"],
            })
            print(f"{code} [{family}]: APC={r['apc']:.2f}% "
                  f"(95%CI {r['apc_low']:.2f}, {r['apc_high']:.2f}) "
                  f"censored={dc['is_censored'].mean():.1%} conv={r['converged']}")

    out = pd.DataFrame(rows).round(3)
    out.to_csv(os.path.join(OUT_DIR, "censored_mle_apc.csv"), index=False, encoding="utf-8-sig")
    print(f"\nsaved: censored_mle_apc.csv")
    return out


if __name__ == "__main__":
    run()
