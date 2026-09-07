# -*- coding: utf-8 -*-
"""秘匿セルの識別区間（下限・上限）と品目収載の完全性検証（査読対応）。

査読指摘への対応（抗アレルギー点眼解析 と同一の方法論）:

指摘①（対象薬剤の選定は妥当か。掲載されていない薬剤があるのでは）
  抗VEGF薬は「クラス全体」を対象としており、上市中の全製品が上市期間の
  全年度でNDBに掲載されていることをデータで検証する（→ listing_completeness）。
  外用薬と異なり、上位品目の足切りによる未収載問題は生じていない。

指摘②（外来院内・入院で非公開のデータがあるのに正確に解析できるのか。
        最大値・最小値の処理は）
  品目×年度×区分ごとに、公表「総計」列から秘匿分の合計
      missing = 総計 − Σ(開示された47都道府県セル)
  を厳密に復元できる。各秘匿セルの真値は [0, missing] に収まる。

  「秘匿セルは必ず10未満（≦9）」という仮定は使えない。NDBは補完的秘匿
  （complementary suppression）を行っており、実データでも部分秘匿行に
  「秘匿セルがちょうど1個」の行は0行、missing が 秘匿セル数×9 を超える行が
  全部分秘匿行に及ぶ（本スクリプトが毎回検証して出力する）。
  従来の five/random 補完（≦9/セル前提）は upper として機能しない。

  総計自体が「-」の行（総計秘匿）のみ missing が計算できないため、
  一次秘匿ルール（総計<10）に基づき 9 − Σ開示 を上限とする。

出力: 03_解析結果/品質管理_感度分析/
  product_censoring_bounds_antivegf.csv   品目×年度×区分の missing と分類
  national_bounds_antivegf.csv            成分・グループ×年度の全国 下限/上限
  prefecture_bounds_antivegf.csv          都道府県×年度×成分の 下限/上限
  agesex_bounds_antivegf.csv              性別×年齢階級×年度×成分の 下限/上限
  listing_completeness_antivegf.csv       製品×年度の掲載有無（指摘①の検証）
  censoring_bounds_report_antivegf.md     方法・検証結果・査読回答の要旨
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from drug_master import DRUG_MASTER, GROUPS, MOLECULE_NAMES, MOLECULE_ORDER  # noqa: E402

# --nokouhi 指定時は「公費含まない」サブフォルダの入出力に切り替える
IN_DIR = os.path.join(BASE, "01_抽出データ")
OUT_DIR = os.path.join(BASE, "03_解析結果", "品質管理_感度分析")
DATASET_NOTE = ""

CAP = 9  # 注射の秘匿閾値は「10未満」。総計秘匿行の総計上限（一次秘匿ルールに基づく）

# 上市期間（年度）。listing_completeness の照合に使う。
MARKETED_YEARS = {
    "622199401": (2014, 2024), "629906401": (2020, 2024),
    "629928401": (2024, 2024), "629918901": (2022, 2024),
    "629907201": (2020, 2024), "620008448": (2014, 2019),
    "621894901": (2015, 2024), "620009103": (2014, 2015),
    "622352001": (2014, 2024), "629916701": (2021, 2024),
}


def load(name, cell_cols):
    d = pd.read_csv(os.path.join(IN_DIR, name), dtype={"医薬品コード": str})
    d = d[d.医薬品コード.isin(DRUG_MASTER)]
    d["molecule"] = d.医薬品コード.map({k: v[1] for k, v in DRUG_MASTER.items()})
    d["category"] = d.医薬品コード.map({k: v[5] for k, v in DRUG_MASTER.items()})
    d = d[d.category == "ANTI_VEGF"]
    return d


def product_bounds(d, axis_label):
    """品目×年度×区分ごとの missing と秘匿分類。"""
    rows = []
    for (year, sheet, code), g in d.groupby(["年度", "区分", "医薬品コード"]):
        total = g.総計_処方数量.iloc[0]
        disclosed = g.loc[g.秘匿フラグ == 0, "処方数量"].sum()
        n_cens = int(g.秘匿フラグ.sum())
        total_censored = pd.isna(total)
        if total_censored:
            missing = np.nan
            upper_add = max(0.0, CAP - disclosed)
            cls = "総計秘匿"
        else:
            missing = max(0.0, total - disclosed)
            upper_add = missing
            cls = ("秘匿なし" if n_cens == 0 else
                   "ブロック秘匿" if disclosed == 0 else "部分秘匿")
        rows.append({
            "axis": axis_label, "year": year, "sheet": sheet, "code": code,
            "product": DRUG_MASTER[code][0], "molecule": DRUG_MASTER[code][1],
            "total": total, "total_censored": total_censored,
            "sum_disclosed": disclosed, "n_cells_censored": n_cens,
            "missing": missing, "upper_add": upper_add, "censor_class": cls,
            "exceeds_cap9": (not total_censored) and missing > CAP * n_cens + .5,
        })
    return pd.DataFrame(rows)


def add_groups(df, keys):
    """成分別集計にグループ（合計等）を追加する。"""
    out = [df]
    for gcode, (gname, members) in GROUPS.items():
        g = (df[df.molecule.isin(members)]
             .groupby([k for k in keys if k != "molecule"], as_index=False)
             [["lower", "upper"]].sum())
        g["molecule"] = gcode
        out.append(g)
    return pd.concat(out, ignore_index=True)


def national_bounds(pb):
    """全国（成分×年度）。総計は公表値がそのまま確定値。総計秘匿行のみ上限を持つ。"""
    pb = pb.copy()
    pb["lower"] = np.where(pb.total_censored, 0.0, pb.total)
    pb["upper"] = np.where(pb.total_censored, pb.upper_add, pb.total)
    g = pb.groupby(["year", "molecule"], as_index=False)[["lower", "upper"]].sum()
    g = add_groups(g, ["year", "molecule"])
    g["width_pct"] = np.where(g.lower > 0, (g.upper - g.lower) / g.lower * 100, np.nan)
    return g.sort_values(["molecule", "year"])


def cell_bounds(d, pb, cell_cols):
    """セル軸（都道府県 or 性別×年齢階級）の下限/上限。

    下限 = 開示セルの合計（秘匿=0）。
    上限 = 開示セルの合計 + その品目行の upper_add（missing 全額が
           当該セルに集中した最悪ケース。1出力セルは各品目行から
           高々1セルしか受け取らないため有効な上限）。
    """
    key = ["year", "sheet", "code"]
    m = d.rename(columns={"年度": "year", "区分": "sheet", "医薬品コード": "code"})
    m = m.merge(pb[key + ["upper_add"]], on=key, how="left")
    m["lower"] = np.where(m.秘匿フラグ == 1, 0.0, m.処方数量.fillna(0.0))
    m["upper"] = np.where(m.秘匿フラグ == 1, m.upper_add, m.処方数量.fillna(0.0))
    g = (m.groupby(["year", "molecule"] + cell_cols, as_index=False)
         [["lower", "upper"]].sum())
    g = add_groups(g, ["year", "molecule"] + cell_cols)
    g["width_pct"] = np.where(g.lower > 0, (g.upper - g.lower) / g.lower * 100, np.nan)
    return g


def listing_completeness(d):
    """指摘①: 上市期間の全年度で掲載されているかを製品ごとに検証する。"""
    listed = d.groupby("医薬品コード")["年度"].agg(set)
    rows = []
    for code, (start, end) in MARKETED_YEARS.items():
        years = listed.get(code, set())
        expect = set(range(start, end + 1))
        missing_years = sorted(expect - years)
        rows.append({
            "code": code, "product": DRUG_MASTER[code][0],
            "marketed_from": start, "marketed_to": end,
            "listed_years": len(years & expect), "expected_years": len(expect),
            "missing_years": "|".join(map(str, missing_years)),
            "complete": not missing_years,
        })
    return pd.DataFrame(rows)


def build_report(pref_pb, age_pb, nat, comp):
    part = pref_pb.censor_class == "部分秘匿"
    block = pref_pb.censor_class == "ブロック秘匿"
    n_part = int(part.sum())
    n_one = int((part & (pref_pb.n_cells_censored == 1)).sum())
    n_exceed = int((part & pref_pb.exceeds_cap9).sum())
    n_block = int(block.sum())
    n_block_ex = int((block & pref_pb.exceeds_cap9).sum())
    part_a = age_pb.censor_class == "部分秘匿"
    block_a = age_pb.censor_class == "ブロック秘匿"
    n_part_a = int(part_a.sum())
    n_one_a = int((part_a & (age_pb.n_cells_censored == 1)).sum())
    n_exceed_a = int((part_a & age_pb.exceeds_cap9).sum())
    n_block_a = int(block_a.sum())
    n_block_ex_a = int((block_a & age_pb.exceeds_cap9).sum())
    total_nat = nat[nat.molecule == "ANTI_VEGF_TOTAL"]
    wmax = total_nat.width_pct.max()
    incomplete = comp[~comp.complete]

    L = []
    A = L.append
    A("# 抗VEGF薬 秘匿識別区間と収載完全性の検証（査読対応）" + DATASET_NOTE)
    A("")
    A("生成: `build_censoring_bounds_antivegf.py`（抗アレルギー点眼解析 と同一の方法論）")
    A("")
    A("## 指摘①への回答: 掲載されていない薬剤による選定バイアスはない")
    A("")
    A("本解析は処方量上位の薬剤を選んだのではなく、**抗VEGF硝子体注射薬という")
    A("クラス全体（全製品）**を対象としている。上市期間とNDB掲載年度の照合結果:")
    A("")
    if incomplete.empty:
        A("- **全10製品が、上市期間の全年度でNDBに掲載されている**（欠落年度なし）。")
        A("  外用薬で問題となった上位品目の足切りによる未収載は、本解析には存在しない。")
    else:
        A("- 掲載欠落のある製品:")
        for _, r in incomplete.iterrows():
            A(f"  - {r['product']}: 欠落年度 {r.missing_years}")
    A("- 詳細: `listing_completeness_antivegf.csv`")
    A("")
    A("## 指摘②への回答: 秘匿セルは missing の厳密復元で区間評価する")
    A("")
    A("品目×年度×区分ごとに `missing = 公表総計 − Σ開示セル` が厳密に復元できる。")
    A("各秘匿セルの真値は `[0, missing]`。総計自体が秘匿の行のみ、一次秘匿ルール")
    A(f"（総計<10）に基づき `{CAP} − Σ開示` を上限とする。")
    A("")
    A("**「秘匿セル≦9」という仮定（five/random 補完の前提）は使えない**。")
    A("補完的秘匿の実証:")
    A("")
    A(f"- 都道府県軸: 部分秘匿 {n_part} 行のうち「秘匿セルがちょうど1個」は {n_one} 行、")
    A(f"  missing が 秘匿セル数×9 を超える行は {n_exceed} 行。")
    A(f"  ブロック秘匿（全セル秘匿・総計は公表） {n_block} 行のうち {n_block_ex} 行でも")
    A("  総計が 9×セル数 を超える。")
    A(f"- 年齢性別軸: 部分秘匿 {n_part_a} 行のうち単独秘匿 {n_one_a} 行、")
    A(f"  9×セル数超は {n_exceed_a} 行。ブロック秘匿 {n_block_a} 行のうち")
    A(f"  9×セル数超は {n_block_ex_a} 行。")
    A("")
    A("すなわち単独秘匿は必ず回避され（補完的秘匿の直接証拠）、秘匿セルの大半は")
    A("閾値10を大きく超える値が巻き添えで伏せられている。")
    A("")
    A("## 区間の実際の幅")
    A("")
    A(f"- **全国合計（成分・年度別）**: 公表総計がそのまま確定値であり、区間幅は")
    A(f"  総計秘匿行（入院の少数行）由来の最大 {wmax:.3f}% に留まる。")
    A("  全国トレンド・APC・シェアの結論は秘匿の影響を受けない。")
    A("- **都道府県別・年齢性別**: `prefecture_bounds_antivegf.csv` /")
    A("  `agesex_bounds_antivegf.csv` の lower/upper を参照。値の小さい県・年齢層では")
    A("  区間が開くため、順位や比を断定する際は区間を併記すること。")
    A("- 従来の zero/five/random 感度分析（`sensitivity_imputation_antivegf.csv`）の")
    A("  five/random は上限として機能していない点に注意。識別区間としては本出力を")
    A("  正とする（zero は下限として引き続き有効）。")
    A("")
    return "\n".join(L) + "\n"


def main():
    global IN_DIR, OUT_DIR, DATASET_NOTE
    ap = argparse.ArgumentParser()
    ap.add_argument("--nokouhi", action="store_true",
                    help="公費レセプトを含まないデータ（抗VEGF薬解析/公費含まない）で解析する")
    args = ap.parse_args()
    if args.nokouhi:
        IN_DIR = os.path.join(BASE, "公費含まない", "01_抽出データ")
        OUT_DIR = os.path.join(BASE, "公費含まない", "03_解析結果", "品質管理_感度分析")
        DATASET_NOTE = "（公費含まないデータ。2024年度のみ公費なし版、2014〜2023年度は共通）"
    os.makedirs(OUT_DIR, exist_ok=True)
    pref = load("ophthalmic_injection_prefecture.csv", ["都道府県"])
    age = load("ophthalmic_injection_agesex.csv", ["性別", "年齢階級"])

    pref_pb = product_bounds(pref, "prefecture")
    age_pb = product_bounds(age, "agesex")
    pb_all = pd.concat([pref_pb, age_pb], ignore_index=True)
    p = os.path.join(OUT_DIR, "product_censoring_bounds_antivegf.csv")
    pb_all.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(pb_all)} rows)")

    nat = national_bounds(pref_pb)
    p = os.path.join(OUT_DIR, "national_bounds_antivegf.csv")
    nat.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(nat)} rows)")

    pref_cells = cell_bounds(pref, pref_pb, ["都道府県"])
    p = os.path.join(OUT_DIR, "prefecture_bounds_antivegf.csv")
    pref_cells.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(pref_cells)} rows)")

    age_cells = cell_bounds(age, age_pb, ["性別", "年齢階級"])
    p = os.path.join(OUT_DIR, "agesex_bounds_antivegf.csv")
    age_cells.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(age_cells)} rows)")

    comp = listing_completeness(pref)
    p = os.path.join(OUT_DIR, "listing_completeness_antivegf.csv")
    comp.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p, BASE)} ({len(comp)} rows, "
          f"complete={int(comp.complete.sum())}/{len(comp)})")

    p = os.path.join(OUT_DIR, "censoring_bounds_report_antivegf.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(build_report(pref_pb, age_pb, nat, comp))
    print(f"-> {os.path.relpath(p, BASE)}")


if __name__ == "__main__":
    main()
