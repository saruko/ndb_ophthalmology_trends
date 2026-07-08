import os
import numpy as np
import pandas as pd
import statsmodels.api as sm

def calculate_gini(array):
    """Gini係数を計算する（本体 src/analysis.py と同等）"""
    array = np.array(array, dtype=np.float64)
    if np.any(array < 0):
        # 負の数はGini係数に適さない
        array -= np.min(array)
    array += 0.0000001  # ゼロ除算防止
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return ((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array)))

def calculate_apc_linear(years, rates):
    """
    単純対数線形回帰による単一のAnnual Percent Change (APC)の算出
    log(rate) = b0 + b1 * year
    APC = (exp(b1) - 1) * 100
    """
    rates = np.maximum(rates, 0.001)
    log_rates = np.log(rates)
    
    # 定数項を追加
    X = sm.add_constant(years)
    model = sm.OLS(log_rates, X)
    results = model.fit()
    
    b1 = results.params[1]
    
    # APCと95%信頼区間
    conf = results.conf_int(alpha=0.05)
    b1_low = conf[1, 0]
    b1_high = conf[1, 1]
    
    apc = (np.exp(b1) - 1) * 100
    apc_low = (np.exp(b1_low) - 1) * 100
    apc_high = (np.exp(b1_high) - 1) * 100
    
    return {
        "apc": apc,
        "apc_low": apc_low,
        "apc_high": apc_high,
        "p_value": results.pvalues[1],
        "r2": results.rsquared
    }

def analyze_pterygium(long_csv_path, covariate_path, output_dir):
    """
    翼状片手術データの統計解析を行う
    """
    print(f"Starting analysis_pterygium. Input: {long_csv_path}")
    
    df_long = pd.read_csv(long_csv_path)
    df_cov = pd.read_csv(covariate_path)
    
    # 共変量データのマージ
    df_long["prefecture"] = df_long["prefecture"].str.strip()
    df_cov["prefecture"] = df_cov["prefecture"].str.strip()
    
    df_merged = pd.merge(df_long, df_cov, on=["year", "prefecture"], how="left")
    
    # 指標算出
    df_merged["count_per_100k"] = (df_merged["count"] / df_merged["population_total"]) * 100000
    df_merged["count_per_100k_65plus"] = (df_merged["count"] / df_merged["population_65plus"]) * 100000
    df_merged["aging_rate"] = df_merged["population_65plus"] / df_merged["population_total"]
    df_merged["docs_per_100k"] = (df_merged["ophthalmologists"] / df_merged["population_total"]) * 100000
    df_merged["facilities_per_100k"] = (df_merged["facilities"] / df_merged["population_total"]) * 100000
    
    # 都道府県・年度・settingごとの人口10万対手術件数データを保存
    rate_csv_path = os.path.join(output_dir, "pterygium_rate_per100k.csv")
    df_merged.to_csv(rate_csv_path, index=False, encoding="utf-8-sig")
    print(f"Saved {rate_csv_path}")
    
    # 2. 地域格差指標（ジニ係数, CV）の年次算出
    disparity_results = []
    
    # setting (outpatient / inpatient / total) ごとにループ
    for setting in ["outpatient", "inpatient", "total"]:
        df_sub = df_merged[df_merged["setting"] == setting]
        if df_sub.empty:
            continue
            
        years = sorted(df_sub["year"].unique())
        for y in years:
            # 2017年の「inpatient」および「total」は欠測として除外
            if y == 2017 and setting in ["inpatient", "total"]:
                continue
                
            df_year = df_sub[df_sub["year"] == y]
            if len(df_year) < 47:
                # 47都道府県揃っていない場合は警告
                print(f"  Warning: Only {len(df_year)} prefectures found for {setting} in {y}")
                
            rates = df_year["count_per_100k"].values
            
            # 変動係数 (CV)
            mean_rate = np.mean(rates)
            std_rate = np.std(rates, ddof=1) if len(rates) > 1 else 0
            cv = std_rate / mean_rate if mean_rate > 0 else 0
            
            # Gini係数
            gini = calculate_gini(rates)
            
            # 最小・最大都道府県
            idx_min = np.argmin(rates)
            idx_max = np.argmax(rates)
            
            min_pref = df_year["prefecture"].iloc[idx_min]
            min_val = rates[idx_min]
            max_pref = df_year["prefecture"].iloc[idx_max]
            max_val = rates[idx_max]
            
            disparity_results.append({
                "year": y,
                "setting": setting,
                "mean_rate_per_100k": mean_rate,
                "cv": cv,
                "gini": gini,
                "min_prefecture": min_pref,
                "min_rate": min_val,
                "max_prefecture": max_pref,
                "max_rate": max_val,
                "max_to_min_ratio": max_val / min_val if min_val > 0 else np.nan
            })
            
    df_disp = pd.DataFrame(disparity_results)
    disp_csv_path = os.path.join(output_dir, "pterygium_gini_cv_trend.csv")
    df_disp.to_csv(disp_csv_path, index=False, encoding="utf-8-sig")
    print(f"Saved {disp_csv_path}")
    
    # 3. 全国レベルのAPCの計算
    # 全国単位での集計（年次・setting別）
    df_national = df_merged.groupby(["year", "setting"]).agg({
        "count": "sum",
        "population_total": "sum"
    }).reset_index()
    df_national["count_per_100k"] = (df_national["count"] / df_national["population_total"]) * 100000
    
    apc_results = []
    for setting in ["outpatient", "inpatient", "total"]:
        df_nat_sub = df_national[df_national["setting"] == setting].copy()
        
        # 2017年の除外（欠測処理）
        if setting in ["inpatient", "total"]:
            df_nat_sub = df_nat_sub[df_nat_sub["year"] != 2017]
            
        if len(df_nat_sub) < 3:
            continue
            
        years_arr = df_nat_sub["year"].values
        rates_arr = df_nat_sub["count_per_100k"].values
        
        res = calculate_apc_linear(years_arr, rates_arr)
        res.update({
            "setting": setting,
            "start_year": int(min(years_arr)),
            "end_year": int(max(years_arr))
        })
        apc_results.append(res)
        
    df_apc = pd.DataFrame(apc_results)
    apc_csv_path = os.path.join(output_dir, "pterygium_apc_linear.csv")
    df_apc.to_csv(apc_csv_path, index=False, encoding="utf-8-sig")
    print(f"Saved {apc_csv_path}")
    
    return df_merged, df_disp, df_apc

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    long_csv = os.path.join(base_dir, "processed/pterygium_long.csv")
    covariate = os.path.join(base_dir, "../data/covariates/prefecture_covariates.csv")
    output = os.path.join(base_dir, "processed")
    
    analyze_pterygium(long_csv, covariate, output)
