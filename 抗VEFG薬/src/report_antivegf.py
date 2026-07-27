"""解析結果のテキストレポートを生成する。"""

import os
import pandas as pd


def _fmt(x, digits=1):
    if pd.isna(x):
        return "n/a"
    return f"{x:,.{digits}f}"


def generate_report(processed_dir, strategy, sensitivity=None):
    out = []
    w = out.append
    w("=" * 60)
    w(" NDB 抗VEGF薬（硝子体注射液）解析 サマリーレポート")
    w(f" 秘匿値の補完戦略: {strategy}")
    w("=" * 60)

    nat = pd.read_csv(os.path.join(processed_dir, "national_trends_antivegf.csv"))
    prod = pd.read_csv(os.path.join(processed_dir, "product_trends_antivegf.csv"))
    apc = pd.read_csv(os.path.join(processed_dir, "national_apc_antivegf.csv"))
    disp = pd.read_csv(os.path.join(processed_dir, "geographic_disparity_antivegf.csv"))
    form = pd.read_csv(os.path.join(processed_dir, "formulation_total_antivegf.csv"))
    fm = pd.read_csv(os.path.join(processed_dir, "formulation_by_molecule_antivegf.csv"))
    bs = pd.read_csv(os.path.join(processed_dir, "biosimilar_national_share.csv"))
    ages = pd.read_csv(os.path.join(processed_dir, "agesex_summary_antivegf.csv"))
    reg = pd.read_csv(os.path.join(processed_dir, "panel_regression_summary_antivegf.csv"))
    qc = pd.read_csv(os.path.join(processed_dir, "masking_qc_antivegf.csv"))
    y_last = int(nat["year"].max())

    w("")
    w(f"1. 全国処方数量トレンド（{y_last}年度時点）")
    w("-" * 60)
    last = nat[nat["year"] == y_last].sort_values("quantity", ascending=False)
    for _, r in last.iterrows():
        if r["quantity"] <= 0:
            continue
        w(f" - {r['name']} ({r['code']}):")
        w(f"   * 全国処方数量  : {_fmt(r['quantity'], 0)} 本")
        w(f"   * 人口10万対   : {_fmt(r['count_per_100k'], 1)}")
        w(f"   * 65歳以上10万対: {_fmt(r['count_per_100k_65plus'], 1)}")
        w(f"   * 抗VEGF全体シェア: {_fmt(r['share_of_antivegf_pct'], 1)} %")

    w("")
    w("2. 年平均変化率（APC・人口10万対ベース）")
    w("-" * 60)
    for _, r in apc.sort_values("apc", ascending=False).iterrows():
        sig = "*有意" if r["p_value"] < 0.05 else "有意差なし"
        w(f" - {r['name']} ({int(r['start_year'])}～{int(r['end_year'])}年度, "
          f"n={int(r['n_years'])}):")
        w(f"   * APC: {_fmt(r['apc'], 2)}% "
          f"(95%CI: {_fmt(r['apc_low'], 2)}% ~ {_fmt(r['apc_high'], 2)}%) ({sig})")
        w(f"   * p={r['p_value']:.4f} | R2={r['r2']:.4f}")

    w("")
    w(f"3. 製品別 処方数量・薬価・薬剤費（{y_last}年度）")
    w("-" * 60)
    pl = prod[prod["year"] == y_last].sort_values("quantity", ascending=False)
    w(f"   {'製品':<28}{'数量':>12}{'シェア%':>9}{'薬価(円)':>11}{'薬剤費(億円)':>13}")
    for _, r in pl.iterrows():
        w(f"   {r['product_name']:<28}{_fmt(r['quantity'], 0):>12}"
          f"{_fmt(r['share_pct'], 1):>9}{_fmt(r['price'], 0):>11}"
          f"{_fmt(r['cost'] / 1e8, 1):>13}")
    w(f"   {'合計':<28}{_fmt(pl['quantity'].sum(), 0):>12}{'100.0':>9}{'':>11}"
      f"{_fmt(pl['cost'].sum() / 1e8, 1):>13}")

    w("")
    w("4. 剤形（注射液 vs キット）")
    w("-" * 60)
    for y in sorted(form["year"].unique()):
        g = form[form["year"] == y]
        parts = " / ".join(f"{r['formulation']}: {_fmt(r['share_pct'], 1)}%"
                           for _, r in g.iterrows())
        w(f" - {y}年度: {parts}")
    w("")
    w(" 【両剤形が併存する成分のキット比率】")
    kit = fm[(fm["has_both_formulations"]) & (fm["formulation"] == "キット")]
    for mol, g in kit.groupby("molecule_name"):
        g = g.sort_values("year")
        first = g[g["share_within_molecule_pct"].notna()].head(1)
        last_ = g[g["share_within_molecule_pct"].notna()].tail(1)
        if first.empty:
            continue
        w(f" - {mol}: {int(first['year'].iloc[0])}年度 "
          f"{_fmt(first['share_within_molecule_pct'].iloc[0], 1)}% → "
          f"{int(last_['year'].iloc[0])}年度 "
          f"{_fmt(last_['share_within_molecule_pct'].iloc[0], 1)}%")

    w("")
    w("5. 先発品 vs バイオシミラー（ラニビズマブ）")
    w("-" * 60)
    for y in sorted(bs["year"].unique()):
        g = bs[bs["year"] == y]
        if g["quantity"].sum() == 0:
            continue
        parts = " / ".join(f"{r['brand_type']}: {_fmt(r['quantity'], 0)}本 "
                           f"({_fmt(r['share_pct'], 1)}%)" for _, r in g.iterrows())
        w(f" - {y}年度: {parts}")
    cost_impact = pd.read_csv(os.path.join(processed_dir, "biosimilar_cost_impact.csv"))
    if "薬剤費削減額(円)" in cost_impact:
        tot = cost_impact["薬剤費削減額(円)"].sum()
        w(f" - BS置換による累積薬剤費差（先発薬価換算との差）: {_fmt(tot / 1e8, 1)} 億円")

    w("")
    w("6. 年齢・性別")
    w("-" * 60)
    for _, r in ages.iterrows():
        w(f" - {int(r['year'])}年度: 平均年齢(近似) {_fmt(r['mean_age_approx'], 1)}歳 / "
          f"75歳以上 {_fmt(r['share_75plus_pct'], 1)}% / "
          f"男性 {_fmt(r['male_share_pct'], 1)}%")

    w("")
    w(f"7. 地域格差（{y_last}年度）")
    w("-" * 60)
    dl = disp[disp["year"] == y_last].sort_values("gini", ascending=False)
    for _, r in dl.iterrows():
        w(f" - {r['name']}: Gini={_fmt(r['gini'], 3)} / CV={_fmt(r['cv'], 3)} / "
          f"最大最小比={_fmt(r['max_to_min_ratio'], 2)} / "
          f"P90/P10={_fmt(r['p90_to_p10_ratio'], 2)} / "
          f"0件の県={int(r['n_zero_prefectures'])}")
        w(f"   * 最多: {r['max_prefecture']} ({_fmt(r['max_rate'], 1)}) / "
          f"最少: {r['min_prefecture']} ({_fmt(r['min_rate'], 1)})")

    w("")
    w("8. パネル回帰（Two-way FE, 都道府県クラスターSE）")
    w("-" * 60)
    for code, g in reg.groupby("code"):
        w(f" - {g['name'].iloc[0]} (within R2={g['r2_within'].iloc[0]:.4f}, "
          f"n={int(g['n_obs'].iloc[0])}):")
        for _, r in g.iterrows():
            sig = "*" if r["p_value"] < 0.05 else " "
            w(f"   {sig} {r['variable']:<22} coef={_fmt(r['coefficient'], 3):>12} "
              f"(p={r['p_value']:.4f})")

    w("")
    w("9. 秘匿によるデータ欠損（QC）")
    w("-" * 60)
    for table, g in qc.groupby("table"):
        gy = g.groupby("year").apply(
            lambda x: pd.Series({
                "coverage": x["observed"].sum() / x["reported_total"].sum() * 100,
                "masked": x["n_masked"].sum() / x["n_cells"].sum() * 100}),
            include_groups=False)
        w(f" 【{table}】")
        for y, r in gy.iterrows():
            w(f" - {y}年度: 公表総計に対する内訳合計の捕捉率 {_fmt(r['coverage'], 1)}% / "
              f"秘匿セル率 {_fmt(r['masked'], 1)}%")

    if sensitivity is not None and not sensitivity.empty:
        w("")
        w("10. 感度分析（補完戦略による頑健性）")
        w("-" * 60)
        for _, r in sensitivity.iterrows():
            w(f" - {r['code']} {int(r['year'])}年度: "
              f"Gini zero={_fmt(r['gini_zero'], 3)} / five={_fmt(r['gini_five'], 3)} / "
              f"random={_fmt(r['gini_random'], 3)} | "
              f"順位相関(zero vs five)={_fmt(r['rank_corr_zero_five'], 3)} / "
              f"(zero vs random)={_fmt(r['rank_corr_zero_random'], 3)}")

    text = "\n".join(out)
    path = os.path.join(processed_dir, f"antivegf_summary_report_{strategy}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  saved {os.path.basename(path)}")
    return text
