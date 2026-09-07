"""
緑内障手術（K268〜K273）を NDB オープンデータ（手術・都道府県別 / 性年齢別）から抽出し、
長形式 CSV を 01_抽出データ/ に出力する。

出力:
  01_抽出データ/glaucoma_surgery_pref_long.csv
      year, code, name, category, subcategory, sheet(外来/入院/全体), prefecture, count, censored
  01_抽出データ/glaucoma_surgery_agesex_long.csv
      year, code, name, category, subcategory, sheet, sex, age_group, count, censored
  01_抽出データ/glaucoma_surgery_national.csv
      year, code, name, category, subcategory, total   (総計列の合計。外来+入院)
  01_抽出データ/code_map.csv

秘匿セル（'-'）は count=NaN, censored=1 とする（区間推定は後段で行う）。
"""
from pathlib import Path
import re
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).resolve().parent / "01_抽出データ"
OUT.mkdir(exist_ok=True)

YEARS = range(2014, 2025)

# 診療行為コード → (category, subcategory)  Tanito 2023 の aggregation1 に対応させつつ細分化
CODE_MAP = {
    "150087510": ("iridectomy", "iridectomy"),                    # K268-1
    "150088410": ("angle_surgery", "outflow_all"),                # K268-2 (〜2021, 眼内外区別なし)
    "150427210": ("angle_surgery", "outflow_ab_externo"),         # K268-2 その他 (2022〜)
    "150435810": ("angle_surgery", "outflow_ab_interno"),         # K268-2 眼内法 (2022〜)
    "150395150": ("angle_surgery", "istent_phaco"),               # K268-6 水晶体再建術併用眼内ドレーン
    "150335910": ("filtration", "trabeculectomy"),                # K268-3
    "150356010": ("filtration", "implant_no_plate"),              # K268-4 ExPRESS / PRESERFLO
    "150373010": ("tube_shunt", "implant_with_plate"),            # K268-5 Ahmed / Baerveldt
    "150427310": ("bleb_revision", "needling"),                   # K268-7 濾過胞再建術 (2022〜) ※Tanito対象外
    "150088810": ("ciliary_coag", "cyclophotocoag"),              # K271
    "150446710": ("ciliary_coag", "cyclophotocoag_endoscopic"),   # K271 (2024〜)
    "150446810": ("ciliary_coag", "cyclophotocoag_other"),        # K271 (2024〜)
    "150088910": ("ciliary_coag", "cyclocryo"),                   # K272 (非レーザー)
    "150088710": ("iris_laser", "laser_iridotomy"),               # K270
    "150089010": ("gonio_laser", "laser_trabeculoplasty"),        # K273
}
LASER_SUB = {"cyclophotocoag", "cyclophotocoag_endoscopic", "cyclophotocoag_other",
             "laser_iridotomy", "laser_trabeculoplasty"}

AGE_MAP = {"0～4歳": "0-4", "5～9歳": "5-9", "10～14歳": "10-14", "15～19歳": "15-19",
           "20～24歳": "20-24", "25～29歳": "25-29", "30～34歳": "30-34", "35～39歳": "35-39",
           "40～44歳": "40-44", "45～49歳": "45-49", "50～54歳": "50-54", "55～59歳": "55-59",
           "60～64歳": "60-64", "65～69歳": "65-69", "70～74歳": "70-74", "75～79歳": "75-79",
           "80～84歳": "80-84", "85～89歳": "85-89", "90歳以上": "90+"}


def parse_cell(v):
    """(count, censored)"""
    if v is None:
        return (float("nan"), 0)
    if isinstance(v, (int, float)):
        return (float(v), 0)
    s = str(v).strip()
    if s in ("-", "‐", "－", "―"):
        return (float("nan"), 1)
    try:
        return (float(s.replace(",", "")), 0)
    except ValueError:
        return (float("nan"), 0)


def iter_target_rows(ws):
    """(code, name, row_values) for glaucoma codes"""
    for r in ws.iter_rows(min_row=5, values_only=True):
        code = str(r[3]).strip() if r[3] is not None else ""
        if code in CODE_MAP:
            yield code, r[4], r


def extract_pref():
    recs = []
    for y in YEARS:
        wb = openpyxl.load_workbook(RAW / f"ndb_shujutsu_{y}.xlsx", read_only=True)
        for sn in wb.sheetnames:
            if "加算" in sn:
                continue
            ws = wb[sn]
            hdr = list(ws.iter_rows(min_row=3, max_row=4, values_only=True))
            prefs = hdr[1]
            for code, name, r in iter_target_rows(ws):
                cat, sub = CODE_MAP[code]
                # 総計
                c, cen = parse_cell(r[6])
                recs.append((y, code, name, cat, sub, sn, "全国", c, cen))
                for j in range(7, len(r)):
                    p = prefs[j] if j < len(prefs) else None
                    if not p:
                        continue
                    c, cen = parse_cell(r[j])
                    recs.append((y, code, name, cat, sub, sn, p, c, cen))
    df = pd.DataFrame(recs, columns=["year", "code", "name", "category", "subcategory",
                                     "sheet", "prefecture", "count", "censored"])
    return df


def extract_agesex():
    recs = []
    for y in YEARS:
        wb = openpyxl.load_workbook(RAW / "ndb_age_sex" / f"ndb_shujutsu_agesex_{y}.xlsx",
                                    read_only=True)
        for sn in wb.sheetnames:
            if "加算" in sn:
                continue
            ws = wb[sn]
            hdr = list(ws.iter_rows(min_row=3, max_row=4, values_only=True))
            sexrow, agerow = hdr[0], hdr[1]
            # 性別は結合セル: 最初に出た性別を以降に引き継ぐ
            cols = []
            cur_sex = None
            for j in range(7, len(agerow)):
                s = sexrow[j] if j < len(sexrow) else None
                if s:
                    cur_sex = "male" if str(s).startswith("男") else "female"
                a = agerow[j]
                if a is not None:
                    a = str(a).replace("-", "～").replace("－", "～").replace("‐", "～").strip()
                if a in AGE_MAP:
                    cols.append((j, cur_sex, AGE_MAP[a]))
            for code, name, r in iter_target_rows(ws):
                cat, sub = CODE_MAP[code]
                for j, sex, ag in cols:
                    c, cen = parse_cell(r[j])
                    recs.append((y, code, name, cat, sub, sn, sex, ag, c, cen))
    df = pd.DataFrame(recs, columns=["year", "code", "name", "category", "subcategory",
                                     "sheet", "sex", "age_group", "count", "censored"])
    return df


def main():
    pref = extract_pref()
    pref.to_csv(OUT / "glaucoma_surgery_pref_long.csv", index=False, encoding="utf-8-sig")

    nat = (pref[pref.prefecture == "全国"]
           .groupby(["year", "code", "name", "category", "subcategory"], as_index=False)["count"]
           .sum().rename(columns={"count": "total"}))
    nat["is_laser"] = nat.subcategory.isin(LASER_SUB).astype(int)
    nat.to_csv(OUT / "glaucoma_surgery_national.csv", index=False, encoding="utf-8-sig")

    ags = extract_agesex()
    ags.to_csv(OUT / "glaucoma_surgery_agesex_long.csv", index=False, encoding="utf-8-sig")

    cm = pd.DataFrame([(k, v[0], v[1], int(v[1] in LASER_SUB)) for k, v in CODE_MAP.items()],
                      columns=["code", "category", "subcategory", "is_laser"])
    cm.to_csv(OUT / "code_map.csv", index=False, encoding="utf-8-sig")

    # 整合性チェック: 全国総計 vs 都道府県合計 vs 性年齢合計
    chk_p = (pref[pref.prefecture != "全国"].groupby(["year", "code"])["count"].sum())
    chk_a = ags.groupby(["year", "code"])["count"].sum()
    chk = nat.set_index(["year", "code"])["total"].to_frame("national")
    chk["pref_sum"] = chk_p
    chk["agesex_sum"] = chk_a
    chk["pref_gap"] = chk.national - chk.pref_sum
    chk["age_gap"] = chk.national - chk.agesex_sum
    chk.to_csv(OUT / "consistency_check.csv", encoding="utf-8-sig")
    print(chk.groupby(level="year")[["national", "pref_sum", "agesex_sum"]].sum())
    print("\n年×category 全国総計:")
    print(nat.pivot_table(index="category", columns="year", values="total", aggfunc="sum").round(0))


if __name__ == "__main__":
    main()
