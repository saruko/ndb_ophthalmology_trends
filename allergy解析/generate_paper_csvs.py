#!/usr/bin/env python3
"""
generate_paper_csvs.py
論文 Fig/Table 用のCSVファイルを生成する。

出力先: allergy解析/論文に使うファイルたち/

生成ファイル:
  - fig1a_age_profile_2024.csv        (Fig 1A: 年齢群別 人口10万対処方量, 2024年度, both)
  - fig1b_age_sex_profile_2024.csv    (Fig 1B: 性別×年齢群 人口10万対処方量, 2024年度)
  - fig2_age_distribution_shift.csv   (Fig 2: 年齢分布シェア経年変化)
  - fig2_weighted_mean_age.csv        (Fig 2: 加重平均処方年齢の推移)
  - fig3_prefecture_ranking.csv       (Fig 3: 都道府県別ランキング) ※既存コピー
  - fig4_national_trends.csv          (Fig 4: 11年間トレンド) ※既存コピー
  - fig4_market_shares.csv            (Fig 4: 市場シェア推移) ※既存コピー
  - table1_drug_summary_2024.csv      (Table 1: 薬剤別処方量・シェア一覧, 2024年度)
  - table2_mf_ratio_2024.csv          (Table 2: M:F比の年齢プロファイル, 2024年度)
  - table3_prefecture_ranking_top3.csv (Table 3: 都道府県ランキング, 主要3成分合計)

原稿が定義する表は Table 1〜3 のみ。以下は対応する表がないため補足資料扱い:
  - supplementary_geographic_disparity.csv  (地域格差指標 CV・Gini) ※既存コピー
  - supplementary_apc_results.csv           (APC結果) ※既存コピー
  - supplementary_apc_joinpoint.csv         (Joinpoint APC) ※既存コピー
  - supplementary_panel_regression.csv      (パネル回帰結果) ※既存コピー
"""
import csv
import os
import shutil
import sys

import pandas as pd
import numpy as np

# ── パス設定 ──
BASE = os.path.dirname(os.path.abspath(__file__))
SUMMARY_DIR = os.path.join(BASE, "内容まとめ")
PROCESSED_DIR = os.path.join(BASE, "processed")
OUT_DIR = os.path.join(BASE, "論文に使うファイルたち")

os.makedirs(OUT_DIR, exist_ok=True)

# 年齢グループのソート用
AGE_ORDER_21 = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80-84", "85-89", "90-94", "95-99", "100+",
]
AGE_ORDER_19 = [
    "0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
    "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
    "80-84", "85-89", "90+",
]

# 年齢グループの代表年齢（加重平均計算用）
AGE_MIDPOINTS = {
    "0-4": 2, "5-9": 7, "10-14": 12, "15-19": 17, "20-24": 22,
    "25-29": 27, "30-34": 32, "35-39": 37, "40-44": 42, "45-49": 47,
    "50-54": 52, "55-59": 57, "60-64": 62, "65-69": 67, "70-74": 72,
    "75-79": 77, "80-84": 82, "85-89": 87, "90-94": 92, "95-99": 97,
    "100+": 100, "90+": 92,
}


def _save(df, filename, index=False):
    path = os.path.join(OUT_DIR, filename)
    df.to_csv(path, index=index, encoding="utf-8-sig")
    print(f"  → {filename} ({len(df)} rows)")
    return path


def _copy(src_dir, src_name, dst_name):
    src = os.path.join(src_dir, src_name)
    dst = os.path.join(OUT_DIR, dst_name)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  → {dst_name} (コピー)")
    else:
        print(f"  ⚠ {src_name} が見つかりません")


def _check_age_labels(series, known):
    """既知の年齢グループラベルに無いものがあればエラー"""
    unknown = sorted(set(series.astype(str)) - set(known))
    if unknown:
        raise ValueError(
            f"未知の age_group ラベルがあります（ExcelでCSVを保存し日付に化けた可能性）: {unknown}"
        )


def sort_age(df, col="age_group"):
    """年齢グループを正しい順序でソート"""
    # 両方のリストを結合して順序マップを作成
    all_ages = AGE_ORDER_21 + ["90+"]
    _check_age_labels(df[col], all_ages)
    order_map = {ag: i for i, ag in enumerate(all_ages)}
    df = df.copy()
    df["_age_sort"] = df[col].map(order_map)
    df = df.sort_values("_age_sort").drop(columns="_age_sort")
    return df


def generate_fig1a():
    """Fig 1A: 年齢群別 人口10万対処方量（2024年度, 男女合算, 全薬剤合計 + 薬剤別）"""
    print("\n=== Fig 1A ===")
    rates = pd.read_csv(os.path.join(PROCESSED_DIR, "age_sex_rates_allergy.csv"))
    
    # 2024年度, both（男女合算）
    mask = (rates["year"] == 2024) & (rates["sex"] == "both")
    df = rates[mask][["code", "procedure_name", "age_group", "count", "population", "count_per_100k"]].copy()
    df = sort_age(df)
    _save(df, "fig1a_age_profile_2024.csv")


def generate_fig1b():
    """Fig 1B: 性別×年齢群 人口10万対処方量（2024年度）"""
    print("\n=== Fig 1B ===")
    rates = pd.read_csv(os.path.join(PROCESSED_DIR, "age_sex_rates_allergy.csv"))
    
    # 2024年度, male/female
    mask = (rates["year"] == 2024) & (rates["sex"].isin(["male", "female"]))
    df = rates[mask][["code", "procedure_name", "sex", "age_group", "count", "population", "count_per_100k"]].copy()
    df = sort_age(df)
    df = df.sort_values(["code", "sex", "_age_sort"] if "_age_sort" in df.columns else ["code", "sex"])
    # sort_ageでドロップ済みなので再ソート
    df_sorted = pd.DataFrame()
    for code in df["code"].unique():
        for sex in ["male", "female"]:
            sub = df[(df["code"] == code) & (df["sex"] == sex)]
            sub = sort_age(sub)
            df_sorted = pd.concat([df_sorted, sub], ignore_index=True)
    _save(df_sorted, "fig1b_age_sex_profile_2024.csv")


TOP3_DRUGS = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
TOP3_CODE = "TOP3_TOTAL"
TOP3_NAME = "上位3剤合計（エピナスチン・オロパタジン・レボカバスチン）"


def generate_fig2():
    """Fig 2: 年齢分布の経年変化（シェア比較 + 加重平均処方年齢の推移）"""
    print("\n=== Fig 2 ===")
    raw = pd.read_csv(os.path.join(SUMMARY_DIR, "ndb_allergy_age_sex_zero.csv"))

    # ソースにALLERGY_EYE_TOTAL等の合計行が既に含まれているのでそのまま使う
    # sex合算、薬剤別に年齢分布シェアを計算
    agg = raw.groupby(["year", "code", "procedure_name", "age_group"])["count"].sum().reset_index()
    total_by_year_code = agg.groupby(["year", "code"])["count"].transform("sum")
    agg["share_pct"] = agg["count"] / total_by_year_code * 100
    agg = sort_age(agg)

    # --- 上位3剤合計行を追加 ---
    top3 = agg[agg["code"].isin(TOP3_DRUGS)].copy()
    top3_agg = top3.groupby(["year", "age_group"])["count"].sum().reset_index()
    top3_total = top3_agg.groupby("year")["count"].transform("sum")
    top3_agg["share_pct"] = top3_agg["count"] / top3_total * 100
    top3_agg["code"] = TOP3_CODE
    top3_agg["procedure_name"] = TOP3_NAME
    top3_agg = sort_age(top3_agg)

    result = pd.concat([
        agg[["year", "code", "procedure_name", "age_group", "count", "share_pct"]],
        top3_agg[["year", "code", "procedure_name", "age_group", "count", "share_pct"]],
    ], ignore_index=True)
    _save(result, "fig2_age_distribution_shift.csv")

    # --- 加重平均処方年齢 ---
    result2 = result.copy()
    result2["midpoint"] = result2["age_group"].map(AGE_MIDPOINTS)
    _check_age_labels(result2["age_group"], AGE_MIDPOINTS)
    result2 = result2.dropna(subset=["midpoint"])

    def weighted_mean_age(g):
        total = g["count"].sum()
        if total == 0:
            return np.nan
        return (g["count"] * g["midpoint"]).sum() / total

    wma = result2.groupby(["year", "code", "procedure_name"])[["count", "midpoint"]].apply(
        weighted_mean_age
    ).reset_index(name="weighted_mean_age")

    wma = wma[["year", "code", "procedure_name", "weighted_mean_age"]]
    wma = wma.sort_values(["code", "year"])
    _save(wma, "fig2_weighted_mean_age.csv")


def generate_table1():
    """Table 1: 対象薬剤の処方量・シェア一覧（2024年度） - 総計列基準"""
    print("\n=== Table 1 (grand total basis) ===")
    pub = pd.read_csv(os.path.join(PROCESSED_DIR, "national_totals_published.csv"),
                      encoding="utf-8-sig")
    cov = pd.read_csv(os.path.join(BASE, "..", "data", "covariates",
                                   "prefecture_covariates.csv"), encoding="utf-8-sig")
    pop_2024 = cov[cov["year"] == 2024]["population_total"].sum()

    t24 = pub[pub["year"] == 2024][["code", "procedure_name", "count_published"]].copy()
    t24.rename(columns={"count_published": "count"}, inplace=True)
    t24["count_per_100k"] = t24["count"] / pop_2024 * 100000

    total_count = t24.loc[t24["code"] == "ALLERGY_EYE_TOTAL", "count"].values[0]
    t24["share_pct"] = np.where(
        t24["code"].isin(["ALLERGY_EYE_TOTAL", "ANTI_HIST", "MED_RELEASE", "IMMUNO"]),
        np.nan,
        t24["count"] / total_count * 100,
    )
    
    # カテゴリ分類を追加
    anti_hist = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE", "KETOTIFEN"]
    med_release = ["TRANILAST", "CROMOGLICATE", "ACITAZANOLAST", "PEMIROLAST", "IBUDILAST"]
    immuno = ["CYCLOSPORINE", "TACROLIMUS"]
    subtotals = ["ALLERGY_EYE_TOTAL", "ANTI_HIST", "MED_RELEASE", "IMMUNO"]
    
    def classify(code):
        if code in anti_hist:
            return "抗ヒスタミン薬"
        elif code in med_release:
            return "メディエーター遊離抑制薬"
        elif code in immuno:
            return "免疫抑制薬"
        elif code in subtotals:
            return "小計/合計"
        return "その他"
    
    t24["drug_class"] = t24["code"].apply(classify)

    # ソート: 合計 → 抗ヒスタミン → 遊離抑制 → 免疫抑制
    class_order = {"小計/合計": 0, "抗ヒスタミン薬": 1, "メディエーター遊離抑制薬": 2, "免疫抑制薬": 3, "その他": 4}
    t24["_class_sort"] = t24["drug_class"].map(class_order)
    t24 = t24.sort_values(["_class_sort", "count"], ascending=[True, False])
    t24 = t24.drop(columns=["_class_sort"])

    _save(t24, "table1_drug_summary_2024.csv")


def generate_table2():
    """Table 2: M:F比の年齢プロファイル（2024年度）"""
    print("\n=== Table 2 ===")
    mf = pd.read_csv(os.path.join(PROCESSED_DIR, "mf_ratio_by_age_allergy.csv"))
    
    # 2024年度
    df = mf[mf["year"] == 2024].copy()
    df = df[["code", "procedure_name", "age_group",
             "count_female", "count_male",
             "count_per_100k_female", "count_per_100k_male",
             "mf_ratio_count", "mf_ratio_rate"]]
    
    # 薬剤×年齢でソート
    df_sorted = pd.DataFrame()
    for code in df["code"].unique():
        sub = df[df["code"] == code]
        sub = sort_age(sub)
        df_sorted = pd.concat([df_sorted, sub], ignore_index=True)
    
    _save(df_sorted, "table2_mf_ratio_2024.csv")


def generate_fig3_top3():
    """Fig 3 (Top 3): 都道府県別ランキング — 上位3剤合計"""
    print("\n=== Fig 3 (Top 3) ===")
    pbd = pd.read_csv(
        os.path.join(PROCESSED_DIR, "prefecture_per_capita_by_drug_allergy.csv"),
        encoding="utf-8-sig",
    )

    top3_names = [
        "エピナスチン点眼（アレジオン系）",
        "オロパタジン点眼（パタノール系）",
        "レボカバスチン点眼（リボスチン系）",
    ]
    top3 = pbd[pbd["procedure_name"].isin(top3_names)].copy()

    year_cols = [c for c in top3.columns if "人口10万対" in c]
    agg = top3.groupby("prefecture")[year_cols].sum().reset_index()

    col_2024 = [c for c in year_cols if "2024" in c][0]
    agg = agg.sort_values(col_2024, ascending=False).reset_index(drop=True)
    agg["2024年_順位"] = range(1, len(agg) + 1)

    _save(agg, "fig3_prefecture_ranking_top3.csv")
    # 原稿の Fig 3A と Table 3 は同一データ
    _save(agg, "table3_prefecture_ranking_top3.csv")


def generate_fig4_top3():
    """Fig 4 (Top 3): 全国トレンド＋シェア — 総計列基準

    従来は都道府県内訳セルの合算値を用いていたが、NDB秘匿セルの
    ゼロ補完により過小評価となるため、NDB公表の「総計」列を基準とする。
    ソース: processed/national_totals_published.csv (build_national_totals.py)
    """
    print("\n=== Fig 4 (Top 3) - grand total basis ===")
    pub = pd.read_csv(
        os.path.join(PROCESSED_DIR, "national_totals_published.csv"),
        encoding="utf-8-sig",
    )

    cov = pd.read_csv(
        os.path.join(BASE, "..", "data", "covariates", "prefecture_covariates.csv"),
        encoding="utf-8-sig",
    )
    pop = cov.groupby("year").agg(
        population_total=("population_total", "sum"),
        population_65plus=("population_65plus", "sum"),
    ).reset_index()

    trends = pub.merge(pop, on="year", how="left")
    trends.rename(columns={"count_published": "count"}, inplace=True)
    trends["count_per_100k"] = trends["count"] / trends["population_total"] * 100000
    trends["count_per_100k_65plus"] = trends["count"] / trends["population_65plus"] * 100000
    trends = trends[["year", "code", "procedure_name", "count",
                      "population_total", "population_65plus",
                      "count_per_100k", "count_per_100k_65plus"]]

    top3_codes = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]

    # --- Fig4A: TOP3_TOTAL トレンド行を追加 ---
    t3 = trends[trends["code"].isin(top3_codes)].copy()
    t3_agg = t3.groupby("year").agg(
        count=("count", "sum"),
        population_total=("population_total", "first"),
        population_65plus=("population_65plus", "first"),
    ).reset_index()
    t3_agg["count_per_100k"] = t3_agg["count"] / t3_agg["population_total"] * 100000
    t3_agg["count_per_100k_65plus"] = t3_agg["count"] / t3_agg["population_65plus"] * 100000
    t3_agg["code"] = TOP3_CODE
    t3_agg["procedure_name"] = TOP3_NAME

    result = pd.concat([trends, t3_agg], ignore_index=True)
    result = result.sort_values(["code", "year"])
    _save(result, "fig4_national_trends.csv")

    # --- Fig4B: シェアを3剤合計基準で再計算 ---
    top3_total = t3.groupby("year")["count"].sum().reset_index(name="top3_total")

    # シェア計算: 各薬剤 / 全体合計 (share) と 各薬剤 / TOP3合計 (share_top3)
    all_total = trends[trends["code"] == "ALLERGY_EYE_TOTAL"][["year", "count"]].rename(
        columns={"count": "all_total"})
    shares = trends[~trends["code"].isin(
        ["ALLERGY_EYE_TOTAL", "ANTI_HIST", "MED_RELEASE", "IMMUNO"])].copy()
    shares = shares.merge(all_total, on="year", how="left")
    shares["share"] = shares["count"] / shares["all_total"]

    s3 = shares[shares["code"].isin(top3_codes)].merge(top3_total, on="year")
    s3["share_top3"] = s3["count"] / s3["top3_total"]
    s3 = s3.drop(columns=["top3_total"])

    result_s = shares.merge(s3[["year", "code", "share_top3"]], on=["year", "code"], how="left")
    result_s = result_s.sort_values(["code", "year"])
    _save(result_s, "fig4_market_shares.csv")


def copy_existing():
    """既存CSVのコピー（Fig 3, Fig 4, 補足資料）

    原稿が定義する表は Table 1〜3 のみ。地域格差指標・APC・パネル回帰は
    原稿に対応する表がないため supplementary_ を接頭辞とする。
    """
    print("\n=== 既存ファイルコピー ===")

    # Fig 3: 都道府県別ランキング
    _copy(SUMMARY_DIR, "prefecture_per_capita_ranking_allergy.csv",
          "fig3_prefecture_ranking.csv")

    # Fig 3 補助: 都道府県別×薬剤別
    _copy(PROCESSED_DIR, "prefecture_per_capita_by_drug_allergy.csv",
          "fig3_prefecture_by_drug.csv")

    # Fig 4: シェア（元ファイルをコピー。generate_fig4_top3で上書きされる）
    _copy(SUMMARY_DIR, "national_shares_allergy.csv",
          "fig4_market_shares.csv")

    # 補足: 地域格差指標（CV・Gini）
    _copy(PROCESSED_DIR, "geographic_disparity_allergy.csv",
          "supplementary_geographic_disparity.csv")

    # 補足: APC
    _copy(PROCESSED_DIR, "national_apc_linear_allergy.csv",
          "supplementary_apc_results.csv")

    # 補足: Joinpoint APC
    _copy(PROCESSED_DIR, "national_apc_joinpoint_allergy.csv",
          "supplementary_apc_joinpoint.csv")

    # 補足: パネル回帰
    _copy(PROCESSED_DIR, "panel_regression_summary_allergy.csv",
          "supplementary_panel_regression.csv")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 60)
    print("論文 Fig/Table 用 CSV 生成")
    print("=" * 60)
    
    generate_fig1a()
    generate_fig1b()
    generate_fig2()
    generate_table1()
    generate_table2()
    copy_existing()
    generate_fig3_top3()
    generate_fig4_top3()
    
    print("\n" + "=" * 60)
    print("完了。出力先:", OUT_DIR)
    print("=" * 60)


if __name__ == "__main__":
    main()
