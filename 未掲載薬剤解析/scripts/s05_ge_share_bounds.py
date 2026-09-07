# -*- coding: utf-8 -*-
"""s05: 足切りが後発品シェア(GEシェア)推定に与えるバイアスの識別区間

後発品は品目あたり処方数量が小さいため、上位N位の足切りで系統的に除外される。
その結果、観測されるGEシェアは真値より系統的に小さい（下方バイアス）。

足切りは診療区分(入院/外来院内/外来院外)ごとに掛かり、非掲載品目は3区分すべてで
非掲載である。したがって分類 c・年度 t の1品目あたり数量上限 m は
**各区分の最小公表銘柄数量の和**:

  m = Σ_区分 min(その区分・その分類で掲載された銘柄の数量)

非掲載品目 j の数量は 0<=q_j<=m。成分 g のGEシェアの識別区間は

  下限 = Q_gen / (Q_gen + Q_brand + n_unpub_brand * m)   … 未掲載先発が全て m
  上限 = (Q_gen + n_unpub_gen * m) / (Q_gen + n_unpub_gen * m + Q_brand)
                                                          … 未掲載後発が全て m

出力:
  processed/ge_share_bounds.csv        成分×年度のGEシェアと識別区間
  processed/ge_share_bounds_eye.csv    抗アレルギー点眼薬に絞った表
"""
import os
import pandas as pd

from paths import OUT_DIR

# 既存の allergy解析 が対象としている抗アレルギー点眼薬
ALLERGY_EYE = [
    "オロパタジン", "エピナスチン", "レボカバスチン", "ケトチフェン",
    "トラニラスト", "ペミロラスト", "アシタザノラスト", "クロモグリク酸",
]


def run():
    roster = pd.read_csv(os.path.join(OUT_DIR, "yakka_roster.csv"), dtype={"yj12": str})
    pub = pd.read_csv(os.path.join(OUT_DIR, "ndb_published.csv"), dtype={"yj12": str})
    roster["class3"] = roster["yj12"].str[:3]
    pub["class3"] = pub["yj12"].str[:3]

    pub_any = (pub.groupby(["fiscal_year", "kind", "yj12"], as_index=False)
                  .agg(total_qty=("total_qty", "sum"),
                       min_brand_qty=("min_brand_qty", "min")))

    full = roster.merge(pub_any, on=["fiscal_year", "kind", "yj12"], how="left")
    full["is_published"] = full["total_qty"].notna().astype(int)
    full["qty"] = full["total_qty"].fillna(0.0)

    # 分類×年度の m（各診療区分の最小公表銘柄数量の和）
    m = (pub.groupby(["fiscal_year", "kind", "class3", "setting"], as_index=False)
            .agg(setting_min=("min_brand_qty", "min"))
            .groupby(["fiscal_year", "kind", "class3"], as_index=False)
            .agg(m=("setting_min", "sum")))

    g = (full.groupby(["fiscal_year", "kind", "class3", "ingredient"], as_index=False)
             .apply(lambda d: pd.Series({
                 "n_brand": int((d["is_generic"] == 0).sum()),
                 "n_generic": int((d["is_generic"] == 1).sum()),
                 "n_pub_brand": int(((d["is_generic"] == 0) & (d["is_published"] == 1)).sum()),
                 "n_pub_generic": int(((d["is_generic"] == 1) & (d["is_published"] == 1)).sum()),
                 "q_brand": float(d.loc[d["is_generic"] == 0, "qty"].sum()),
                 "q_generic": float(d.loc[d["is_generic"] == 1, "qty"].sum()),
             }), include_groups=False))

    g = g.merge(m, on=["fiscal_year", "kind", "class3"], how="left")
    g["n_unpub_brand"] = g["n_brand"] - g["n_pub_brand"]
    g["n_unpub_generic"] = g["n_generic"] - g["n_pub_generic"]

    denom = g["q_generic"] + g["q_brand"]
    g["ge_share_obs"] = g["q_generic"] / denom.where(denom > 0)

    up_gen = g["q_generic"] + g["n_unpub_generic"] * g["m"]
    g["ge_share_upper"] = up_gen / (up_gen + g["q_brand"])
    up_brand = g["q_brand"] + g["n_unpub_brand"] * g["m"]
    g["ge_share_lower"] = g["q_generic"] / (g["q_generic"] + up_brand)
    g["bound_width"] = g["ge_share_upper"] - g["ge_share_lower"]

    g.to_csv(os.path.join(OUT_DIR, "ge_share_bounds.csv"),
             index=False, encoding="utf-8-sig")
    print("[s05] ge_share_bounds.csv 出力 (%d行)" % len(g))

    pat = "|".join(ALLERGY_EYE)
    eye = g[(g["class3"] == "131") & (g["kind"] == "外用薬") &
            g["ingredient"].astype(str).str.contains(pat, na=False)].copy()
    eye = eye.sort_values(["ingredient", "fiscal_year"])
    eye.to_csv(os.path.join(OUT_DIR, "ge_share_bounds_eye.csv"),
               index=False, encoding="utf-8-sig")

    print("\n[s05] 抗アレルギー点眼薬の GEシェア識別区間")
    print("  （obs=観測値, [lower,upper]=足切りを考慮した識別区間）")
    for ing, d in eye.groupby("ingredient"):
        if d["n_generic"].max() == 0:
            continue
        print("\n--- %s ---" % ing)
        cols = ["fiscal_year", "n_generic", "n_pub_generic", "n_unpub_generic",
                "ge_share_obs", "ge_share_lower", "ge_share_upper"]
        print(d[cols].to_string(index=False, na_rep="-",
                                float_format=lambda v: "%.4f" % v))
    return g


if __name__ == "__main__":
    run()
