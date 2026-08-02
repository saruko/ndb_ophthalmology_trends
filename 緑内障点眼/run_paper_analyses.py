"""論文用の2系統の解析を実行する。

NDBオープンデータは第10回（2022年度分）から外用薬の収録品目が大幅に増えたため、
2021年度以前と2022年度以降の処方量は直接比較できない。そこで解析を2系統に分ける。

  【主解析】薬剤間・薬効群間の比較 → 2022〜2024年度に限定する
      全品目が収載されたフルカバレッジ期間であり、薬剤間の量比較・シェア・地域差を
      バイアスなく比較できる。

  【長期解析】全年度に収載され続けた品目のみの均衡パネル
      Panel A: 2014〜2024年度の11年度すべてに収載された品目（6品目）
      Panel B: 2015〜2024年度の10年度すべてに収載された品目（20品目）
      収載品目が固定されているため、収載拡大の影響を受けずに長期トレンドを追える。
      ただし対象は個々の「品目」であり、後発品を含む成分全体の量ではない。

    python 緑内障点眼/run_paper_analyses.py

前提: run_glaucoma_pipeline.py と build_product_inventory.py の実行済み出力。
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))

from analysis_glaucoma import calculate_apc_linear, calculate_gini  # noqa: E402
from preprocess_glaucoma import GROUP_DEFS, TOTAL_CODES  # noqa: E402
from paths import add_nokouhi_arg, find, output_dir  # noqa: E402

FULL_COVERAGE_START = 2022
GROUP_CODES = [c for c, _, _ in GROUP_DEFS]
GROUP_NAMES = {c: n for c, n, _ in GROUP_DEFS}


# ─────────────────────────────────────────────
# 【主解析】2022〜2024年度に限定した薬剤間・群間比較
# ─────────────────────────────────────────────

def _summarize(df, codes, label_col="code"):
    """年度×カテゴリの全国数量・人口10万対・都道府県間格差をまとめる。"""
    total_by_year = (df[df["code"] == "GLAUCOMA_EYE_TOTAL"]
                     .groupby("year")["count_ml"].sum())
    rows = []
    for (year, code), g in df[df["code"].isin(codes)].groupby(["year", "code"]):
        rates = g["count_per_100k"].values
        mean_rate = float(np.mean(rates))
        national_ml = float(g["count_ml"].sum())
        pop = float(g["population_total"].sum())
        rows.append({
            "year": int(year),
            "code": code,
            "procedure_name": g["procedure_name"].iloc[0],
            "count_ml": national_ml,
            "count_per_100k": national_ml / pop * 100000 if pop else np.nan,
            "share": (national_ml / total_by_year[year]
                      if total_by_year.get(year) else np.nan),
            "cv": float(np.std(rates, ddof=1) / mean_rate) if mean_rate > 0 else np.nan,
            "gini": calculate_gini(rates) if mean_rate > 0 else np.nan,
            "min_prefecture": g.loc[g["count_per_100k"].idxmin(), "prefecture"],
            "max_prefecture": g.loc[g["count_per_100k"].idxmax(), "prefecture"],
            "max_to_min_ratio": (float(np.max(rates) / np.min(rates))
                                 if np.min(rates) > 0 else np.nan),
        })
    return pd.DataFrame(rows)


def run_full_coverage_analysis(processed_csv, out_dir):
    """2022〜2024年度に限定した薬剤間・薬効群間の比較。"""
    print(f"\n【主解析】{FULL_COVERAGE_START}〜2024年度（フルカバレッジ期間）")
    df = pd.read_csv(processed_csv)
    df = df[df["year"] >= FULL_COVERAGE_START]

    drug_codes = sorted(TOTAL_CODES)
    summary = _summarize(df, drug_codes + GROUP_CODES + ["GLAUCOMA_EYE_TOTAL"])
    summary.to_csv(os.path.join(out_dir, "fullcov_summary_glaucoma.csv"),
                   index=False, encoding="utf-8-sig")

    # 2022→2024の変化
    rows = []
    for code, g in summary.groupby("code"):
        g = g.sort_values("year")
        if len(g) < 2:
            continue
        first, last = g.iloc[0], g.iloc[-1]
        n = last["year"] - first["year"]
        cagr = ((last["count_per_100k"] / first["count_per_100k"]) ** (1 / n) - 1) * 100 \
            if first["count_per_100k"] > 0 and n > 0 else np.nan
        rows.append({
            "code": code,
            "procedure_name": first["procedure_name"],
            "start_year": int(first["year"]),
            "end_year": int(last["year"]),
            "count_ml_start": first["count_ml"],
            "count_ml_end": last["count_ml"],
            "count_per_100k_start": first["count_per_100k"],
            "count_per_100k_end": last["count_per_100k"],
            "share_start": first["share"],
            "share_end": last["share"],
            "share_change_pt": (last["share"] - first["share"]) * 100,
            "pct_change": ((last["count_per_100k"] / first["count_per_100k"] - 1) * 100
                           if first["count_per_100k"] > 0 else np.nan),
            "cagr_pct": cagr,
        })
    change = pd.DataFrame(rows).sort_values("count_ml_end", ascending=False)
    change.to_csv(os.path.join(out_dir, "fullcov_change_2022_2024_glaucoma.csv"),
                  index=False, encoding="utf-8-sig")

    # 都道府県ランキング（3年平均・全体および薬効群）
    pref = (df[df["code"].isin(GROUP_CODES + ["GLAUCOMA_EYE_TOTAL"])]
            .groupby(["code", "procedure_name", "prefecture"], as_index=False)
            .agg(count_ml=("count_ml", "sum"),
                 count_per_100k=("count_per_100k", "mean")))
    pref["rank"] = pref.groupby("code")["count_per_100k"].rank(
        ascending=False, method="min").astype(int)
    pref = pref.sort_values(["code", "rank"])
    pref.to_csv(os.path.join(out_dir, "fullcov_prefecture_ranking_glaucoma.csv"),
                index=False, encoding="utf-8-sig")

    print(f"  対象年度: {sorted(df['year'].unique())}")
    print(f"  薬剤カテゴリ {len(drug_codes)} / 薬効群 {len(GROUP_CODES)}")
    return summary, change


# ─────────────────────────────────────────────
# 【長期解析】収載品目を固定した均衡パネル
# ─────────────────────────────────────────────

def run_balanced_panel_analysis(inventory_csv, out_dir):
    """全年度に収載され続けた品目のみで長期トレンドを追う。

    数量は各品目行の公表「総計」列（都道府県セルの合計ではない）を用いる。
    秘匿の影響を受けにくく、全国トレンドの推定に適するため。
    """
    print("\n【長期解析】収載品目を固定した均衡パネル")
    inv = pd.read_csv(inventory_csv)
    inv = inv[inv["group_code"] != "EXCLUDED"]     # アプラクロニジンは除外

    panels = {
        "A": (2014, "11年度均衡パネル（2014〜2024年度に連続収載）"),
        "B": (2015, "10年度均衡パネル（2015〜2024年度に連続収載）"),
    }

    all_products, all_trends, all_apc = [], [], []
    for key, (start, label) in panels.items():
        years = list(range(start, 2025))
        cnt = (inv[inv["year"].isin(years)]
               .groupby("product_name")["year"].nunique())
        keep = set(cnt[cnt == len(years)].index)
        sub = inv[inv["year"].isin(years) & inv["product_name"].isin(keep)].copy()
        if sub.empty:
            continue
        sub["panel"] = key

        prod = (sub.drop_duplicates("product_name")[
            ["product_name", "group_code", "group_name", "code",
             "category_name", "drug_type", "ml_per_unit"]].copy())
        prod["panel"] = key
        prod["panel_label"] = label
        prod["start_year"] = start
        all_products.append(prod)

        # 品目別・カテゴリ別・パネル全体の全国数量
        pop = (pd.read_csv(find("ndb_processed_glaucoma_zero.csv", True))
               .query("code == 'GLAUCOMA_EYE_TOTAL'")
               .groupby("year")["population_total"].sum())

        for level, keys in [("product", ["product_name"]),
                            ("category", ["code", "category_name"]),
                            ("panel_total", [])]:
            grp = ["year"] + keys
            t = sub.groupby(grp, as_index=False)["quantity_ml"].sum()
            t["level"] = level
            t["panel"] = key
            if level == "panel_total":
                t["series"] = f"Panel {key} 合計"
            elif level == "category":
                t["series"] = t["category_name"]
            else:
                t["series"] = t["product_name"]
            t["count_per_100k"] = t["quantity_ml"] / t["year"].map(pop) * 100000
            all_trends.append(t[["panel", "level", "series", "year",
                                 "quantity_ml", "count_per_100k"]])

            for s, g in t.groupby("series"):
                g = g.sort_values("year")
                if len(g) < 3 or (g["count_per_100k"] <= 0).any():
                    continue
                res = calculate_apc_linear(g["year"].values,
                                           g["count_per_100k"].values)
                res.update({"panel": key, "level": level, "series": s,
                            "start_year": int(g["year"].min()),
                            "end_year": int(g["year"].max()),
                            "n_years": len(g)})
                all_apc.append(res)

        print(f"  Panel {key}: {label}: {len(keep)}品目")

    products = pd.concat(all_products, ignore_index=True)
    trends = pd.concat(all_trends, ignore_index=True)
    apc = pd.DataFrame(all_apc)

    products.to_csv(os.path.join(out_dir, "balanced_panel_products_glaucoma.csv"),
                    index=False, encoding="utf-8-sig")
    trends.to_csv(os.path.join(out_dir, "balanced_panel_trends_glaucoma.csv"),
                  index=False, encoding="utf-8-sig")
    apc.to_csv(os.path.join(out_dir, "balanced_panel_apc_glaucoma.csv"),
               index=False, encoding="utf-8-sig")
    return products, trends, apc


# ─────────────────────────────────────────────
# 【成分内シェア】同一成分のなかでの品目別処方数量シェア
# ─────────────────────────────────────────────

def run_within_agent_share(inventory_csv, out_dir):
    """同一成分内での品目別シェア（先発品 vs 各後発品）を算出する。

    数量は各品目行の公表「総計」列を用いる。2024年10月開始の選定療養により
    分割収載された「（選）」は build_product_inventory.py の時点で親品目へ
    名寄せ済みである（「（選）」は2024年度にのみ44品目出現し、他年度には存在しない）。
    """
    print("\n【成分内シェア】同一成分のなかでの品目別シェア")
    inv = pd.read_csv(inventory_csv)
    inv = inv[inv["group_code"] != "EXCLUDED"].copy()

    tot = inv.groupby(["year", "code"], as_index=False)["quantity_ml"].sum()
    tot = tot.rename(columns={"quantity_ml": "agent_total_ml"})
    d = inv.merge(tot, on=["year", "code"], how="left")
    d["share_within_agent"] = d["quantity_ml"] / d["agent_total_ml"]
    d["kind"] = np.where(d["drug_type"].str.startswith("後発"), "後発品", "先発品")
    d["rank_within_agent"] = d.groupby(["year", "code"])["quantity_ml"].rank(
        ascending=False, method="min").astype(int)

    prod = d[["year", "group_name", "code", "category_name", "product_name",
              "drug_type", "kind", "quantity_ml", "agent_total_ml",
              "share_within_agent", "rank_within_agent"]].sort_values(
        ["year", "code", "rank_within_agent"])
    prod.to_csv(os.path.join(out_dir, "within_agent_product_share_glaucoma.csv"),
                index=False, encoding="utf-8-sig")

    # 成分ごとの要約（品目数・先発後発比・集中度）
    rows = []
    for (year, code), g in d.groupby(["year", "code"]):
        total = g["quantity_ml"].sum()
        if total <= 0:
            continue
        s = g["share_within_agent"].fillna(0)
        br = g[g["kind"] == "先発品"]["quantity_ml"].sum()
        top = g.loc[g["quantity_ml"].idxmax()]
        rows.append({
            "year": int(year), "code": code,
            "category_name": g["category_name"].iloc[0],
            "n_products": g["product_name"].nunique(),
            "n_generic_products": g[g["kind"] == "後発品"]["product_name"].nunique(),
            "agent_total_ml": total,
            "originator_share": br / total,
            "generic_share": 1 - br / total,
            "top_product": top["product_name"],
            "top_product_share": top["quantity_ml"] / total,
            "top3_share": s.nlargest(3).sum(),
            "hhi_within_agent": float((s ** 2).sum()),
        })
    summ = pd.DataFrame(rows).sort_values(["year", "agent_total_ml"],
                                          ascending=[True, False])
    summ.to_csv(os.path.join(out_dir, "within_agent_summary_glaucoma.csv"),
                index=False, encoding="utf-8-sig")
    print(f"  成分 {summ['code'].nunique()} / 品目 {prod['product_name'].nunique()}")
    return prod, summ


def main():
    ap = argparse.ArgumentParser()
    add_nokouhi_arg(ap)
    args = ap.parse_args()
    out_dir = output_dir(args.nokouhi)

    processed = find("ndb_processed_glaucoma_zero.csv", args.nokouhi)
    inventory = find("product_inventory_glaucoma.csv", args.nokouhi)
    for p in (processed, inventory):
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"{p} がありません。run_glaucoma_pipeline.py と "
                f"build_product_inventory.py を先に実行してください。")

    run_full_coverage_analysis(processed, out_dir)
    run_balanced_panel_analysis(inventory, out_dir)
    run_within_agent_share(inventory, out_dir)

    print("\n【年齢調整】都道府県比較（間接標準化・2層）")
    from analysis_age_adjusted import run_age_adjustment
    agesex = find("ndb_glaucoma_age_sex_zero.csv", args.nokouhi)
    pop = find("population_age_sex.csv", args.nokouhi)
    run_age_adjustment(processed, agesex, pop, out_dir,
                       codes=GROUP_CODES + ["GLAUCOMA_EYE_TOTAL"])

    print(f"\n出力先: {out_dir}")


if __name__ == "__main__":
    main()
