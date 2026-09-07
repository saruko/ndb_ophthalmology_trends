"""抗VEGF薬（硝子体注射液）解析パイプライン。

使い方:
    python run_antivegf_pipeline.py                 # zeroを主解析、five/randomで感度分析
    python run_antivegf_pipeline.py --imputation five --no-sensitivity
"""

import argparse
import os
import sys

import pandas as pd
from scipy.stats import spearmanr

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from preprocess_antivegf import preprocess_all
from analysis_antivegf import (analyze_national_trends, analyze_geographic_disparity,
                               analyze_covariates_correlation, run_panel_regression,
                               build_prefecture_pivots, calculate_gini)
from analysis_product import (analyze_by_product, analyze_formulation,
                              analyze_biosimilar, analyze_age_sex, masking_qc)
from visualization_antivegf import plot_all
from report_antivegf import generate_report

ANTIVEGF_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(ANTIVEGF_DIR)
COVARIATES = os.path.join(BASE, "data", "covariates", "prefecture_covariates.csv")

# --nokouhi 指定時は「公費含まない」サブフォルダの入出力に切り替える
DATA_DIR = ANTIVEGF_DIR
OUT_DIR = os.path.join(DATA_DIR, "processed")
PLOTS_DIR = os.path.join(OUT_DIR, "plots")

SENSITIVITY_CODES = ["ANTI_VEGF_TOTAL", "AFLIBERCEPT", "RANIBIZUMAB_BS"]


def run_sensitivity(strategies, output_dir):
    """補完戦略ごとにGini係数と都道府県順位の一致度を比較する。"""
    print("Running sensitivity analysis across imputation strategies...")
    panels = {}
    for s in strategies:
        panel = preprocess_all(DATA_DIR, output_dir, COVARIATES, s)[3]
        panels[s] = panel

    rows = []
    base = "zero"
    for code in SENSITIVITY_CODES:
        for year in sorted(panels[base]["year"].unique()):
            rec = {"code": code, "year": year}
            ref = panels[base].query("code == @code and year == @year"
                                     ).set_index("prefecture")["count_per_100k"]
            if ref.sum() == 0:
                continue
            for s in strategies:
                cur = panels[s].query("code == @code and year == @year"
                                      ).set_index("prefecture")["count_per_100k"]
                rec[f"gini_{s}"] = calculate_gini(cur.values)
                if s != base:
                    rho, _ = spearmanr(ref, cur.reindex(ref.index))
                    rec[f"rank_corr_{base}_{s}"] = rho
            rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(output_dir, "sensitivity_imputation_antivegf.csv"),
              index=False, encoding="utf-8-sig")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imputation", choices=["zero", "five", "random"], default="zero",
                    help="秘匿値（10未満）の補完方法")
    ap.add_argument("--no-sensitivity", action="store_true",
                    help="補完戦略の感度分析を省略する")
    ap.add_argument("--nokouhi", action="store_true",
                    help="公費レセプトを含まないデータ（抗VEGF薬解析/公費含まない）で解析する")
    args = ap.parse_args()

    global DATA_DIR, OUT_DIR, PLOTS_DIR
    if args.nokouhi:
        DATA_DIR = os.path.join(ANTIVEGF_DIR, "公費含まない")
        OUT_DIR = os.path.join(DATA_DIR, "processed")
        PLOTS_DIR = os.path.join(OUT_DIR, "plots")

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"=== 抗VEGF薬 解析パイプライン (imputation={args.imputation}) ===")

    print("[1/6] 前処理")
    pref, nat, agesex, panel = preprocess_all(DATA_DIR, OUT_DIR, COVARIATES,
                                             args.imputation)

    print("[2/6] 全国トレンド・APC・地域格差・共変量相関")
    analyze_national_trends(nat, COVARIATES, OUT_DIR)
    analyze_geographic_disparity(panel, OUT_DIR)
    analyze_covariates_correlation(panel, OUT_DIR)
    build_prefecture_pivots(panel, OUT_DIR)

    print("[3/6] 製品・剤形・先発/後発・年齢性別")
    analyze_by_product(nat, pref, OUT_DIR)
    analyze_formulation(nat, pref, OUT_DIR)
    analyze_biosimilar(nat, pref, OUT_DIR)
    analyze_age_sex(agesex, OUT_DIR)
    masking_qc(pref, agesex, OUT_DIR, DATA_DIR)

    print("[4/6] パネル回帰")
    run_panel_regression(panel, OUT_DIR)

    sens = None
    if not args.no_sensitivity:
        print("[5/6] 感度分析")
        sens = run_sensitivity(["zero", "five", "random"], OUT_DIR)
        # 主解析の補完戦略で前処理結果を戻す
        preprocess_all(DATA_DIR, OUT_DIR, COVARIATES, args.imputation)
    else:
        print("[5/6] 感度分析はスキップ")

    print("[6/6] 図表とレポート")
    plot_all(OUT_DIR, PLOTS_DIR)
    generate_report(OUT_DIR, args.imputation, sens)
    print(f"完了: {OUT_DIR}")


if __name__ == "__main__":
    main()
