"""抗VEGF薬の追加解析（変化点・65歳以上分母・収束・感度・性差検定・県別突合）。

    python 抗VEGF薬解析/analyze_advanced.py
    python 抗VEGF薬解析/analyze_advanced.py --nokouhi

入力（run_antivegf_pipeline.py と analyze_g016.py の出力）:
    national_trends_antivegf.csv   年度×解析単位の数量・人口10万対
    panel_zero/five/random.csv     都道府県×年度×解析単位のパネル
    processed_agesex_zero.csv      年齢性別内訳（秘匿0補完）
    g016_prefecture_panel.csv      G016の都道府県×年度（秘匿なし）

出力（processed/ → organize_outputs.py で 03_解析結果/ 配下へ）:
    trend_joinpoint_antivegf.csv        分節対数線形回帰（区間別APCとAAPC）
    prefecture_per_65plus_ranking_antivegf.csv  65歳以上10万対の県別ランキング
    geographic_disparity_65plus_antivegf.csv    65歳以上分母での格差指標
    convergence_beta_antivegf.csv       β収束・σ収束
    sensitivity_apc_antivegf.csv        補完戦略別のAPC
    agesex_sex_ratio_tests.csv          男性比率の傾向検定（参考値）
    g016_vs_drug_by_prefecture.csv      G016算定回数と薬剤数量の県別突合

【注意】
- 年齢調整率は算出できない。NDBオープンデータは都道府県別表と年齢性別表が
  独立に公表され、**都道府県×年齢のクロス集計が存在しない**ため。
  代替として65歳以上人口を分母にした率を併記する。
- agesex_sex_ratio_tests.csv の検定は「バイアル本数」を観測単位としており、
  独立した患者ではない。p値は参考値であって推論の根拠にしてはならない。
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import find  # noqa: E402
from analysis_antivegf import calculate_apc_linear, calculate_gini  # noqa: E402

ANTIVEGF_DIR = os.path.dirname(os.path.abspath(__file__))

# 変化点解析の対象（データ点が多く、臨床的に解釈できる単位に絞る）
JOINPOINT_CODES = [
    "ANTI_VEGF_TOTAL", "AFLIBERCEPT_ALL", "AFLIBERCEPT",
    "RANIBIZUMAB_ALL", "RANIBIZUMAB_ORIG",
]
MIN_SEGMENT_POINTS = 3   # 1区間あたりの最小データ点数
MAX_JOINPOINTS = 2

# 年齢階級の順序（経年比較用19区分）
AGE_ORDER = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳",
    "25～29歳", "30～34歳", "35～39歳", "40～44歳", "45～49歳",
    "50～54歳", "55～59歳", "60～64歳", "65～69歳", "70～74歳",
    "75～79歳", "80～84歳", "85～89歳", "90歳以上",
]


# ── 1. 変化点解析（分節対数線形回帰） ────────────────────────────

def _hinge_design(years, taus):
    """log(rate) = b0 + b1*t + Σ d_k * max(0, t - tau_k) の計画行列。

    連続な折れ線（区間の境目で値が跳ばない）を仮定する。Joinpoint Regression
    Program の既定モデルと同じ形。
    """
    t = np.asarray(years, dtype=float)
    cols = [np.ones_like(t), t] + [np.maximum(0.0, t - tau) for tau in taus]
    return np.column_stack(cols)


def _candidate_taus(years, n_join):
    """各区間が MIN_SEGMENT_POINTS 点以上になる変化点の組を列挙する。

    変化点は観測年上でのみ探索する（年の途中に置いても解釈できないため）。
    """
    n = len(years)
    lo, hi = MIN_SEGMENT_POINTS - 1, n - MIN_SEGMENT_POINTS
    idx = range(lo, hi + 1)
    if n_join == 0:
        return [()]
    if n_join == 1:
        return [(years[i],) for i in idx]
    return [(years[i], years[j]) for i in idx for j in idx
            if j - i >= MIN_SEGMENT_POINTS]


def _fit_segmented(years, rates, taus):
    """指定した変化点でモデルを当てはめ、区間ごとの傾きと分散を返す。"""
    y = np.log(np.maximum(rates, 0.001))
    X = _hinge_design(years, taus)
    res = sm.OLS(y, X).fit()
    V = np.asarray(res.cov_params())
    beta = np.asarray(res.params)

    # 区間 k の傾き = b1 + Σ_{j<=k} d_j → 係数ベクトル c_k との内積
    slopes = []
    for k in range(len(taus) + 1):
        c = np.zeros(len(beta))
        c[1] = 1.0
        for j in range(k):
            c[2 + j] = 1.0
        slopes.append(c)
    return res, beta, V, slopes


def _apc_from_contrast(beta, V, c):
    """係数の線形結合（＝対数傾き）を APC(%) と95%CIに変換する。"""
    slope = float(c @ beta)
    se = float(np.sqrt(max(c @ V @ c, 0.0)))
    return {
        "apc": (np.exp(slope) - 1) * 100,
        "apc_low": (np.exp(slope - 1.96 * se) - 1) * 100,
        "apc_high": (np.exp(slope + 1.96 * se) - 1) * 100,
        "slope_log": slope, "slope_se": se,
    }


def joinpoint(series, out_dir):
    """BIC最小のモデルを選び、区間別APCと期間全体のAAPCを算出する。

    series: {code: (name, years, rates)} の辞書。
    AAPC は区間長で重みづけした平均傾きから求める（Clegg et al. 2009 と同じ定義）。
    """
    rows = []
    for code, (name, years, rates) in series.items():
        years = np.asarray(years, dtype=float)
        rates = np.asarray(rates, dtype=float)
        n = len(years)
        if n < MIN_SEGMENT_POINTS * 2:
            max_j = 0
        else:
            max_j = min(MAX_JOINPOINTS, (n // MIN_SEGMENT_POINTS) - 1)

        best = None
        for n_join in range(max_j + 1):
            for taus in _candidate_taus(list(years), n_join):
                res, beta, V, slopes = _fit_segmented(years, rates, taus)
                if best is None or res.bic < best[0]:
                    best = (res.bic, taus, res, beta, V, slopes)
        bic, taus, res, beta, V, slopes = best

        bounds = [years[0]] + list(taus) + [years[-1]]
        # AAPC: 区間長で重みづけした平均対数傾き
        w = np.array([bounds[k + 1] - bounds[k] for k in range(len(slopes))], dtype=float)
        c_aapc = sum(wk * ck for wk, ck in zip(w, slopes)) / w.sum()
        aapc = _apc_from_contrast(beta, V, c_aapc)

        for k, c in enumerate(slopes):
            seg = _apc_from_contrast(beta, V, c)
            rows.append({
                "code": code, "name": name,
                "n_joinpoints": len(taus),
                "joinpoints": ";".join(str(int(t)) for t in taus),
                "segment": k + 1,
                "segment_start": int(bounds[k]), "segment_end": int(bounds[k + 1]),
                "apc": seg["apc"], "apc_low": seg["apc_low"], "apc_high": seg["apc_high"],
                "significant": not (seg["apc_low"] <= 0 <= seg["apc_high"]),
                "aapc": aapc["apc"], "aapc_low": aapc["apc_low"],
                "aapc_high": aapc["apc_high"],
                "bic": bic, "r2": res.rsquared, "n_years": n,
            })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "trend_joinpoint_antivegf.csv"),
              index=False, encoding="utf-8-sig")
    print(f"  trend_joinpoint_antivegf.csv ({len(df)} rows)")
    return df


# ── 2. 65歳以上人口を分母にした率と格差 ──────────────────────────

def rates_65plus(panel, out_dir):
    """65歳以上10万対の県別率・順位・格差指標。

    真の年齢調整率は都道府県×年齢のクロス表が非公表のため算出できない。
    抗VEGF薬の対象疾患（AMD・DME・RVO）が高齢層に集中することを踏まえ、
    高齢人口を分母に置くことで年齢構成の県差を部分的に調整する。
    """
    p = panel.copy()
    p["count_per_100k_65plus"] = p["quantity"] / p["population_65plus"] * 100000

    total = p[p["code"] == "ANTI_VEGF_TOTAL"]
    rank = total.pivot_table(index="prefecture", columns="year",
                             values="count_per_100k_65plus")
    rank.columns = [f"{int(c)}年度_65歳以上10万対" for c in rank.columns]
    last = rank.columns[-1]
    rank[f"{last.split('年度')[0]}年度_順位"] = rank[last].rank(ascending=False).astype(int)
    rank = rank.sort_values(last, ascending=False).reset_index()
    rank.to_csv(os.path.join(out_dir, "prefecture_per_65plus_ranking_antivegf.csv"),
                index=False, encoding="utf-8-sig")

    rows = []
    for (year, code), g in p.groupby(["year", "code"]):
        r65 = g["count_per_100k_65plus"].values
        rtot = g["count_per_100k"].values
        if np.nansum(r65) == 0:
            continue
        m = np.nanmean(r65)
        imin, imax = int(np.nanargmin(r65)), int(np.nanargmax(r65))
        rows.append({
            "year": year, "code": code, "name": g["name"].iloc[0],
            "mean_rate_per_100k_65plus": m,
            "cv_65plus": (np.nanstd(r65, ddof=1) / m) if m > 0 else np.nan,
            "gini_65plus": calculate_gini(r65),
            "gini_total_pop": calculate_gini(rtot),
            "max_to_min_ratio_65plus": (r65[imax] / r65[imin]) if r65[imin] > 0 else np.nan,
            "max_prefecture": g["prefecture"].iloc[imax],
            "min_prefecture": g["prefecture"].iloc[imin],
        })
    disp = pd.DataFrame(rows)
    disp["gini_reduction_pct"] = ((disp["gini_total_pop"] - disp["gini_65plus"])
                                  / disp["gini_total_pop"] * 100)
    disp.to_csv(os.path.join(out_dir, "geographic_disparity_65plus_antivegf.csv"),
                index=False, encoding="utf-8-sig")
    print(f"  prefecture_per_65plus_ranking_antivegf.csv ({len(rank)} rows)")
    print(f"  geographic_disparity_65plus_antivegf.csv ({len(disp)} rows)")
    return rank, disp


# ── 3. 収束の検定 ────────────────────────────────────────────────

def convergence(panel, out_dir):
    """β収束（初期水準の高い県ほど伸びが低いか）とσ収束（対数SDの推移）。

    β<0 なら県間格差は縮小方向。半減期 = ln(2) / (-ln(1+β*T)/T) で年数換算する。
    初期年に0（＝全セル秘匿）の県は対数がとれないため除外し、n に反映する。
    """
    total = panel[panel["code"] == "ANTI_VEGF_TOTAL"]
    years = sorted(total["year"].unique())
    wide = total.pivot_table(index="prefecture", columns="year",
                             values="count_per_100k")

    periods = [(years[0], years[-1]), (years[0], 2019), (2019, years[-1])]
    rows = []
    for y0, y1 in periods:
        if y0 not in wide.columns or y1 not in wide.columns:
            continue
        sub = wide[[y0, y1]].dropna()
        sub = sub[(sub[y0] > 0) & (sub[y1] > 0)]
        T = y1 - y0
        growth = (np.log(sub[y1]) - np.log(sub[y0])) / T   # 年平均対数成長率
        x = sm.add_constant(np.log(sub[y0].values))
        res = sm.OLS(growth.values, x).fit()
        beta = float(res.params[1])
        # 収束速度 λ と半減期（β = -(1-exp(-λT))/T の関係を解く）
        lam = -np.log(1 + beta * T) / T if (1 + beta * T) > 0 else np.nan
        rows.append({
            "period": f"{y0}-{y1}", "n_prefectures": len(sub),
            "beta": beta, "se": float(res.bse[1]), "p_value": float(res.pvalues[1]),
            "r2": res.rsquared,
            "converging": beta < 0 and res.pvalues[1] < 0.05,
            "lambda_per_year": lam,
            "half_life_years": np.log(2) / lam if lam and lam > 0 else np.nan,
        })
    beta_df = pd.DataFrame(rows)

    # σ収束: 各年の対数率の標準偏差
    sigma = []
    for y in years:
        v = wide[y].dropna()
        v = v[v > 0]
        sigma.append({"year": int(y), "n_prefectures": len(v),
                      "sd_log_rate": float(np.std(np.log(v.values), ddof=1)),
                      "cv": float(np.std(v.values, ddof=1) / np.mean(v.values))})
    sigma_df = pd.DataFrame(sigma)

    # 1ファイルに2ブロックで書き出す（列名が異なるため section 列で区別）
    beta_df.insert(0, "section", "beta収束")
    sigma_df.insert(0, "section", "sigma収束")
    out = pd.concat([beta_df, sigma_df], ignore_index=True)
    out.to_csv(os.path.join(out_dir, "convergence_beta_antivegf.csv"),
               index=False, encoding="utf-8-sig")
    print(f"  convergence_beta_antivegf.csv ({len(out)} rows)")
    return beta_df, sigma_df


# ── 4. 補完戦略別のAPC感度分析 ───────────────────────────────────

def sensitivity_apc(data_dir, out_dir):
    """zero/five/random それぞれの県別集計から求めたAPCを比較する。

    全国トレンドのAPC（§2-3）は公表総計ベースなので補完の影響を受けない。
    ここでは**県別内訳を全国に足し上げた率**でAPCを再計算し、
    補完方法によって傾向推定が変わらないことを示す。
    """
    rows = []
    for strategy in ["zero", "five", "random"]:
        panel = pd.read_csv(find(data_dir, f"panel_{strategy}.csv"))
        agg = panel.groupby(["code", "year"], as_index=False).agg(
            quantity=("quantity", "sum"), name=("name", "first"),
            population_total=("population_total", "sum"))
        agg["rate"] = agg["quantity"] / agg["population_total"] * 100000
        for code, g in agg.groupby("code"):
            g = g[g["quantity"] > 0].sort_values("year")
            if len(g) < 3:
                continue
            res = calculate_apc_linear(g["year"].values, g["rate"].values)
            res.update({"code": code, "name": g["name"].iloc[0],
                        "imputation": strategy,
                        "start_year": int(g["year"].min()),
                        "end_year": int(g["year"].max()), "n_years": len(g)})
            rows.append(res)

    df = pd.DataFrame(rows)
    base = df[df["imputation"] == "zero"].set_index("code")["apc"]
    df["apc_diff_vs_zero"] = df["apc"] - df["code"].map(base)
    df = df[["code", "name", "imputation", "start_year", "end_year", "n_years",
             "apc", "apc_low", "apc_high", "p_value", "r2", "apc_diff_vs_zero"]]
    df = df.sort_values(["code", "imputation"])
    df.to_csv(os.path.join(out_dir, "sensitivity_apc_antivegf.csv"),
              index=False, encoding="utf-8-sig")
    print(f"  sensitivity_apc_antivegf.csv ({len(df)} rows)")
    return df


# ── 5. 男性比率の傾向検定（参考値） ──────────────────────────────

def _cochran_armitage(counts_a, counts_b, scores):
    """Cochran–Armitage 傾向検定。counts_a/b は各水準の度数、scores は順序得点。

    z>0 なら scores が大きいほど a の割合が高い。
    """
    a = np.asarray(counts_a, dtype=float)
    b = np.asarray(counts_b, dtype=float)
    n = a + b
    s = np.asarray(scores, dtype=float)
    N = n.sum()
    if N == 0:
        return np.nan, np.nan
    p = a.sum() / N
    s_bar = float((n * s).sum() / N)
    num = float((a * (s - s_bar)).sum())
    var = p * (1 - p) * float((n * (s - s_bar) ** 2).sum())
    if var <= 0:
        return np.nan, np.nan
    z = num / np.sqrt(var)
    from scipy.stats import norm
    return z, 2 * (1 - norm.cdf(abs(z)))


def sex_ratio_tests(agesex, out_dir):
    """男性比率の年齢傾向・経年傾向の検定と、性別×年齢の独立性検定。

    【重大な注意】観測単位はバイアル本数であって患者ではない。
    同一患者が年間6〜12回投与を受けるため、実質的な標本サイズは本数より
    はるかに小さい。ここで得られるp値は**極端に小さく出る**ので、
    効果量（男性比率そのもの、男/女比）で解釈し、p値は参考に留めること。
    """
    from scipy.stats import chi2_contingency

    df = agesex[(agesex["category"] == "ANTI_VEGF") &
                (agesex["setting"] == "外来(院内)")].copy()
    order = {a: i for i, a in enumerate(AGE_ORDER)}

    rows = []
    for year, g in df.groupby("year"):
        piv = g.pivot_table(index="age_group", columns="sex",
                            values="quantity", aggfunc="sum", fill_value=0)
        for s in ["男", "女"]:
            if s not in piv.columns:
                piv[s] = 0.0
        piv = piv.reindex([a for a in AGE_ORDER if a in piv.index])
        # 全セル0の年齢階級は検定から落とす（情報を持たない）
        piv = piv[(piv["男"] + piv["女"]) > 0]
        scores = [order[a] for a in piv.index]

        z, p = _cochran_armitage(piv["男"].values, piv["女"].values, scores)
        chi2, p_chi, dof, _ = chi2_contingency(
            np.round(piv[["男", "女"]].values).astype(int) + 1)
        male = piv["男"].sum()
        female = piv["女"].sum()
        rows.append({
            "test": "年齢傾向（Cochran–Armitage）", "year": int(year),
            "male": male, "female": female,
            "male_share_pct": male / (male + female) * 100 if male + female else np.nan,
            "male_female_ratio": male / female if female else np.nan,
            "statistic": z, "p_value": p,
            "chi2_independence": chi2, "p_value_chi2": p_chi, "dof": dof,
            "n_age_groups": len(piv),
        })

    trend = pd.DataFrame(rows).sort_values("year")

    # 経年トレンド: 年度を順序得点とした男性比率の傾向
    z_y, p_y = _cochran_armitage(trend["male"].values, trend["female"].values,
                                 trend["year"].values - trend["year"].min())
    trend = pd.concat([trend, pd.DataFrame([{
        "test": "経年傾向（Cochran–Armitage）", "year": np.nan,
        "male": trend["male"].sum(), "female": trend["female"].sum(),
        "male_share_pct": np.nan, "male_female_ratio": np.nan,
        "statistic": z_y, "p_value": p_y, "n_age_groups": np.nan,
    }])], ignore_index=True)

    trend.to_csv(os.path.join(out_dir, "agesex_sex_ratio_tests.csv"),
                 index=False, encoding="utf-8-sig")
    print(f"  agesex_sex_ratio_tests.csv ({len(trend)} rows)")
    return trend


# ── 6. G016算定回数と薬剤数量の県別突合 ─────────────────────────

def g016_vs_drug_by_prefecture(panel, data_dir, out_dir):
    """県別に「抗VEGF薬数量 ÷ G016算定回数」を求める。

    G016の都道府県別データには秘匿セルが1件もない。一方、薬剤の県別内訳は
    秘匿補完に依存している。両者の比は**県ごとの秘匿による欠落量の推定値**
    になり、県別解析の妥当性を県単位で検証できる。
    比が1を超える県は、抗VEGF薬以外の硝子体注射より秘匿欠落の方が小さい等の
    要因が考えられるため、外れ値として個別に確認する。
    """
    g016 = pd.read_csv(find(data_dir, "g016_prefecture_panel.csv"))
    g016 = g016[["year", "prefecture", "count"]].rename(
        columns={"count": "g016_procedures"})

    drug = panel[panel["code"] == "ANTI_VEGF_TOTAL"][
        ["year", "prefecture", "quantity"]].rename(
        columns={"quantity": "antivegf_vials"})

    df = drug.merge(g016, on=["year", "prefecture"], how="inner")
    df["ratio_pct"] = df["antivegf_vials"] / df["g016_procedures"] * 100
    df = df.sort_values(["year", "ratio_pct"])
    df.to_csv(os.path.join(out_dir, "g016_vs_drug_by_prefecture.csv"),
              index=False, encoding="utf-8-sig")

    summary = df.groupby("year").agg(
        n_prefectures=("prefecture", "size"),
        mean_ratio_pct=("ratio_pct", "mean"),
        median_ratio_pct=("ratio_pct", "median"),
        min_ratio_pct=("ratio_pct", "min"),
        max_ratio_pct=("ratio_pct", "max"),
        n_over_100=("ratio_pct", lambda s: int((s > 100).sum())),
    ).reset_index()
    idx_min = df.groupby("year")["ratio_pct"].idxmin()
    summary["min_prefecture"] = df.loc[idx_min, "prefecture"].values
    summary.to_csv(os.path.join(out_dir, "g016_vs_drug_prefecture_summary.csv"),
                   index=False, encoding="utf-8-sig")
    print(f"  g016_vs_drug_by_prefecture.csv ({len(df)} rows)")
    print(f"  g016_vs_drug_prefecture_summary.csv ({len(summary)} rows)")
    return df, summary


# ── 7. 薬価改定の年表 ───────────────────────────────────────────

# 薬価改定の実施年度と区分。2016年12月「薬価制度の抜本改革に向けた基本方針」により
# 2021年度から毎年改定（中間年改定）が導入された。
# 【出典】中央社会保険医療協議会 薬価専門部会資料。年表は改定の"区分"のみを与え、
# 実際の改定額は本解析の入力（NDBオープンデータの薬価欄）から算出している。
PRICE_REVISIONS = {
    2014: ("通常改定", "診療報酬改定と同時。消費税8%への引上げ対応を含む"),
    2015: ("改定なし", ""),
    2016: ("通常改定", "診療報酬改定と同時"),
    2017: ("改定なし", ""),
    2018: ("通常改定", "診療報酬改定と同時"),
    2019: ("臨時改定", "消費税10%への引上げ対応（2019年10月実施）"),
    2020: ("通常改定", "診療報酬改定と同時"),
    2021: ("中間年改定", "毎年薬価改定の初回"),
    2022: ("通常改定", "診療報酬改定と同時"),
    2023: ("中間年改定", ""),
    2024: ("通常改定", "診療報酬改定と同時"),
}


def price_revision_timeline(data_dir, out_dir):
    """製品別の薬価改定額を年表化する。

    薬価はNDBオープンデータの「薬価」欄をそのまま用いており、**年度あたり1値**である。
    このため年度途中の改定（2019年10月の消費税対応）は分離できない。
    改定率は前年度に収載があった製品のみ算出する（新規収載は改定ではない）。
    """
    price = pd.read_csv(find(data_dir, "product_price_table_antivegf.csv"))
    year_cols = [c for c in price.columns if c.endswith("_薬価(円)")]
    years = [int(c.split("年度")[0]) for c in year_cols]

    rows = []
    for _, r in price.iterrows():
        for (prev_y, prev_c), (cur_y, cur_c) in zip(
                zip(years[:-1], year_cols[:-1]), zip(years[1:], year_cols[1:])):
            p0, p1 = r[prev_c], r[cur_c]
            if pd.isna(p0) or pd.isna(p1):
                continue
            kind, note = PRICE_REVISIONS.get(cur_y, ("", ""))
            rows.append({
                "year": cur_y, "revision_type": kind, "note": note,
                "product_name": r["product_name"], "drug_code": r["drug_code"],
                "price_prev": p0, "price_current": p1,
                "change_yen": p1 - p0,
                "change_pct": (p1 - p0) / p0 * 100,
                "revised": p1 != p0,
            })
    df = pd.DataFrame(rows).sort_values(["year", "product_name"])
    df.to_csv(os.path.join(out_dir, "product_price_revision_timeline.csv"),
              index=False, encoding="utf-8-sig")

    summary = df.groupby(["year", "revision_type"], as_index=False).agg(
        n_products=("product_name", "size"),
        n_revised=("revised", "sum"),
        mean_change_pct=("change_pct", "mean"),
        min_change_pct=("change_pct", "min"),
        max_change_pct=("change_pct", "max"))
    summary.to_csv(os.path.join(out_dir, "product_price_revision_summary.csv"),
                   index=False, encoding="utf-8-sig")
    print(f"  product_price_revision_timeline.csv ({len(df)} rows)")
    print(f"  product_price_revision_summary.csv ({len(summary)} rows)")
    return df, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nokouhi", action="store_true",
                    help="公費レセプトを含まないデータ（抗VEGF薬解析/公費含まない）で解析する")
    args = ap.parse_args()

    data_dir = os.path.join(ANTIVEGF_DIR, "公費含まない") if args.nokouhi else ANTIVEGF_DIR
    out_dir = os.path.join(data_dir, "processed")
    os.makedirs(out_dir, exist_ok=True)
    print(f"=== 抗VEGF薬 追加解析 ===\n入力/出力: {out_dir}")

    nat = pd.read_csv(find(data_dir, "national_trends_antivegf.csv"))
    panel = pd.read_csv(find(data_dir, "panel_zero.csv"))
    agesex = pd.read_csv(find(data_dir, "processed_agesex_zero.csv"))

    print("[1/7] 変化点解析（分節対数線形回帰）")
    series = {}
    for code in JOINPOINT_CODES:
        g = nat[(nat["code"] == code) & (nat["quantity"] > 0)].sort_values("year")
        if len(g) >= MIN_SEGMENT_POINTS * 2:
            series[code] = (g["name"].iloc[0], g["year"].values,
                            g["count_per_100k"].values)
    # G016（人口10万対、2015–2024）も同じ枠組みで解析する
    g016_nat = pd.read_csv(find(data_dir, "g016_national_trends.csv"))
    g016_tot = g016_nat[g016_nat["setting"] == "合計"].sort_values("year")
    series["G016_TOTAL"] = ("G016 硝子体内注射（合計）", g016_tot["year"].values,
                            g016_tot["count_per_100k"].values)
    joinpoint(series, out_dir)

    print("[2/7] 65歳以上分母の率と格差")
    rates_65plus(panel, out_dir)

    print("[3/7] 収束の検定")
    convergence(panel, out_dir)

    print("[4/7] 補完戦略別APC")
    sensitivity_apc(data_dir, out_dir)

    print("[5/7] 男性比率の傾向検定")
    sex_ratio_tests(agesex, out_dir)

    print("[6/7] G016との県別突合")
    g016_vs_drug_by_prefecture(panel, data_dir, out_dir)

    print("[7/7] 薬価改定の年表")
    price_revision_timeline(data_dir, out_dir)
    print("完了")


if __name__ == "__main__":
    main()
