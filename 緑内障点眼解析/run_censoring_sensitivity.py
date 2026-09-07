# -*- coding: utf-8 -*-
"""秘匿セルの感度分析（識別区間の下限・上限）

NDBオープンデータの外用薬（処方薬）では、処方数量1,000未満のセルが「-」で秘匿される。
秘匿セルの真値は区間 [0, 1000) にあるため、

    zero  補完 (0)   → 全指標の下限
    upper 補完 (999) → 全指標の上限

の両方で前処理をやり直すと、公表値のみから到達可能な**識別区間**が得られる。
主解析（zero）の結論がこの区間の中で変わらないことを確認するのが本スクリプトの目的。

    python 緑内障点眼解析/run_censoring_sensitivity.py

出力（一次出力先 processed*/ 配下）:
    censoring_sensitivity_glaucoma.csv        薬効群・薬剤別の zero / upper 比較
    censoring_sensitivity_prefecture.csv      都道府県ランキングの頑健性
    censoring_sensitivity_report.txt          人間可読な要約
"""

import argparse
import os
import sys
import tempfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))

from analysis_glaucoma import calculate_gini  # noqa: E402
from preprocess_glaucoma import (GROUP_DEFS, TOTAL_CODES,  # noqa: E402
                                 preprocess_glaucoma)
from paths import (COVARIATE_PATH, RAW_DIR, add_nokouhi_arg,  # noqa: E402
                   output_dir)

FULL_COV_START = 2022
GROUP_CODES = [c for c, _, _ in GROUP_DEFS]
TARGET_CODES = ["GLAUCOMA_EYE_TOTAL"] + GROUP_CODES + sorted(TOTAL_CODES)


def _load(strategy, nokouhi, tmp_dir):
    """指定した補完戦略で前処理をやり直して読み込む。"""
    print(f"  前処理中（--imputation {strategy}）...")
    return preprocess_glaucoma(
        raw_dir=RAW_DIR, covariate_path=COVARIATE_PATH,
        output_dir=tmp_dir, imputation_strategy=strategy, nokouhi=nokouhi)


def _metrics(df, year):
    """年度を指定して、カテゴリごとの全国量・人口10万対・シェア・CV・ジニを返す。"""
    d = df[df["year"] == year]
    total = d[d["code"] == "GLAUCOMA_EYE_TOTAL"]["count_ml"].sum()
    rows = []
    for code in TARGET_CODES:
        g = d[d["code"] == code]
        if g.empty:
            continue
        rates = g["count_per_100k"].values
        ml = float(g["count_ml"].sum())
        pop = float(g["population_total"].sum())
        mean_rate = float(np.mean(rates))
        rows.append({
            "year": year, "code": code,
            "procedure_name": g["procedure_name"].iloc[0],
            "count_ml": ml,
            "count_per_100k": ml / pop * 100000 if pop else np.nan,
            "share": ml / total if total else np.nan,
            "cv": float(np.std(rates, ddof=1) / mean_rate) if mean_rate > 0 else np.nan,
            "gini": calculate_gini(rates) if mean_rate > 0 else np.nan,
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="*", default=None,
                    help="評価する年度（既定: 2022〜2024＝フルカバレッジ期間）")
    add_nokouhi_arg(ap)
    args = ap.parse_args()
    out_dir = output_dir(args.nokouhi)

    print("秘匿セルの感度分析（zero = 識別区間の下限 / upper = 上限）")
    with tempfile.TemporaryDirectory() as tmp:
        lo = _load("zero", args.nokouhi, tmp)
        hi = _load("upper", args.nokouhi, tmp)

    years = args.years or sorted(y for y in lo["year"].unique()
                                 if y >= FULL_COV_START)

    # ── 1. カテゴリ別の指標比較 ──
    frames = []
    for y in years:
        a = _metrics(lo, y).set_index(["year", "code", "procedure_name"])
        b = _metrics(hi, y).set_index(["year", "code", "procedure_name"])
        m = a.join(b, lsuffix="_zero", rsuffix="_upper").reset_index()
        frames.append(m)
    comp = pd.concat(frames, ignore_index=True)

    for col in ["count_ml", "count_per_100k", "share", "cv", "gini"]:
        comp[f"{col}_diff"] = comp[f"{col}_upper"] - comp[f"{col}_zero"]
        comp[f"{col}_rel_diff_pct"] = np.where(
            comp[f"{col}_zero"].abs() > 0,
            comp[f"{col}_diff"] / comp[f"{col}_zero"] * 100, np.nan)
    order = {c: i for i, c in enumerate(TARGET_CODES)}
    comp["_o"] = comp["code"].map(order)
    comp = comp.sort_values(["year", "_o"]).drop(columns="_o")
    comp.to_csv(os.path.join(out_dir, "censoring_sensitivity_glaucoma.csv"),
                index=False, encoding="utf-8-sig")

    # ── 2. 都道府県ランキングの頑健性 ──
    pref_rows = []
    for y in years:
        for code in ["GLAUCOMA_EYE_TOTAL"] + GROUP_CODES:
            a = lo[(lo["year"] == y) & (lo["code"] == code)][
                ["prefecture", "count_per_100k"]].set_index("prefecture")
            b = hi[(hi["year"] == y) & (hi["code"] == code)][
                ["prefecture", "count_per_100k"]].set_index("prefecture")
            if a.empty or b.empty:
                continue
            j = a.join(b, lsuffix="_zero", rsuffix="_upper").dropna()
            if len(j) < 10 or j["count_per_100k_zero"].std() == 0:
                continue
            rho, p = spearmanr(j["count_per_100k_zero"], j["count_per_100k_upper"])
            rank_z = j["count_per_100k_zero"].rank(ascending=False)
            rank_u = j["count_per_100k_upper"].rank(ascending=False)
            pref_rows.append({
                "year": y, "code": code,
                "spearman_rho": rho, "p_value": p,
                "max_rank_change": int((rank_z - rank_u).abs().max()),
                "n_prefectures_rank_changed": int((rank_z != rank_u).sum()),
                "top1_zero": rank_z.idxmin(), "top1_upper": rank_u.idxmin(),
                "bottom1_zero": rank_z.idxmax(), "bottom1_upper": rank_u.idxmax(),
            })
    pref = pd.DataFrame(pref_rows)
    pref.to_csv(os.path.join(out_dir, "censoring_sensitivity_prefecture.csv"),
                index=False, encoding="utf-8-sig")

    # ── 3. 要約テキスト ──
    path = os.path.join(out_dir, "censoring_sensitivity_report.txt")
    latest = max(years)
    with open(path, "w", encoding="utf-8") as f:
        f.write("=" * 78 + "\n")
        f.write(" NDB緑内障点眼薬 秘匿セルの感度分析\n")
        f.write(" zero = 0補完（識別区間の下限） / upper = 999補完（上限）\n")
        f.write(f" 評価年度: {', '.join(str(y) for y in years)}\n")
        f.write("=" * 78 + "\n\n")

        f.write(f"1. {latest}年度の処方数量・シェアの識別区間\n")
        f.write("-" * 78 + "\n")
        d = comp[comp["year"] == latest]
        t = d[["procedure_name", "count_per_100k_zero", "count_per_100k_upper",
               "count_per_100k_rel_diff_pct", "share_zero", "share_upper"]].copy()
        t.columns = ["薬剤・薬効群", "人口10万対_zero", "人口10万対_upper",
                     "相対差(%)", "シェア_zero", "シェア_upper"]
        t["人口10万対_zero"] = t["人口10万対_zero"].round(0)
        t["人口10万対_upper"] = t["人口10万対_upper"].round(0)
        t["相対差(%)"] = t["相対差(%)"].round(2)
        t["シェア_zero"] = (t["シェア_zero"] * 100).round(2)
        t["シェア_upper"] = (t["シェア_upper"] * 100).round(2)
        f.write(t.to_string(index=False) + "\n\n")

        worst = d.loc[d["count_per_100k_rel_diff_pct"].idxmax()]
        f.write(f" 最大の相対差: {worst['procedure_name']} "
                f"{worst['count_per_100k_rel_diff_pct']:.2f}%\n")
        tot = d[d["code"] == "GLAUCOMA_EYE_TOTAL"].iloc[0]
        f.write(f" 全体合計の相対差: {tot['count_per_100k_rel_diff_pct']:.2f}%"
                f"（{tot['count_per_100k_zero']:,.0f} 〜 "
                f"{tot['count_per_100k_upper']:,.0f} mL/10万人）\n\n")

        f.write("2. シェアの順位は入れ替わるか\n")
        f.write("-" * 78 + "\n")
        g = d[d["code"].isin(GROUP_CODES)].copy()
        g["rank_zero"] = g["share_zero"].rank(ascending=False)
        g["rank_upper"] = g["share_upper"].rank(ascending=False)
        swapped = g[g["rank_zero"] != g["rank_upper"]]
        if swapped.empty:
            f.write(" → 薬効群のシェア順位は zero / upper で完全に一致した。\n\n")
        else:
            f.write(" ★順位が入れ替わった薬効群:\n")
            for _, r in swapped.iterrows():
                f.write(f"   {r['procedure_name']}: "
                        f"{int(r['rank_zero'])}位 → {int(r['rank_upper'])}位\n")
            f.write("\n")

        f.write("3. 都道府県ランキングの頑健性\n")
        f.write("-" * 78 + "\n")
        if pref.empty:
            f.write(" 評価できる系列がなかった。\n")
        else:
            p = pref[pref["year"] == latest][
                ["code", "spearman_rho", "max_rank_change",
                 "n_prefectures_rank_changed", "top1_zero", "top1_upper",
                 "bottom1_zero", "bottom1_upper"]].copy()
            p["spearman_rho"] = p["spearman_rho"].round(4)
            f.write(p.to_string(index=False) + "\n\n")
            f.write(f" 最小のSpearman ρ: {pref['spearman_rho'].min():.4f}\n")
            f.write(f" 最大の順位変動: {int(pref['max_rank_change'].max())} 位\n\n")

        f.write("4. 結論（自動判定）\n")
        f.write("-" * 78 + "\n")
        gg = d[d["code"].isin(GROUP_CODES)]
        robust = gg[gg["count_per_100k_rel_diff_pct"] < 5]["procedure_name"].tolist()
        fragile = gg[gg["count_per_100k_rel_diff_pct"] >= 20]["procedure_name"].tolist()
        f.write(f" 全体合計の識別区間幅: {tot['count_per_100k_rel_diff_pct']:.2f}%\n")
        f.write(f" 区間幅5%未満（頑健）の薬効群: {'、'.join(robust) or 'なし'}\n")
        f.write(f" 区間幅20%以上（要注意）の薬効群: {'、'.join(fragile) or 'なし'}\n")
        top2_z = gg.nlargest(2, "share_zero")["procedure_name"].tolist()
        top2_u = gg.nlargest(2, "share_upper")["procedure_name"].tolist()
        f.write(f" 上位2群の順位: zero={top2_z} / upper={top2_u}"
                f" → {'不変' if top2_z == top2_u else '★入れ替わり'}\n")
        if not pref.empty:
            pl = pref[pref["year"] == latest]
            weak = pl[pl["spearman_rho"] < 0.9]["code"].tolist()
            f.write(f" 都道府県順位のSpearman ρ が0.9未満の系列: "
                    f"{'、'.join(weak) or 'なし'}\n")
        f.write("\n 秘匿されるのは処方数量1,000未満のセルであるため、処方量の多い薬効群では\n")
        f.write(" 補完戦略を下限から上限へ振っても指標はほとんど動かない。一方、少量の薬効群は\n")
        f.write(" 秘匿セルの比率が高く区間が広いため、絶対値・順位ともに慎重な扱いを要する。\n")
        f.write(" 論文で少量薬剤の値を示す際は本表の識別区間を併記すること。\n")

    print(f"\nwrote {os.path.join(out_dir, 'censoring_sensitivity_glaucoma.csv')}")
    print(f"wrote {os.path.join(out_dir, 'censoring_sensitivity_prefecture.csv')}")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
