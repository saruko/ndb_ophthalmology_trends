"""NDBオープンデータ「医科診療行為 G注射」から G016 硝子体内注射 を抽出してCSV化する。

出力（いずれもロング形式・秘匿セルも行として保持）:
  g016_prefecture.csv        : 都道府県別 算定回数
  g016_agesex.csv            : 年齢階級・性別 算定回数
  g016_data_availability.csv : 年度ごとのデータ有無

第1回（2014年度）は医科診療行為に「G注射」の区分がないためデータなし。
「外来（加算）」「入院（加算）」シートは加算であり実施回数ではないため対象外
（2024年度の入院（加算）に「未熟児加算（硝子体内注射）」があるが集計しない）。
"""

import argparse
import csv
import re
from pathlib import Path

import openpyxl

BASE = Path(r"G:\マイドライブ\NDB_眼科診療トレンド解析_研究計画書")
SRC_DIR = BASE / "data" / "raw" / "ndb_g_chusha_koui"
NOKOUHI_DIR = BASE / "data" / "raw" / "ndb_2024_nokouhi"
OUT_DIR = BASE / "抗VEFG薬"

TARGET_CODE = "130012010"  # G016 硝子体内注射
SHEETS = ["外来", "入院"]   # 加算シートは対象外
YEARS = range(2014, 2025)
NO_DATA_YEARS = {2014: "第1回NDBオープンデータには医科診療行為「G注射」の区分がないため"}


def clean(v):
    return "" if v is None else re.sub(r"\s+", "", str(v))


def load_sheet(path, sheet_name, kind):
    """G016の行を読み、((上段,下段), 生値) のリストとメタを返す。"""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    if sheet_name not in wb.sheetnames:
        wb.close()
        return None
    ws = wb[sheet_name]
    rows = ws.iter_rows(values_only=True)

    for row in rows:
        if clean(row[0]).startswith("分類"):
            top = [clean(c) for c in row]
            break
    else:
        wb.close()
        raise ValueError(f"header not found: {path.name} / {sheet_name}")
    sub = [clean(c) for c in next(rows)]

    idx = {c: i for i, c in enumerate(top) if c}
    # 2019年度の年齢性別表のみ見出しが「区分名称」（他年度は「分類名称」）
    if "分類名称" not in idx and "区分名称" in idx:
        idx["分類名称"] = idx["区分名称"]
    total_idx = next(i for i, c in enumerate(top) if c.startswith("総計"))
    first_val = total_idx + 1

    filled_top, last = [], ""
    for c in top:
        if c:
            last = c
        filled_top.append(last)
    header = list(zip(filled_top, sub))

    out = None
    cls_code = cls_name = ""
    for row in rows:
        if clean(row[idx["分類コード"]]):
            cls_code = clean(row[idx["分類コード"]])
            cls_name = clean(row[idx["分類名称"]])
        if clean(row[idx["診療行為コード"]]) != TARGET_CODE:
            continue
        meta = {
            "分類コード": cls_code,
            "分類名称": cls_name,
            "診療行為コード": TARGET_CODE,
            "診療行為": clean(row[idx["診療行為"]]),
            "点数": clean(row[idx["点数"]]),
            "総計_算定回数": clean(row[total_idx]),
        }
        vals = [(header[i], row[i]) for i in range(first_val, len(row))]
        out = (meta, vals)
        break
    wb.close()
    return out


def extract(kind, nokouhi=False):
    """kind: 'pref' or 'agesex'"""
    prefix = "ndb_g_chusha_pref" if kind == "pref" else "ndb_g_chusha_agesex"
    records, availability = [], []
    for year in YEARS:
        if nokouhi and year == 2024:
            # 2024年度のみ「公費レセプトを含まない」版に差し替える
            path = NOKOUHI_DIR / f"{prefix}_{year}_nokouhi.xlsx"
        else:
            path = SRC_DIR / f"{prefix}_{year}.xlsx"
        if not path.exists():
            availability.append((year, "なし", NO_DATA_YEARS.get(year, "ファイル未取得")))
            print(f"  {year}: なし")
            continue
        n0 = len(records)
        for sheet in SHEETS:
            res = load_sheet(path, sheet, kind)
            if res is None:
                continue
            meta, vals = res
            for (top, subv), v in vals:
                raw = clean(v)
                if raw == "":
                    continue
                hidden = raw in ("-", "－", "‐")
                rec = {"年度": year, "区分": sheet, **meta}
                if kind == "pref":
                    rec["都道府県"] = subv
                else:
                    # 2014年度以外は「男/女」表記だが念のため正規化
                    rec["性別"] = top.replace("性", "")
                    rec["年齢階級"] = subv
                rec["算定回数"] = "" if hidden else raw
                rec["秘匿フラグ"] = 1 if hidden else 0
                rec["原表記"] = raw
                records.append(rec)
        availability.append((year, "あり", ""))
        print(f"  {year}: +{len(records) - n0} rows")
    return records, availability


def write_csv(rows, path, cols):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path.name} ({len(rows)} rows)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nokouhi", action="store_true",
                    help="2024年度を公費レセプトを含まない版にして「公費含まない」へ出力")
    args = ap.parse_args()
    out_dir = OUT_DIR / "公費含まない" if args.nokouhi else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_cols = ["年度", "区分", "分類コード", "分類名称", "診療行為コード", "診療行為",
                 "点数", "総計_算定回数"]
    tail = ["算定回数", "秘匿フラグ", "原表記"]

    print("[都道府県別]")
    pref, avail_pref = extract("pref", args.nokouhi)
    write_csv(pref, out_dir / "g016_prefecture.csv", meta_cols + ["都道府県"] + tail)

    print("[年齢性別]")
    agesex, avail_age = extract("agesex", args.nokouhi)
    write_csv(agesex, out_dir / "g016_agesex.csv",
              meta_cols + ["性別", "年齢階級"] + tail)

    rows = []
    for (year, st, note), (_, st2, _) in zip(avail_pref, avail_age):
        rows.append({"年度": year, "都道府県別": st, "年齢性別": st2, "備考": note})
    write_csv(rows, out_dir / "g016_data_availability.csv",
              ["年度", "都道府県別", "年齢性別", "備考"])


if __name__ == "__main__":
    main()
