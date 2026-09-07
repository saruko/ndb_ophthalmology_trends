"""硝子体注射液の製品軸の解析。

1. 薬剤製品毎（医薬品コード単位）の数量・シェア・薬価・薬剤費
2. 各成分の 注射液（バイアル）／キット（プレフィルドシリンジ）比率
3. 先発品と後発品（ルセンティス vs ラニビズマブBS）の比率
4. 年齢階級・性別分布
5. 秘匿による取りこぼし率のQC
"""

import os
import numpy as np
import pandas as pd

from drug_master import MOLECULE_NAMES
from paths import input_path

ANTI = "ANTI_VEGF"


def _share(df, group_keys, value="quantity"):
    total = df.groupby(group_keys)[value].transform("sum")
    return np.where(total > 0, df[value] / total * 100, np.nan)


def analyze_by_product(national, pref, output_dir):
    """1. 製品毎の年度別 数量・シェア・薬価・薬剤費（全国値は公表総計ベース）。"""
    print("Analyzing by product...")
    anti = national[national["category"] == ANTI]

    prod = anti.groupby(
        ["year", "drug_code", "product_name", "molecule_name", "formulation",
         "brand_type"], as_index=False
    ).agg(quantity=("quantity", "sum"), cost=("cost", "sum"),
          price=("price", "first"))
    prod["share_pct"] = _share(prod, ["year"])
    prod["cost_share_pct"] = _share(prod, ["year"], "cost")
    prod = prod.sort_values(["year", "quantity"], ascending=[True, False])
    prod.to_csv(os.path.join(output_dir, "product_trends_antivegf.csv"),
                index=False, encoding="utf-8-sig")

    # 外来／入院の内訳
    setting = anti.groupby(["year", "setting", "product_name"], as_index=False)[
        "quantity"].sum()
    setting["share_within_product_pct"] = _share(setting, ["year", "product_name"])
    setting.to_csv(os.path.join(output_dir, "product_by_setting_antivegf.csv"),
                   index=False, encoding="utf-8-sig")

    # 薬価一覧（年度×製品）
    price = prod.pivot_table(index=["product_name", "drug_code"], columns="year",
                             values="price")
    price.columns = [f"{y}年度_薬価(円)" for y in price.columns]
    price.to_csv(os.path.join(output_dir, "product_price_table_antivegf.csv"),
                 encoding="utf-8-sig")

    # 製品別ピボット（数量・シェア）
    for value, fname in [("quantity", "product_quantity_pivot_antivegf.csv"),
                         ("share_pct", "product_share_pivot_antivegf.csv"),
                         ("cost", "product_cost_pivot_antivegf.csv")]:
        p = prod.pivot_table(index="product_name", columns="year", values=value)
        p.to_csv(os.path.join(output_dir, fname), encoding="utf-8-sig")
    return prod


def analyze_formulation(national, pref, output_dir):
    """2. 成分ごとの 注射液 vs キット の比率（全国値は公表総計ベース）。"""
    print("Analyzing formulation (vial vs kit)...")
    anti = national[national["category"] == ANTI]
    # 両剤形が存在する成分のみ比率に意味があるため、その旨を列で示す
    form = anti.groupby(["year", "molecule", "molecule_name", "formulation"],
                        as_index=False)["quantity"].sum()
    form["share_within_molecule_pct"] = _share(form, ["year", "molecule"])

    both = (anti.groupby("molecule")["formulation"].nunique() > 1)
    form["has_both_formulations"] = form["molecule"].map(both)
    form.to_csv(os.path.join(output_dir, "formulation_by_molecule_antivegf.csv"),
                index=False, encoding="utf-8-sig")

    # 抗VEGF全体での剤形比率
    total = anti.groupby(["year", "formulation"], as_index=False)["quantity"].sum()
    total["share_pct"] = _share(total, ["year"])
    total.to_csv(os.path.join(output_dir, "formulation_total_antivegf.csv"),
                 index=False, encoding="utf-8-sig")

    # 都道府県別キット比率（最新年度）— 都道府県内訳は秘匿補完後の値を使う
    pref_anti = pref[pref["category"] == ANTI]
    latest = pref_anti[pref_anti["year"] == pref_anti["year"].max()]
    pref_form = latest.groupby(["prefecture", "formulation"], as_index=False)[
        "quantity"].sum()
    pref_form["share_pct"] = _share(pref_form, ["prefecture"])
    kit = pref_form[pref_form["formulation"] == "キット"].sort_values(
        "share_pct", ascending=False)
    kit.to_csv(os.path.join(output_dir, "formulation_kit_share_by_prefecture.csv"),
               index=False, encoding="utf-8-sig")
    return form


def analyze_biosimilar(national, pref, output_dir):
    """3. ラニビズマブの先発 vs バイオシミラー比率（全国・都道府県別）。

    全国シェアは公表総計ベース。先発は残存数量が少なく都道府県内訳の秘匿欠落が
    大きいため、内訳合計で計算するとBSシェアが過大評価になる。
    """
    print("Analyzing originator vs biosimilar (ranibizumab)...")
    mols = ["RANIBIZUMAB_ORIG", "RANIBIZUMAB_BS"]
    rani = national[national["molecule"].isin(mols)]

    nat = rani.groupby(["year", "brand_type"], as_index=False)["quantity"].sum()
    nat["share_pct"] = _share(nat, ["year"])
    nat.to_csv(os.path.join(output_dir, "biosimilar_national_share.csv"),
               index=False, encoding="utf-8-sig")

    # BS発売以降の年度で都道府県別のBSシェア（内訳は補完後の値）
    pref_rani = pref[pref["molecule"].isin(mols)]
    bs_years = sorted(nat.loc[(nat["brand_type"] == "バイオシミラー") &
                              (nat["quantity"] > 0), "year"].unique())
    pref_share = pref_rani[pref_rani["year"].isin(bs_years)].groupby(
        ["year", "prefecture", "brand_type"], as_index=False)["quantity"].sum()
    pref_share["share_pct"] = _share(pref_share, ["year", "prefecture"])
    bs = pref_share[pref_share["brand_type"] == "バイオシミラー"]
    piv = bs.pivot_table(index="prefecture", columns="year", values="share_pct")
    piv.columns = [f"{y}年度_BSシェア(%)" for y in piv.columns]
    if len(piv.columns):
        piv = piv.sort_values(piv.columns[-1], ascending=False)
    piv.to_csv(os.path.join(output_dir, "biosimilar_share_by_prefecture.csv"),
               encoding="utf-8-sig")

    # BS導入によるラニビズマブ薬剤費への影響（先発薬価で置換した場合との差）
    cost = rani.groupby(["year", "brand_type"], as_index=False)["cost"].sum()
    cost_piv = cost.pivot_table(index="year", columns="brand_type", values="cost")
    orig_price = rani[rani["brand_type"] == "先発"].groupby("year")["price"].max()
    bs_qty = rani[rani["brand_type"] == "バイオシミラー"].groupby("year")["quantity"].sum()
    cost_piv["BS数量を先発薬価で換算(円)"] = bs_qty * orig_price
    cost_piv["薬剤費削減額(円)"] = (cost_piv["BS数量を先発薬価で換算(円)"]
                              - cost_piv.get("バイオシミラー", 0))
    cost_piv.to_csv(os.path.join(output_dir, "biosimilar_cost_impact.csv"),
                    encoding="utf-8-sig")
    return nat


def analyze_age_sex(agesex, output_dir):
    """4. 年齢階級・性別分布（全体／薬剤別／年度別）。

    年齢区分の粒度は年度で異なる（2014年度は90歳以上が最上位、2015年度以降は
    90〜94/95〜99/100歳以上に細分化）。方針は次のとおり:
      - 年度内のシェア計算 → その年度の公開粒度をそのまま使う（published）
      - 年度をまたぐ比較   → 区分数の少ない方に揃える（comparable、90歳以上に統合）
    """
    print("Analyzing age and sex distribution...")
    anti = agesex[agesex["category"] == ANTI]

    # 年度内シェア（公開粒度のまま）
    pub = anti.groupby(["year", "sex", "age_group_detail"],
                       as_index=False)["quantity"].sum()
    pub["share_within_year_pct"] = _share(pub, ["year"])
    pub.to_csv(os.path.join(output_dir, "agesex_distribution_published_antivegf.csv"),
               index=False, encoding="utf-8-sig")

    # 経年比較用（90歳以上に統合）
    dist = anti.groupby(["year", "sex", "age_group"], as_index=False)["quantity"].sum()
    dist["share_pct"] = _share(dist, ["year"])
    dist.to_csv(os.path.join(output_dir, "agesex_distribution_comparable_antivegf.csv"),
                index=False, encoding="utf-8-sig")

    by_drug = anti.groupby(["year", "molecule_name", "sex", "age_group"],
                           as_index=False)["quantity"].sum()
    by_drug["share_within_drug_pct"] = _share(by_drug, ["year", "molecule_name"])
    by_drug.to_csv(os.path.join(output_dir, "agesex_by_molecule_antivegf.csv"),
                   index=False, encoding="utf-8-sig")

    # 平均年齢（階級中央値による近似）と高齢者比率の推移
    # 経年比較のため統合後の age_group を用いる
    mid = {g: (75 if g == "90歳以上" else int(g.split("～")[0]) + 2.5)
           for g in anti["age_group"].unique()}
    mid["90歳以上"] = 92.5
    tmp = anti.copy()
    tmp["age_mid"] = tmp["age_group"].map(mid)
    summ = tmp.groupby("year").apply(
        lambda g: pd.Series({
            "mean_age_approx": np.average(g["age_mid"], weights=g["quantity"])
            if g["quantity"].sum() > 0 else np.nan,
            "share_75plus_pct": g.loc[g["age_mid"] >= 75, "quantity"].sum()
            / g["quantity"].sum() * 100 if g["quantity"].sum() > 0 else np.nan,
            "male_share_pct": g.loc[g["sex"] == "男", "quantity"].sum()
            / g["quantity"].sum() * 100 if g["quantity"].sum() > 0 else np.nan,
        }), include_groups=False).reset_index()
    summ.to_csv(os.path.join(output_dir, "agesex_summary_antivegf.csv"),
                index=False, encoding="utf-8-sig")
    return dist, summ


def masking_qc(pref, agesex, output_dir, raw_dir):
    """5. 秘匿による取りこぼし率（内訳合計 ÷ 公表総計）を年度×製品で算出。"""
    print("Computing masking QC...")
    rows = []
    for label, path, keys in [
        ("都道府県版", input_path(raw_dir, "ophthalmic_injection_prefecture.csv"),
         ["年度", "区分", "医薬品コード"]),
        ("年齢性別版", input_path(raw_dir, "ophthalmic_injection_agesex.csv"),
         ["年度", "区分", "医薬品コード"]),
    ]:
        raw = pd.read_csv(path, dtype={"医薬品コード": str})
        g = raw.groupby(keys).agg(
            observed=("処方数量", "sum"),
            reported_total=("総計_処方数量", "first"),
            n_cells=("処方数量", "size"),
            n_masked=("秘匿フラグ", "sum"),
        ).reset_index()
        g["table"] = label
        g["coverage_pct"] = g["observed"] / g["reported_total"] * 100
        g["masked_cell_pct"] = g["n_masked"] / g["n_cells"] * 100
        rows.append(g)
    qc = pd.concat(rows, ignore_index=True)
    qc = qc.rename(columns={"年度": "year", "区分": "setting", "医薬品コード": "drug_code"})
    qc.to_csv(os.path.join(output_dir, "masking_qc_antivegf.csv"),
              index=False, encoding="utf-8-sig")
    return qc
