"""緑内障点眼薬の品目マスタ（対象薬剤一覧・先発/後発・単位・秘匿状況）を構築する。

NDBオープンデータの外用薬ファイルを走査し、解析対象となった全品目について
以下を1行ずつ記録する。「どの点眼薬を対象にしたか」「後発品はどれか」
「数量の単位は個数かmLか」「どこが秘匿されているか」の問いに一括で答えるための出力。

    python 緑内障点眼解析/build_product_inventory.py

出力（一次出力先 processed*/ 配下）:
    product_inventory_glaucoma.csv   品目マスタ（品目×年度）
    product_master_glaucoma.csv      品目マスタ（品目単位に集約：収載年度・単位・先発後発）
    censoring_report_glaucoma.csv    年度×薬剤カテゴリの秘匿セル数と秘匿率
    inventory_summary_glaucoma.txt   人間可読な要約
"""

import argparse
import os
import re
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from preprocess_glaucoma import (  # noqa: E402
    AGGREGATE_DEFS, GROUP_DEFS, PREFECTURES, TOTAL_CODES,
    base_name, classify_drug, clean_count_value, ml_per_unit,
)
from paths import add_nokouhi_arg, output_dir, raw_file  # noqa: E402

YEARS = range(2014, 2025)
CENSOR_MARKS = ["-", "—", "－"]

# 各カテゴリの先発品（商品名）。品名がこれで始まる品目を先発品とみなす。
# 「（選）」付きは長期収載品の選定療養分（2024年10月〜）であり先発品として扱う。
BRAND_PREFIXES = {
    "LATANOPROST":   ["キサラタン"],
    "TRAVOPROST":    ["トラバタンズ"],
    "TAFLUPROST":    ["タプロス"],
    "BIMATOPROST":   ["ルミガン"],
    "OMIDENEPAG":    ["エイベリス"],
    "UNOPROSTONE":   ["レスキュラ"],
    "TIMOLOL":       ["チモプトール", "リズモン"],
    "CARTEOLOL":     ["ミケラン"],
    "BETAXOLOL":     ["ベトプティック"],
    "LEVOBUNOLOL":   ["ミロル"],
    "NIPRADILOL":    ["ハイパジール", "ニプラノール"],
    "DORZOLAMIDE":   ["トルソプト"],
    "BRINZOLAMIDE":  ["エイゾプト"],
    "BRIMONIDINE":   ["アイファガン"],
    "RIPASUDIL":     ["グラナテック"],
    "BUNAZOSIN":     ["デタントール"],
    "PILOCARPINE":   ["サンピロ"],
    "DIPIVEFRINE":   ["ピバレフリン"],
    "DISTIGMINE":    ["ウブレチド"],
    "APRACLONIDINE": ["アイオピジン"],
    "FDC_PG_BETA":   ["ザラカム", "デュオトラバ", "タプコム", "ミケルナ"],
    "FDC_CAI_BETA":  ["コソプト", "アゾルガ"],
    "FDC_A2_BETA":   ["アイベータ"],
    "FDC_A2_CAI":    ["アイラミド"],
    "FDC_ROCK_A2":   ["グラアルファ"],
}

# 薬剤カテゴリ → 薬効群（作用機序に基づく分類）
CODE_TO_GROUP = {}
for gcode, gname, members in GROUP_DEFS:
    for m in members:
        CODE_TO_GROUP[m] = (gcode, gname)


def drug_type(code, name):
    """先発品 / 後発品（銘柄別） / 後発品（統一名収載） を判定する。

    NDBオープンデータには先発後発の区別を示す列がないため品名から判定する。
      先発品      : 品名が当該成分の先発品名で始まる（「（選）」＝選定療養分を含む）
      銘柄別収載品: 品名に「メーカー名」が付く（例: ラタノプロスト点眼液0.005%「トーワ」）
      統一名収載品: 品名がメーカー名を持たない一般名表記（例: ラタノプロスト0.005%1mL点眼液）
    """
    for p in BRAND_PREFIXES.get(code, []):
        if name.startswith(p):
            return "先発品"
    return "後発品（銘柄別収載）" if "「" in name else "後発品（統一名収載）"


def scan_year(path, year):
    rows = []
    xl = pd.ExcelFile(path)
    for sheet in [s for s in xl.sheet_names if "外用薬" in s]:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        df[0] = df[0].ffill()
        row2 = [str(x) for x in df.iloc[2]]
        row3 = [str(x).strip() for x in df.iloc[3]]
        total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
        if total_col is None:
            continue
        unit_col = next((i for i in range(total_col + 1)
                         if "単位" in row2[i] or "単位" in row3[i]), None)
        pref_cols = [i for i in range(total_col + 1, min(total_col + 48, df.shape[1]))
                     if row3[i] in PREFECTURES]
        if not pref_cols:
            pref_cols = list(range(total_col + 1, min(total_col + 48, df.shape[1])))

        for r in range(4, len(df)):
            if str(df.iloc[r, 0]).strip() != "131":
                continue
            name = str(df.iloc[r, 3]).strip()
            if "点眼" not in name:
                continue
            res = classify_drug(name)
            if res is None:
                continue
            code, catname = res
            factor = ml_per_unit(name)
            raw_total = df.iloc[r, total_col]
            censored_cells = [c for c in pref_cols
                              if str(df.iloc[r, c]).strip() in CENSOR_MARKS]
            pref_sum = sum(clean_count_value(df.iloc[r, c]) for c in pref_cols)
            gcode, gname = CODE_TO_GROUP.get(code, ("EXCLUDED", "合計対象外（別掲）"))
            rows.append({
                "year": year,
                "sheet": sheet,
                "product_base": base_name(name),
                "group_code": gcode,
                "group_name": gname,
                "code": code,
                "category_name": catname,
                "product_name": name,
                "drug_type": drug_type(code, name),
                "drug_code": str(df.iloc[r, 2]).strip(),
                "unit_published": str(df.iloc[r, unit_col]).strip() if unit_col is not None else "",
                "ml_per_unit": factor,
                "quantity_published": clean_count_value(raw_total),
                "quantity_ml": clean_count_value(raw_total) * factor,
                "total_censored": str(raw_total).strip() in CENSOR_MARKS,
                "pref_sum_ml": pref_sum * factor,
                "n_pref_cells": len(pref_cols),
                "n_pref_censored": len(censored_cells),
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    add_nokouhi_arg(ap)
    args = ap.parse_args()
    out_dir = output_dir(args.nokouhi)

    rows = []
    for year in YEARS:
        path = raw_file("ndb_gaiyo", year, args.nokouhi)
        if not os.path.exists(path):
            continue
        print(f"  scanning {year} ...")
        rows += scan_year(path, year)

    df = pd.DataFrame(rows)
    # 3シート（外来院内・外来院外・入院）を合算して品目×年度の1行にする
    inv = df.groupby(
        ["year", "group_code", "group_name", "code", "category_name",
         "product_base", "drug_type", "unit_published", "ml_per_unit"],
        as_index=False
    ).agg(quantity_published=("quantity_published", "sum"),
          quantity_ml=("quantity_ml", "sum"),
          pref_sum_ml=("pref_sum_ml", "sum"),
          n_sheets_total_censored=("total_censored", "sum"),
          n_pref_cells=("n_pref_cells", "sum"),
          n_pref_censored=("n_pref_censored", "sum"))
    inv["pref_censor_rate"] = inv["n_pref_censored"] / inv["n_pref_cells"]
    inv = inv.rename(columns={"product_base": "product_name"})
    inv = inv.sort_values(["group_code", "code", "product_name", "year"])
    inv.to_csv(os.path.join(out_dir, "product_inventory_glaucoma.csv"),
               index=False, encoding="utf-8-sig")

    # ── 品目マスタ（品目単位に集約）──
    master = inv.groupby(
        ["group_code", "group_name", "code", "category_name",
         "product_name", "drug_type"], as_index=False
    ).agg(years_listed=("year", lambda s: ",".join(str(int(y)) for y in sorted(s))),
          n_years=("year", "nunique"),
          unit_published=("unit_published", lambda s: "/".join(
              sorted({v for v in s if v}) or {"（単位列なし）"})),
          ml_per_unit=("ml_per_unit", "first"),
          quantity_ml_total=("quantity_ml", "sum"))
    master = master.sort_values(["group_code", "code", "drug_type", "product_name"])
    master.to_csv(os.path.join(out_dir, "product_master_glaucoma.csv"),
                  index=False, encoding="utf-8-sig")

    # ── 秘匿レポート（年度×薬剤カテゴリ）──
    cen = inv.groupby(["year", "code", "category_name"], as_index=False).agg(
        n_products=("product_name", "nunique"),
        n_pref_cells=("n_pref_cells", "sum"),
        n_pref_censored=("n_pref_censored", "sum"),
        quantity_ml=("quantity_ml", "sum"),
        pref_sum_ml=("pref_sum_ml", "sum"))
    cen["pref_censor_rate"] = cen["n_pref_censored"] / cen["n_pref_cells"]
    # 秘匿により都道府県別合計から失われた数量の割合
    cen["ml_lost_to_censoring"] = cen["quantity_ml"] - cen["pref_sum_ml"]
    cen["ml_lost_rate"] = cen["ml_lost_to_censoring"] / cen["quantity_ml"].replace(0, pd.NA)
    cen.to_csv(os.path.join(out_dir, "censoring_report_glaucoma.csv"),
               index=False, encoding="utf-8-sig")

    # ── 要約テキスト ──
    path = os.path.join(out_dir, "inventory_summary_glaucoma.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("=" * 78 + "\n")
        f.write(" NDB緑内障点眼薬 品目マスタ・単位・秘匿状況の要約\n")
        f.write(" 対象: 薬効分類131（眼科用剤）かつ品名に「点眼」を含む品目\n")
        f.write("=" * 78 + "\n\n")

        f.write("1. 薬効群別の品目数（2014〜2024年度の通算・ユニーク品目）\n")
        f.write("-" * 78 + "\n")
        t = master.pivot_table(index=["group_name", "category_name"],
                               columns="drug_type", values="product_name",
                               aggfunc="count", fill_value=0)
        t["計"] = t.sum(axis=1)
        f.write(t.to_string() + "\n\n")

        f.write("2. 処方数量の単位（品目別）\n")
        f.write("-" * 78 + "\n")
        f.write("※単位列はNDBオープンデータ第3回（2016年度分）以降のみ存在する。\n")
        f.write("  容器単位（瓶・個）の品目は品名末尾の容量でmLに換算している。\n\n")
        u = master.groupby(["category_name", "unit_published", "ml_per_unit"],
                           as_index=False)["product_name"].count()
        u = u.rename(columns={"product_name": "品目数"})
        f.write(u.to_string(index=False) + "\n\n")
        f.write("  mL以外の単位で収載され換算した品目:\n")
        for _, r in master[master["ml_per_unit"] != 1.0].iterrows():
            f.write(f"    {r['product_name']}  [{r['unit_published']}] "
                    f"→ ×{r['ml_per_unit']} mL\n")
        f.write("\n")

        f.write("3. 秘匿の状況\n")
        f.write("-" * 78 + "\n")
        f.write("※外用薬（処方薬）の秘匿閾値は処方数量1,000未満。該当セルは「-」で公表され、\n")
        f.write("  本解析では0で補完している（--imputation zero。上限は999）。\n\n")
        tot_cells = int(cen["n_pref_cells"].sum())
        tot_cen = int(cen["n_pref_censored"].sum())
        f.write(f" 都道府県セル総数: {tot_cells:,} / うち秘匿: {tot_cen:,} "
                f"({tot_cen / tot_cells:.1%})\n\n")

        f.write(" 3-1. 年度別の秘匿率（都道府県セル）\n")
        by_year = cen.groupby("year").agg(
            n_pref_cells=("n_pref_cells", "sum"),
            n_pref_censored=("n_pref_censored", "sum"),
            quantity_ml=("quantity_ml", "sum"),
            pref_sum_ml=("pref_sum_ml", "sum"))
        by_year["秘匿率"] = (by_year["n_pref_censored"] / by_year["n_pref_cells"]).round(3)
        by_year["秘匿で失われた数量の割合"] = (
            1 - by_year["pref_sum_ml"] / by_year["quantity_ml"]).round(4)
        f.write(by_year[["n_pref_cells", "n_pref_censored", "秘匿率",
                         "秘匿で失われた数量の割合"]].to_string() + "\n\n")

        f.write(" 3-2. 薬剤カテゴリ別の秘匿率（全年度通算）\n")
        by_code = cen.groupby("category_name").agg(
            n_pref_cells=("n_pref_cells", "sum"),
            n_pref_censored=("n_pref_censored", "sum"),
            quantity_ml=("quantity_ml", "sum"),
            pref_sum_ml=("pref_sum_ml", "sum"))
        by_code["秘匿率"] = (by_code["n_pref_censored"] / by_code["n_pref_cells"]).round(3)
        by_code["秘匿で失われた数量の割合"] = (
            1 - by_code["pref_sum_ml"] / by_code["quantity_ml"].replace(0, pd.NA)).round(4)
        f.write(by_code.sort_values("秘匿率", ascending=False)[
            ["n_pref_cells", "n_pref_censored", "秘匿率",
             "秘匿で失われた数量の割合"]].to_string() + "\n\n")

        f.write(" 3-3. 全国総計そのものが秘匿された品目×年度\n")
        blanked = df[df["total_censored"]].drop_duplicates(
            ["year", "product_name", "sheet"])
        if blanked.empty:
            f.write("   なし\n")
        else:
            f.write(f"   {len(blanked)} 件（シート単位）。主に入院・院内処方シート。\n")
            agg = blanked.groupby(["category_name", "sheet"]).size()
            f.write(agg.to_string() + "\n")
        f.write("\n")

        f.write("4. 収載年度が限られる品目（経年比較に使えない品目）\n")
        f.write("-" * 78 + "\n")
        for _, r in master[master["n_years"] < 11].sort_values(
                ["n_years", "category_name"]).iterrows():
            f.write(f" {r['n_years']:2d}/11年度  {r['category_name']:32s} "
                    f"{r['product_name']}  [{r['years_listed']}]\n")

    print(f"\nwrote {os.path.join(out_dir, 'product_inventory_glaucoma.csv')}")
    print(f"wrote {os.path.join(out_dir, 'product_master_glaucoma.csv')}")
    print(f"wrote {os.path.join(out_dir, 'censoring_report_glaucoma.csv')}")
    print(f"wrote {path}")
    print(f"品目数（通算ユニーク）: {master['product_name'].nunique()}")


if __name__ == "__main__":
    main()
