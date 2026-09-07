# -*- coding: utf-8 -*-
"""s03: NDBオープンデータ薬剤ファイル → 掲載品目パネル

注射薬・外用薬について、年度 × 診療区分(外来院内/外来院外/入院) ごとに
掲載されている品目と全国総計数量を抽出する。

計数単位が2つあることに注意:
  - NDBの行単位 = 医薬品コード(Yコード, 9桁) = 銘柄。足切り(上位N位)はこの単位で掛かる。
  - 薬価基準収載品目リストの行単位 = 薬価基準収載医薬品コード(12桁)。
    統一名収載により複数銘柄が1コードに集約されるため、NDB→リストは多対一。
突合は両者に共通する12桁コード単位で行い、足切りの天井観察は行(銘柄)単位で行う。

列位置は年度で動く(2019年度以降「単位」列が挿入される)ため、
12桁コード列・総計列はいずれも内容/ヘッダから自動検出する。

出力: processed/ndb_published.csv (12桁単位), processed/ndb_class_counts.csv (銘柄単位)
"""
import os
import re
import pandas as pd

from paths import NDB_RAW, OUT_DIR

KINDS = {"chusha": "注射薬", "gaiyo": "外用薬"}
YEARS = list(range(2014, 2025))
CODE_RE = re.compile(r"^\d{4}[0-9A-Z]{3}[0-9A-Z]\d{4}$")


def _setting(sheet_name):
    if "入院" in sheet_name:
        return "入院"
    if "院内" in sheet_name:
        return "外来院内"
    if "院外" in sheet_name:
        return "外来院外"
    return sheet_name


def _load_sheet(path, sheet):
    header = pd.read_excel(path, sheet_name=sheet, header=None, skiprows=2, nrows=1)
    hdr = [str(x).replace("\n", "") for x in header.iloc[0].tolist()]
    body = pd.read_excel(path, sheet_name=sheet, header=None, skiprows=4, dtype=object)

    code_col, best = None, 0
    for c in body.columns[:9]:
        n = body[c].astype(str).str.strip().apply(lambda x: bool(CODE_RE.match(x))).sum()
        if n > best:
            code_col, best = c, n
    if code_col is None:
        raise ValueError("12桁コード列が見つからない: %s / %s" % (path, sheet))

    total_col, ge_col = None, None
    for i, h in enumerate(hdr):
        if total_col is None and "総計" in h:
            total_col = i
        if ge_col is None and "後発品" in h:
            ge_col = i
    if total_col is None:
        raise ValueError("総計列が見つからない: %s / %s" % (path, sheet))

    name_col = 3
    out = pd.DataFrame({
        "ycode": body[2].astype(str).str.strip(),
        "yj12": body[code_col].astype(str).str.strip(),
        "product": body[name_col].astype(str).str.strip(),
        "is_generic": (pd.to_numeric(body[ge_col], errors="coerce").fillna(0).astype(int)
                       if ge_col is not None else 0),
        "total_raw": body[total_col].astype(str).str.strip(),
    })
    out = out[out["yj12"].apply(lambda s: bool(CODE_RE.match(s)))]
    # "-" は秘匿(全国計では通常発生しないが念のため NaN)
    out["total_qty"] = pd.to_numeric(
        out["total_raw"].str.replace(",", "", regex=False), errors="coerce")
    return out.drop(columns=["total_raw"])


def build():
    os.makedirs(OUT_DIR, exist_ok=True)
    frames = []
    for kind, kind_jp in KINDS.items():
        for y in YEARS:
            path = os.path.join(NDB_RAW, "ndb_%s_%d.xlsx" % (kind, y))
            if not os.path.exists(path):
                print("  skip (無し): %s" % os.path.basename(path))
                continue
            xl = pd.ExcelFile(path)
            for sheet in xl.sheet_names:
                df = _load_sheet(path, sheet)
                df.insert(0, "setting", _setting(sheet))
                df.insert(0, "kind", kind_jp)
                df.insert(0, "fiscal_year", y)
                frames.append(df)
            print("  FY%d %-7s %d シート" % (y, kind, len(xl.sheet_names)))

    rows = pd.concat(frames, ignore_index=True)
    rows["class3"] = rows["yj12"].str[:3]
    rows["class4"] = rows["yj12"].str[:4]

    # --- (1) 足切りの天井: 銘柄(Yコード)単位で薬効分類ごとの掲載数を数える ---
    cc = (rows.groupby(["fiscal_year", "kind", "setting", "class3"])
              .size().rename("n_brands").reset_index())
    ceil = (cc.groupby(["fiscal_year", "kind", "setting"])["n_brands"]
              .agg(max_brands="max", n_class="count").reset_index())
    n_at_max = (cc.merge(ceil, on=["fiscal_year", "kind", "setting"])
                  .query("n_brands == max_brands")
                  .groupby(["fiscal_year", "kind", "setting"]).size()
                  .rename("n_at_max").reset_index())
    ceil = ceil.merge(n_at_max, on=["fiscal_year", "kind", "setting"], how="left")
    cc.to_csv(os.path.join(OUT_DIR, "ndb_class_counts.csv"),
              index=False, encoding="utf-8-sig")
    ceil.to_csv(os.path.join(OUT_DIR, "ndb_ceiling.csv"),
                index=False, encoding="utf-8-sig")

    # --- (2) 突合用: 12桁コード単位に集約（同一コードの複数銘柄は数量を合算） ---
    pub = (rows.groupby(["fiscal_year", "kind", "setting", "yj12", "class3", "class4"],
                        as_index=False)
               .agg(n_brands=("ycode", "nunique"),
                    total_qty=("total_qty", "sum"),
                    min_brand_qty=("total_qty", "min"),
                    is_generic=("is_generic", "max"),
                    product=("product", "first")))
    fp = os.path.join(OUT_DIR, "ndb_published.csv")
    pub.to_csv(fp, index=False, encoding="utf-8-sig")
    print("[s03] 出力: %s (銘柄%d行 -> 12桁%d行)" % (fp, len(rows), len(pub)))

    print("[s03] 年度×剤形×区分ごとの観測天井（銘柄単位）:")
    print(ceil.to_string(index=False))
    return pub


if __name__ == "__main__":
    build()
