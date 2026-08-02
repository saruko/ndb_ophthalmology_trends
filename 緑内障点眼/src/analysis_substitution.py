"""
analysis_substitution.py
治療的代替パターン分析・市場構造分析・収束分析（緑内障点眼薬）

§① 記述統計（シェア・HHI）
§② 治療的代替の定量化（差分パネル回帰）
§③ 地域格差の構造分析（Theil T・収束検定）

allergy解析/src/analysis_substitution.py と同一の設計だが、代替モデルは緑内障の
処方構造に合わせている:
  - クラス内代替: PG関連薬のブランド間（ラタノプロスト ← 他のPG関連薬）
  - クラス間代替: 配合剤への移行（配合剤 ← 単剤β遮断薬・単剤PG関連薬）
"""
import os
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
import statsmodels.api as sm

# 完全パネルを形成できる個別薬剤コード（2014年度から全年度で処方実績あり）
FULL_PANEL_DRUGS = {"LATANOPROST", "TRAVOPROST", "TAFLUPROST", "BIMATOPROST",
                    "TIMOLOL", "CARTEOLOL"}
# クラス内代替モデルの説明変数（被説明変数 LATANOPROST を除いたPG関連薬）
INTRA_CLASS_X = ["TRAVOPROST", "TAFLUPROST", "BIMATOPROST"]


def _aggregate_codes():
    from preprocess_glaucoma import AGGREGATE_DEFS
    return {code for code, _, _ in AGGREGATE_DEFS}


# ─────────────────────────────────────────────
# §① 記述統計：シェアとHHI
# ─────────────────────────────────────────────

def compute_shares(df: pd.DataFrame) -> pd.DataFrame:
    """
    都道府県×年度パネルで各薬剤のGLAUCOMA_EYE_TOTAL内シェアを計算する。
    入力: ndb_processed_glaucoma_*.csv（個別薬剤コードの行のみ使用）
    """
    from preprocess_glaucoma import TOTAL_CODES
    df_ind = df[df["code"].isin(TOTAL_CODES)].copy()
    df_total = df[df["code"] == "GLAUCOMA_EYE_TOTAL"][["year", "prefecture", "count_ml"]].copy()
    df_total = df_total.rename(columns={"count_ml": "total_count"})

    df_share = df_ind.merge(df_total, on=["year", "prefecture"], how="left")
    df_share["share"] = df_share["count_ml"] / df_share["total_count"]
    df_share["share"] = df_share["share"].fillna(0).clip(0, 1)
    return df_share


def compute_hhi(df_share: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """
    都道府県×年度ごとにHerfindahl-Hirschman Index (HHI) を計算する。
    HHI = Σ(share_i²) で、1/N（完全均等）〜 1（完全独占）の範囲。
    """
    hhi = df_share.groupby(["year", "prefecture"]).apply(
        lambda g: (g["share"] ** 2).sum(), include_groups=False
    ).reset_index(name="hhi")
    hhi.to_csv(
        os.path.join(output_dir, "market_hhi_glaucoma.csv"),
        index=False, encoding="utf-8-sig"
    )
    return hhi


def compute_national_shares(df_share: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """全国レベルのシェア推移を算出する。"""
    national = df_share.groupby(["year", "code", "procedure_name"]).agg(
        {"count_ml": "sum", "total_count": "sum"}
    ).reset_index()
    national["share"] = national["count_ml"] / national["total_count"]
    national.to_csv(
        os.path.join(output_dir, "national_shares_glaucoma.csv"),
        index=False, encoding="utf-8-sig"
    )
    return national


# ─────────────────────────────────────────────
# §② 治療的代替の定量化
# ─────────────────────────────────────────────

def estimate_substitution(df_share: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """
    差分パネル回帰で治療的代替パターンを推定する。

    モデル1（クラス内代替 / PG関連薬のブランド間）:
      ΔShare(LATANOPROST)_it = β₁ΔShare(TRAVOPROST)_it + β₂ΔShare(TAFLUPROST)_it
                              + β₃ΔShare(BIMATOPROST)_it + 県FE + 年FE + ε

    モデル2（クラス間代替 / 配合剤への移行）:
      ΔShare(FDC_TOTAL)_it = β₁ΔShare(BETA単剤)_it + β₂ΔShare(PGA単剤)_it
                            + 県FE + 年FE + ε

    負のβ → 代替関係の直接的証拠。
    """
    wide = df_share[df_share["code"].isin(FULL_PANEL_DRUGS)].pivot_table(
        index=["year", "prefecture"], columns="code", values="share"
    ).reset_index()

    for col in FULL_PANEL_DRUGS:
        if col not in wide.columns:
            wide[col] = 0.0

    wide = wide.sort_values(["prefecture", "year"])

    # 1階差分
    for col in FULL_PANEL_DRUGS:
        wide[f"d_{col}"] = wide.groupby("prefecture")[col].diff()

    wide = wide.dropna(subset=[f"d_{c}" for c in FULL_PANEL_DRUGS])

    # --- モデル1: クラス内代替（ラタノプロスト ← 他のPG関連薬）---
    panel = wide.set_index(["prefecture", "year"])
    y = panel["d_LATANOPROST"]
    x_cols = [f"d_{c}" for c in INTRA_CLASS_X]
    X = panel[x_cols]

    results_list = []
    try:
        model1 = PanelOLS(y, X, entity_effects=True, time_effects=True)
        res1 = model1.fit(cov_type="clustered", cluster_entity=True)
        for var in x_cols:
            results_list.append({
                "model": "intra_class_substitution",
                "dependent": "d_LATANOPROST",
                "variable": var,
                "coefficient": res1.params[var],
                "std_err": res1.std_errors[var],
                "t_stat": res1.tstats[var],
                "p_value": res1.pvalues[var],
                "r2_within": res1.rsquared_within,
                "n_obs": res1.nobs,
            })
        report_path = os.path.join(output_dir, "substitution_intra_class_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(str(res1))
    except Exception as e:
        print(f"Intra-class substitution model failed: {e}")

    # --- モデル2: クラス間代替（配合剤 ← 単剤β遮断薬・単剤PG関連薬）---
    inter = _build_class_panel(df_share)
    if inter is not None:
        panel2 = inter.set_index(["prefecture", "year"])
        y2 = panel2["d_FDC_TOTAL"]
        X2 = panel2[["d_BETA", "d_PGA"]]
        try:
            model2 = PanelOLS(y2, X2, entity_effects=True, time_effects=True)
            res2 = model2.fit(cov_type="clustered", cluster_entity=True)
            for var in ["d_BETA", "d_PGA"]:
                results_list.append({
                    "model": "inter_class_substitution",
                    "dependent": "d_FDC_TOTAL",
                    "variable": var,
                    "coefficient": res2.params[var],
                    "std_err": res2.std_errors[var],
                    "t_stat": res2.tstats[var],
                    "p_value": res2.pvalues[var],
                    "r2_within": res2.rsquared_within,
                    "n_obs": res2.nobs,
                })
            report_path = os.path.join(output_dir, "substitution_inter_class_report.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(str(res2))
        except Exception as e:
            print(f"Inter-class substitution model failed: {e}")

    df_sub = pd.DataFrame(results_list)
    df_sub.to_csv(
        os.path.join(output_dir, "substitution_regression_glaucoma.csv"),
        index=False, encoding="utf-8-sig"
    )
    print("Saved substitution regression results.")
    return df_sub


def _build_class_panel(df_share: pd.DataFrame) -> pd.DataFrame | None:
    """FDC_TOTAL・BETA・PGA のシェアでクラス間パネルを構築する。"""
    from preprocess_glaucoma import PGA_CODES, BETA_CODES, FDC_CODES

    records = []
    for (year, pref), group in df_share.groupby(["year", "prefecture"]):
        total = group["total_count"].iloc[0] if len(group) > 0 else 0
        if total == 0:
            continue
        records.append({
            "year": year, "prefecture": pref,
            "FDC_TOTAL": group[group["code"].isin(FDC_CODES)]["count_ml"].sum() / total,
            "BETA": group[group["code"].isin(BETA_CODES)]["count_ml"].sum() / total,
            "PGA": group[group["code"].isin(PGA_CODES)]["count_ml"].sum() / total,
        })

    if not records:
        return None

    wide = pd.DataFrame(records).sort_values(["prefecture", "year"])
    for col in ["FDC_TOTAL", "BETA", "PGA"]:
        wide[f"d_{col}"] = wide.groupby("prefecture")[col].diff()
    wide = wide.dropna(subset=["d_FDC_TOTAL", "d_BETA", "d_PGA"])
    return wide


# ─────────────────────────────────────────────
# §③ 地域格差の構造分析
# ─────────────────────────────────────────────

def compute_theil_t(values: np.ndarray) -> float:
    """Theil T index（GE(1)）を計算する。"""
    values = values[values > 0]
    if len(values) < 2:
        return 0.0
    mu = np.mean(values)
    return float(np.mean((values / mu) * np.log(values / mu)))


def analyze_theil_decomposition(df: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """
    Theil T indexを年度×薬剤で計算し、格差の推移を記録する。
    （県間成分のみ。NDBオープンデータでは県内の下位地域データがないため）
    """
    print("Computing Theil T index for disparity decomposition...")
    skip = _aggregate_codes() - {"GLAUCOMA_EYE_TOTAL"}
    results = []
    for (year, code), group in df.groupby(["year", "code"]):
        if code in skip:
            continue
        rates = group["count_per_100k"].values
        theil = compute_theil_t(rates)
        results.append({
            "year": year, "code": code,
            "procedure_name": group["procedure_name"].iloc[0],
            "theil_t": theil,
            "n_prefectures": len(rates),
        })

    df_theil = pd.DataFrame(results)
    df_theil.to_csv(
        os.path.join(output_dir, "theil_index_glaucoma.csv"),
        index=False, encoding="utf-8-sig"
    )
    print("Saved theil_index_glaucoma.csv")
    return df_theil


def analyze_convergence(df: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """
    σ-convergence と β-convergence を検定する。

    σ-convergence: CV(count_per_100k)の時系列変化（減少→収束）
    β-convergence: log(rate_tN/rate_t0) = α + β*log(rate_t0) + ε
                   β < 0 → 初期値が低い県ほど成長率が高い → 収束
    """
    print("Testing σ-convergence and β-convergence...")
    convergence_results = []

    target_codes = (FULL_PANEL_DRUGS
                    | {"PGA", "BETA", "FDC_TOTAL", "GLAUCOMA_EYE_TOTAL"})

    for code in sorted(target_codes):
        sub = df[df["code"] == code].copy()
        if sub.empty:
            continue

        years = sorted(sub["year"].unique())
        if len(years) < 3:
            continue

        proc_name = sub["procedure_name"].iloc[0]

        # σ-convergence: CV per year
        cv_series = sub.groupby("year")["count_per_100k"].apply(
            lambda s: s.std(ddof=1) / s.mean() if s.mean() > 0 else np.nan
        )
        cv_first = cv_series.iloc[0] if not np.isnan(cv_series.iloc[0]) else None
        cv_last = cv_series.iloc[-1] if not np.isnan(cv_series.iloc[-1]) else None

        # OLS: CV_t = α + β*t で傾きの有意性を検定
        cv_df = cv_series.dropna().reset_index()
        cv_df.columns = ["year", "cv"]
        sigma_slope = None
        sigma_p = None
        if len(cv_df) >= 3:
            X_t = sm.add_constant(cv_df["year"])
            res_sigma = sm.OLS(cv_df["cv"], X_t).fit()
            sigma_slope = res_sigma.params.iloc[1]
            sigma_p = res_sigma.pvalues.iloc[1]

        # β-convergence
        t0 = years[0]
        tN = years[-1]
        df_t0 = sub[sub["year"] == t0][["prefecture", "count_per_100k"]].rename(
            columns={"count_per_100k": "rate_t0"}
        )
        df_tN = sub[sub["year"] == tN][["prefecture", "count_per_100k"]].rename(
            columns={"count_per_100k": "rate_tN"}
        )
        merged = df_t0.merge(df_tN, on="prefecture")
        merged = merged[(merged["rate_t0"] > 0) & (merged["rate_tN"] > 0)]

        beta_coef = None
        beta_p = None
        beta_r2 = None
        if len(merged) >= 10:
            merged["log_rate_t0"] = np.log(merged["rate_t0"])
            merged["log_growth"] = np.log(merged["rate_tN"] / merged["rate_t0"])
            X_b = sm.add_constant(merged["log_rate_t0"])
            res_beta = sm.OLS(merged["log_growth"], X_b).fit()
            beta_coef = res_beta.params.iloc[1]
            beta_p = res_beta.pvalues.iloc[1]
            beta_r2 = res_beta.rsquared

        convergence_results.append({
            "code": code,
            "procedure_name": proc_name,
            "start_year": t0,
            "end_year": tN,
            "cv_start": cv_first,
            "cv_end": cv_last,
            "sigma_slope": sigma_slope,
            "sigma_p_value": sigma_p,
            "sigma_converging": sigma_slope < 0 if sigma_slope is not None else None,
            "beta_coefficient": beta_coef,
            "beta_p_value": beta_p,
            "beta_r2": beta_r2,
            "beta_converging": beta_coef < 0 if beta_coef is not None else None,
        })

    df_conv = pd.DataFrame(convergence_results)
    df_conv.to_csv(
        os.path.join(output_dir, "convergence_analysis_glaucoma.csv"),
        index=False, encoding="utf-8-sig"
    )
    print("Saved convergence_analysis_glaucoma.csv")
    return df_conv


def analyze_specialization_vs_disparity(df: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """
    薬剤の「専門性スコア」（処方頻度の逆数 ∝ 希少性）と地域格差（Gini）の関係を定量化する。
    最新年度の横断データで評価。
    """
    from analysis_glaucoma import calculate_gini
    from preprocess_glaucoma import TOTAL_CODES

    print("Analyzing specialization-disparity correlation...")

    year_target = df["year"].max()
    df_yr = df[(df["year"] == year_target) & df["code"].isin(TOTAL_CODES)]

    results = []
    for code, group in df_yr.groupby("code"):
        rates = group["count_per_100k"].values
        mean_rate = np.mean(rates)
        if mean_rate <= 0:
            continue
        gini = calculate_gini(rates)
        cv = np.std(rates, ddof=1) / mean_rate if mean_rate > 0 else 0
        results.append({
            "code": code,
            "procedure_name": group["procedure_name"].iloc[0],
            "mean_rate_per_100k": mean_rate,
            "log_mean_rate": np.log(mean_rate) if mean_rate > 0 else np.nan,
            "specialization_score": 1.0 / mean_rate,
            "gini": gini,
            "cv": cv,
        })

    df_spec = pd.DataFrame(results)
    if len(df_spec) >= 4:
        from scipy.stats import spearmanr
        rho, p = spearmanr(df_spec["specialization_score"], df_spec["gini"])
        df_spec.attrs["spearman_rho"] = rho
        df_spec.attrs["spearman_p"] = p
        print(f"  Specialization vs Gini: ρ={rho:.4f}, p={p:.4f}")

    df_spec.to_csv(
        os.path.join(output_dir, "specialization_disparity_glaucoma.csv"),
        index=False, encoding="utf-8-sig"
    )
    print("Saved specialization_disparity_glaucoma.csv")
    return df_spec


# ─────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────

def run_substitution_analysis(processed_csv_path: str, output_dir: str):
    """全ての代替パターン・市場構造・収束分析を実行する。"""
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(processed_csv_path)

    print("\n" + "=" * 60)
    print("§① Market structure: shares and HHI")
    print("=" * 60)
    df_share = compute_shares(df)
    compute_hhi(df_share, output_dir)
    compute_national_shares(df_share, output_dir)

    print("\n" + "=" * 60)
    print("§② Therapeutic substitution estimation")
    print("=" * 60)
    estimate_substitution(df_share, output_dir)

    print("\n" + "=" * 60)
    print("§③ Disparity structure: Theil, convergence, specialization")
    print("=" * 60)
    analyze_theil_decomposition(df, output_dir)
    analyze_convergence(df, output_dir)
    analyze_specialization_vs_disparity(df, output_dir)

    print("\nAll substitution & structure analyses completed.")


if __name__ == "__main__":
    run_substitution_analysis(
        processed_csv_path="緑内障点眼/processed_nokouhi/ndb_processed_glaucoma_zero.csv",
        output_dir="緑内障点眼/processed_nokouhi",
    )
