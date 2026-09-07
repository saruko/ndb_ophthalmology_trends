# -*- coding: utf-8 -*-
"""秘匿セルの識別区間（下限・上限）と未収載品目の感度分析（査読対応）。

抗アレルギー点眼解析 と同一の方法論を緑内障点眼薬に適用する。

指摘①（2021年度以前は収載品目に限りがある。掲載されていない薬剤があるのに
        処方量の比較は妥当か）
  2021年度以前は上位品目の足切りにより、上市中でもNDBに行が無い（未収載）品目がある。
  成分×年度ごとに、2022年度以降に掲載された品目のうち当該年度に無い品目を
  「未収載候補」とし、
    上限①（順位ベース）: 未収載品目の総量 ≤ その年度に公表された最小品目総量
    上限②（逆推計）    : 公表総量 ÷ Σ(当該年度に掲載済み品目の2022年度シェア)
  の2通りで公表値の上限を構成する（→ category_unlisted_bounds_glaucoma.csv）。

指摘②（外来院内・院外・入院で非公開データがある中で正確に解析できるのか。
        最大値・最小値の処理は）
  品目×年度ごとに `missing = 公表総計(mL) − Σ開示都道府県セル(mL)` が厳密に復元できる
  （品目マスタの quantity_ml − pref_sum_ml）。各秘匿セルの真値は [0, missing]。

  「秘匿セルは必ず1,000未満（≦999）」という仮定（--imputation upper の前提）は
  成立しない。NDBは補完的秘匿を行っており、実データでも部分秘匿の品目×年度に
  「秘匿セルがちょうど1個」は0行、missing が 秘匿セル数×999×mL係数 を超える行がある
  （本スクリプトが毎回検証して出力する）。したがって upper=999/セル は
  識別区間の上限として機能せず、本スクリプトの missing ベース上限を正とする。

入力: 03_解析結果/品目マスタ/product_inventory_glaucoma.csv
      01_抽出データ/ndb_processed_glaucoma_zero.csv
出力: 03_解析結果/品質管理_感度分析/
  product_censoring_bounds_glaucoma.csv    品目×年度の missing と分類
  category_national_bounds_glaucoma.csv    成分・薬効群×年度の全国 下限/上限(mL)
  prefecture_bounds_glaucoma.csv           都道府県×年度×成分の 下限/上限(mL)
  category_unlisted_bounds_glaucoma.csv    未収載品目まで拡張した上限（指摘①）
  censoring_bounds_report_glaucoma.md      方法・検証結果・査読回答の要旨
"""
import os
import re

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
INV_PATH = os.path.join(BASE, "03_解析結果", "品目マスタ", "product_inventory_glaucoma.csv")
PROC_PATH = os.path.join(BASE, "01_抽出データ", "ndb_processed_glaucoma_zero.csv")
OUT_DIR = os.path.join(BASE, "03_解析結果", "品質管理_感度分析")

CAP = 999           # 外用薬の秘匿閾値は処方数量1,000未満（一次秘匿ルール）
FULL_YEARS = (2022, 2023, 2024)   # 足切り撤廃後のフルカバレッジ期間
SHARE_BASE_YEAR = 2022


def base_name(name: str) -> str:
    return re.sub(r"（選）|\(選\)", "", str(name)).strip()


def load_inventory():
    inv = pd.read_csv(INV_PATH)
    inv["base_name"] = inv.product_name.map(base_name)
    inv["missing_ml"] = (inv.quantity_ml - inv.pref_sum_ml).clip(lower=0)
    # 総計秘匿シートの上限: 1シートあたり総計<1,000（一次秘匿ルール）
    inv["tc_cap_ml"] = inv.n_sheets_total_censored * CAP * inv.ml_per_unit
    return inv


def product_bounds(inv):
    d = inv.copy()
    d["censor_class"] = np.select(
        [d.n_pref_censored == 0,
         (d.pref_sum_ml <= 0) & (d.n_pref_censored > 0)],
        ["秘匿なし", "ブロック秘匿"], default="部分秘匿")
    d.loc[d.n_sheets_total_censored > 0, "censor_class"] = (
        d.loc[d.n_sheets_total_censored > 0, "censor_class"] + "+総計秘匿シートあり")
    d["exceeds_cap999"] = d.missing_ml > d.n_pref_censored * CAP * d.ml_per_unit + .5
    cols = ["year", "group_code", "code", "category_name", "product_name",
            "base_name", "drug_type", "ml_per_unit", "quantity_ml", "pref_sum_ml",
            "missing_ml", "n_pref_cells", "n_pref_censored",
            "n_sheets_total_censored", "tc_cap_ml", "censor_class", "exceeds_cap999"]
    return d[cols].sort_values(["year", "code", "product_name"])


def national_bounds(inv):
    """成分（code）・薬効群（group_code）×年度の全国mL区間。

    公表「総計」は都道府県セルの秘匿の影響を受けないため lower は確定値。
    総計自体が秘匿のシートのみ tc_cap_ml を上限に加算する。
    """
    def agg(key):
        g = (inv.groupby([key, "year"], as_index=False)
             .agg(lower=("quantity_ml", "sum"), tc=("tc_cap_ml", "sum"),
                  n_products=("product_name", "nunique")))
        g["upper"] = g.lower + g.tc
        g["width_pct"] = np.where(g.lower > 0, (g.upper - g.lower) / g.lower * 100,
                                  np.nan)
        return g.rename(columns={key: "code"})

    by_code = agg("code")
    # 薬効群・全体合計は対象外群（EXCLUDED: アプラクロニジン等）を含めない
    # （パイプラインの GLAUCOMA_EYE_TOTAL の定義に合わせる）
    inv = inv[inv.group_code != "EXCLUDED"]
    by_group = agg("group_code")
    total = (by_group.groupby("year", as_index=False)[["lower", "upper"]].sum()
             .assign(code="GLAUCOMA_EYE_TOTAL"))
    total["width_pct"] = (total.upper - total.lower) / total.lower * 100
    out = pd.concat([by_code, by_group, total], ignore_index=True)
    return out[["code", "year", "n_products", "lower", "upper", "width_pct"]]


def prefecture_bounds(inv, nat):
    """都道府県×年度×成分。lower = zero補完値（開示セル合計）。
    upper = lower + その成分×年度の missing 合計 + 総計秘匿シートの上限
    （欠落分すべてが当該県に集中した最悪ケース）。"""
    proc = pd.read_csv(PROC_PATH)
    # 欠落分は成分・薬効群・全体合計の3水準で用意する
    # （ndb_processed の code 列には3水準すべての行が含まれるため）
    miss_code = (inv.groupby(["code", "year"], as_index=False)
                 .agg(missing=("missing_ml", "sum"), tc=("tc_cap_ml", "sum")))
    ing = inv[inv.group_code != "EXCLUDED"]
    miss_grp = (ing.groupby(["group_code", "year"], as_index=False)
                .agg(missing=("missing_ml", "sum"), tc=("tc_cap_ml", "sum"))
                .rename(columns={"group_code": "code"}))
    miss_tot = (ing.groupby("year", as_index=False)
                .agg(missing=("missing_ml", "sum"), tc=("tc_cap_ml", "sum"))
                .assign(code="GLAUCOMA_EYE_TOTAL"))
    miss = pd.concat([miss_code, miss_grp, miss_tot], ignore_index=True)
    m = proc.merge(miss, on=["code", "year"], how="left")
    m[["missing", "tc"]] = m[["missing", "tc"]].fillna(0.0)
    m["lower"] = m.count_ml
    m["upper"] = m.count_ml + m.missing + m.tc
    m["width_pct"] = np.where(m.lower > 0, (m.upper - m.lower) / m.lower * 100,
                              np.nan)
    return m[["year", "prefecture", "code", "procedure_name",
              "lower", "upper", "width_pct", "count_per_100k"]]


def unlisted_bounds(inv):
    """指摘①: 未収載品目まで拡張した成分×年度の上限（2021年度以前）。"""
    # フルカバレッジ期間に観測された品目全体を「上市品目の候補集合」とする
    full = inv[inv.year.isin(FULL_YEARS)]
    candidates = full.groupby("code")["base_name"].agg(set)
    ml_of = full.groupby("base_name")["ml_per_unit"].max()

    base = inv[inv.year == SHARE_BASE_YEAR]
    base_qty = base.groupby(["code", "base_name"])["quantity_ml"].sum()

    rows = []
    for year in range(2014, 2022):
        y = inv[inv.year == year]
        if y.empty:
            continue
        # 順位ベースの1品目あたり上限: その年度に公表された最小の品目総量（生単位）
        min_pub_raw = y.quantity_published.min()
        listed_names = y.groupby("code")["base_name"].agg(set)
        pub_ml = y.groupby("code")["quantity_ml"].sum()
        for code, cand in candidates.items():
            listed = listed_names.get(code, set())
            unlisted = cand - listed
            published = float(pub_ml.get(code, 0.0))
            per_item = sum(min_pub_raw * float(ml_of.get(n, y.ml_per_unit.max()))
                           for n in unlisted)
            upper1 = published + per_item
            # 逆推計: 掲載済み品目の2022年度シェア合計で割り戻す
            upper2, cov = np.nan, np.nan
            if code in base_qty.index.get_level_values(0):
                bq = base_qty.loc[code]
                tot = bq.sum()
                if tot > 0 and listed:
                    cov = bq.reindex(listed).fillna(0).sum() / tot
                    if cov > 0 and published > 0:
                        upper2 = published / cov
            rows.append({
                "code": code, "year": year, "published_ml": published,
                "n_listed": len(listed), "n_unlisted_candidates": len(unlisted),
                "upper1_rank_ml": upper1,
                "upper1_width_pct": (upper1 - published) / published * 100
                if published > 0 else np.nan,
                "covered_2022_share": cov,
                "upper2_backcast_ml": upper2,
                "upper2_width_pct": (upper2 - published) / published * 100
                if (published > 0 and pd.notna(upper2)) else np.nan,
            })
    return pd.DataFrame(rows).sort_values(["code", "year"])


def build_report(pb, nat, unl):
    part = pb[pb.censor_class.str.startswith("部分秘匿")]
    n_one = int((part.n_pref_censored == 1).sum())
    n_exceed = int(pb.exceeds_cap999.sum())
    tot = nat[nat.code == "GLAUCOMA_EYE_TOTAL"]
    pre = unl[unl.year <= 2021]

    L = []
    A = L.append
    A("# 緑内障点眼薬 秘匿識別区間と未収載品目感度分析（査読対応）")
    A("")
    A("生成: `build_censoring_bounds_glaucoma.py`（抗アレルギー点眼解析 と同一の方法論）")
    A("")
    A("## 指摘①への回答: 2021年度以前の処方量は識別区間つきでのみ比較可能")
    A("")
    A("2021年度以前は上位品目の足切りにより未収載品目があるため、公表値は真の総量の")
    A("**下限**である。フルカバレッジ期間（2022〜2024年度）に観測された品目のうち")
    A("当該年度に無いものを未収載候補として、順位ベース（仮定ゼロ）と2022年度シェアの")
    A("逆推計の2通りで上限を構成した（`category_unlisted_bounds_glaucoma.csv`）。")
    A("")
    yearly = pre.groupby("year")["upper1_width_pct"].agg(["mean", "max"])
    A("| 年度 | 上限①の平均区間幅 | 最大区間幅 |")
    A("|---|--:|--:|")
    for yy, r in yearly.iterrows():
        A(f"| {yy} | +{r['mean']:.1f}% | +{r['max']:.1f}% |")
    A("")
    A("**したがって薬剤間・薬効群間の量比較とシェアは、主解析どおり2022〜2024年度に")
    A("限定するのが妥当**であり（`run_paper_analyses.py` の設計）、2021年度以前は")
    A("収載品目を固定した均衡パネル（Panel A/B）または識別区間の併記が必要である。")
    A("")
    A("なお順位ベース上限の「最小品目総量」は緑内障点眼薬の掲載品目内の最小値を")
    A("用いており、薬効分類131全体の最小値より大きい（＝上限としてはより保守的）。")
    A("")
    A("## 指摘②への回答: 秘匿セルは missing の厳密復元で区間評価する")
    A("")
    A("品目×年度ごとに `missing = 公表総計(mL) − Σ開示都道府県セル(mL)` を厳密に復元し、")
    A("都道府県別集計を下限（秘匿=0）／上限（missing 全額を当該県に割付）つきで")
    A("`prefecture_bounds_glaucoma.csv` に出力した。")
    A("")
    A("**「秘匿セル≦999」という仮定（--imputation upper の前提）は成立しない**。")
    A("補完的秘匿の実証:")
    A("")
    A(f"- 部分秘匿の品目×年度 {len(part)} 行のうち「秘匿セルがちょうど1個」は {n_one} 行")
    A("  （単独秘匿は必ず回避されている＝補完的秘匿の直接証拠）")
    A(f"- missing が 秘匿セル数×999×mL係数 を超える行が {n_exceed} 行")
    A("  （閾値1,000を超えるセルが巻き添えで伏せられている）")
    A("")
    A("よって `run_censoring_sensitivity.py` の zero/upper 区間のうち upper は")
    A("真の上限を過小評価しうる。識別区間としては本出力（missingベース）を正とする")
    A("（zero は下限として引き続き有効）。")
    A("")
    A("## 区間の実際の幅（全国合計）")
    A("")
    A("全国合計は公表「総計」列ベースのため都道府県セルの秘匿の影響を受けず、")
    A("区間幅は総計自体が秘匿のシート由来のみ:")
    A("")
    A("| 年度 | 下限(mL) | 上限(mL) | 幅 |")
    A("|---|--:|--:|--:|")
    for _, r in tot.sort_values("year").iterrows():
        A(f"| {r.year} | {r.lower:,.0f} | {r.upper:,.0f} | +{r.width_pct:.3f}% |")
    A("")
    A("都道府県別は成分・県によって区間が開くため、順位・比を示す際は")
    A("`prefecture_bounds_glaucoma.csv` の width_pct を確認して区間を併記すること。")
    A("")
    return "\n".join(L) + "\n"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    inv = load_inventory()

    pb = product_bounds(inv)
    p = os.path.join(OUT_DIR, "product_censoring_bounds_glaucoma.csv")
    pb.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(pb)} rows)")

    nat = national_bounds(inv)
    p = os.path.join(OUT_DIR, "category_national_bounds_glaucoma.csv")
    nat.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(nat)} rows)")

    pref = prefecture_bounds(inv, nat)
    p = os.path.join(OUT_DIR, "prefecture_bounds_glaucoma.csv")
    pref.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(pref)} rows)")

    unl = unlisted_bounds(inv)
    p = os.path.join(OUT_DIR, "category_unlisted_bounds_glaucoma.csv")
    unl.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(unl)} rows)")

    p = os.path.join(OUT_DIR, "censoring_bounds_report_glaucoma.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(build_report(pb, nat, unl))
    print(f"-> {os.path.relpath(p, BASE)}")


if __name__ == "__main__":
    main()
