# -*- coding: utf-8 -*-
"""
先発品/後発品・製剤別（エピナスチンLX vs 標準）の集計を生データから構築する。

Figure 5 系列の元データを生成する。従来これらのCSVは生成コードが存在せず
再現できなかったため、本スクリプトで生成過程を明示する。

分類規則:
  先発品 = 品目名が先発品名（アレジオン／リボスチン／パタノール）で始まる
           ※「（選）」付き品目は長期収載品の選定療養分（2024年10月〜）であり
             先発品として扱う
  後発品 = それ以外（一般名ベースの品目名）
  LX製剤 = 品目名に「ＬＸ」を含む（エピナスチン 0.1%、1日2回投与）

数量は各品目行の公表「総計」列を、3シート（外来院内・外来院外・入院）
にわたって合算した値を用いる。

出力:
  processed/brand_generic_products.csv          品目別（year, category, type, product_name, quantity）
  processed/brand_generic_share.csv             成分別 先発/後発シェア
  processed/epinastine_lx_vs_standard.csv       エピナスチン LX vs 標準
  processed/epinastine_lx_formulation_detail.csv エピナスチン 製剤×先発後発 の2×2
  processed/epinastine_lx_share_by_age.csv      エピナスチン内LXシェアの年齢群別内訳
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))
from preprocess_allergy import classify_drug  # noqa: E402

from paths import nokouhi_from_argv, output_dir, raw_file, raw_file_map  # noqa: E402

NOKOUHI = nokouhi_from_argv()
OUT = output_dir(NOKOUHI)

CATEGORIES = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]
BRAND_PREFIX = {
    "EPINASTINE": "アレジオン",
    "OLOPATADINE": "パタノール",
    "LEVOCASTINE": "リボスチン",
}


def drug_type(code, name):
    """先発品(brand) / 後発品(generic) の判定。"""
    return "brand" if name.startswith(BRAND_PREFIX[code]) else "generic"


def is_lx(name):
    """LX製剤（0.1%、1日2回）か。"""
    return "ＬＸ" in name or "LX" in name


def age_cols(df):
    """「歳」を含むラベル行の列インデックス（=年齢×性別セル）と、その年齢ラベル。"""
    best, bestn, brow = [], 0, None
    for r in range(min(6, len(df))):
        idx = [c for c in range(df.shape[1]) if "歳" in str(df.iloc[r, c])]
        if len(idx) > bestn:
            best, bestn, brow = idx, len(idx), r
    labels = [str(df.iloc[brow, c]) for c in best] if brow is not None else []
    return best, labels


def norm_age(label):
    """「0～4歳」→「0-4」、「100歳以上」→「100+」。"""
    s = label.replace("歳以上", "+").replace("歳", "")
    s = s.replace("～", "-").replace("〜", "-").replace("~", "-")
    return s.strip()


# ------------------------------------------------------------------
# 1. 品目別数量（都道府県ファイルの総計列）
# ------------------------------------------------------------------
def build_products():
    rows = []
    files = raw_file_map("ndb_gaiyo", NOKOUHI)
    for year in sorted(files):
        path = files[year]
        xl = pd.ExcelFile(path)
        for sheet in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
            row2 = [str(x) for x in df.iloc[2]]
            tc = next((i for i, v in enumerate(row2) if "総計" in v), None)
            if tc is None:
                continue
            df[0] = df[0].ffill()
            for r in range(4, len(df)):
                if str(df.iloc[r, 0]).strip() != "131":
                    continue
                name = str(df.iloc[r, 3]).strip()
                if "点眼" not in name:
                    continue
                hit = classify_drug(name)
                if hit is None or hit[0] not in CATEGORIES:
                    continue
                q = pd.to_numeric(df.iloc[r, tc], errors="coerce")
                if pd.isna(q):
                    continue
                rows.append({"year": year, "category": hit[0],
                             "type": drug_type(hit[0], name),
                             "product_name": name, "quantity": float(q)})
    prod = (pd.DataFrame(rows)
            .groupby(["year", "category", "type", "product_name"], as_index=False)
            ["quantity"].sum()
            .sort_values(["year", "category", "type", "product_name"]))
    return prod


# ------------------------------------------------------------------
# 2. 先発/後発シェア
# ------------------------------------------------------------------
def build_share(prod):
    p = prod.pivot_table(index=["year", "category"], columns="type",
                         values="quantity", aggfunc="sum").fillna(0.0).reset_index()
    for c in ("brand", "generic"):
        if c not in p.columns:
            p[c] = 0.0
    p = p.rename(columns={"brand": "quantity_brand", "generic": "quantity_generic"})
    p["total"] = p["quantity_brand"] + p["quantity_generic"]
    p["share_pct_brand"] = (p["quantity_brand"] / p["total"] * 100).round(2)
    p["share_pct_generic"] = (p["quantity_generic"] / p["total"] * 100).round(2)
    p.columns.name = None
    return p[["year", "category", "quantity_brand", "quantity_generic", "total",
              "share_pct_brand", "share_pct_generic"]].sort_values(["category", "year"])


# ------------------------------------------------------------------
# 3. エピナスチン LX vs 標準／2x2
# ------------------------------------------------------------------
def build_epinastine(prod):
    e = prod[prod.category == "EPINASTINE"].copy()
    e["form"] = np.where(e.product_name.map(is_lx), "LX_0.1pct", "standard_0.05pct")

    lx = (e.pivot_table(index="year", columns="form", values="quantity",
                        aggfunc="sum").fillna(0.0).reset_index())
    for c in ("LX_0.1pct", "standard_0.05pct"):
        if c not in lx.columns:
            lx[c] = 0.0
    lx["total"] = lx["LX_0.1pct"] + lx["standard_0.05pct"]
    lx["LX_pct"] = (lx["LX_0.1pct"] / lx["total"] * 100).round(2)
    lx["standard_pct"] = (lx["standard_0.05pct"] / lx["total"] * 100).round(2)
    lx.columns.name = None
    lx = lx[["year", "LX_0.1pct", "standard_0.05pct", "total", "LX_pct", "standard_pct"]]

    e["cell"] = e["form"] + "_" + e["type"]
    det = (e.pivot_table(index="year", columns="cell", values="quantity",
                         aggfunc="sum").fillna(0.0).reset_index())
    cells = ["LX_0.1pct_brand", "LX_0.1pct_generic",
             "standard_0.05pct_brand", "standard_0.05pct_generic"]
    for c in cells:
        if c not in det.columns:
            det[c] = 0.0
    det["total"] = det[cells].sum(axis=1)
    for c in cells:
        det[c + "_pct"] = (det[c] / det["total"] * 100).round(2)
    det.columns.name = None
    return lx, det[["year"] + cells + ["total"] + [c + "_pct" for c in cells]]


# ------------------------------------------------------------------
# 4. エピナスチン内 LXシェアの年齢群別内訳（年齢性別ファイル）
# ------------------------------------------------------------------
def build_lx_by_age(year=2024):
    path = raw_file("ndb_gaiyo_agesex", year, NOKOUHI, agesex=True)
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    acc = {}
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        cols, labels = age_cols(df)
        if not cols:
            continue
        df[0] = df[0].ffill()
        for r in range(len(df)):
            if str(df.iloc[r, 0]).strip() != "131":
                continue
            name = str(df.iloc[r, 3]).strip()
            if "点眼" not in name:
                continue
            hit = classify_drug(name)
            if hit is None or hit[0] != "EPINASTINE":
                continue
            form = "LX" if is_lx(name) else "standard"
            v = pd.to_numeric(df.iloc[r, cols], errors="coerce").fillna(0.0).values
            for lab, val in zip(labels, v):
                ag = norm_age(lab)
                acc.setdefault(ag, {"LX": 0.0, "standard": 0.0})
                acc[ag][form] += float(val)

    order = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
             "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74",
             "75-79", "80-84", "85-89", "90-94", "95-99", "100+"]
    rows = []
    for ag in order:
        if ag not in acc:
            continue
        lxq, stq = acc[ag]["LX"], acc[ag]["standard"]
        tot = lxq + stq
        rows.append({"year": year, "age_group": ag, "LX_0.1pct": lxq,
                     "standard_0.05pct": stq, "total": tot,
                     "LX_pct": round(lxq / tot * 100, 2) if tot else np.nan})
    out = pd.DataFrame(rows)
    # 処方量が僅少な年齢群では標準製剤側が秘匿（<1,000）で0となり、
    # LXシェアが見かけ上100%に振れる。エピナスチン全体の0.1%未満の群は
    # 比率が信頼できないため reliable=False とし、幅の算出から除外する。
    out["volume_share_pct"] = (out["total"] / out["total"].sum() * 100).round(4)
    out["reliable"] = out["volume_share_pct"] >= 0.1
    return out


def _save(df, name):
    path = os.path.join(OUT, name)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  -> {name} ({len(df)} rows)")


def main():
    print("=== 品目別数量を生データから集計中 ===")
    prod = build_products()
    _save(prod, "brand_generic_products.csv")

    share = build_share(prod)
    _save(share, "brand_generic_share.csv")

    lx, det = build_epinastine(prod)
    _save(lx, "epinastine_lx_vs_standard.csv")
    _save(det, "epinastine_lx_formulation_detail.csv")

    print("=== エピナスチン内LXシェアの年齢群別内訳 (2024年度) ===")
    by_age = build_lx_by_age(2024)
    _save(by_age, "epinastine_lx_share_by_age.csv")

    rel = by_age[by_age.reliable].set_index("age_group")["LX_pct"]
    span = rel.max() - rel.min()
    print(f"\n  0-4歳 {rel.get('0-4'):.1f}% / 5-9歳 {rel.get('5-9'):.1f}% / "
          f"80-84歳 {rel.get('80-84'):.1f}% / 90-94歳 {rel.get('90-94'):.1f}%")
    print(f"  最大 {rel.max():.1f}% ({rel.idxmax()}) - 最小 {rel.min():.1f}% ({rel.idxmin()}) "
          f"= 幅 {span:.1f} ポイント")
    excl = by_age[~by_age.reliable]["age_group"].tolist()
    if excl:
        print(f"  （処方量僅少のため幅の算出から除外: {', '.join(excl)}）")

    print("\n=== 2024年度 エピナスチン 製剤×先発後発 ===")
    d = det[det.year == 2024].iloc[0]
    print(f"  LX先発 {d['LX_0.1pct_brand_pct']:.1f}%  LX後発 {d['LX_0.1pct_generic_pct']:.1f}%  "
          f"標準先発 {d['standard_0.05pct_brand_pct']:.1f}%  "
          f"標準後発 {d['standard_0.05pct_generic_pct']:.1f}%")
    lxrow = lx[lx.year == 2024].iloc[0]
    gen_in_lx = d["LX_0.1pct_generic"] / lxrow["LX_0.1pct"] * 100
    print(f"  LX全体 {lxrow['LX_0.1pct']:,.0f} mL のうち後発品 "
          f"{d['LX_0.1pct_generic']:,.0f} mL ({gen_in_lx:.1f}%)")

    sen = prod[(prod.year == 2024) & (prod.product_name.str.contains("（選）"))]
    if len(sen):
        epi_tot = prod[(prod.year == 2024) & (prod.category == "EPINASTINE")]["quantity"].sum()
        for _, r in sen[sen.category == "EPINASTINE"].iterrows():
            print(f"  選定療養分: {r['product_name']} {r['quantity']:,.0f} mL "
                  f"({r['quantity'] / epi_tot * 100:.1f}%)")


if __name__ == "__main__":
    main()
