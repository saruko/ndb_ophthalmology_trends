import os
import argparse
import sys
import pandas as pd

# srcディレクトリをパスに追加してインポートを可能にする
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from paths import output_dir as processed_dir
from preprocess_pterygium import preprocess_pterygium
from analysis_pterygium import analyze_pterygium
from visualization_pterygium import visualize_pterygium_all

def fmt_p(p):
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"

def generate_prefecture_pivots(rate_csv_path, output_dir):
    """都道府県別のピボットCSV（手術件数・人口10万対・ランキング）を生成する。"""
    print("Generating prefecture pivot CSVs...")
    df = pd.read_csv(rate_csv_path)
    
    # 1. 都道府県×設定別 手術件数のピボット
    for setting in ["outpatient", "inpatient", "total"]:
        df_sub = df[df["setting"] == setting]
        if df_sub.empty:
            continue
        pivot_count = df_sub.pivot_table(
            index="prefecture", columns="year", values="count", aggfunc="sum"
        )
        pivot_count.columns = [f"{int(y)}年_手術件数" for y in pivot_count.columns]
        out_path = os.path.join(output_dir, f"prefecture_surgeries_{setting}.csv")
        pivot_count.to_csv(out_path, encoding="utf-8-sig")
        print(f"  Saved {out_path}")
        
    # 2. 都道府県別 人口10万対ランキング（主解析である外来 outpatient を基準）
    df_out = df[df["setting"] == "outpatient"]
    if not df_out.empty:
        years = sorted(df_out["year"].unique())
        pivot_rate = df_out.pivot_table(
            index="prefecture", columns="year", values="count_per_100k", aggfunc="mean"
        )
        pivot_rate.columns = [f"{int(y)}年_人口10万対" for y in pivot_rate.columns]
        latest_year = years[-1]
        latest_col = f"{int(latest_year)}年_人口10万対"
        
        pivot_rate[f"{int(latest_year)}年_順位"] = pivot_rate[latest_col].rank(ascending=False).astype(int)
        pivot_rate = pivot_rate.sort_values(latest_col, ascending=False)
        
        out_path = os.path.join(output_dir, "prefecture_rate_ranking_outpatient.csv")
        pivot_rate.to_csv(out_path, encoding="utf-8-sig")
        print(f"  Saved {out_path}")

def generate_summary_report(output_dir, imputation_strategy):
    """解析結果から人間可読なサマリーレポートを生成する"""
    print("Generating human-readable summary report...")
    report_path = os.path.join(output_dir, "pterygium_summary_report.txt")
    
    rate_csv = os.path.join(output_dir, "pterygium_rate_per100k.csv")
    disparity_csv = os.path.join(output_dir, "pterygium_gini_cv_trend.csv")
    apc_csv = os.path.join(output_dir, "pterygium_apc_linear.csv")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write(" NDB 翼状片手術（K224） サブ解析 サマリーレポート\n")
        f.write(f" 補完戦略: {imputation_strategy}\n")
        f.write("==================================================\n\n")
        
        # 1. 全国レベルのトレンド概要
        if os.path.exists(rate_csv):
            df_rate = pd.read_csv(rate_csv)
            df_national = df_rate.groupby(["year", "setting"]).agg({
                "count": "sum",
                "population_total": "sum"
            }).reset_index()
            df_national["count_per_100k"] = (df_national["count"] / df_national["population_total"]) * 100000
            
            latest_year = df_national["year"].max()
            f.write(f"1. 全国手術件数・件数率トレンド ({latest_year}年度時点)\n")
            f.write("--------------------------------------------------\n")
            df_latest = df_national[df_national["year"] == latest_year]
            for _, row in df_latest.iterrows():
                setting_str = "全体 (外来+入院)" if row['setting'] == 'total' else ("外来" if row['setting'] == 'outpatient' else "入院")
                f.write(f" - {setting_str} ({row['setting']}):\n")
                f.write(f"   * 全国年間手術件数: {int(row['count']):,} 件\n")
                f.write(f"   * 人口10万対件数  : {row['count_per_100k']:.2f} 件\n")
            f.write("\n")
            
        # 2. APC (年平均変化率)
        if os.path.exists(apc_csv):
            f.write("2. 年平均変化率 (APC)\n")
            f.write("--------------------------------------------------\n")
            df_apc = pd.read_csv(apc_csv)
            for _, row in df_apc.iterrows():
                setting_str = "全体 (外来+入院)" if row['setting'] == 'total' else ("外来" if row['setting'] == 'outpatient' else "入院")
                sig = "(*有意)" if row['p_value'] < 0.05 else "(有意差なし)"
                f.write(f" - {setting_str} ({row['start_year']}~{row['end_year']}年度, 2017年欠測除外):\n")
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
                setting_str = "全体 (外来+入院)" if row['setting'] == 'total' else ("外来" if row['setting'] == 'outpatient' else "入院")
                f.write(f" - {setting_str}:\n")
                f.write(f"   * 変動係数 (CV): {row['cv']:.3f}\n")
                f.write(f"   * ジニ係数 (Gini): {row['gini']:.3f}\n")
                f.write(f"   * 最大/最小比: {row['max_to_min_ratio']:.3f}倍 (最小: {row['min_prefecture']} {row['min_rate']:.2f}件 / 最大: {row['max_prefecture']} {row['max_rate']:.2f}件)\n")
            f.write("\n")
            
    print(f"Summary report saved to {report_path}")

def main():
    parser = argparse.ArgumentParser(description="NDB翼状片手術（K224）トレンド解析パイプライン")
    parser.add_argument(
        "--imputation",
        type=str,
        choices=["zero", "five", "random"],
        default="zero",
        help="秘匿閾値（10件未満）の補完戦略: zero (0補完), five (5補完), random (1-9一様乱数)"
    )
    args = parser.parse_args()
    
    # フォルダパスの設定
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(base_dir, "../data/raw")
    covariate_path = os.path.join(base_dir, "../data/covariates/prefecture_covariates.csv")
    output_dir = processed_dir()

    print("==================================================")
    print("      NDB 翼状片手術 解析パイプライン")
    print(f"      補完戦略: {args.imputation}")
    print("==================================================")
    
    # 1. 前処理
    preprocess_pterygium(
        raw_dir=raw_dir,
        output_dir=output_dir,
        imputation_strategy=args.imputation
    )
    
    # 2. 統計解析
    long_csv = os.path.join(output_dir, "pterygium_long.csv")
    analyze_pterygium(
        long_csv_path=long_csv,
        covariate_path=covariate_path,
        output_dir=output_dir
    )
    
    # 3. 可視化
    visualize_pterygium_all(
        processed_dir=output_dir
    )
    
    # 4. 都道府県別ピボットCSV生成
    rate_csv = os.path.join(output_dir, "pterygium_rate_per100k.csv")
    generate_prefecture_pivots(rate_csv, output_dir)
    
    # 5. サマリーテキスト出力
    generate_summary_report(output_dir, args.imputation)
    
    print("\n[SUCCESS] 翼状片解析パイプラインの実行が正常に完了しました！")
    print(f"結果出力先: {os.path.abspath(output_dir)}")
    print("次に `python 翼状片解析/organize_outputs.py` を実行すると 01〜05 のフォルダへ振り分けられます。")
    print("==================================================")

if __name__ == "__main__":
    main()
