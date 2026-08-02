import os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm
from linearmodels.panel import PanelOLS
import pwlf

def calculate_gini(array):
    """Gini係数を計算する"""
    array = np.array(array, dtype=np.float64)
    if np.any(array < 0):
        array -= np.min(array)
    array += 0.0000001  # ゼロ除算防止
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return ((np.sum((2 * index - n - 1) * array)) / (n * np.sum(array)))

def calculate_apc_linear(years, rates):
    """単純対数線形回帰による単一のAnnual Percent Change (APC)の算出"""
    rates = np.maximum(rates, 0.001)
    log_rates = np.log(rates)
    X = sm.add_constant(years)
    model = sm.OLS(log_rates, X)
    results = model.fit()
    
    b1 = results.params[1]
    b1_se = results.bse[1]
    
    apc = (np.exp(b1) - 1) * 100
    apc_low = (np.exp(b1 - 1.96 * b1_se) - 1) * 100
    apc_high = (np.exp(b1 + 1.96 * b1_se) - 1) * 100
    
    return {
        "apc": apc,
        "apc_low": apc_low,
        "apc_high": apc_high,
        "p_value": results.pvalues[1],
        "r2": results.rsquared
    }

def calculate_joinpoint_apc(years, rates, num_segments=2):
    """pwlfを用いた折れ線対数線形回帰によるセグメント別APCの算出"""
    rates = np.maximum(rates, 0.001)
    log_rates = np.log(rates)
    my_pwlf = pwlf.PiecewiseLinFit(years, log_rates)
    
    try:
        knots = my_pwlf.fit(num_segments)
    except Exception as e:
        print(f"pwlf fit failed: {e}. Falling back.")
        return None

    slopes = my_pwlf.slopes
    apcs = []
    for i in range(num_segments):
        start_year = knots[i]
        end_year = knots[i+1]
        if abs(end_year - start_year) < 1.0:
            continue
        slope = slopes[i]
        slope_clamped = np.clip(slope, -5, 5)
        apc = (np.exp(slope_clamped) - 1) * 100
        apcs.append({
            "segment": i + 1,
            "start_year": round(start_year, 1),
            "end_year": round(end_year, 1),
            "slope": slope,
            "apc": apc
        })
    return {"knots": knots.tolist(), "segments": apcs}

def analyze_trends_and_apc(df, output_dir):
    """緑内障点眼薬の全国トレンドおよびAPCを計算して保存する"""
    print("Analyzing national trends and APC for glaucoma eye drops...")

    # 全国単位での集計
    # 処方数量はmL統一換算後の count_ml を用いる（count は単位混在の公表値素合算）
    df_national = df.groupby(["year", "code", "procedure_name"]).agg({
        "count": "sum",
        "count_ml": "sum",
        "population_total": "sum",
        "population_65plus": "sum"
    }).reset_index()

    df_national["count_per_100k"] = (df_national["count_ml"] / df_national["population_total"]) * 100000
    df_national["count_per_100k_65plus"] = (df_national["count_ml"] / df_national["population_65plus"]) * 100000

    apc_results = []
    joinpoint_results = []

    for code, group in df_national.groupby("code"):
        proc_name = group["procedure_name"].iloc[0]
        start_year = 2014
        
        apc_group = group[group["year"] >= start_year]
        years = apc_group["year"].values
        rates = apc_group["count_per_100k"].values
        
        if len(years) < 3:
            print(f"  {code}: Too few data points ({len(years)}) for APC.")
            continue

        # 1. 単純線形APC
        res = calculate_apc_linear(years, rates)
        res.update({
            "code": code,
            "procedure_name": proc_name,
            "start_year": int(min(years)),
            "end_year": int(max(years))
        })
        apc_results.append(res)

        # 2. Joinpoint APC (データ数が5点以上の場合)
        if len(years) >= 5:
            jp = calculate_joinpoint_apc(years, rates, num_segments=2)
            if jp:
                for seg in jp["segments"]:
                    joinpoint_results.append({
                        "code": code,
                        "procedure_name": proc_name,
                        "knots": str([round(k, 2) for k in jp["knots"]]),
                        "segment": seg["segment"],
                        "start_year": seg["start_year"],
                        "end_year": seg["end_year"],
                        "apc": seg["apc"]
                    })
                    
    df_apc = pd.DataFrame(apc_results)
    df_apc.to_csv(os.path.join(output_dir, "national_apc_linear_glaucoma.csv"), index=False, encoding="utf-8-sig")
    
    if joinpoint_results:
        df_jp = pd.DataFrame(joinpoint_results)
        df_jp.to_csv(os.path.join(output_dir, "national_apc_joinpoint_glaucoma.csv"), index=False, encoding="utf-8-sig")
        
    df_national.to_csv(os.path.join(output_dir, "national_trends_glaucoma.csv"), index=False, encoding="utf-8-sig")
    print("Saved national trends and APC CSVs.")
    return df_national

def analyze_geographic_disparity(df, output_dir):
    """都道府県別の格差指標（CV, Gini）を年次・薬剤コードごとに計算する"""
    print("Analyzing geographic disparity (CV & Gini) for glaucoma eye drops...")

    disparity_results = []

    for (year, code), group in df.groupby(["year", "code"]):
            
        proc_name = group["procedure_name"].iloc[0]
        rates = group["count_per_100k"].values
        
        mean_rate = np.mean(rates)
        std_rate = np.std(rates, ddof=1) if len(rates) > 1 else 0
        cv = std_rate / mean_rate if mean_rate > 0 else 0
        gini = calculate_gini(rates)
        
        idx_min = np.argmin(rates)
        idx_max = np.argmax(rates)
        
        min_pref = group["prefecture"].iloc[idx_min]
        min_val = rates[idx_min]
        max_pref = group["prefecture"].iloc[idx_max]
        max_val = rates[idx_max]
        
        disparity_results.append({
            "year": year,
            "code": code,
            "procedure_name": proc_name,
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
    df_disp.to_csv(os.path.join(output_dir, "geographic_disparity_glaucoma.csv"), index=False, encoding="utf-8-sig")
    print("Saved geographic_disparity_glaucoma.csv")
    return df_disp

def analyze_covariates_correlation(df, output_dir):
    """高齢化率、眼科専門医数、眼科施設数とのSpearman相関を算出する"""
    print("Analyzing correlation with covariates for glaucoma eye drops...")

    corr_results = []

    for (year, code), group in df.groupby(["year", "code"]):
        proc_name = group["procedure_name"].iloc[0]
        
        valid_data = group[[
            "count_per_100k", "aging_rate", "docs_per_100k", "facilities_per_100k"
        ]].dropna()
        
        if len(valid_data) < 5:
            continue
            
        rate = valid_data["count_per_100k"].values
        aging = valid_data["aging_rate"].values
        docs = valid_data["docs_per_100k"].values
        facs = valid_data["facilities_per_100k"].values

        if np.std(rate) == 0 or np.std(aging) == 0 or np.std(docs) == 0 or np.std(facs) == 0:
            continue

        rho_aging, p_aging = spearmanr(rate, aging)
        rho_docs, p_docs = spearmanr(rate, docs)
        rho_facs, p_facs = spearmanr(rate, facs)
        
        corr_results.append({
            "year": year,
            "code": code,
            "procedure_name": proc_name,
            "sample_size": len(valid_data),
            "spearman_rho_aging": rho_aging,
            "p_value_aging": p_aging,
            "spearman_rho_docs": rho_docs,
            "p_value_docs": p_docs,
            "spearman_rho_facilities": rho_facs,
            "p_value_facilities": p_facs
        })
        
    df_corr = pd.DataFrame(corr_results)
    df_corr.to_csv(os.path.join(output_dir, "covariates_correlation_glaucoma.csv"), index=False, encoding="utf-8-sig")
    print("Saved covariates_correlation_glaucoma.csv")
    return df_corr

def run_panel_regression(df, output_dir, summary_filename="panel_regression_summary_glaucoma.csv"):
    """Two-way FE（都道府県＋年固定効果）、都道府県クラスターSEでのパネル回帰"""
    print("Running panel data regression...")

    regression_summary = []

    for code, group in df.groupby("code"):
        proc_name = group["procedure_name"].iloc[0]

        panel_df = group.copy()
        panel_df = panel_df.set_index(["prefecture", "year"])
        panel_df = panel_df[[
            "count_per_100k", "aging_rate", "docs_per_100k", "facilities_per_100k"
        ]].dropna()

        if panel_df.empty:
            continue

        y = panel_df["count_per_100k"]
        X = panel_df[["aging_rate", "docs_per_100k", "facilities_per_100k"]]

        try:
            # Two-way FE Model
            model = PanelOLS(y, X, entity_effects=True, time_effects=True)
            results = model.fit(cov_type="clustered", cluster_entity=True)

            for var in ["aging_rate", "docs_per_100k", "facilities_per_100k"]:
                regression_summary.append({
                    "code": code,
                    "procedure_name": proc_name,
                    "variable": var,
                    "coefficient": results.params[var],
                    "std_err": results.std_errors[var],
                    "t_stat": results.tstats[var],
                    "p_value": results.pvalues[var],
                    "r2_within": results.rsquared_within,
                    "n_obs": results.nobs
                })

            report_path = os.path.join(output_dir, f"panel_regression_{code}_glaucoma_report.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(str(results))
            print(f"Saved regression report for {code} to {report_path}")

        except Exception as e:
            print(f"Panel regression failed for {code}: {e}")

    if regression_summary:
        df_reg = pd.DataFrame(regression_summary)
        df_reg.to_csv(os.path.join(output_dir, summary_filename), index=False, encoding="utf-8-sig")
        print(f"Saved {summary_filename}")
        return df_reg
    return None

def analyze_glaucoma_all(processed_csv_path, output_dir):
    """すべての緑内障点眼薬の統計解析を実行するエントリーポイント"""
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(processed_csv_path)
    
    analyze_trends_and_apc(df, output_dir)
    analyze_geographic_disparity(df, output_dir)
    analyze_covariates_correlation(df, output_dir)
    run_panel_regression(df, output_dir)
    print("All glaucoma analyses completed successfully!")

if __name__ == "__main__":
    analyze_glaucoma_all(
        processed_csv_path="緑内障点眼/processed_nokouhi/ndb_processed_glaucoma_zero.csv",
        output_dir="緑内障点眼/processed_nokouhi"
    )
