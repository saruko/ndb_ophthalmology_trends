import os
import argparse
import subprocess
import sys
import pandas as pd

# srcディレクトリをパスに追加してインポートを可能にする
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from paths import (RAW_DIR, COVARIATE_PATH, add_nokouhi_arg,
                   output_dir as output_dir_for)
from preprocess_glaucoma import preprocess_glaucoma
from analysis_glaucoma import analyze_glaucoma_all, run_panel_regression
from analysis_substitution import run_substitution_analysis
from analysis_group_comparison import run_group_comparison
from visualization_glaucoma import visualize_glaucoma_all

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def fmt_p(p):
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def generate_prefecture_pivots(processed_csv_path, output_dir):
    """都道府県別のピボットCSV（処方数量・人口10万対・ランキング）を生成する。"""
    print("Generating prefecture pivot CSVs...")
    from preprocess_glaucoma import TOTAL_CODES
    df = pd.read_csv(processed_csv_path)
    years = sorted(df["year"].unique())

    # 1. 都道府県別 全体処方数量（GLAUCOMA_EYE_TOTAL）のピボット
    df_total = df[df["code"] == "GLAUCOMA_EYE_TOTAL"]
    pivot_total = df_total.pivot_table(
        index="prefecture", columns="year", values="count_ml", aggfunc="sum"
    )
    pivot_total.columns = [f"{int(y)}年_処方数量mL" for y in pivot_total.columns]
    pivot_total.to_csv(
        os.path.join(output_dir, "prefecture_prescriptions_glaucoma.csv"),
        encoding="utf-8-sig"
    )

    # 2. 都道府県×薬剤別 処方数量のピボット
    df_ind = df[df["code"].isin(TOTAL_CODES)]
    pivot_by_drug = df_ind.pivot_table(
        index=["prefecture", "procedure_name"], columns="year",
        values="count_ml", aggfunc="sum"
    )
    pivot_by_drug.columns = [f"{int(y)}年_処方数量mL" for y in pivot_by_drug.columns]
    pivot_by_drug.to_csv(
        os.path.join(output_dir, "prefecture_prescriptions_by_drug_glaucoma.csv"),
        encoding="utf-8-sig"
    )

    # 3. 都道府県別 人口10万対ランキング（GLAUCOMA_EYE_TOTAL）
    pivot_rate = df_total.pivot_table(
        index="prefecture", columns="year", values="count_per_100k", aggfunc="mean"
    )
    pivot_rate.columns = [f"{int(y)}年_人口10万対mL" for y in pivot_rate.columns]
    latest_col = pivot_rate.columns[-1]
    pivot_rate[f"{int(years[-1])}年_順位"] = pivot_rate[latest_col].rank(ascending=False).astype(int)
    pivot_rate = pivot_rate.sort_values(latest_col, ascending=False)
    pivot_rate.to_csv(
        os.path.join(output_dir, "prefecture_per_capita_ranking_glaucoma.csv"),
        encoding="utf-8-sig"
    )

    # 4. 都道府県×薬剤別 人口10万対のピボット
    pivot_rate_drug = df_ind.pivot_table(
        index=["prefecture", "procedure_name"], columns="year",
        values="count_per_100k", aggfunc="mean"
    )
    pivot_rate_drug.columns = [f"{int(y)}年_人口10万対mL" for y in pivot_rate_drug.columns]
    pivot_rate_drug.to_csv(
        os.path.join(output_dir, "prefecture_per_capita_by_drug_glaucoma.csv"),
        encoding="utf-8-sig"
    )
    print("Saved 4 prefecture pivot CSVs.")


def analyze_ingredient_trends(output_dir, imputation_strategy):
    """成分別曝露量（配合剤を成分に分解）の全国トレンドとAPCを算出する。"""
    from analysis_glaucoma import calculate_apc_linear
    src = os.path.join(output_dir, f"ingredient_exposure_glaucoma_{imputation_strategy}.csv")
    if not os.path.exists(src):
        return
    print("Analyzing ingredient-level exposure trends...")
    df = pd.read_csv(src)
    national = df.groupby(["year", "code", "procedure_name"]).agg(
        {"count_ml": "sum", "population_total": "sum"}
    ).reset_index()
    national["count_per_100k"] = national["count_ml"] / national["population_total"] * 100000
    national.to_csv(
        os.path.join(output_dir, "national_ingredient_trends_glaucoma.csv"),
        index=False, encoding="utf-8-sig")

    rows = []
    for code, g in national.groupby("code"):
        res = calculate_apc_linear(g["year"].values, g["count_per_100k"].values)
        res.update({"code": code, "procedure_name": g["procedure_name"].iloc[0],
                    "start_year": int(g["year"].min()), "end_year": int(g["year"].max())})
        rows.append(res)
    pd.DataFrame(rows).to_csv(
        os.path.join(output_dir, "national_ingredient_apc_glaucoma.csv"),
        index=False, encoding="utf-8-sig")
    print("Saved ingredient-level trend/APC CSVs.")


def generate_summary_report(output_dir, imputation_strategy):
    """解析結果から人間可読なサマリーレポートを生成する"""
    print("Generating human-readable summary report...")
    report_path = os.path.join(output_dir, "glaucoma_summary_report.txt")

    trends_csv = os.path.join(output_dir, "national_trends_glaucoma.csv")
    apc_csv = os.path.join(output_dir, "national_apc_linear_glaucoma.csv")
    disparity_csv = os.path.join(output_dir, "geographic_disparity_glaucoma.csv")
    panel_csv = os.path.join(output_dir, "panel_regression_summary_glaucoma.csv")
    sub_csv = os.path.join(output_dir, "substitution_regression_glaucoma.csv")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write(" NDB緑内障点眼薬 解析 サマリーレポート\n")
        f.write(f" 補完戦略: {imputation_strategy}\n")
        f.write(" 処方数量は品目単位（ｍＬ/瓶/個）をmLに統一換算した値\n")
        f.write("==================================================\n\n")

        # 1. トレンド概要
        if os.path.exists(trends_csv):
            df_trends = pd.read_csv(trends_csv)
            latest_year = df_trends["year"].max()
            f.write(f"1. 全国処方数量・処方率トレンド ({latest_year}年度時点)\n")
            f.write("--------------------------------------------------\n")
            df_latest = df_trends[df_trends["year"] == latest_year].sort_values(
                "count_ml", ascending=False)
            for _, row in df_latest.iterrows():
                f.write(f" - {row['procedure_name']} ({row['code']}):\n")
                f.write(f"   * 全国年間処方数量: {int(row['count_ml']):,} mL\n")
                f.write(f"   * 人口10万対数量  : {row['count_per_100k']:.1f} mL\n")
            f.write("\n")

        # 2. APC (年平均変化率)
        if os.path.exists(apc_csv):
            f.write("2. 年平均変化率 (APC)\n")
            f.write("--------------------------------------------------\n")
            df_apc = pd.read_csv(apc_csv)
            for _, row in df_apc.iterrows():
                sig = "(*有意)" if row['p_value'] < 0.05 else "(有意差なし)"
                f.write(f" - {row['procedure_name']} ({row['start_year']}~{row['end_year']}):\n")
                f.write(f"   * APC: {row['apc']:.2f}% (95%CI: {row['apc_low']:.2f}% ~ {row['apc_high']:.2f}%) {sig}\n")
                f.write(f"   * p-value: {fmt_p(row['p_value'])} | R²: {row['r2']:.4f}\n")
            f.write("\n")

        # 3. 地域格差指標 (最新年度)
        if os.path.exists(disparity_csv):
            df_disp = pd.read_csv(disparity_csv)
            latest_disp_year = df_disp["year"].max()
            f.write(f"3. 地域格差指標 ({latest_disp_year}年度)\n")
            f.write("--------------------------------------------------\n")
            df_disp_latest = df_disp[df_disp["year"] == latest_disp_year]
            for _, row in df_disp_latest.iterrows():
                f.write(f" - {row['procedure_name']}:\n")
                f.write(f"   * 変動係数 (CV): {row['cv']:.3f}\n")
                f.write(f"   * ジニ係数 (Gini): {row['gini']:.3f}\n")
                f.write(f"   * 最大/最小比: {row['max_to_min_ratio']:.2f}倍 (最小: {row['min_prefecture']} / 最大: {row['max_prefecture']})\n")
            f.write("\n")

        # 4. パネル回帰結果
        if os.path.exists(panel_csv):
            f.write("4. 固定効果パネル回帰分析 (Two-way FE, 都道府県クラスターSE)\n")
            f.write("--------------------------------------------------\n")
            f.write("※人口10万対処方数量(mL)を被説明変数とし、都道府県および年度の固定効果を制御\n")
            df_panel = pd.read_csv(panel_csv)
            for code, group in df_panel.groupby("code"):
                proc_name = group["procedure_name"].iloc[0]
                f.write(f" - {proc_name} ({code}):\n")
                for _, row in group.iterrows():
                    sig = "(*有意)" if row['p_value'] < 0.05 else ""
                    f.write(f"   * {row['variable']}: 係数={row['coefficient']:.3f} | t-stat={row['t_stat']:.3f} | p={fmt_p(row['p_value'])} {sig}\n")
                f.write(f"   * 決定係数 (Within R²): {group['r2_within'].iloc[0]:.4f} | 観測値数: {group['n_obs'].iloc[0]}\n")
            f.write("\n")

        # 5. 治療的代替
        if os.path.exists(sub_csv):
            f.write("5. 治療的代替の推定 (差分パネル回帰, Two-way FE)\n")
            f.write("--------------------------------------------------\n")
            f.write("※負の係数はシェアの奪い合い（代替関係）を示す\n")
            df_sub = pd.read_csv(sub_csv)
            for model, group in df_sub.groupby("model"):
                f.write(f" - {model} (被説明変数: {group['dependent'].iloc[0]}):\n")
                for _, row in group.iterrows():
                    sig = "(*有意)" if row['p_value'] < 0.05 else ""
                    f.write(f"   * {row['variable']}: 係数={row['coefficient']:.4f} | t-stat={row['t_stat']:.3f} | p={fmt_p(row['p_value'])} {sig}\n")
                f.write(f"   * Within R²: {group['r2_within'].iloc[0]:.4f} | 観測値数: {group['n_obs'].iloc[0]}\n")
            f.write("\n")

    print(f"Summary report saved to {report_path}")


def main():
    parser = argparse.ArgumentParser(description="NDB緑内障点眼薬 解析パイプライン")
    parser.add_argument(
        "--imputation",
        type=str,
        choices=["zero", "upper", "five", "random"],
        default="zero",
        help="秘匿セル（数量1,000未満）の補完戦略: zero (0補完=識別区間の下限), "
             "upper (999補完=上限), five/random は閾値10前提の旧仕様"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="出力先ディレクトリ（既定: processed_nokouhi、--kouhi 時は processed）。"
             "感度分析で主解析を上書きしないために使う"
    )
    parser.add_argument(
        "--skip-agesex", action="store_true",
        help="年齢性別の集計（build_glaucoma_age_sex.py）をスキップする"
    )
    add_nokouhi_arg(parser)
    args = parser.parse_args()

    raw_dir = RAW_DIR
    covariate_path = COVARIATE_PATH
    output_dir = args.output_dir or output_dir_for(args.nokouhi)
    os.makedirs(output_dir, exist_ok=True)

    print("==================================================")
    print("       NDB緑内障点眼薬 解析パイプライン")
    print(f"      補完戦略: {args.imputation}")
    print(f"      公費レセプト: {'含まない（主解析）' if args.nokouhi else '含む（参考）'}")
    print("==================================================")

    # 1. 前処理
    preprocess_glaucoma(
        raw_dir=raw_dir,
        covariate_path=covariate_path,
        output_dir=output_dir,
        imputation_strategy=args.imputation,
        nokouhi=args.nokouhi
    )

    # 2. 統計解析
    processed_csv = os.path.join(output_dir, f"ndb_processed_glaucoma_{args.imputation}.csv")
    analyze_glaucoma_all(
        processed_csv_path=processed_csv,
        output_dir=output_dir
    )

    # 3. 治療的代替・市場構造・収束分析
    run_substitution_analysis(
        processed_csv_path=processed_csv,
        output_dir=output_dir
    )

    # 4. 可視化
    visualize_glaucoma_all(
        processed_csv_path=processed_csv,
        output_dir=output_dir
    )

    # 5. 薬効群（ガイドライン第5版の分類）どうしの比較
    run_group_comparison(
        processed_csv_path=processed_csv,
        output_dir=output_dir
    )

    # 6. 成分別曝露量（配合剤を成分に分解）のトレンド
    analyze_ingredient_trends(output_dir, args.imputation)

    # 7. 都道府県別ピボットCSV生成
    generate_prefecture_pivots(processed_csv, output_dir)

    # 8. 年齢性別集計と年齢階級別処方率
    if not args.skip_agesex:
        nokouhi_flag = [] if args.nokouhi else ["--kouhi"]
        subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "build_glaucoma_age_sex.py"),
             "--imputation", args.imputation] + nokouhi_flag,
            check=True)
        subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "src", "analysis_age_sex_rates.py")]
            + nokouhi_flag,
            check=True, cwd=os.path.join(BASE_DIR, "src"))

    # 9. サマリーテキスト出力
    generate_summary_report(output_dir, args.imputation)

    print("\n[SUCCESS] パイプラインの実行がすべて正常に完了しました！")
    print(f"結果出力先: {os.path.abspath(output_dir)}")
    print("==================================================")


if __name__ == "__main__":
    main()
