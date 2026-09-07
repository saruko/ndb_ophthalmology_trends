import os
import sys
import argparse
import traceback

# srcディレクトリをPythonのモジュール検索パスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from preprocess import preprocess_all
from analysis import analyze_all
from visualization import plot_all

def main():
    parser = argparse.ArgumentParser(description="NDB眼科診療トレンド解析パイプライン")
    parser.add_argument(
        "--imputation", 
        type=str, 
        default="zero", 
        choices=["zero", "five", "random"],
        help="10件未満の秘匿データに対する補完方法 (zero: 0補完, five: 5補完, random: 1-9の一様乱数)"
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="NDB生データExcelが格納されているディレクトリ"
    )
    parser.add_argument(
        "--covariates",
        type=str,
        default="data/covariates/prefecture_covariates.csv",
        help="共変量（人口・医師数等）CSVのパス"
    )
    parser.add_argument(
        "--mapping-config",
        type=str,
        default="configs/ndb_mapping.json",
        help="年度別Excelマッピング定義ファイルのパス"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="処理・解析結果の出力ディレクトリ"
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print(" NDB Ophthalmic Trend Analysis Pipeline ")
    print("="*60)
    print(f"・Imputation strategy: {args.imputation}")
    print(f"・Raw data directory:  {args.raw_dir}")
    print(f"・Covariates path:     {args.covariates}")
    print(f"・Mapping config:      {args.mapping_config}")
    print(f"・Output directory:    {args.output_dir}")
    print("-"*60)
    
    # 必要フォルダの作成
    os.makedirs(args.output_dir, exist_ok=True)
    
    try:
        # Step 1: 前処理とマージ
        print("\n[Step 1/3] データの前処理と標準化...")
        preprocess_all(
            raw_dir=args.raw_dir,
            covariate_path=args.covariates,
            mapping_path=args.mapping_config,
            output_dir=args.output_dir,
            imputation_strategy=args.imputation
        )
        
        # Step 2: 統計解析の実行
        print("\n[Step 2/3] 統計解析の実行（トレンド, 地域差, 相関, パネル回帰）...")
        processed_csv = os.path.join(args.output_dir, f"ndb_processed_{args.imputation}.csv")
        analyze_all(
            processed_csv_path=processed_csv,
            output_dir=args.output_dir
        )
        
        # サブ解析の実行（K280などの内訳比較）
        print("\n[Step 2-sub/3] サブ解析の実行（K280などの内訳比較）...")
        sub_processed_csv = os.path.join(args.output_dir, f"ndb_processed_k280_sub_{args.imputation}.csv")
        sub_output_dir = os.path.join(args.output_dir, "sub_analysis")
        analyze_all(
            processed_csv_path=sub_processed_csv,
            output_dir=sub_output_dir
        )
        
        # Step 3: 可視化グラフの生成
        print("\n[Step 3/3] グラフ・可視化結果の出力...")
        plot_all(
            processed_csv_path=processed_csv,
            output_dir=args.output_dir
        )
        
        print("\n" + "="*60)
        print(" パイプライン処理が正常に完了しました！")
        print("="*60)
        
    except Exception as e:
        print("\n" + "!"*60)
        print(" エラーが発生しました。処理を中断します。")
        print(f" エラー内容: {e}")
        print("!"*60)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
