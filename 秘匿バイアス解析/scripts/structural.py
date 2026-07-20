# -*- coding: utf-8 -*-
"""
構造的欠測の除外ルール（s03 / s05 共通）

NDBオープンデータの "-" は通常「10件未満秘匿」（区間 [1,9]）だが、
ある code×year×stratum の全47都道府県が "-" の場合、それは閾値秘匿ではなく
項目レベルの非公表・集計対象外とみなすのが妥当（例: K281 の 2016年入院層は
前後年に各県1000件超があるのに全県 "-"）。この場合セルを [1,9] として
扱うと大きなバイアスを生むため、解析から除外する。

同様に、年によって層数が異なる場合（例: 2014年は1シート構成）は
レベルが比較不能なため、最頻層数と一致する年のみを残す。
"""
import pandas as pd


def clean_structural(dc, verbose=True, label=""):
    """dc: 単一コードのセルDF (year, prefecture, stratum, count, is_censored)"""
    # 1) 全県秘匿の year×stratum を除外（項目レベル欠測）
    grp = dc.groupby(["year", "stratum"])["is_censored"].mean()
    bad = grp[grp >= 1.0].index.tolist()
    if bad:
        if verbose:
            print(f"{label}: 全県秘匿のため除外 (year, stratum) = {bad}")
        mask = ~dc.set_index(["year", "stratum"]).index.isin(bad)
        dc = dc[mask]

    # 2) 層数が最頻値と異なる年を除外
    n_strata = dc.groupby("year")["stratum"].nunique()
    modal = n_strata.mode().iloc[0]
    keep_years = n_strata[n_strata == modal].index
    dropped = sorted(set(n_strata.index) - set(keep_years))
    if dropped and verbose:
        print(f"{label}: 層構造が異なる年 {dropped} を除外（最頻層数={modal}）")
    return dc[dc["year"].isin(keep_years)].copy()
