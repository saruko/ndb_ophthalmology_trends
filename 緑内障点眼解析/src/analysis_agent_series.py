# -*- coding: utf-8 -*-
"""成分別の年次系列（収載開始年度から最新年度まで）と、薬効群シェアの年次推移。

NDBオープンデータは成分ごとに収載開始年度が異なる。ある成分が「いつから追跡できるか」は
次の2つの理由で決まり、両者は意味がまったく違う。

  (a) 新規発売  … その年度に発売されたため、それ以前は存在しない（実態）
  (b) 収載拡大  … 薬自体は以前からあるが、第10回（2022年度分）の収録品目拡大まで
                  NDBに載っていなかった（データの都合）

本モジュールは各成分の初収載年度・連続収載の起点・欠測年度を機械的に求め、
(a)(b) の判別材料として2022年初収載成分の伸び方（発売直後なら低値から急増、
既存薬が収載されただけなら初年度から横ばい）も併記する。

出力:
  agent_annual_series_glaucoma.csv   薬効群×成分×年度の数量・人口10万対・シェア（未収載はNR）
  agent_traceability_glaucoma.csv    成分ごとの追跡可能期間の判定とその期間のAPC
  group_share_by_year_glaucoma.csv   年度×薬効群（下位分類を含む）のシェア推移
"""
import os

import numpy as np
import pandas as pd

from analysis_glaucoma import calculate_apc_linear
from preprocess_glaucoma import GROUP_DEFS, SUBGROUP_DEFS, TOTAL_CODES

FULL_COV_START = 2022          # 収載品目が拡大した年度（第10回）
GROUP_ORDER = [c for c, _, _ in GROUP_DEFS]
SUBGROUP_ORDER = [c for c, _, _ in SUBGROUP_DEFS]
CODE_TO_GROUP = {m: (g, n) for g, n, ms in GROUP_DEFS for m in ms}
SUB_PARENT = {"PGA_FP": "PGA", "PGA_EP2": "PGA",
              "BETA_NONSEL": "BETA", "BETA_B1SEL": "BETA", "BETA_A1B": "BETA"}


def _classify_start(first, years, last_year):
    """収載開始の性格を機械的に判定し、(判定, 欠測年, 連続収載の起点) を返す。

    連続収載の起点は「最新年度から途切れずに遡れる最初の年度」。最新年度に
    収載がない成分は最新年度まで追跡できないため None を返す。
    """
    missing = [y for y in range(first, last_year + 1) if y not in years]

    if last_year not in years:
        listed = ", ".join(str(y) for y in sorted(years))
        return (f"★最新年度({last_year})に収載なし（収載年度: {listed}）",
                missing, None)

    cont = last_year
    while cont - 1 in years:
        cont -= 1

    if first <= 2014 and not missing:
        return "全期間追跡可能（2014年度から連続収載）", missing, cont
    if first == 2015 and not missing:
        return "2015年度から連続収載（2014年度は第1回で上位品目のみ）", missing, cont
    if missing:
        return (f"★欠測年あり（{', '.join(str(y) for y in missing)}）"
                f"／{cont}年度以降は連続", missing, cont)
    if first >= FULL_COV_START:
        return "★2022年度から収載（新規発売か収載拡大かの判別が必要）", missing, cont
    return f"{first}年度から連続収載", missing, cont


def run_agent_series(processed_csv, output_dir, inventory_csv=None):
    """成分別の年次系列と薬効群シェアを算出する。

    「その年度にNDBへ収載されたか」は品目マスタ（公表「総計」列）で判定する。
    都道府県セルの合計は秘匿の影響を受けるため、収載されていても合計が0になる
    成分（ジスチグミン等）があり、収載の有無の判定に使えないため。
    """
    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(processed_csv)
    last_year = int(df["year"].max())
    all_years = sorted(df["year"].unique())

    # 年度×成分の収載の有無と公表総計（秘匿の影響を受けない）
    listed_years, published = {}, {}
    if inventory_csv and os.path.exists(inventory_csv):
        inv = pd.read_csv(inventory_csv)
        agg = inv.groupby(["year", "code"], as_index=False)["quantity_ml"].sum()
        for _, r in agg.iterrows():
            listed_years.setdefault(r["code"], set()).add(int(r["year"]))
            published[(r["code"], int(r["year"]))] = float(r["quantity_ml"])

    # ── 全国レベルに集計 ──
    nat = df.groupby(["year", "code", "procedure_name"], as_index=False).agg(
        count_ml=("count_ml", "sum"), population=("population_total", "sum"))
    nat["count_per_100k"] = nat["count_ml"] / nat["population"] * 100000
    total = nat[nat["code"] == "GLAUCOMA_EYE_TOTAL"].set_index("year")["count_ml"]
    grp_tot = (nat[nat["code"].isin(GROUP_ORDER)]
               .set_index(["year", "code"])["count_ml"])

    # ── 1. 成分別の年次系列（未収載はNR）──
    agents = sorted(TOTAL_CODES)
    rows = []
    for code in agents:
        g = nat[nat["code"] == code]
        listed = listed_years.get(code) or set(g[g["count_ml"] > 0]["year"])
        gcode, gname = CODE_TO_GROUP.get(code, ("EXCLUDED", "合計対象外"))
        name = g["procedure_name"].iloc[0] if len(g) else code
        for y in all_years:
            row = {"group_code": gcode, "group_name": gname,
                   "code": code, "category_name": name, "year": int(y)}
            if y in listed:
                v = g[g["year"] == y].iloc[0]
                row.update({
                    "listed": True,
                    "quantity_ml_published": published.get((code, int(y)), np.nan),
                    "count_ml": float(v["count_ml"]),
                    "count_per_100k": float(v["count_per_100k"]),
                    "share_of_total_pct": float(v["count_ml"] / total[y] * 100),
                    "share_within_group_pct": (
                        float(v["count_ml"] / grp_tot.get((y, gcode), np.nan) * 100)
                        if grp_tot.get((y, gcode), 0) else np.nan),
                })
            else:
                row.update({"listed": False,
                            "quantity_ml_published": np.nan,
                            "count_ml": np.nan,
                            "count_per_100k": np.nan,
                            "share_of_total_pct": np.nan,
                            "share_within_group_pct": np.nan})
            rows.append(row)
    series = pd.DataFrame(rows)
    series["_g"] = series["group_code"].map({c: i for i, c in enumerate(GROUP_ORDER)})
    series = series.sort_values(["_g", "code", "year"]).drop(columns="_g")
    series.to_csv(os.path.join(output_dir, "agent_annual_series_glaucoma.csv"),
                  index=False, encoding="utf-8-sig")

    # ── 2. 成分ごとの追跡可能性の判定 ──
    recs = []
    for code in agents:
        gall = nat[nat["code"] == code].sort_values("year")
        years = listed_years.get(code) or set(
            int(y) for y in gall[gall["count_ml"] > 0]["year"])
        if not years:
            continue
        g = gall[gall["year"].isin(years)]
        if g.empty:
            continue
        first = min(years)
        verdict, missing, cont = _classify_start(first, years, last_year)

        sub = g[g["year"] >= cont] if cont else g.iloc[0:0]
        apc = {}
        if len(sub) >= 3 and (sub["count_per_100k"] > 0).all():
            apc = calculate_apc_linear(sub["year"].values,
                                       sub["count_per_100k"].values)

        first_v = float(g.iloc[0]["count_per_100k"])
        last_v = float(g.iloc[-1]["count_per_100k"])
        # 2022年初収載の成分について、発売直後（低値から急増）か既存薬の収載開始（横ばい）か
        pattern = ""
        if first >= FULL_COV_START and len(g) >= 2:
            ratio = last_v / first_v if first_v > 0 else np.nan
            pattern = ("初年度比 {:.1f}倍：新規発売の可能性が高い".format(ratio)
                       if ratio >= 2 else
                       "初年度比 {:.2f}倍：既存薬が収載拡大で可視化された可能性が高い".format(ratio))

        recs.append({
            "group_code": CODE_TO_GROUP.get(code, ("EXCLUDED", ""))[0],
            "group_name": CODE_TO_GROUP.get(code, ("", "合計対象外"))[1],
            "code": code,
            "category_name": g["procedure_name"].iloc[0],
            "first_listed_year": first,
            "last_year": last_year,
            "n_years_listed": len(years),
            "missing_years": ", ".join(str(y) for y in missing),
            "continuous_since": cont,
            "n_years_continuous": (last_year - cont + 1) if cont else 0,
            "traceability": verdict,
            "start_pattern": pattern,
            "first_year_per_100k": first_v,
            "last_year_per_100k": last_v,
            # 都道府県合計は秘匿でゼロになることがあるため、公表総計も併記する
            "first_year_published_ml": published.get((code, first), np.nan),
            "last_year_published_ml": published.get((code, last_year), np.nan),
            "apc_over_continuous_period": apc.get("apc"),
            "apc_low": apc.get("apc_low"),
            "apc_high": apc.get("apc_high"),
            "apc_p_value": apc.get("p_value"),
        })
    trace = pd.DataFrame(recs)
    trace["_g"] = trace["group_code"].map({c: i for i, c in enumerate(GROUP_ORDER)})
    trace = trace.sort_values(["_g", "first_listed_year", "code"]).drop(columns="_g")
    trace.to_csv(os.path.join(output_dir, "agent_traceability_glaucoma.csv"),
                 index=False, encoding="utf-8-sig")

    # ── 3. 薬効群シェアの年次推移（下位分類を含む）──
    rows = []
    for code in GROUP_ORDER + SUBGROUP_ORDER:
        g = nat[nat["code"] == code]
        for _, v in g.iterrows():
            y = int(v["year"])
            rows.append({
                "level": "薬効群" if code in GROUP_ORDER else "下位分類",
                "parent_group": SUB_PARENT.get(code, code),
                "code": code,
                "group_name": v["procedure_name"],
                "year": y,
                "count_ml": float(v["count_ml"]),
                "count_per_100k": float(v["count_per_100k"]),
                "share_of_total_pct": float(v["count_ml"] / total[y] * 100),
            })
    gs = pd.DataFrame(rows)
    order = {c: i for i, c in enumerate(GROUP_ORDER + SUBGROUP_ORDER)}
    gs["_o"] = gs["code"].map(order)
    gs = gs.sort_values(["year", "_o"]).drop(columns="_o")
    gs.to_csv(os.path.join(output_dir, "group_share_by_year_glaucoma.csv"),
              index=False, encoding="utf-8-sig")

    cs = trace["continuous_since"]
    print(f"  成分 {len(trace)} / 全期間追跡可能 {(cs <= 2014).sum()} / "
          f"2015年度から {(cs == 2015).sum()} / "
          f"2022年度以降のみ {(cs >= FULL_COV_START).sum()} / "
          f"最新年度に収載なし {cs.isna().sum()}")
    return series, trace, gs
