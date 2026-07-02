#!/usr/bin/env python3
"""
rate_and_trend_analysis.py

チェックリスト項目2・4・5に対応:
  2. 人口10万対rateへの変換し、粗数トレンドとの方向一致を確認
  4. 虹彩・毛様体・脈絡膜腫瘍切除術（K265, K266）はデータ不足のため分析対象外と明記
  5. Poisson回帰によるtrend test（傾向性検定）でp値・95%CIを算出

rate変換・trend testには、年齢・性別クロス集計由来の合計値ではなく
眼腫瘍手術トレンド_2014_2023.csv（都道府県別集計由来、秘匿の影響が小さい真の全国算定回数）を用いる。
年齢・性別クロス集計は個々のセルが10件未満で頻繁にマスクされるため、
そこから再合算した値は低頻度術式ほど過小評価される（extract_age_stratified.pyの整合性チェックで確認済み）。

入力:
  眼腫瘍解析/眼腫瘍手術トレンド_2014_2023.csv （都道府県別集計由来の真の全国合計、年次）
  眼腫瘍解析/人口_4群層別化_2014_2023.csv （4群人口、年次）
出力:
  眼腫瘍解析/rate_per_100k_national_trend.csv   （全年齢人口10万対rateの年次推移）
  眼腫瘍解析/poisson_trend_test_results.csv     （術式別 Poisson回帰トレンド検定結果）
"""
import os
import numpy as np
import pandas as pd
import statsmodels.api as sm

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # 眼腫瘍解析/

# K265（虹彩腫瘍切除術）, K266（毛様体腫瘍切除術・脈絡膜腫瘍切除術）は
# NDBオープンデータの年齢・性別クロス集計で秘匿(10件未満マスク)により
# ほぼ全年度・全年齢階級で計上不能（extract_age_stratified.pyの整合性チェックで確認済み、
# 多くの年で年齢別合計が全国合計の0〜数%しか復元できない）。
# 全国合計自体も年間0〜19件と極めて少数であり、年齢階級別・rate換算・trend testのいずれも
# 統計的に意味のある推定を行えないため、本解析では「データ不足のため分析対象外」として除外する。
EXCLUDED_CODES = {"K265", "K266"}

# K225-4（角結膜悪性腫瘍切除術）は2022年度診療報酬改定でコード新設のため、
# 観測期間が2022-2023年の2年分のみ。10年間のtrend testの対象としては不適切なため
# 参考値（改定前後の比較）にとどめ、Poisson回帰の対象からは除外する。
NEW_CODE_MIN_YEARS = 2022

# K225（結膜腫瘍冷凍凝固術）は2022年度にK225-4が新設されたことで
# 2023年に算定回数が急減（前年比-73%）しており、2014-2023の10年を単一線形モデルで
# 回帰すると断絶が「なだらかな増加」に均されてしまい、実態を反映しない。
# そのため改定前（2014-2021年）の8年間のみでPoisson trend testを実施する。
K225_REFORM_YEAR = 2022


def poisson_trend_test(df_code):
    """
    count ~ year (offset = log(全年齢人口)) のPoisson回帰でAPC・p値・95%CIを算出する。
    """
    df_code = df_code.sort_values("year")
    y = df_code["count"].values
    year = df_code["year"].values
    offset = np.log(df_code["population_total"].values)

    X = sm.add_constant(year.astype(float))
    model = sm.GLM(y, X, family=sm.families.Poisson(), offset=offset)
    result = model.fit()

    b1 = result.params[1]
    b1_se = result.bse[1]
    p_value = result.pvalues[1]
    ci_low, ci_high = result.conf_int()[1]

    apc = (np.exp(b1) - 1) * 100
    apc_ci_low = (np.exp(ci_low) - 1) * 100
    apc_ci_high = (np.exp(ci_high) - 1) * 100

    return {
        "apc_percent": apc,
        "apc_ci_low": apc_ci_low,
        "apc_ci_high": apc_ci_high,
        "p_value": p_value,
        "n_years": len(df_code),
    }


def main():
    df_total = pd.read_csv(os.path.join(BASE_DIR, "眼腫瘍手術トレンド_2014_2023.csv"))
    df_pop = pd.read_csv(os.path.join(BASE_DIR, "人口_4群層別化_2014_2023.csv"))

    # 全年齢人口（千人 -> 人）を年次で算出
    pop_national = (
        df_pop.groupby("year", as_index=False)["population_thousands"].sum()
    )
    pop_national["population_total"] = pop_national["population_thousands"] * 1000

    # Total_Count は「-」（10件未満秘匿）を含むため0に補完（main pipelineのzero補完方針に合わせる）
    df_total["count"] = pd.to_numeric(df_total["Total_Count"].replace("-", 0), errors="coerce").fillna(0)
    df_total = df_total.rename(columns={"Actual_K_Code": "k_code_group", "Year": "year"})

    # 外来/入院/全体（2014年のみ）を年ごとに合算。K266は行動名称が2種類あるが
    # k_code_group単位で合算してから解析対象コードを確定する
    df_agg = df_total.groupby(["year", "k_code_group"], as_index=False)["count"].sum()

    # ── rate per 100k（全年齢, 全国） ──
    df_rate = pd.merge(df_agg, pop_national[["year", "population_total"]], on="year", how="left")
    df_rate["count_per_100k"] = df_rate["count"] / df_rate["population_total"] * 100000
    rate_out = os.path.join(BASE_DIR, "rate_per_100k_national_trend.csv")
    df_rate.sort_values(["k_code_group", "year"]).to_csv(rate_out, index=False, encoding="utf-8-sig")
    print(f"Saved: {rate_out} (shape={df_rate.shape})")

    # 粗数トレンドとrateトレンドの方向一致チェック（2014->2023の増減方向）
    print("\n=== 粗数 vs rate トレンド方向の一致チェック（2014年→2023年） ===")
    consistency_rows = []
    for code, g in df_rate.groupby("k_code_group"):
        g = g.sort_values("year")
        if len(g) < 2:
            continue
        raw_dir = np.sign(g["count"].iloc[-1] - g["count"].iloc[0])
        rate_dir = np.sign(g["count_per_100k"].iloc[-1] - g["count_per_100k"].iloc[0])
        match = raw_dir == rate_dir
        consistency_rows.append({"k_code_group": code, "raw_direction": raw_dir, "rate_direction": rate_dir, "match": match})
        flag = "OK" if match else "MISMATCH"
        print(f"  {code}: raw_dir={raw_dir:+.0f} rate_dir={rate_dir:+.0f} [{flag}]")

    # ── Poisson trend test（K265, K266は除外） ──
    results = []
    for code, g in df_rate.groupby("k_code_group"):
        if code in EXCLUDED_CODES:
            results.append({
                "k_code_group": code, "apc_percent": np.nan, "apc_ci_low": np.nan,
                "apc_ci_high": np.nan, "p_value": np.nan, "n_years": len(g),
                "note": "データ不足のため分析対象外（K265/K266は年齢・性別クロス集計の秘匿により大部分が欠測）",
            })
            continue
        if code == "K225-4":
            results.append({
                "k_code_group": code, "apc_percent": np.nan, "apc_ci_low": np.nan,
                "apc_ci_high": np.nan, "p_value": np.nan, "n_years": len(g),
                "note": f"2022年度診療報酬改定でコード新設のため{NEW_CODE_MIN_YEARS}-2023年の2年分のみ。"
                        "10年trend testの対象外（改定前後の参考値のみ算出可）",
            })
            continue
        if code == "K225":
            # 2022年度K225-4新設により2023年に算定回数が急減（前年比-73%）しており、
            # 10年通しの単一線形Poissonモデルは構造的断絶を均すため不適切。
            # 改定前（2014-2021年）の8年間のみでtrend testを実施する。
            g_pre = g[g["year"] < K225_REFORM_YEAR]
            res = poisson_trend_test(g_pre)
            res["k_code_group"] = code
            res["note"] = (
                f"2022年度K225-4新設による構造的断絶のため、改定前（2014-{K225_REFORM_YEAR - 1}年）"
                f"の{len(g_pre)}年間のみでtrend testを実施。"
                "2022年463件→2023年123件（前年比-73%）はK225-4への症例移行が関連する可能性。"
                "10年通しの単一線形回帰（APC +1.4%）は断絶を均すため採用しない。"
            )
            results.append(res)
            continue
        if g["count"].sum() == 0:
            results.append({
                "k_code_group": code, "apc_percent": np.nan, "apc_ci_low": np.nan,
                "apc_ci_high": np.nan, "p_value": np.nan, "n_years": len(g),
                "note": "全年度で件数0（年齢別集計上の秘匿等）のためPoisson回帰不能",
            })
            continue
        res = poisson_trend_test(g)
        res["k_code_group"] = code
        res["note"] = ""
        results.append(res)

    df_results = pd.DataFrame(results)[
        ["k_code_group", "n_years", "apc_percent", "apc_ci_low", "apc_ci_high", "p_value", "note"]
    ]
    trend_out = os.path.join(BASE_DIR, "poisson_trend_test_results.csv")
    df_results.sort_values("k_code_group").to_csv(trend_out, index=False, encoding="utf-8-sig")
    print(f"\nSaved: {trend_out}")
    print(df_results.sort_values("k_code_group").to_string(index=False))


if __name__ == "__main__":
    main()
