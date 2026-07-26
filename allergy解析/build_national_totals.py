# -*- coding: utf-8 -*-
"""
NDBオープンデータの「総計（処方数量）」列から全国集計を構築する。

背景:
  従来の全国集計値は都道府県別の内訳セルを合計したものであり、
  処方数量1,000未満の秘匿セルがゼロ補完されるため過小評価となる。
  NDBは秘匿されない「総計」列を同一シートに公表しているため、
  全国レベルの数量はこちらを用いる方が正確である。
  都道府県別・年齢別の内訳は引き続き内訳セルを用いる（総計列は分割不能なため）。

出力:
  processed/national_totals_published.csv
      year, code, procedure_name, count_published, count_detail, censoring_loss,
      censoring_loss_pct
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))
from preprocess_allergy import (  # noqa: E402
    ANTI_HIST_CODES, IMMUNO_CODES, MED_RELEASE_CODES, classify_drug)

RAW = os.path.join(BASE, "..", "data", "raw")
OUT = os.path.join(BASE, "processed")


def load_year(year, path):
    """1年分の全シートから、薬剤別の総計列合計と内訳セル合計を返す。"""
    xl = pd.ExcelFile(path)
    rows = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        row2 = [str(x) for x in df.iloc[2]]
        total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
        if total_col is None:
            continue
        df[0] = df[0].ffill()
        pref_cols = list(range(total_col + 1, min(total_col + 48, df.shape[1])))

        for r in range(4, len(df)):
            if str(df.iloc[r, 0]).strip() != "131":
                continue
            name = str(df.iloc[r, 3]).strip()
            if "点眼" not in name:
                continue
            hit = classify_drug(name)
            if hit is None:
                continue
            code, cname = hit
            tot = pd.to_numeric(df.iloc[r, total_col], errors="coerce")
            cells = pd.to_numeric(df.iloc[r, pref_cols], errors="coerce")
            rows.append({
                "year": year, "code": code, "procedure_name": cname,
                "total": float(tot) if pd.notna(tot) else np.nan,
                "detail": float(np.nansum(cells.values)),
                "total_masked": int(pd.isna(tot)),
            })
    return rows


def main():
    files = {}
    for p in glob.glob(os.path.join(RAW, "ndb_gaiyo_*.xlsx")):
        m = os.path.basename(p).replace("ndb_gaiyo_", "").replace(".xlsx", "")
        if m.isdigit():
            files[int(m)] = p

    rec = []
    for year in sorted(files):
        print(f"Processing {year} ...")
        rec.extend(load_year(year, files[year]))
    df = pd.DataFrame(rec)

    masked = df["total_masked"].sum()
    if masked:
        print(f"  警告: 総計列が秘匿されている品目行が {masked} 件あります")

    g = (df.groupby(["year", "code", "procedure_name"], as_index=False)
           .agg(count_published=("total", "sum"), count_detail=("detail", "sum")))

    # 小計・合計行を追加
    extra = []
    for (year,), sub in g.groupby(["year"]):
        for label, codes in [("ANTI_HIST", ANTI_HIST_CODES),
                             ("MED_RELEASE", MED_RELEASE_CODES),
                             ("IMMUNO", IMMUNO_CODES),
                             ("ALLERGY_EYE_TOTAL", None)]:
            s = sub if codes is None else sub[sub.code.isin(codes)]
            if s.empty:
                continue
            nm = {"ANTI_HIST": "抗ヒスタミン点眼薬（合計）",
                  "MED_RELEASE": "メディエーター遊離抑制点眼薬（合計）",
                  "IMMUNO": "免疫抑制点眼薬（合計）",
                  "ALLERGY_EYE_TOTAL": "抗アレルギー点眼薬（全体合計）"}[label]
            extra.append({"year": year, "code": label, "procedure_name": nm,
                          "count_published": s["count_published"].sum(),
                          "count_detail": s["count_detail"].sum()})
    g = pd.concat([g, pd.DataFrame(extra)], ignore_index=True)

    g["censoring_loss"] = g["count_published"] - g["count_detail"]
    g["censoring_loss_pct"] = g["censoring_loss"] / g["count_published"] * 100
    g = g.sort_values(["year", "code"]).round(3)

    path = os.path.join(OUT, "national_totals_published.csv")
    g.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nsaved: {path}  ({len(g)} rows)")

    print("\n=== 全体合計: 公表総計 vs 内訳セル合計 ===")
    t = g[g.code == "ALLERGY_EYE_TOTAL"].set_index("year")
    print(f"  {'年度':>6s} {'公表総計':>16s} {'内訳セル合計':>16s} {'秘匿欠落':>12s} {'欠落率':>8s}")
    for y, r in t.iterrows():
        print(f"  {y:>6d} {r['count_published']:>16,.0f} {r['count_detail']:>16,.0f} "
              f"{r['censoring_loss']:>12,.0f} {r['censoring_loss_pct']:>7.3f}%")


if __name__ == "__main__":
    main()
