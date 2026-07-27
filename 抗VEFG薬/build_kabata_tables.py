"""Kabata et al. (PLoS One 2026;21(5):e0348087) の図表を再現するCSVを生成する。

先行研究はFY2017–2022を対象としているが、本スクリプトは取得済みの全期間
（薬剤 2014–2024年度、G016 2015–2024年度）を出力する。
先行研究が区別していなかったラニビズマブの先発／バイオシミラーは分離して併記する。

出力先: 抗VEFG薬/公費含まない/  （--kouhi 指定時は 抗VEFG薬/）
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, ttest_ind

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from drug_master import DRUG_MASTER  # noqa: E402

BASE = r"G:\マイドライブ\NDB_眼科診療トレンド解析_研究計画書"
ANTIVEGF_DIR = os.path.join(BASE, "抗VEFG薬")
COVARIATES = os.path.join(BASE, "data", "covariates", "prefecture_covariates.csv")

# 先行研究の地域区分（論文Methodsの定義をそのまま使用）
METRO = ["東京都", "神奈川県", "埼玉県", "千葉県", "愛知県", "大阪府", "兵庫県", "福岡県"]
EAST = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県",
        "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "山梨県",
        "長野県", "静岡県"]

# 先行研究が集計した4剤（成分コード → 論文の表記）
KABATA_AGENTS = {
    "AFLIBERCEPT": "aflibercept",
    "AFLIBERCEPT_8MG": "aflibercept",
    "RANIBIZUMAB_ORIG": "ranibizumab",
    "RANIBIZUMAB_BS": "ranibizumab",
    "BROLUCIZUMAB": "brolucizumab",
    "FARICIMAB": "faricimab",
}


def load_drugs(data_dir):
    """薬剤の公表総計（全国）と都道府県内訳を読む。"""
    path = os.path.join(data_dir, "ophthalmic_injection_prefecture.csv")
    df = pd.read_csv(path, dtype={"医薬品コード": str})
    m = df["医薬品コード"].map(DRUG_MASTER)
    df["molecule"] = m.map(lambda x: x[1])
    df["category"] = m.map(lambda x: x[5])
    df = df.rename(columns={"年度": "year", "区分": "setting", "都道府県": "prefecture"})
    df["quantity"] = pd.to_numeric(df["処方数量"], errors="coerce").fillna(0.0)

    nat = df.groupby(["year", "setting", "医薬品コード", "molecule", "category"],
                     as_index=False)["総計_処方数量"].first()
    nat["quantity"] = pd.to_numeric(nat["総計_処方数量"], errors="coerce").fillna(0.0)
    return df, nat


def load_g016(data_dir):
    path = os.path.join(data_dir, "g016_prefecture.csv")
    df = pd.read_csv(path)
    df = df.rename(columns={"年度": "year", "区分": "setting", "都道府県": "prefecture"})
    df["count"] = pd.to_numeric(df["算定回数"], errors="coerce").fillna(0.0)
    nat = df.groupby(["year", "setting"], as_index=False)["総計_算定回数"].first()
    nat = nat.rename(columns={"総計_算定回数": "count"})
    return df, nat


def table1(g016_nat, drug_nat, out_dir):
    """Table 1: 年度別 G016算定回数と薬剤別数量。"""
    g = g016_nat.pivot_table(index="year", columns="setting", values="count").fillna(0)
    g["g016_total"] = g.sum(axis=1)
    g = g.rename(columns={"外来": "g016_outpatient", "入院": "g016_inpatient"})

    anti = drug_nat[drug_nat["category"] == "ANTI_VEGF"]
    mol = anti.pivot_table(index="year", columns="molecule", values="quantity",
                           aggfunc="sum").fillna(0)
    t = pd.DataFrame(index=sorted(set(g.index) | set(mol.index)))
    t.index.name = "fiscal_year"
    for c in ["g016_total", "g016_outpatient", "g016_inpatient"]:
        t[c] = g[c]
    t["aflibercept"] = mol.get("AFLIBERCEPT", 0) + mol.get("AFLIBERCEPT_8MG", 0)
    t["aflibercept_2mg"] = mol.get("AFLIBERCEPT", 0)
    t["aflibercept_8mg"] = mol.get("AFLIBERCEPT_8MG", 0)
    t["ranibizumab"] = mol.get("RANIBIZUMAB_ORIG", 0) + mol.get("RANIBIZUMAB_BS", 0)
    t["ranibizumab_originator"] = mol.get("RANIBIZUMAB_ORIG", 0)
    t["ranibizumab_biosimilar"] = mol.get("RANIBIZUMAB_BS", 0)
    t["brolucizumab"] = mol.get("BROLUCIZUMAB", 0)
    t["faricimab"] = mol.get("FARICIMAB", 0)
    t["pegaptanib"] = mol.get("PEGAPTANIB", 0)

    # 先行研究の定義（4剤）に一致する合計と、本研究の全抗VEGF薬合計
    t["antivegf_sum_kabata4"] = (t["aflibercept"] + t["ranibizumab"]
                                 + t["brolucizumab"] + t["faricimab"])
    t["antivegf_sum_all"] = t["antivegf_sum_kabata4"] + t["pegaptanib"]
    t["non_vegf_n"] = t["g016_total"] - t["antivegf_sum_all"]
    t["non_vegf_pct"] = t["non_vegf_n"] / t["g016_total"] * 100
    t = t.round(1).reset_index()
    t.to_csv(os.path.join(out_dir, "kabata_table1_national_counts.csv"),
             index=False, encoding="utf-8-sig")
    return t


def _pref_rates(g016_pref, cov):
    p = g016_pref.groupby(["year", "prefecture"], as_index=False)["count"].sum()
    p = p.merge(cov, on=["year", "prefecture"], how="left")
    p["rate_per_100k"] = p["count"] / p["population_total"] * 100000
    p["rate_per_100k_65plus"] = p["count"] / p["population_65plus"] * 100000
    return p


def table2(pref_rates, out_dir):
    """Table 2: 都道府県別 粗利用率の分布（年度別）。"""
    rows = []
    for year, g in pref_rates.groupby("year"):
        r = g["rate_per_100k"].values
        n = len(r)
        sd = r.std(ddof=1)
        se = sd / np.sqrt(n)
        rows.append({
            "fiscal_year": year, "n_prefectures": n,
            "mean": r.mean(), "sd": sd,
            "ci95_lower": r.mean() - 1.96 * se, "ci95_upper": r.mean() + 1.96 * se,
            "minimum": r.min(), "maximum": r.max(),
            "min_prefecture": g.loc[g["rate_per_100k"].idxmin(), "prefecture"],
            "max_prefecture": g.loc[g["rate_per_100k"].idxmax(), "prefecture"],
            "max_min_ratio": r.max() / r.min(), "cv": sd / r.mean(),
        })
    t = pd.DataFrame(rows).round(3)
    t.to_csv(os.path.join(out_dir, "kabata_table2_crude_rate_distribution.csv"),
             index=False, encoding="utf-8-sig")
    return t


def fig1(table1_df, out_dir):
    """Fig 1: 薬剤別の年次推移（棒）＋抗VEGF合計（折れ線）。"""
    cols = ["aflibercept", "ranibizumab_originator", "ranibizumab_biosimilar",
            "brolucizumab", "faricimab", "pegaptanib"]
    f = table1_df[["fiscal_year"] + cols + ["antivegf_sum_all", "g016_total"]].copy()
    f.to_csv(os.path.join(out_dir, "kabata_fig1_annual_trends_wide.csv"),
             index=False, encoding="utf-8-sig")
    long = f.melt(id_vars="fiscal_year", value_vars=cols,
                  var_name="agent", value_name="quantity")
    long = long[long["quantity"] > 0]
    long.to_csv(os.path.join(out_dir, "kabata_fig1_annual_trends_long.csv"),
                index=False, encoding="utf-8-sig")
    return f


def s1_table(drug_pref, out_dir):
    """S1 Table: 都道府県×年度の薬剤別シェア。"""
    anti = drug_pref[drug_pref["category"] == "ANTI_VEGF"].copy()
    anti["agent"] = anti["molecule"].map(KABATA_AGENTS).fillna("other")
    g = anti.groupby(["year", "prefecture", "agent"], as_index=False)["quantity"].sum()
    tot = g.groupby(["year", "prefecture"])["quantity"].transform("sum")
    g["share_pct"] = np.where(tot > 0, g["quantity"] / tot * 100, np.nan)
    piv = g.pivot_table(index=["prefecture", "year"], columns="agent",
                        values="share_pct").reset_index()
    piv.to_csv(os.path.join(out_dir, "kabata_s1_prefecture_agent_shares.csv"),
               index=False, encoding="utf-8-sig")

    # 成分レベル（先発/BS分離）のシェアも併せて出力
    g2 = anti.groupby(["year", "prefecture", "molecule"], as_index=False)["quantity"].sum()
    tot2 = g2.groupby(["year", "prefecture"])["quantity"].transform("sum")
    g2["share_pct"] = np.where(tot2 > 0, g2["quantity"] / tot2 * 100, np.nan)
    piv2 = g2.pivot_table(index=["prefecture", "year"], columns="molecule",
                          values="share_pct").reset_index()
    piv2.to_csv(os.path.join(out_dir, "kabata_s1b_prefecture_molecule_shares.csv"),
                index=False, encoding="utf-8-sig")
    return piv


def s2_table(pref_rates, out_dir, base_year, last_year):
    """S2 Table: 都道府県別の粗利用率（基準年と最終年）と変化率。

    先行研究は75歳以上人口を分母とした感度分析も併記しているが、
    都道府県×75歳以上の人口が入手できないため65歳以上人口で代用している。
    """
    a = pref_rates[pref_rates["year"] == base_year].set_index("prefecture")
    b = pref_rates[pref_rates["year"] == last_year].set_index("prefecture")
    t = pd.DataFrame({
        f"count_{base_year}": a["count"], f"count_{last_year}": b["count"],
        f"crude_rate_{base_year}": a["rate_per_100k"],
        f"crude_rate_{last_year}": b["rate_per_100k"],
        f"rate_65plus_{base_year}": a["rate_per_100k_65plus"],
        f"rate_65plus_{last_year}": b["rate_per_100k_65plus"],
    })
    t["pct_change_count"] = (t[f"count_{last_year}"] / t[f"count_{base_year}"] - 1) * 100
    t["crude_rate_index"] = (t[f"crude_rate_{last_year}"]
                             / t[f"crude_rate_{base_year}"] * 100)
    t = t.sort_values(f"crude_rate_{last_year}", ascending=False).round(2).reset_index()
    t.to_csv(os.path.join(out_dir,
                          f"kabata_s2_prefecture_utilization_{base_year}_{last_year}.csv"),
             index=False, encoding="utf-8-sig")
    return t


def s4_table(pref_rates, out_dir):
    """S4 Table: 粗利用率および65歳以上分母での県間ばらつきの要約。"""
    rows = []
    for year, g in pref_rates.groupby("year"):
        for label, col in [("crude_per_100k_total", "rate_per_100k"),
                           ("per_100k_65plus", "rate_per_100k_65plus")]:
            r = g[col].dropna().values
            rows.append({
                "fiscal_year": year, "metric": label, "n": len(r),
                "mean": r.mean(), "sd": r.std(ddof=1),
                "minimum": r.min(), "maximum": r.max(),
                "max_min_ratio": r.max() / r.min(),
                "cv": r.std(ddof=1) / r.mean(),
            })
    t = pd.DataFrame(rows).round(3)
    t.to_csv(os.path.join(out_dir, "kabata_s4_variation_summary.csv"),
             index=False, encoding="utf-8-sig")
    return t


def regional_comparison(pref_rates, out_dir):
    """本文の地域群比較（大都市圏 vs その他、東日本 vs 西日本）。"""
    rows = []
    for year, g in pref_rates.groupby("year"):
        for label, members in [("metropolitan_vs_other", METRO),
                               ("east_vs_west", EAST)]:
            a = g[g["prefecture"].isin(members)]["rate_per_100k"].values
            b = g[~g["prefecture"].isin(members)]["rate_per_100k"].values
            t_p = ttest_ind(a, b, equal_var=False).pvalue
            u_p = mannwhitneyu(a, b).pvalue
            rows.append({
                "fiscal_year": year, "comparison": label,
                "group1_n": len(a), "group1_mean": a.mean(), "group1_sd": a.std(ddof=1),
                "group2_n": len(b), "group2_mean": b.mean(), "group2_sd": b.std(ddof=1),
                "welch_t_p": t_p, "mann_whitney_p": u_p,
            })
    t = pd.DataFrame(rows).round(4)
    t.to_csv(os.path.join(out_dir, "kabata_regional_group_comparison.csv"),
             index=False, encoding="utf-8-sig")
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kouhi", action="store_true",
                    help="公費レセプトを含むデータ（抗VEFG薬直下）で生成する")
    args = ap.parse_args()
    data_dir = ANTIVEGF_DIR if args.kouhi else os.path.join(ANTIVEGF_DIR, "公費含まない")
    out_dir = data_dir
    os.makedirs(out_dir, exist_ok=True)
    print(f"入力/出力: {out_dir}")

    drug_pref, drug_nat = load_drugs(data_dir)
    g016_pref, g016_nat = load_g016(data_dir)
    cov = pd.read_csv(COVARIATES)
    rates = _pref_rates(g016_pref, cov)

    t1 = table1(g016_nat, drug_nat, out_dir)
    table2(rates, out_dir)
    fig1(t1, out_dir)
    s1_table(drug_pref, out_dir)
    years = sorted(rates["year"].unique())
    s2_table(rates, out_dir, years[0], years[-1])
    s2_table(rates, out_dir, 2017, 2022)  # 先行研究と同一の基準年・最終年
    s4_table(rates, out_dir)
    regional_comparison(rates, out_dir)
    rates.round(3).to_csv(os.path.join(out_dir, "kabata_prefecture_rates_by_year.csv"),
                          index=False, encoding="utf-8-sig")
    print("完了")


if __name__ == "__main__":
    main()
