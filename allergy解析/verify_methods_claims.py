# -*- coding: utf-8 -*-
"""
論文 Methods の生データ由来の主張を再検証する。

検証する主張:
  C1. 年齢・性別内訳のブロック単位秘匿（2016・2017年度）
      「エピナスチン点眼液の外来（院外）における年齢・性別内訳が42セルすべて秘匿された」
      「同一薬剤の外来院内シートの秘匿率は4.8%にとどまる」
  C2. 年齢・性別データの捕捉率（各薬剤の公表総計に対する年齢別内訳合計の比）
      2016年度 エピナスチン18.4% / レボカバスチン54.0% / オロパタジン80.6%
      2017年度 エピナスチン17.5% / レボカバスチン57.4% / オロパタジン81.1%
  C3. 最小集計単位の秘匿閾値
      「薬効分類131の点眼液全品目で非秘匿セルの最小値は全年度1,000ちょうど、
        1,000未満は全シートで1件も存在しない」
  C4. 総計列自体が秘匿されている品目行が全期間で182件

出力:
  processed/methods_claims_verification.csv  （検証結果の一覧）
  標準出力に主張との突合結果
"""
import json
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))
from preprocess_allergy import classify_drug  # noqa: E402

RAW = os.path.join(BASE, "..", "data", "raw")
RAWAS = os.path.join(RAW, "ndb_age_sex")
PROCESSED = os.path.join(BASE, "processed")
YEARS = list(range(2014, 2025))

# 論文に記載されている値
CLAIM_CENSOR_PCT = {  # (year, sheet_keyword) -> 秘匿率(%)
    (2016, "院外"): 100.0, (2016, "院内"): 4.8,
    (2017, "院外"): 100.0, (2017, "院内"): 4.8,
}
CLAIM_CAPTURE = {  # (year, code) -> 捕捉率(%)
    (2015, "EPINASTINE"): 100.0, (2015, "LEVOCASTINE"): 99.9, (2015, "OLOPATADINE"): 100.0,
    (2016, "EPINASTINE"): 18.4, (2016, "LEVOCASTINE"): 54.0, (2016, "OLOPATADINE"): 80.6,
    (2017, "EPINASTINE"): 17.5, (2017, "LEVOCASTINE"): 57.4, (2017, "OLOPATADINE"): 81.1,
    (2018, "EPINASTINE"): 100.0, (2018, "LEVOCASTINE"): 99.9, (2018, "OLOPATADINE"): 100.0,
}
CLAIM_MASKED_TOTAL_ROWS = 182


def age_cols(df):
    """「歳」を含むラベル行を探し、その列インデックス（=年齢×性別セル）を返す。"""
    best, bestn = [], 0
    for r in range(min(6, len(df))):
        idx = [c for c in range(df.shape[1]) if "歳" in str(df.iloc[r, c])]
        if len(idx) > bestn:
            best, bestn = idx, len(idx)
    return best


def iter_eyedrop_rows(df, target_only=True):
    """薬効分類131かつ品目名に「点眼」を含む行を返す。"""
    df[0] = df[0].ffill()
    for r in range(len(df)):
        if str(df.iloc[r, 0]).strip() != "131":
            continue
        name = str(df.iloc[r, 3]).strip()
        if "点眼" not in name:
            continue
        hit = classify_drug(name)
        if target_only and hit is None:
            continue
        yield r, name, hit


def check_c1_c3():
    """年齢性別ファイルを走査して C1（秘匿率）と C3（最小値）を求める。"""
    censor_rows, min_rows = [], []
    for year in YEARS:
        path = os.path.join(RAWAS, f"ndb_gaiyo_agesex_{year}.xlsx")
        if not os.path.exists(path):
            continue
        xl = pd.ExcelFile(path)
        y_min_target = y_min_all = None
        y_below = 0
        for sheet in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
            acs = age_cols(df)
            if not acs:
                continue
            # --- C1: エピナスチンのシート別秘匿率 ---
            cells = masked = nrow = 0
            for r, _, hit in iter_eyedrop_rows(df.copy(), target_only=True):
                if hit[0] != "EPINASTINE":
                    continue
                nrow += 1
                v = pd.to_numeric(df.iloc[r, acs], errors="coerce")
                cells += len(acs)
                masked += int(v.isna().sum())
            if nrow:
                censor_rows.append({
                    "year": year, "sheet": sheet, "drug": "EPINASTINE",
                    "n_rows": nrow, "n_age_cols": len(acs), "cells": cells,
                    "masked": masked, "masked_pct": round(masked / cells * 100, 1),
                })
            # --- C3: 非秘匿セルの最小値 ---
            for target_only in (True, False):
                for r, _, _ in iter_eyedrop_rows(df.copy(), target_only=target_only):
                    v = pd.to_numeric(df.iloc[r, acs], errors="coerce").dropna()
                    v = v[v > 0]
                    if not len(v):
                        continue
                    m = float(v.min())
                    if target_only:
                        y_min_target = m if y_min_target is None else min(y_min_target, m)
                    else:
                        y_min_all = m if y_min_all is None else min(y_min_all, m)
                        y_below += int((v < 1000).sum())
        min_rows.append({
            "year": year, "scope": "agesex",
            "min_target_drugs": y_min_target, "min_all_eyedrops": y_min_all,
            "n_cells_below_1000": y_below,
        })
    return pd.DataFrame(censor_rows), pd.DataFrame(min_rows)


def check_c3_pref_and_c4():
    """都道府県ファイルを走査して C3（最小値）と C4（総計列秘匿件数）を求める。"""
    rows, masked_total_rows = [], 0
    for year in YEARS:
        path = os.path.join(RAW, f"ndb_gaiyo_{year}.xlsx")
        if not os.path.exists(path):
            continue
        xl = pd.ExcelFile(path)
        y_min_target = y_min_all = None
        y_below = 0
        for sheet in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
            row2 = [str(x) for x in df.iloc[2]]
            tc = next((i for i, v in enumerate(row2) if "総計" in v), None)
            if tc is None:
                continue
            cols = list(range(tc + 1, min(tc + 48, df.shape[1])))
            for target_only in (True, False):
                for r, _, _ in iter_eyedrop_rows(df.copy(), target_only=target_only):
                    if target_only and pd.isna(pd.to_numeric(df.iloc[r, tc], errors="coerce")):
                        masked_total_rows += 1
                    v = pd.to_numeric(df.iloc[r, cols], errors="coerce").dropna()
                    v = v[v > 0]
                    if not len(v):
                        continue
                    m = float(v.min())
                    if target_only:
                        y_min_target = m if y_min_target is None else min(y_min_target, m)
                    else:
                        y_min_all = m if y_min_all is None else min(y_min_all, m)
                        y_below += int((v < 1000).sum())
        rows.append({
            "year": year, "scope": "prefecture",
            "min_target_drugs": y_min_target, "min_all_eyedrops": y_min_all,
            "n_cells_below_1000": y_below,
        })
    return pd.DataFrame(rows), masked_total_rows


def check_c2():
    """捕捉率 = 年齢別内訳の合計 / 公表総計。"""
    asr = pd.read_csv(os.path.join(PROCESSED, "age_sex_rates_allergy.csv"),
                      encoding="utf-8-sig")
    pub = pd.read_csv(os.path.join(PROCESSED, "national_totals_published.csv"),
                      encoding="utf-8-sig")
    both = (asr[asr.sex == "both"]
            .groupby(["year", "code"], as_index=False)["count"].sum())
    mg = both.merge(pub[["year", "code", "count_published"]], on=["year", "code"], how="left")
    mg["capture_pct"] = (mg["count"] / mg["count_published"] * 100).round(1)
    return mg[mg.code.isin(["EPINASTINE", "LEVOCASTINE", "OLOPATADINE"])][
        ["year", "code", "count", "count_published", "capture_pct"]]


def main():
    print("=== C1/C3(agesex): 年齢性別ファイルを走査中 ===")
    censor, min_as = check_c1_c3()
    print("=== C3(pref)/C4: 都道府県ファイルを走査中 ===")
    min_pref, masked_total_rows = check_c3_pref_and_c4()
    print("=== C2: 捕捉率 ===")
    capture = check_c2()

    ok = True

    # --- C1 ---
    print("\n--- C1. エピナスチン 年齢性別内訳の秘匿率 ---")
    for (year, kw), claim in sorted(CLAIM_CENSOR_PCT.items()):
        sub = censor[(censor.year == year) & (censor.sheet.str.contains(kw))]
        if sub.empty:
            print(f"  {year} {kw}: シートなし  [NG]")
            ok = False
            continue
        got = float(sub.iloc[0]["masked_pct"])
        hit = abs(got - claim) < 0.05
        ok &= hit
        print(f"  {year} {kw}: 論文 {claim:5.1f}%  実測 {got:5.1f}%  "
              f"({int(sub.iloc[0]['masked'])}/{int(sub.iloc[0]['cells'])} セル)  "
              f"[{'OK' if hit else 'NG'}]")

    # --- C2 ---
    print("\n--- C2. 年齢・性別データの捕捉率 ---")
    cap = capture.set_index(["year", "code"])["capture_pct"]
    for (year, code), claim in sorted(CLAIM_CAPTURE.items()):
        got = float(cap.loc[(year, code)]) if (year, code) in cap.index else np.nan
        hit = (not np.isnan(got)) and abs(got - claim) < 0.05
        ok &= hit
        print(f"  {year} {code:12s}: 論文 {claim:5.1f}%  実測 {got:5.1f}%  "
              f"[{'OK' if hit else 'NG'}]")

    # --- C3 ---
    print("\n--- C3. 秘匿閾値（非秘匿セルの最小値） ---")
    mins = pd.concat([min_as, min_pref], ignore_index=True)
    below = int(mins["n_cells_below_1000"].sum())
    # 年度単位の最小値（都道府県別・年齢性別の両シート群をまとめた値）
    per_year = mins.groupby("year")["min_all_eyedrops"].min().dropna()
    hit = below == 0 and bool((per_year == 1000.0).all())
    ok &= hit
    for y, v in per_year.items():
        print(f"  {y}: 全131点眼薬の最小値 {v:.1f}")
    print(f"  1,000未満のセル数: {below} 件  [{'OK' if hit else 'NG'}]")

    # --- C4 ---
    print("\n--- C4. 総計列が秘匿されている品目行 ---")
    hit = masked_total_rows == CLAIM_MASKED_TOTAL_ROWS
    ok &= hit
    print(f"  論文 {CLAIM_MASKED_TOTAL_ROWS} 件  実測 {masked_total_rows} 件  "
          f"[{'OK' if hit else 'NG'}]")

    # --- 保存 ---
    censor["check"] = "C1_censor_rate"
    mins["check"] = "C3_min_cell"
    capture = capture.copy()
    capture["check"] = "C2_capture_rate"
    res = pd.concat([censor, capture, mins], ignore_index=True)
    res.loc[len(res)] = {"check": "C4_masked_total_rows", "n_rows": masked_total_rows}
    path = os.path.join(PROCESSED, "methods_claims_verification.csv")
    res.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\nsaved: {path}  ({len(res)} rows)")
    print(f"\n総合判定: {'ALL OK' if ok else 'NG あり'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
