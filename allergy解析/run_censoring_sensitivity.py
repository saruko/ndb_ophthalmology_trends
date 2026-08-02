# -*- coding: utf-8 -*-
"""
秘匿セルの感度分析（識別区間の下限・上限）

NDBオープンデータの外用薬（処方薬）では、数量1,000未満のセルが「-」で秘匿される。
この閾値は生データ検証により全年度・全シート共通であることを確認済み
（薬効分類131の点眼液全品目で非秘匿セルの最小値は全11年度とも1,000ちょうど。
  検証は verify_methods_claims.py の C3 を参照）。

したがって秘匿セルの真値は区間 [0, 1000) にあり、
  zero  補完 → 全指標の下限
  upper 補完 (999) → 全指標の上限
として、公表値のみから到達可能な識別区間を与える。

出力: processed/censoring_sensitivity_allergy.csv
      processed/censoring_sensitivity_report.txt
"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))
from preprocess_allergy import preprocess_allergy  # noqa: E402

from paths import (COVARIATE_PATH, RAW_DIR,  # noqa: E402
                   nokouhi_from_argv, output_dir)

NOKOUHI = nokouhi_from_argv()
RAW = RAW_DIR
COV = COVARIATE_PATH
OUT = output_dir(NOKOUHI)

MAIN_CODES = ["ALLERGY_EYE_TOTAL", "ANTI_HIST", "MED_RELEASE", "IMMUNO",
              "EPINASTINE", "OLOPATADINE", "LEVOCASTINE", "TOP3_TOTAL"]

# 本文の経年比較・都道府県間比較で用いる主要3成分（全期間で収録が保証される）
TOP3_CODES = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]


def add_top3(df):
    """主要3成分の合計を TOP3_TOTAL として追加する。

    本文の地域格差（最大/最小比 3.087倍）は3成分合計に基づくため、
    感度分析でも同じ集計単位を評価できるようにする。
    """
    t3 = (df[df.code.isin(TOP3_CODES)]
          .groupby(["year", "prefecture"], as_index=False)
          .agg(count=("count", "sum"),
               population_total=("population_total", "first")))
    t3["code"] = "TOP3_TOTAL"
    return pd.concat([df, t3], ignore_index=True)


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return np.nan
    cum = np.cumsum(x)
    return (n + 1 - 2 * (cum / cum[-1]).sum()) / n


def summarise(df):
    """年度×薬剤の全国数量・人口10万対、および2024年の都道府県格差指標"""
    nat = (df.groupby(["year", "code"], as_index=False)
             .agg(count=("count", "sum"), population=("population_total", "sum")))
    nat["per100k"] = nat["count"] / nat["population"] * 1e5

    d24 = df[df.year == 2024]
    rows = []
    for code, g in d24.groupby("code"):
        r = g["count"] / g["population_total"] * 1e5
        rows.append({"code": code, "gini": gini(r), "cv": r.std(ddof=1) / r.mean(),
                     "max_to_min": r.max() / r.min() if r.min() > 0 else np.nan})
    return nat, pd.DataFrame(rows)


def main():
    res = {}
    for strategy in ["zero", "upper"]:
        with tempfile.TemporaryDirectory() as tmp:
            df = preprocess_allergy(raw_dir=RAW, covariate_path=COV, nokouhi=NOKOUHI,
                                    output_dir=tmp, imputation_strategy=strategy)
        res[strategy] = summarise(add_top3(df))

    # ── 全国数量・人口10万対の識別区間 ──
    lo, hi = res["zero"][0], res["upper"][0]
    nat = lo.merge(hi, on=["year", "code"], suffixes=("_lower", "_upper"))
    nat = nat[nat.code.isin(MAIN_CODES)].copy()
    nat["count_width_pct"] = (nat["count_upper"] - nat["count_lower"]) / nat["count_lower"] * 100
    nat["per100k_width_pct"] = (nat["per100k_upper"] - nat["per100k_lower"]) / nat["per100k_lower"] * 100
    nat = nat[["year", "code", "count_lower", "count_upper", "count_width_pct",
               "per100k_lower", "per100k_upper", "per100k_width_pct"]]
    nat.round(3).to_csv(os.path.join(OUT, "censoring_sensitivity_allergy.csv"),
                        index=False, encoding="utf-8-sig")

    # ── 2024年 地域格差指標の識別区間 ──
    dl, dh = res["zero"][1], res["upper"][1]
    disp = dl.merge(dh, on="code", suffixes=("_zero", "_upper"))
    disp = disp[disp.code.isin(MAIN_CODES)]
    disp.round(3).to_csv(os.path.join(OUT, "censoring_sensitivity_disparity.csv"),
                         index=False, encoding="utf-8-sig")

    lines = []
    lines.append("秘匿セル感度分析（識別区間）")
    lines.append("=" * 64)
    lines.append("秘匿閾値: 数量1,000未満（全年度・全シート共通、生データ検証済み）")
    lines.append("下限 = 秘匿セルに0を充当 / 上限 = 999を充当")
    lines.append("")
    lines.append("■ 全国処方数量の識別区間（主要年度）")
    for y in [2014, 2016, 2017, 2024]:
        d = nat[(nat.year == y) & (nat.code == "ALLERGY_EYE_TOTAL")]
        if len(d):
            r = d.iloc[0]
            lines.append(f"  {y}: {r['count_lower']:>15,.0f} 〜 {r['count_upper']:>15,.0f} mL "
                         f"(幅 +{r['count_width_pct']:.3f}%)")
    lines.append("")
    lines.append("■ 主要薬剤の2024年度 人口10万対処方数量")
    for c in MAIN_CODES:
        d = nat[(nat.year == 2024) & (nat.code == c)]
        if len(d):
            r = d.iloc[0]
            lines.append(f"  {c:18s} {r['per100k_lower']:>10,.0f} 〜 {r['per100k_upper']:>10,.0f} "
                         f"(幅 +{r['per100k_width_pct']:.3f}%)")
    lines.append("")
    lines.append("■ 2024年度 地域格差指標の識別区間")
    lines.append("  （格差指標は補完値に対して単調でないため、0充当と999充当の min〜max を区間とする。")
    lines.append("   いずれも999充当side が小さく、0充当は格差を過大に見積もる方向に働く）")
    for _, r in disp.iterrows():
        g = sorted([r["gini_zero"], r["gini_upper"]])
        c = sorted([r["cv_zero"], r["cv_upper"]])
        mz, mu = r["max_to_min_zero"], r["max_to_min_upper"]
        mm = (f"max/min {mz:.3f}→{mu:.3f}" if pd.notna(mz)
              else f"max/min 算出不能→{mu:.3f}")
        lines.append(f"  {r['code']:18s} Gini {g[0]:.3f}〜{g[1]:.3f} (0充当={r['gini_zero']:.3f})  "
                     f"CV {c[0]:.3f}〜{c[1]:.3f} (0充当={r['cv_zero']:.3f})  {mm}")
    lines.append("")
    lines.append("■ 全年度・全薬剤での最大区間幅")
    lines.append(f"  処方数量: +{nat['count_width_pct'].max():.3f}% "
                 f"({nat.loc[nat['count_width_pct'].idxmax(), 'code']}, "
                 f"{int(nat.loc[nat['count_width_pct'].idxmax(), 'year'])}年度)")

    txt = "\n".join(lines)
    with open(os.path.join(OUT, "censoring_sensitivity_report.txt"), "w",
              encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
