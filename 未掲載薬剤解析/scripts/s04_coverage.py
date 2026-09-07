# -*- coding: utf-8 -*-
"""s04: 名簿 × NDB掲載 の突合（掲載カバレッジと欠測数量の識別区間）

薬価基準収載品目リスト(分母) と NDBオープンデータ掲載品目(分子) を
薬価基準収載医薬品コード(12桁)で外部結合する。

足切りは「処方数量の上位N位まで掲載」なので、非掲載品目の数量は
掲載された最下位品目の数量で上から押さえられる（打ち切りの向きが既知なため
上限が識別できる）。ただし足切りは **診療区分(入院/外来院内/外来院外)ごと** に
掛かるため、非掲載品目の3区分合計は各区分の最小公表数量の **和** で押さえる:

  0 <= q_unpublished <= Σ_区分 min(その区分・その分類で掲載された銘柄の数量)

3区分を跨いだ単一の最小値を使うと上限が50〜80倍過小になる（入院の最小値は
外来の1〜2桁下のため）。これにより分類合計の識別区間 [下限, 上限] が計算できる。

出力:
  processed/coverage_class.csv   分類×年度のカバレッジと数量区間
  processed/unpublished_items.csv 非掲載品目の一覧（品名つき）
  processed/join_diagnostics.csv  突合の健全性チェック
"""
import os
import pandas as pd

from paths import OUT_DIR

NDB_KINDS = ["注射薬", "外用薬"]


def run():
    roster = pd.read_csv(os.path.join(OUT_DIR, "yakka_roster.csv"), dtype={"yj12": str})
    pub = pd.read_csv(os.path.join(OUT_DIR, "ndb_published.csv"), dtype={"yj12": str})

    roster = roster[roster["kind"].isin(NDB_KINDS)].copy()
    # class3 は両者とも12桁コードから引き直す（CSV往復で型が揺れるため）
    roster["class3"] = roster["yj12"].str[:3]
    pub["class3"] = pub["yj12"].str[:3]

    # 診療区分をまたいで「いずれかに掲載されていれば掲載」とみなす
    pub_any = (pub.groupby(["fiscal_year", "kind", "yj12", "class3"], as_index=False)
                  .agg(total_qty=("total_qty", "sum"),
                       min_brand_qty=("min_brand_qty", "min"),
                       n_settings=("setting", "nunique"),
                       ndb_generic=("is_generic", "max"),
                       product_ndb=("product", "first")))

    # --- 突合の健全性: NDBにあって名簿に無いコード ---
    merged = pub_any.merge(
        roster[["fiscal_year", "kind", "yj12"]].assign(in_roster=1),
        on=["fiscal_year", "kind", "yj12"], how="left")
    diag = (merged.assign(in_roster=merged["in_roster"].fillna(0))
                  .groupby(["fiscal_year", "kind"], as_index=False)
                  .agg(n_ndb=("yj12", "size"), n_matched=("in_roster", "sum")))
    diag["match_rate"] = diag["n_matched"] / diag["n_ndb"]
    diag.to_csv(os.path.join(OUT_DIR, "join_diagnostics.csv"),
                index=False, encoding="utf-8-sig")
    print("[s04] 突合率（NDB掲載コードが名簿に存在する割合）:")
    print(diag.to_string(index=False))

    # --- 分類×年度のカバレッジ ---
    full = roster.merge(pub_any, on=["fiscal_year", "kind", "yj12", "class3"], how="left")
    full["is_published"] = full["total_qty"].notna().astype(int)

    # 足切りは診療区分ごとに銘柄単位の数量順位で行われる。非掲載品目は3区分すべてで
    # 非掲載なので、その3区分合計の上限は各区分の最小公表数量の和になる。
    minq = (pub.groupby(["fiscal_year", "kind", "class3", "setting"], as_index=False)
               .agg(setting_min=("min_brand_qty", "min"))
               .groupby(["fiscal_year", "kind", "class3"], as_index=False)
               .agg(min_published_qty=("setting_min", "sum")))
    tot = (full[full["is_published"] == 1]
           .groupby(["fiscal_year", "kind", "class3"], as_index=False)
           .agg(published_total=("total_qty", "sum")))
    minq = minq.merge(tot, on=["fiscal_year", "kind", "class3"], how="right")

    cov = (full.groupby(["fiscal_year", "kind", "class3"], as_index=False)
               .agg(n_roster=("yj12", "size"),
                    n_published=("is_published", "sum"),
                    n_roster_generic=("is_generic", "sum")))
    gen_pub = (full[full["is_generic"] == 1]
               .groupby(["fiscal_year", "kind", "class3"], as_index=False)
               .agg(n_published_generic=("is_published", "sum")))
    cov = cov.merge(gen_pub, on=["fiscal_year", "kind", "class3"], how="left")
    cov["n_published_generic"] = cov["n_published_generic"].fillna(0).astype(int)
    cov["n_unpublished"] = cov["n_roster"] - cov["n_published"]
    cov["n_unpublished_generic"] = cov["n_roster_generic"] - cov["n_published_generic"]
    cov = cov.merge(minq, on=["fiscal_year", "kind", "class3"], how="left")
    cov["coverage_rate"] = cov["n_published"] / cov["n_roster"]
    cov["coverage_rate_generic"] = cov["n_published_generic"] / cov["n_roster_generic"]
    cov["qty_lower"] = cov["published_total"]
    cov["qty_upper"] = cov["published_total"] + cov["n_unpublished"] * cov["min_published_qty"]
    cov["max_missing_share"] = 1 - cov["qty_lower"] / cov["qty_upper"]
    cov.to_csv(os.path.join(OUT_DIR, "coverage_class.csv"),
               index=False, encoding="utf-8-sig")
    print("\n[s04] coverage_class.csv 出力 (%d行)" % len(cov))

    # --- 非掲載品目の一覧 ---
    unpub = full[full["is_published"] == 0][
        ["fiscal_year", "kind", "class3", "yj12", "ingredient", "product",
         "maker", "senpatsu", "is_generic", "price"]].copy()
    unpub.to_csv(os.path.join(OUT_DIR, "unpublished_items.csv"),
                 index=False, encoding="utf-8-sig")
    print("[s04] unpublished_items.csv 出力 (%d行)" % len(unpub))

    # --- 眼科用剤(131)の要約 ---
    eye = cov[(cov["class3"] == "131") & (cov["kind"] == "外用薬")].sort_values("fiscal_year")
    print("\n[s04] 眼科用剤(131・外用薬) の掲載カバレッジ")
    show = eye[["fiscal_year", "n_roster", "n_published", "n_unpublished", "coverage_rate",
                "n_roster_generic", "n_published_generic", "coverage_rate_generic",
                "max_missing_share"]]
    print(show.to_string(index=False, float_format=lambda v: "%.3f" % v))
    return cov


if __name__ == "__main__":
    run()
