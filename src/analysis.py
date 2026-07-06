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
    # ゼロ除算・対数エラー防止
    rates = np.maximum(rates, 0.001)
    log_rates = np.log(rates)
    
    # 定数項を追加
    X = sm.add_constant(years)
    model = sm.OLS(log_rates, X)
    results = model.fit()
    
    b1 = results.params[1]
    b1_se = results.bse[1]
    
    # APCと95%信頼区間
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
    """
    pwlf (Piecewise Linear Fitting)を用いた折れ線対数線形回帰
    セグメントごとのAPCを算出する
    """
    rates = np.maximum(rates, 0.001)
    log_rates = np.log(rates)
    
    # ピースワイズ線形回帰モデルの初期化
    my_pwlf = pwlf.PiecewiseLinFit(years, log_rates)

    # 指定セグメント数でのフィッティング（セグメント数=2の場合、変化点1つ）
    # セグメントの境界（ノット）を見つける
    try:
        knots = my_pwlf.fit(num_segments)
    except Exception as e:
        print(f"pwlf fit failed: {e}. Falling back to simple linear model.")
        return None

    # 各セグメントでの傾き（slopes）を取得
    slopes = my_pwlf.slopes

    apcs = []
    for i in range(num_segments):
        start_year = knots[i]
        end_year = knots[i+1]

        # 退化セグメント（区間幅が1年未満）はスキップ
        if abs(end_year - start_year) < 1.0:
            continue

        slope = slopes[i]

        # オーバーフロー防止: 極端な傾きをクランプ
        slope_clamped = np.clip(slope, -5, 5)
        apc = (np.exp(slope_clamped) - 1) * 100
        apcs.append({
            "segment": i + 1,
            "start_year": round(start_year, 1),
            "end_year": round(end_year, 1),
            "slope": slope,
            "apc": apc
        })
        
    return {
        "knots": knots.tolist(),
        "segments": apcs
    }

def analyze_trends_and_apc(df, output_dir):
    """主要術式の全国トレンドおよびAPCを算出して保存する"""
    print("Analyzing national trends and APC...")
    
    # 全国単位での集計（年次・術式コード別）
    df_national = df.groupby(["year", "code", "procedure_name"]).agg({
        "count": "sum",
        "population_total": "sum",
        "population_65plus": "sum"
    }).reset_index()
    
    df_national["count_per_100k"] = (df_national["count"] / df_national["population_total"]) * 100000
    df_national["count_per_100k_65plus"] = (df_national["count"] / df_national["population_65plus"]) * 100000
    
    # 術式ごとのAPC計算
    apc_results = []
    joinpoint_results = []
    
    # K268は2022年のコード体系変更（MIGS新コード追加）によりデータの連続性が
    # 断絶しているため、APC・Joinpoint回帰は2014-2021年に限定する
    APC_TRUNCATE = {"K268": 2021}

    for code, group in df_national.groupby("code"):
        proc_name = group["procedure_name"].iloc[0]

        max_year = APC_TRUNCATE.get(code, None)
        if max_year:
            apc_group = group[group["year"] <= max_year]
            print(f"  {code}: APC/Joinpoint truncated to <={max_year} (code system change)")
        else:
            apc_group = group

        years = apc_group["year"].values
        rates = apc_group["count_per_100k"].values

        # 1. 単純線形回帰のAPC
        linear_apc = calculate_linear_apc_wrapper(years, rates, code, proc_name)
        apc_results.append(linear_apc)

        # 2. Joinpoint (pwlf) のAPC（データ数が十分ある場合、例えば5点以上）
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
    df_apc.to_csv(os.path.join(output_dir, "national_apc_linear.csv"), index=False, encoding="utf-8-sig")
    print("Saved national_apc_linear.csv")

    if joinpoint_results:
        df_jp = pd.DataFrame(joinpoint_results)
        df_jp.to_csv(os.path.join(output_dir, "national_apc_joinpoint.csv"), index=False, encoding="utf-8-sig")
        print("Saved national_apc_joinpoint.csv")

    df_national.to_csv(os.path.join(output_dir, "national_trends.csv"), index=False, encoding="utf-8-sig")
    return df_national

def calculate_linear_apc_wrapper(years, rates, code, proc_name):
    res = calculate_apc_linear(years, rates)
    res.update({
        "code": code,
        "procedure_name": proc_name,
        "start_year": min(years),
        "end_year": max(years)
    })
    return res

def analyze_geographic_disparity(df, output_dir):
    """都道府県別の格差指標（CV, Gini）を年次・術式ごとに計算する"""
    print("Analyzing geographic disparity (CV & Gini)...")
    
    disparity_results = []
    
    # 年・術式ごとのループ
    for (year, code), group in df.groupby(["year", "code"]):
        proc_name = group["procedure_name"].iloc[0]
        rates = group["count_per_100k"].values
        
        # 変動係数 (CV)
        mean_rate = np.mean(rates)
        std_rate = np.std(rates, ddof=1) if len(rates) > 1 else 0
        cv = std_rate / mean_rate if mean_rate > 0 else 0
        
        # Gini係数
        gini = calculate_gini(rates)
        
        # 最小・最大都道府県
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
    df_disp.to_csv(os.path.join(output_dir, "geographic_disparity.csv"), index=False, encoding="utf-8-sig")
    print("Saved geographic_disparity.csv")
    return df_disp

def analyze_covariates_correlation(df, output_dir):
    """高齢化率、専門医数、施設数とのSpearman相関を算出する"""
    print("Analyzing correlation with covariates...")
    
    corr_results = []
    
    # 術式・年次ごとに相関を計算
    for (year, code), group in df.groupby(["year", "code"]):
        proc_name = group["procedure_name"].iloc[0]
        
        # 必要な変数の抽出（欠損値を除く）
        valid_data = group[[
            "count_per_100k", "aging_rate", "docs_per_100k", "facilities_per_100k"
        ]].dropna()
        
        if len(valid_data) < 5:
            continue
            
        rate = valid_data["count_per_100k"].values
        aging = valid_data["aging_rate"].values
        docs = valid_data["docs_per_100k"].values
        facs = valid_data["facilities_per_100k"].values

        # 定数配列（分散ゼロ）はSpearman相関が定義できないためスキップ
        if np.std(rate) == 0 or np.std(aging) == 0 or np.std(docs) == 0 or np.std(facs) == 0:
            continue

        # Spearman相関
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
    df_corr.to_csv(os.path.join(output_dir, "covariates_correlation.csv"), index=False, encoding="utf-8-sig")
    print("Saved covariates_correlation.csv")
    return df_corr

def _run_panel_ols(df, output_dir, suffix="", entity_effects=True, time_effects=True,
                   cov_type="clustered", cluster_entity=True):
    """
    パネルOLS回帰の共通実装。
    suffix: 出力ファイル名の末尾識別子（感度分析用）
    """
    regression_summary = []

    for code, group in df.groupby("code"):
        proc_name = group["procedure_name"].iloc[0]
        panel_df = group.set_index(["prefecture", "year"])
        panel_df = panel_df[[
            "count_per_100k", "aging_rate", "docs_per_100k", "facilities_per_100k"
        ]].dropna()

        if panel_df.empty:
            continue

        y = panel_df["count_per_100k"]
        X = panel_df[["aging_rate", "docs_per_100k", "facilities_per_100k"]]

        try:
            model = PanelOLS(y, X, entity_effects=entity_effects, time_effects=time_effects)
            results = model.fit(cov_type=cov_type, cluster_entity=cluster_entity)

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

            report_path = os.path.join(output_dir, f"panel_regression_{code}{suffix}_report.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(str(results))
            print(f"Saved regression report for {code}{suffix} to {report_path}")

        except Exception as e:
            print(f"Panel regression failed for {code}{suffix}: {e}")

    if regression_summary:
        df_reg = pd.DataFrame(regression_summary)
        out_name = f"panel_regression_summary{suffix}.csv"
        df_reg.to_csv(os.path.join(output_dir, out_name), index=False, encoding="utf-8-sig")
        print(f"Saved {out_name}")
        return df_reg
    return None


def run_panel_regression(df, output_dir):
    """
    主解析: Two-way FE（都道府県＋年固定効果）、都道府県クラスターSE
    感度分析: 共変量が実測値の年度のみ（補間年を除外）
    """
    print("Running panel data regression (Two-way FE, Clustered SE)...")

    # 主解析: two-way FE
    df_reg = _run_panel_ols(df, output_dir)

    # 感度分析: 共変量が実測値の調査実施年のみ
    # 眼科医数: 偶数年(2014,2016,2018,2020,2022)、施設数: 2014,2017,2020,2023
    # 共通して実測値が存在する年: 2014, 2020（両方とも実測）
    # 医師数が実測の偶数年かつ施設数が実測の年 = 2014, 2020
    # より広い基準: 医師数が実測の偶数年（施設数は最大3年の補間）
    survey_years = [2014, 2016, 2018, 2020, 2022, 2024]
    df_survey = df[df["year"].isin(survey_years)]
    if not df_survey.empty:
        print("Running sensitivity analysis (survey years only: %s)..." % survey_years)
        _run_panel_ols(df_survey, output_dir, suffix="_sensitivity_survey_years")

    return df_reg

def analyze_all(processed_csv_path, output_dir):
    """すべての統計解析を実行するエントリーポイント"""
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(processed_csv_path)
    
    # 各種解析の実行
    analyze_trends_and_apc(df, output_dir)
    analyze_geographic_disparity(df, output_dir)
    analyze_covariates_correlation(df, output_dir)
    run_panel_regression(df, output_dir)
    print("All analyses completed successfully!")

if __name__ == "__main__":
    analyze_all(
        processed_csv_path="data/processed/ndb_processed_zero.csv",
        output_dir="data/processed"
    )
