import os
import argparse
import sys
import pandas as pd

# srcディレクトリをパスに追加してインポートを可能にする
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from preprocess_allergy import preprocess_allergy
from analysis_allergy import analyze_allergy_all
from analysis_substitution import run_substitution_analysis
from visualization_allergy import visualize_allergy_all

def generate_summary_report(output_dir, imputation_strategy):
    """解析結果から人間可読なサマリーレポートを生成する"""
    print("Generating human-readable summary report...")
    report_path = os.path.join(output_dir, "allergy_summary_report.txt")
    
    trends_csv = os.path.join(output_dir, "national_trends_allergy.csv")
    apc_csv = os.path.join(output_dir, "national_apc_linear_allergy.csv")
    disparity_csv = os.path.join(output_dir, "geographic_disparity_allergy.csv")
    panel_csv = os.path.join(output_dir, "panel_regression_summary_allergy.csv")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("==================================================\n")
        f.write(" NDBアレルギー関連薬 サブ解析 サマリーレポート\n")
        f.write(f" 補完戦略: {imputation_strategy}\n")
        f.write("==================================================\n\n")
        
        # 1. トレンド概要
        if os.path.exists(trends_csv):
            f.write("1. 全国処方件数・処方率トレンド (2023年度時点)\n")
            f.write("--------------------------------------------------\n")
            df_trends = pd.read_csv(trends_csv)
            df_2023 = df_trends[df_trends["year"] == 2023]
            for _, row in df_2023.iterrows():
                f.write(f" - {row['procedure_name']} ({row['code']}):\n")
                f.write(f"   * 全国年間処方件数: {int(row['count']):,} 件\n")
                f.write(f"   * 人口10万対件数  : {row['count_per_100k']:.2f} 件\n")
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
                f.write(f"   * p-value: {row['p_value']:.4f} | R²: {row['r2']:.4f}\n")
            f.write("\n")
            
        # 3. 地域格差指標 (最新2023年)
        if os.path.exists(disparity_csv):
            f.write("3. 地域格差指標 (2023年度)\n")
            f.write("--------------------------------------------------\n")
            df_disp = pd.read_csv(disparity_csv)
            df_disp_2023 = df_disp[df_disp["year"] == 2023]
            for _, row in df_disp_2023.iterrows():
                f.write(f" - {row['procedure_name']}:\n")
                f.write(f"   * 変動係数 (CV): {row['cv']:.4f}\n")
                f.write(f"   * ジニ係数 (Gini): {row['gini']:.4f}\n")
                f.write(f"   * 最大/最小比: {row['max_to_min_ratio']:.2f}倍 (最小: {row['min_prefecture']} / 最大: {row['max_prefecture']})\n")
            f.write("\n")
            
        # 4. パネル回帰結果
        if os.path.exists(panel_csv):
            f.write("4. 固定効果パネル回帰分析 (Two-way FE, 都道府県クラスターSE)\n")
            f.write("--------------------------------------------------\n")
            f.write("※人口10万対件数を被説明変数とし、都道府県および年度の固定効果を制御\n")
            df_panel = pd.read_csv(panel_csv)
            for code, group in df_panel.groupby("code"):
                proc_name = group["procedure_name"].iloc[0]
                f.write(f" - {proc_name} ({code}):\n")
                for _, row in group.iterrows():
                    sig = "(*有意)" if row['p_value'] < 0.05 else ""
                    f.write(f"   * {row['variable']}: 係数={row['coefficient']:.4f} | t-stat={row['t_stat']:.2f} | p={row['p_value']:.4e} {sig}\n")
                f.write(f"   * 決定係数 (Within R²): {group['r2_within'].iloc[0]:.4f} | 観測値数: {group['n_obs'].iloc[0]}\n")
            f.write("\n")
            
    print(f"Summary report saved to {report_path}")

def main():
    parser = argparse.ArgumentParser(description="NDBアレルギー関連薬剤サブ解析パイプライン")
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
    output_dir = os.path.join(base_dir, "processed")
    
    print("==================================================")
    print("      NDBアレルギー関連薬 サブ解析パイプライン")
    print(f"      補完戦略: {args.imputation}")
    print("==================================================")
    
    # 1. 前処理
    preprocess_allergy(
        raw_dir=raw_dir,
        covariate_path=covariate_path,
        output_dir=output_dir,
        imputation_strategy=args.imputation
    )
    
    # 2. 統計解析
    processed_csv = os.path.join(output_dir, f"ndb_processed_allergy_{args.imputation}.csv")
    analyze_allergy_all(
        processed_csv_path=processed_csv,
        output_dir=output_dir
    )
    
    # 3. 治療的代替・市場構造・収束分析
    run_substitution_analysis(
        processed_csv_path=processed_csv,
        output_dir=output_dir
    )

    # 4. 可視化
    visualize_allergy_all(
        processed_csv_path=processed_csv,
        output_dir=output_dir
    )

    # 5. サマリーテキスト出力
    generate_summary_report(output_dir, args.imputation)
    
    print("\n[SUCCESS] パイプラインの実行がすべて正常に完了しました！")
    print(f"結果出力先: {os.path.abspath(output_dir)}")
    print("==================================================")

if __name__ == "__main__":
    main()
