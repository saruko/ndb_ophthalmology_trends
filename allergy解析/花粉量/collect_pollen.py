import os
import pandas as pd
import argparse
from npo_pollen import get_npo_pollen
from env_pollen import get_env_pollen
from local_pollen import get_tokyo_pollen

def collect_all_sources(year):
    """
    指定された年度について、3つの手段（NPO, 環境省, 自治体/東京）からスギ・ヒノキのデータを収集し、
    1つのDataFrameに集計する。
    """
    combined_data = []
    
    # 1. NPO法人花粉情報協会のデータ取得
    print(f"\n--- Gathering NPO Pollen Net Data for {year} ---")
    for p_type in ["sugi", "hinoki"]:
        try:
            records = get_npo_pollen(year, p_type)
            combined_data.extend(records)
            print(f"  Successfully gathered NPO data for {p_type}. Records count: {len(records)}")
        except Exception as e:
            print(f"  [ERROR] NPO ({p_type}): {e}")
            
    # 2. 環境省のデータ取得（Excel優先、なければPDFに自動フォールバック）
    print(f"\n--- Gathering Ministry of Environment Data for {year} ---")
    for p_type in ["sugi", "hinoki"]:
        try:
            records = get_env_pollen(year, p_type)
            combined_data.extend(records)
            print(f"  Successfully gathered MOE data for {p_type}. Records count: {len(records)}")
        except Exception as e:
            print(f"  [ERROR] MOE ({p_type}): {e}")
            
    # 3. 各都道府県自治体のデータ取得（代表例：東京都）
    print(f"\n--- Gathering Tokyo Local Government Data for {year} ---")
    for p_type in ["sugi", "hinoki"]:
        try:
            records = get_tokyo_pollen(year, p_type)
            combined_data.extend(records)
            print(f"  Successfully gathered Tokyo data for {p_type}. Records count: {len(records)}")
        except Exception as e:
            print(f"  [ERROR] Tokyo ({p_type}): {e}")
            
    if not combined_data:
        raise Exception("No pollen data could be gathered from any source.")
        
    df = pd.DataFrame(combined_data)
    
    # 重複排除やソート（念のため）
    df = df.sort_values(by=["year", "source", "prefecture", "station", "pollen_type"]).reset_index(drop=True)
    return df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pollen Data Aggregator (NPO, MOE, Local)")
    parser.add_argument("--year", type=int, default=2024, help="Target year to collect (e.g. 2024)")
    parser.add_argument("--out", type=str, default="output/pollen_summary_standard.csv", help="Path to output standard CSV")
    args = parser.parse_args()
    
    try:
        df_result = collect_all_sources(args.year)
        
        # 出力先ディレクトリの作成
        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            
        df_result.to_csv(args.out, index=False, encoding='utf-8')
        
        print("\n========================================")
        print("Aggregation Completed Successfully!")
        print(f"Output saved to: {args.out}")
        print(f"Total Records: {len(df_result)}")
        print("\nSummary by Source & Pollen Type:")
        print(df_result.groupby(["source", "pollen_type"]).size().to_string())
        print("\nSample records:")
        print(df_result.head(10).to_string())
        print("========================================")
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Aggregation failed: {e}")
