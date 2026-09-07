# -*- coding: utf-8 -*-
"""論文用のFig/Table workbookを、秘匿識別区間（下限・上限）つきで再生成する。

旧 `allergy解析/05_論文成果物/公費含まない/` の Fig1〜Fig5・SupplTable・Tables_123 は
秘匿セル・未収載品目を考慮しない点推定だった。本スクリプトは同じ図表構成を、
査読指摘2点に対応した形で作り直す。

  指摘①（主要3成分のシェアは本当に多いのか）
    → Fig4 に「3成分シェアの識別区間」シートを追加。未収載品目の順位ベース上限
      （NDB非掲載の成分・年度も上市品目数×最小公表総計で上限を構成）まで含めて
      シェアの下限・上限を示す。
  指摘②（非公開データがある中で正確か。最大値・最小値の処理は）
    → すべての図表を下限（秘匿セル=0）・上限（秘匿セル合計=missing の配分上限）
      の2列で提示する。算出方法は bounded_outputs_report.md と同一。

単位はすべてmLに換算（ｍＬ=×1、瓶=×品目名記載の容器容量、個=×品目名記載の容器容量）。
換算係数は決め打ちではなく、NDB品目名に含まれる規格表記（例「…３．４５ｍｇ５ｍＬ」）
から品目ごとに取得している（src/units.py）。その全品目リストを
unit_conversion_audit.csv として出力する（換算根拠の監査証跡）。

入力: 01_抽出データ/*.csv、05_論文成果物/公費含めない_new/*.csv、
      03_解析結果/後発品_剤形/ge_share_annotated.csv
出力: 05_論文成果物/公費含めない_new/論文図表/
        Fig1_age_sex_profile_bounds.xlsx
        Fig2_age_distribution_bounds.xlsx
        Fig3_prefecture_map_bounds.xlsx
        Fig4_trends_shares_bounds.xlsx      ← 指摘①のシェア識別区間を含む
        Fig5_ge_formulation_bounds.xlsx
        SupplTable_annual_totals_bounds.xlsx
        Tables_123_bounds.xlsx
        unit_conversion_audit.csv
        csv/  各シートと同内容のCSV
"""
import os
import sys

import numpy as np
import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from drug_master import (ANTI_HIST_CODES, DRUG_NAME_JA,   # noqa: E402
                         DRUG_ORDER, MED_RELEASE_CODES)
from ndb_reader import SHEET_ORDER                        # noqa: E402
from paths import BASE_DIR, INPUT_DIR, ensure             # noqa: E402

NEW_DIR = os.path.join(BASE_DIR, "05_論文成果物", "公費含めない_new")
OUT = os.path.join(NEW_DIR, "論文図表")
CSV_OUT = os.path.join(OUT, "csv")

TOP3 = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
DRUG_EN = {
    "EPINASTINE": "Epinastine", "OLOPATADINE": "Olopatadine",
    "LEVOCASTINE": "Levocabastine", "KETOTIFEN": "Ketotifen",
    "TRANILAST": "Tranilast", "CROMOGLICATE": "Sodium cromoglicate",
    "ACITAZANOLAST": "Acitazanolast", "PEMIROLAST": "Pemirolast",
    "IBUDILAST": "Ibudilast",
    "ALLERGY_EYE_TOTAL": "All 9 agents", "TOP3_TOTAL": "Top 3 total",
    "ANTI_HIST": "Antihistamines subtotal",
    "MED_RELEASE": "Mediator release inhibitors subtotal",
}
SEX_EN = {"male": "Male", "female": "Female"}

AGE_ORDER = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34",
             "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69",
             "70-74", "75-79", "80-84", "85-89", "90-94", "95-99", "100+", "90+"]
AGE_MID = {g: (int(g.split("-")[0]) + int(g.split("-")[1])) / 2 + 0.5
           for g in AGE_ORDER if "-" in g}
AGE_MID.update({"90+": 95.0, "100+": 102.5})


def age_sorted(df, col="age_group"):
    key = {g: i for i, g in enumerate(AGE_ORDER)}
    return df.sort_values(col, key=lambda s: s.map(key))


# ----------------------------------------------------------------------
# 入力
# ----------------------------------------------------------------------
def load_all():
    p = lambda n: os.path.join(NEW_DIR, n)  # noqa: E731
    dat = {
        "nat": pd.read_csv(p("national_trends_bounds.csv")),
        "pref": pd.read_csv(p("prefecture_per_capita_bounds.csv")),
        "rank": pd.read_csv(p("prefecture_ranking_bounds.csv")),
        "agesex": pd.read_csv(p("agesex_bounds.csv")),
        "ge": pd.read_csv(p("brand_generic_share_bounds.csv")),
        "uns": pd.read_csv(p("unlisted_sensitivity.csv"), comment="#"),
        "inv": pd.read_csv(p("unlisted_products_inventory.csv")),
        "level": pd.read_csv(os.path.join(INPUT_DIR, "product_level_censoring.csv")),
        "agesex_level": pd.read_csv(os.path.join(INPUT_DIR, "product_agesex_censoring.csv")),
        "counts": pd.read_csv(os.path.join(INPUT_DIR, "eye_product_counts.csv")),
        "geann": pd.read_csv(os.path.join(BASE_DIR, "03_解析結果", "後発品_剤形",
                                          "ge_share_annotated.csv")),
    }
    return dat


# ----------------------------------------------------------------------
# 単位換算の監査証跡（換算係数の根拠 = NDB品目名の規格表記）
# ----------------------------------------------------------------------
def unit_audit(level, agesex_level):
    u = (pd.concat([level, agesex_level])
         [["code", "product_name", "unit", "unit_source", "ml_factor"]]
         .drop_duplicates()
         .sort_values(["code", "product_name"]))
    u["drug"] = u.code.map(DRUG_NAME_JA)
    u["ml_factor_basis"] = np.where(
        u.unit == "ｍＬ", "単位がmLそのもの（×1）",
        "品目名の規格表記から取得（例: 「…５ｍＬ」→5mL/容器）")
    u.loc[u.unit_source == "backfilled", "ml_factor_basis"] += (
        "／2014-2015年度は単位列が無いため同一品目名の後年度から補完")
    return u[["code", "drug", "product_name", "unit", "ml_factor",
              "unit_source", "ml_factor_basis"]]


# ----------------------------------------------------------------------
# 指摘①: 3成分シェアの識別区間（NDB非掲載の成分・年度も上限を構成する）
# ----------------------------------------------------------------------
def top3_share_bounds(uns, inv, counts, level):
    counts = counts[counts.sheet != "全シート通算（ユニーク）"]
    min_total = counts.set_index(["year", "sheet"])["min_total"].to_dict()
    code_factor = level.groupby("code")["ml_factor"].max().to_dict()

    rows = []
    for year in range(2014, 2025):
        per_item_raw = sum(min_total.get((year, s), 0) or 0 for s in SHEET_ORDER)
        pub, upp = {}, {}
        for code in DRUG_ORDER:
            r = uns[(uns.code == code) & (uns.year == year)].iloc[0]
            if bool(r.listed_in_ndb):
                pub[code] = r.published_total
                upp[code] = r.upper1
            else:
                # NDB非掲載（NR）: 公表0。上限は上市品目数×最小公表総計（順位ベース）
                iv = inv[(inv.code == code) & (inv.year == year)].iloc[0]
                n_items = int(iv.marketed_generic_lo) + int(iv.marketed_brand)
                pub[code] = 0.0
                upp[code] = n_items * per_item_raw * code_factor[code]
        t3_pub = sum(pub[c] for c in TOP3)
        t3_upp = sum(upp[c] for c in TOP3)
        ot_pub = sum(pub[c] for c in DRUG_ORDER if c not in TOP3)
        ot_upp = sum(upp[c] for c in DRUG_ORDER if c not in TOP3)
        rows.append({
            "year": year,
            "top3_published_mL": t3_pub, "top3_upper_mL": t3_upp,
            "others_published_mL": ot_pub, "others_upper_mL": ot_upp,
            "top3_share_lower_pct": t3_pub / (t3_pub + ot_upp) * 100,
            "top3_share_upper_pct": t3_upp / (t3_upp + ot_pub) * 100,
            "top3_share_published_pct": t3_pub / (t3_pub + ot_pub) * 100
            if (t3_pub + ot_pub) else np.nan,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# Fig1: 年齢・性別プロファイル（FY2024）
# ----------------------------------------------------------------------
def fig1_sheets(agesex):
    y24 = agesex[agesex.year == 2024]
    sheets = {}

    # Fig1A: TOP3 男女計 per100k
    g = (y24[y24.code == "TOP3_TOTAL"]
         .groupby("age_group", as_index=False)
         .agg(count_lower=("count_lower", "sum"), count_upper=("count_upper", "sum"),
              population=("population", "sum")))
    g["per100k_lower"] = g.count_lower / g.population * 1e5
    g["per100k_upper"] = g.count_upper / g.population * 1e5
    g = age_sorted(g).rename(columns={"age_group": "Age Group"})
    sheets["Fig1A_TOP3"] = g[["Age Group", "per100k_lower", "per100k_upper",
                              "count_lower", "count_upper", "population"]]

    # Fig1B: 性別×年齢 per100k（TOP3と各成分）
    for code, name in [("TOP3_TOTAL", "TOP3")] + [(c, DRUG_EN[c]) for c in TOP3]:
        s = y24[y24.code == code]
        w = s.pivot_table(index="age_group", columns="sex",
                          values=["per100k_lower", "per100k_upper"])
        w.columns = [f"{SEX_EN[sx]}_{v.replace('per100k_', '')}" for v, sx in w.columns]
        w = age_sorted(w.reset_index()).rename(columns={"age_group": "Age Group"})
        # 男女計（本文 Fig 1B が描いている値）: 人数の合計 / 人口の合計
        t = (s.groupby("age_group")
             .agg(cl=("count_lower", "sum"), cu=("count_upper", "sum"),
                  pp=("population", "sum")))
        w["Total_lower"] = w["Age Group"].map(t.cl / t.pp * 1e5).values
        w["Total_upper"] = w["Age Group"].map(t.cu / t.pp * 1e5).values
        cols = ["Age Group", "Male_lower", "Male_upper", "Female_lower", "Female_upper",
                "Total_lower", "Total_upper"]
        sheets[f"Fig1B_{name}"] = w[[c for c in cols if c in w.columns]]
    return sheets


# ----------------------------------------------------------------------
# Fig2: 年齢分布（構成比）と加重平均年齢
# ----------------------------------------------------------------------
def share_bounds(g):
    """年齢構成比の識別区間。lo_g/(lo_g+Σhi_-g) 〜 hi_g/(hi_g+Σlo_-g)。"""
    lo, hi = g.count_lower.values, g.count_upper.values
    slo, shi = lo.sum(), hi.sum()
    share_lo = np.where(lo + (shi - hi) > 0, lo / (lo + (shi - hi)) * 100, 0)
    share_hi = np.where(hi + (slo - lo) > 0, hi / (hi + (slo - lo)) * 100, 0)
    return share_lo, share_hi


def mean_age_bounds(g):
    """加重平均年齢の識別区間（頂点解の全探索: 若い側からk群をhi/loに固定）。"""
    g = age_sorted(g)
    mid = g.age_group.map(AGE_MID).values
    lo, hi = g.count_lower.values, g.count_upper.values
    means = []
    n = len(mid)
    for k in range(n + 1):
        for young_hi in (True, False):
            x = np.where(np.arange(n) < k, hi if young_hi else lo,
                         lo if young_hi else hi)
            if x.sum() > 0:
                means.append((mid * x).sum() / x.sum())
    return (min(means), max(means)) if means else (np.nan, np.nan)


def fig2_sheets(agesex):
    sheets = {}
    t3 = agesex[agesex.code == "TOP3_TOTAL"]

    # Fig2A: FY2014 vs FY2024 の年齢構成比（%）
    rows = []
    for year in (2014, 2024):
        g = age_sorted(t3[t3.year == year]
                       .groupby("age_group", as_index=False)
                       [["count_lower", "count_upper"]].sum())
        slo, shi = share_bounds(g)
        for ag, a, b in zip(g.age_group, slo, shi):
            rows.append({"Age Group": ag, "year": year,
                         "share_pct_lower": a, "share_pct_upper": b})
    w = pd.DataFrame(rows).pivot(index="Age Group", columns="year")
    w.columns = [f"FY{y} (%)_{v.split('_')[-1]}" for v, y in w.columns]
    sheets["Fig2A_age_share"] = age_sorted(w.reset_index(), "Age Group")

    # Fig2B: 加重平均年齢の推移（TOP3・各成分）
    rows = []
    for year in sorted(t3.year.unique()):
        rec = {"Year": year}
        for code, name in [("TOP3_TOTAL", "Top 3 total")] + \
                          [(c, DRUG_EN[c]) for c in TOP3]:
            g = (agesex[(agesex.code == code) & (agesex.year == year)]
                 .groupby("age_group", as_index=False)
                 [["count_lower", "count_upper"]].sum())
            if g.empty or g.count_upper.sum() == 0:
                rec[f"{name}_lower"], rec[f"{name}_upper"] = np.nan, np.nan
            else:
                rec[f"{name}_lower"], rec[f"{name}_upper"] = mean_age_bounds(g)
        rows.append(rec)
    sheets["Fig2B_mean_age"] = pd.DataFrame(rows)
    return sheets


# ----------------------------------------------------------------------
# Fig3: 都道府県（FY2024・全年）
# ----------------------------------------------------------------------
def fig3_sheets(pref, rank):
    sheets = {}
    y24 = pref[pref.year == 2024]
    codes = [("ALLERGY_EYE_TOTAL", "All9"), ("TOP3_TOTAL", "TOP3")] + \
            [(c, DRUG_EN[c]) for c in TOP3]
    base = None
    for code, name in codes:
        s = (y24[y24.code == code]
             [["prefecture", "per100k_lower", "per100k_upper"]]
             .rename(columns={"per100k_lower": f"{name}_lower",
                              "per100k_upper": f"{name}_upper"}))
        base = s if base is None else base.merge(s, on="prefecture")
    sheets["Fig3_2024_per100k"] = base.rename(columns={"prefecture": "Prefecture"})

    for code, name in [("ALLERGY_EYE_TOTAL", "All9"), ("TOP3_TOTAL", "TOP3")]:
        w = (pref[pref.code == code]
             .pivot_table(index="prefecture", columns="year",
                          values=["per100k_lower", "per100k_upper"]))
        w.columns = [f"{y}_{v.replace('per100k_', '')}" for v, y in w.columns]
        w = w[sorted(w.columns, key=lambda c: (int(c.split("_")[0]), c))]
        sheets[f"Fig3_full_{name}"] = w.reset_index().rename(
            columns={"prefecture": "Prefecture"})

    sheets["Fig3_ranking"] = rank
    return sheets


# ----------------------------------------------------------------------
# Fig4: 全国トレンドと3成分シェア（指摘①）
# ----------------------------------------------------------------------
def fig4_sheets(nat, share, ann):
    """Fig4A/4B の上限は Suppl Table S5 と同じ定義（総計秘匿の加算＋2021年度以前の
    未収載品目の順位ベース加算）。national_trends_bounds の count_upper は
    セル秘匿分しか含まず全国総計では下限と一致してしまうため、ここでは使わない。
    人口は national_trends_bounds の count_lower/per100k_lower から逆算する。"""
    sheets = {}
    codes = [("ALLERGY_EYE_TOTAL", "All 9 agents"), ("TOP3_TOTAL", "Top 3 total")] + \
            [(c, DRUG_EN[c]) for c in TOP3]
    pop = nat[nat.code == "TOP3_TOTAL"].set_index("year")
    pop = (pop.count_lower / pop.per100k_lower * 1e5)
    a = ann.set_index(["code", "year"])
    for value, label in [("per100k", "Fig4A_per100k"), ("count", "Fig4B_volume_mL")]:
        base = None
        for code, name in codes:
            s = nat[nat.code == code][["year", f"{value}_lower"]].copy()
            s = s.rename(columns={f"{value}_lower": f"{name}_lower"})
            up = s.year.map(lambda y: a.loc[(code, y), "upper"])
            if value == "per100k":
                up = up / s.year.map(pop) * 1e5
            s[f"{name}_upper"] = up.values
            base = s if base is None else base.merge(s, on="year")
        sheets[label] = base.rename(columns={"year": "Year"})
    # シェア比較は足切りが実質解消した2022年度以降に限定する（本文§2.6の方針）。
    # 2021年度以前は識別区間が公表値と同オーダーに開くため図示しない。
    sheets["Fig4C_top3_share_bounds"] = (share[share.year >= 2022]
                                         .rename(columns={"year": "Year"}))
    # Fig4D: 総量の全期間（2014〜）。未収載品目まで含めた上限つき。
    # Fig1（総量トレンド）と「増加が識別できるか」の判定の一次表。
    d = share[["year", "top3_published_mL", "top3_upper_mL",
               "others_published_mL", "others_upper_mL"]].copy()
    d["all9_published_mL"] = d.top3_published_mL + d.others_published_mL
    d["all9_upper_mL"] = d.top3_upper_mL + d.others_upper_mL
    sheets["Fig4D_totals_full_period"] = d.rename(columns={"year": "Year"})
    return sheets


# ----------------------------------------------------------------------
# Fig5: エピナスチンLX/標準・先発後発シェア
# ----------------------------------------------------------------------
def fig5_sheets(level, ge, geann, agesex_level):
    sheets = {}
    epi = level[level.code == "EPINASTINE"].copy()
    epi["is_lx"] = epi.product_name.str.contains("ＬＸ")
    epi["cap_ml"] = np.where(epi.total_censored,
                             (999 - epi.sum_disclosed).clip(lower=0) * epi.ml_factor,
                             epi.total * epi.ml_factor)
    epi["lower_ml"] = np.where(epi.total_censored, 0.0, epi.total * epi.ml_factor)
    g = (epi.groupby(["year", "is_lx"], as_index=False)
         .agg(mL_lower=("lower_ml", "sum"), mL_upper=("cap_ml", "sum")))
    w = g.pivot(index="year", columns="is_lx")
    w.columns = [f"{'LX' if lx else 'Standard+GE'}_{v.split('_')[-1]}"
                 for v, lx in w.columns]
    sheets["Fig5A_epinastine_LX"] = w.reset_index().rename(columns={"year": "Year"})

    # Fig6B: エピナスチンの 0.1%(LX)/0.05% × 先発/後発 4区分の年度別シェア（区間つき）。
    # 各区分のシェア = 区分/(区分+他3区分)。下限は「自区分を最小・他を最大」、
    # 上限は「自区分を最大・他を最小」で組む（brand_generic_share_bounds と同じ作法）。
    epi["is_generic"] = epi.product_type.str.startswith("generic")
    epi["formulation"] = np.where(epi.is_lx, "LX_0.1pct", "standard_0.05pct")
    epi["btype"] = np.where(epi.is_generic, "generic", "brand")
    q = (epi.groupby(["year", "formulation", "btype"], as_index=False)
         .agg(lower=("lower_ml", "sum"), upper=("cap_ml", "sum")))
    cats = [("LX_0.1pct", "brand"), ("LX_0.1pct", "generic"),
            ("standard_0.05pct", "brand"), ("standard_0.05pct", "generic")]
    rows = []
    for year in sorted(epi.year.unique()):
        rec = {"Year": year}
        qq = q[q.year == year].set_index(["formulation", "btype"])
        lo = {c: float(qq.loc[c, "lower"]) if c in qq.index else 0.0 for c in cats}
        hi = {c: float(qq.loc[c, "upper"]) if c in qq.index else 0.0 for c in cats}
        rec["total_lower"] = sum(lo.values())
        rec["total_upper"] = sum(hi.values())
        for c in cats:
            name = f"{c[0]}_{c[1]}"
            oth_lo = sum(v for k, v in lo.items() if k != c)
            oth_hi = sum(v for k, v in hi.items() if k != c)
            rec[f"{name}_lower"] = lo[c]
            rec[f"{name}_upper"] = hi[c]
            rec[f"{name}_pct_lower"] = (lo[c] / (lo[c] + oth_hi) * 100
                                        if lo[c] + oth_hi else np.nan)
            rec[f"{name}_pct_upper"] = (hi[c] / (hi[c] + oth_lo) * 100
                                        if hi[c] + oth_lo else np.nan)
        rows.append(rec)
    sheets["Fig6B_epinastine_formulation_bounds"] = pd.DataFrame(rows)

    # Fig5B: 2024年度 年齢群別の 0.1%(LX) 割合（区間つき）。年齢性別軸の縦持ちセルに
    # 同軸の品目レベル（missing は都道府県軸と別物）から秘匿セル1個あたりの上限を付ける。
    lvl = agesex_level[agesex_level.code == "EPINASTINE"].copy()
    lvl["per_cell_cap"] = np.where(lvl.total_censored,
                                   (999 - lvl.sum_disclosed).clip(lower=0),
                                   lvl.missing.clip(lower=0))
    key = ["year", "sheet", "code", "product_name"]
    al = pd.read_csv(os.path.join(INPUT_DIR, "product_agesex_long.csv"))
    al = al[al.code == "EPINASTINE"].merge(lvl[key + ["per_cell_cap"]], on=key, how="left")
    al["lower_ml"] = al.value.fillna(0.0) * al.ml_factor
    al["upper_ml"] = np.where(al.censored, al.per_cell_cap, al.value) * al.ml_factor
    al["is_lx"] = al.product_name.str.contains("ＬＸ")
    al["age"] = (al.age_group.str.replace("歳以上", "+", regex=False)
                 .str.replace("歳", "", regex=False)
                 .str.replace("～", "-", regex=False).str.replace("〜", "-", regex=False))
    a = (al.groupby(["year", "age", "is_lx"], as_index=False)
         [["lower_ml", "upper_ml"]].sum())
    rows = []
    for (year, age), g in a.groupby(["year", "age"]):
        gi = g.set_index("is_lx")
        lx_lo = float(gi.lower_ml.get(True, 0.0)); lx_hi = float(gi.upper_ml.get(True, 0.0))
        st_lo = float(gi.lower_ml.get(False, 0.0)); st_hi = float(gi.upper_ml.get(False, 0.0))
        rows.append({
            "Year": year, "Age Group": age,
            "LX_0.1pct_lower": lx_lo, "LX_0.1pct_upper": lx_hi,
            "standard_0.05pct_lower": st_lo, "standard_0.05pct_upper": st_hi,
            "LX_pct_published": lx_lo / (lx_lo + st_lo) * 100 if lx_lo + st_lo else np.nan,
            "LX_pct_lower": lx_lo / (lx_lo + st_hi) * 100 if lx_lo + st_hi else np.nan,
            "LX_pct_upper": lx_hi / (lx_hi + st_lo) * 100 if lx_hi + st_lo else np.nan,
        })
    b = pd.DataFrame(rows)
    b = age_sorted(b, "Age Group").sort_values(["Year"], kind="stable")
    sheets["Fig5B_LX_share_by_age_bounds"] = b.reset_index(drop=True)

    m = ge.merge(geann[["year", "code", "ge_class", "ge_class_label", "usable"]],
                 on=["year", "code"], how="left")
    m["drug_en"] = m.code.map(DRUG_EN)
    sheets["Fig5B_GE_share_bounds"] = m[[
        "year", "code", "drug_en", "share_pct_generic_lower",
        "share_pct_generic_upper", "quantity_brand_lower", "quantity_brand_upper",
        "quantity_generic_lower", "quantity_generic_upper",
        "ge_class", "ge_class_label", "usable"]].rename(columns={"year": "Year"})
    return sheets


# ----------------------------------------------------------------------
# SupplTable: 成分×年度の全国mL（区間つき）
# ----------------------------------------------------------------------
def annual_bounds(nat, uns, inv, counts, level):
    """成分×年度の識別区間。上限は原稿 §2.5 の定義（未収載加算は2021年度以前のみ）。

    upper = 公表値 + 総計秘匿の上限加算 + 未収載品目の順位ベース上限加算（year<=2021）
    NDB非掲載の成分・年度は公表値=0（真値不明）とし、上限は
    上市品目数 × 3区分合計の最小公表総計 × mL換算係数 で構成する。
    build_trend_identification.py（Fig 1・Suppl Table S4）と同一の上限になる。
    """
    counts = counts[counts.sheet != "全シート通算（ユニーク）"]
    min_total = counts.set_index(["year", "sheet"])["min_total"].to_dict()
    code_factor = level.groupby("code")["ml_factor"].max().to_dict()
    natix = nat.set_index(["code", "year"])

    rows = []
    for year in range(2014, 2025):
        per_item_raw = sum(min_total.get((year, s), 0) or 0 for s in SHEET_ORDER)
        for code in DRUG_ORDER:
            r = uns[(uns.code == code) & (uns.year == year)].iloc[0]
            if bool(r.listed_in_ndb):
                pub = float(r.published_total)
                unl = float(r.upper1) - pub
                tc = float(natix.loc[(code, year), "count_upper"]
                           - natix.loc[(code, year), "count_lower"])
            else:
                iv = inv[(inv.code == code) & (inv.year == year)].iloc[0]
                n_items = int(iv.marketed_generic_lo) + int(iv.marketed_brand)
                pub, tc = 0.0, 0.0
                unl = n_items * per_item_raw * code_factor[code]
            if year > 2021:
                unl = 0.0
            rows.append({"year": year, "code": code,
                         "listed_in_ndb": bool(r.listed_in_ndb),
                         "lower": pub, "censored_add": tc, "unlisted_add": unl})
    d = pd.DataFrame(rows)
    for name, codes in (("ANTI_HIST", ANTI_HIST_CODES),
                        ("MED_RELEASE", MED_RELEASE_CODES),
                        ("TOP3_TOTAL", TOP3),
                        ("ALLERGY_EYE_TOTAL", DRUG_ORDER)):
        g = (d[d.code.isin(codes)].groupby("year", as_index=False)
             [["lower", "censored_add", "unlisted_add"]].sum())
        g["code"], g["listed_in_ndb"] = name, True
        d = pd.concat([d, g], ignore_index=True)
    d["upper_published_items"] = d.lower + d.censored_add
    d["upper"] = d.upper_published_items + d.unlisted_add
    return d


def suppl_sheets(nat, uns, inv, counts, level):
    order = DRUG_ORDER + ["ANTI_HIST", "MED_RELEASE", "TOP3_TOTAL",
                          "ALLERGY_EYE_TOTAL"]
    d = annual_bounds(nat, uns, inv, counts, level)
    base = None
    for code in order:
        name = DRUG_EN[code]
        s = (d[d.code == code][["year", "lower", "upper",
                                "upper_published_items"]]
             .rename(columns={"lower": f"{name}_lower",
                              "upper": f"{name}_upper",
                              "upper_published_items":
                                  f"{name}_upper_published_items"}))
        base = s if base is None else base.merge(s, on="year", how="outer")
    nr = (d[(~d.listed_in_ndb) & (d.code.isin(DRUG_ORDER))]
          .assign(en=lambda x: x.code.map(DRUG_EN))
          .groupby("year")["en"].apply(lambda s: ", ".join(sorted(s))))
    base["agents_not_listed_in_NDB"] = base.year.map(nr).fillna("")
    return {"SupplTable_annual_mL": base.rename(columns={"year": "Fiscal year"})}


# ----------------------------------------------------------------------
# Tables 1-3
# ----------------------------------------------------------------------
def tables_sheets(nat, agesex, ge, geann, rank):
    sheets = {}
    y24 = nat[nat.year == 2024]
    ge24 = ge[ge.year == 2024].set_index("code")
    rows = []
    for code in DRUG_ORDER + ["TOP3_TOTAL", "ALLERGY_EYE_TOTAL"]:
        r = y24[y24.code == code]
        if r.empty:
            continue
        r = r.iloc[0]
        rec = {"Drug": DRUG_EN[code],
               "Volume_mL_lower": r.count_lower, "Volume_mL_upper": r.count_upper,
               "Per100k_lower": r.per100k_lower, "Per100k_upper": r.per100k_upper}
        if code in ge24.index:
            rec["GE_share_pct_lower"] = ge24.loc[code, "share_pct_generic_lower"]
            rec["GE_share_pct_upper"] = ge24.loc[code, "share_pct_generic_upper"]
        rows.append(rec)
    sheets["Table1_FY2024"] = pd.DataFrame(rows)

    # Table2: M/F比（FY2024、TOP3）。比の区間は [M_lo/F_hi, M_hi/F_lo]
    t = agesex[(agesex.code == "TOP3_TOTAL") & (agesex.year == 2024)]
    w = t.pivot_table(index="age_group", columns="sex",
                      values=["count_lower", "count_upper", "per100k_lower",
                              "per100k_upper"])
    w.columns = [f"{SEX_EN[sx]}_{v}" for v, sx in w.columns]
    w = age_sorted(w.reset_index())
    w["MF_per100k_ratio_lower"] = w.Male_per100k_lower / w.Female_per100k_upper
    w["MF_per100k_ratio_upper"] = w.Male_per100k_upper / w.Female_per100k_lower
    sheets["Table2_MF_ratio"] = w.rename(columns={"age_group": "Age Group"})

    sheets["Table3_pref_ranking"] = rank
    return sheets


# ----------------------------------------------------------------------
# 出力
# ----------------------------------------------------------------------
NOTES = [
    "抗アレルギー点眼薬9成分（NDBオープンデータ第1〜11回、公費レセプトを含まない集計）",
    "全数量はmL換算（換算係数はNDB品目名の規格表記から品目ごとに取得。unit_conversion_audit.csv 参照）",
    "lower = 秘匿セルを0とした下限 / upper = 行内秘匿合計(missing)を単一セルに割り付けた上限",
    "総計自体が秘匿の品目は 999−公表済みセル合計 を上限とする（補完的秘匿のため999/セルは使わない）",
    "算出方法の詳細: bounded_outputs_report.md / unlisted_sensitivity_report.md（3成分シェアの区間）",
]


def write_book(fname, sheets, extra_notes=()):
    path = os.path.join(OUT, fname)
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        readme = pd.DataFrame({"Notes": list(NOTES) + list(extra_notes)})
        readme.to_excel(xw, sheet_name="README", index=False)
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
            csv_name = f"{os.path.splitext(fname)[0]}__{name}.csv"
            df.to_csv(os.path.join(CSV_OUT, csv_name),
                      index=False, encoding="utf-8-sig")
        for ws in xw.book.worksheets:
            for cell in ws[1]:
                cell.font = Font(name="Arial", bold=True)
            for col_idx, col in enumerate(ws.iter_cols(min_row=1, max_row=1), 1):
                width = max(10, min(38, len(str(col[0].value or "")) + 4))
                ws.column_dimensions[get_column_letter(col_idx)].width = width
            ws.freeze_panes = "A2"
    print(f"-> {os.path.relpath(path, BASE)} ({len(sheets)} sheets)")


def main():
    ensure(OUT)
    ensure(CSV_OUT)
    dat = load_all()

    audit = unit_audit(dat["level"], dat["agesex_level"])
    p = os.path.join(OUT, "unit_conversion_audit.csv")
    audit_readme = [
        "# ============ README（この行はデータではない。読込時は comment='#' を指定） ============",
        "# 対象品目一覧（品目名・成分・単位・mL換算係数・根拠）。Suppl Table S1 の元データ。",
        "# code / drug        : 成分コード / 成分名",
        "# product_name       : NDB掲載の品目名（規格・容量を含む）",
        "# unit               : NDB上の数量単位（mL／瓶／個）",
        "# ml_factor          : 1単位あたりのmL換算係数",
        "# unit_source        : 'backfilled' の行は、2014・2015年度分の単位。",
        "#                      NDBオープンデータは2014・2015年度に単位列自体が存在しないため、",
        "#                      同一品目名を持つ2016年度以降の行から単位・換算係数を遡って補完した。",
        "#                      空欄はNDBの単位列がそのまま使えた行（補完なし）。",
        "# ml_factor_basis    : 換算係数の根拠（品目名の規格表記、または単位がmLそのもの）。",
        "#                      backfilled の行は末尾に補完した旨を付記。",
        "# ======================================================================================",
    ]
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        f.write("\n".join(audit_readme) + "\n")
        audit.to_csv(f, index=False)
    print(f"-> {os.path.relpath(p, BASE)} ({len(audit)} rows)")

    share = top3_share_bounds(dat["uns"], dat["inv"], dat["counts"], dat["level"])

    write_book("Fig1_age_sex_profile_bounds.xlsx", fig1_sheets(dat["agesex"]),
               ["FY2024。per100k = mL換算数量 / 人口 × 10万"])
    write_book("Fig2_age_distribution_bounds.xlsx", fig2_sheets(dat["agesex"]),
               ["Fig2A: 年齢構成比の識別区間。Fig2B: 加重平均年齢の識別区間"
                "（頂点解の全探索による厳密な下限・上限）"])
    write_book("Fig3_prefecture_map_bounds.xlsx",
               fig3_sheets(dat["pref"], dat["rank"]),
               ["都道府県は医療機関・薬局の所在地（患者の居住地ではない）"])
    ann = annual_bounds(dat["nat"], dat["uns"], dat["inv"], dat["counts"], dat["level"])
    write_book("Fig4_trends_shares_bounds.xlsx", fig4_sheets(dat["nat"], share, ann),
               ["Fig4A/4B の _upper は Suppl Table S5 と同じ定義（総計秘匿＋2021年度以前の"
                "未収載品目の順位ベース上限）。人口10万対は同じ人口で割った値",
                "Fig4C: 指摘①への回答。others_upper はNDB非掲載成分も"
                "上市品目数×最小公表総計（順位ベース）で上限を構成",
                "3成分シェアを厳密に主張できるのは足切り撤廃後の2022年度以降"])
    write_book("Fig5_ge_formulation_bounds.xlsx",
               fig5_sheets(dat["level"], dat["ge"], dat["geann"], dat["agesex_level"]),
               ["Fig5B_GE_share_bounds: ge_class B/C の年度はGE比率の経年比較に使えない"
                "（足切りによる非掲載。ge_share_report.md 参照）",
                "Fig5B_LX_share_by_age_bounds: 本文 Figure 5B。LX_pct_published は公表値"
                "（＝下限どうしの比）、_lower/_upper はセル秘匿を含む識別区間",
                "Fig6B_epinastine_formulation_bounds: 本文 Figure 6B。"
                "各区分のシェア区間は [自区分下限/(自区分下限+他区分上限), "
                "自区分上限/(自区分上限+他区分下限)]"])
    write_book("SupplTable_annual_totals_bounds.xlsx",
               suppl_sheets(dat["nat"], dat["uns"], dat["inv"], dat["counts"],
                            dat["level"]),
               ["_upper = 公表値 + 総計秘匿の上限加算 + 未収載品目の順位ベース"
                "上限加算。未収載加算は足切りが働いていた2021年度以前のみ"
                "（原稿 §2.5）。Fig 1・Suppl Table S4 と同一の上限",
                "_upper_published_items = 公表品目のみを対象にした上限"
                "（セル秘匿・総計秘匿のみ。未収載品目を含まない）",
                "NDB非掲載の成分・年度は _lower = 0（公表なし＝真値不明）。"
                "該当成分は agents_not_listed_in_NDB 列に列挙",
                "2022年度以降は _upper と _upper_published_items が一致する"
                "（足切り解消により未収載加算なし）"])
    write_book("Tables_123_bounds.xlsx",
               tables_sheets(dat["nat"], dat["agesex"], dat["ge"], dat["geann"],
                             dat["rank"]),
               ["Table2のM/F比の区間は [M下限/F上限, M上限/F下限]"])

    p = os.path.join(CSV_OUT, "Fig4_trends_shares_bounds__Fig4C_top3_share_bounds.csv")
    print(f"   指摘①の一次表: {os.path.relpath(p, BASE)}")


if __name__ == "__main__":
    main()
