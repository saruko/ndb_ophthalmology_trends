"""NDBオープンデータの収載品目カバレッジと単位判定を検証する。

NDBオープンデータは第10回（2022年度分）から外用薬の収録品目が大幅に増えており、
2021年度以前は各薬効分類の上位品目しか都道府県別表に載っていない。この制約を
薬剤カテゴリごとに可視化しないと、2021→2022の増加を実態の増加と誤読してしまう。

あわせて、処方数量の単位（ｍＬ / 瓶 / 個）を品名から判定する ml_per_unit() の
規則が、単位列（2016年度以降のみ存在）と一致することを全行で検証する。

さらに年齢性別表の完全性を検証する。NDBオープンデータには、公表『総計』欄に
数百万mL規模の値がありながら年齢性別セルが全て秘匿されている行が存在し、
年齢性別表に基づく集計ではその行が丸ごと失われる。通常のセル単位の秘匿
（1,000未満）では説明できない量であり、年齢層別解析の可否を左右するため、
年度ごとの回収率として明示する。

    python 緑内障点眼解析/verify_coverage.py

出力（一次出力先 processed*/ 配下）:
    coverage_by_year_glaucoma.csv        年度×カテゴリの収載品目数・全国数量・都道府県合計
    agesex_completeness_glaucoma.csv     品目×年度の年齢性別セル合計と公表総計の対照
    coverage_summary_glaucoma.txt        人間可読なカバレッジ要約と単位判定の検証結果
"""

import argparse
import os
import re
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from preprocess_glaucoma import (  # noqa: E402
    PREFECTURES, base_name, classify_drug, clean_count_value, ml_per_unit,
)
from paths import add_nokouhi_arg, output_dir, raw_file  # noqa: E402

YEARS = range(2014, 2025)


def scan_year(path, year):
    """1年度分の外用薬ファイルから品目単位の行を収集する。"""
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
            factor = ml_per_unit(name)
            pref_sum = sum(clean_count_value(df.iloc[r, c]) for c in pref_cols)
            n_censored = sum(1 for c in pref_cols
                             if str(df.iloc[r, c]).strip() in ["-", "—", "－"])
            rows.append({
                "year": year,
                "sheet": sheet,
                "code": res[0],
                "product": base_name(name),
                "unit_published": str(df.iloc[r, unit_col]).strip() if unit_col is not None else "",
                "ml_per_unit": factor,
                "total_published": clean_count_value(df.iloc[r, total_col]),
                "pref_sum": pref_sum,
                "n_censored_pref": n_censored,
            })
    return rows


_AGE_RE = re.compile(r"^(\d+～\d+歳|\d+歳以上)$")


def scan_agesex_year(path, year):
    """1年度分の年齢性別表から、行の公表総計と年齢性別セル合計を収集する。"""
    rows = []
    xl = pd.ExcelFile(path)
    for sheet in [s for s in xl.sheet_names if "外用薬" in s]:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        df[0] = df[0].ffill()
        row2 = [str(x) for x in df.iloc[2]]
        row3 = [str(x) for x in df.iloc[3]]
        total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
        if total_col is None:
            continue

        cell_cols, last = [], None
        for i in range(total_col + 1, df.shape[1]):
            v = re.sub(r"\s", "", row2[i])
            if v.startswith("男") or v.startswith("女"):
                last = v[0]
            if last and _AGE_RE.match(re.sub(r"\s", "", row3[i])):
                cell_cols.append(i)
        if not cell_cols:
            continue

        for r in range(4, len(df)):
            if str(df.iloc[r, 0]).strip() != "131":
                continue
            name = str(df.iloc[r, 3]).strip()
            if "点眼" not in name:
                continue
            res = classify_drug(name)
            if res is None:
                continue
            factor = ml_per_unit(name)
            total = clean_count_value(df.iloc[r, total_col]) * factor
            cell_sum = sum(clean_count_value(df.iloc[r, c]) for c in cell_cols) * factor
            n_censored = sum(1 for c in cell_cols
                             if str(df.iloc[r, c]).strip() in ["-", "—", "－"])
            rows.append({
                "year": year,
                "sheet": sheet,
                "code": res[0],
                "product": base_name(name),
                "total_published_ml": total,
                "agesex_sum_ml": cell_sum,
                "n_cells": len(cell_cols),
                "n_censored_cells": n_censored,
                "fully_suppressed": bool(total > 0 and cell_sum == 0),
            })
    return rows


def find_listing_gaps(df):
    """前後の年度には収載されているのに、その年度だけ品目行が存在しない箇所を洗い出す。

    セル単位の秘匿（数量1,000未満）とは別物で、行そのものが公表対象から外れている。
    該当年度の薬効群合計は品目1つ分まるごと過小になるため、年次差を実態として
    解釈してよいかの判断材料になる。欠落量は前後年度の平均で見積もる。
    """
    d = df[df["code"] != "APRACLONIDINE"].copy()
    d["total_ml"] = d["total_published"] * d["ml_per_unit"]
    w = (d.groupby(["product", "year"])["total_ml"].sum().unstack()
         .reindex(columns=list(YEARS)))
    code = d.drop_duplicates("product").set_index("product")["code"]
    rows = []
    for prod, r in w.iterrows():
        yrs = [y for y in w.columns if pd.notna(r[y])]
        if len(yrs) < 2:
            continue
        for y in range(min(yrs), max(yrs) + 1):
            if pd.isna(r[y]):
                prev = max(a for a in yrs if a < y)
                nxt = min(a for a in yrs if a > y)
                rows.append({"year": y, "product": prod, "code": code[prod],
                             "prev_year": prev, "prev_ml": r[prev],
                             "next_year": nxt, "next_ml": r[nxt],
                             "expected_missing_ml": (r[prev] + r[nxt]) / 2})
    gaps = pd.DataFrame(rows, columns=["year", "product", "code", "prev_year",
                                       "prev_ml", "next_year", "next_ml",
                                       "expected_missing_ml"])
    gaps = gaps.sort_values(["year", "expected_missing_ml"],
                            ascending=[True, False])
    total = d.groupby("year")["total_ml"].sum()
    agg = gaps.groupby("year")["expected_missing_ml"].agg(["size", "sum"])
    gap_year = pd.DataFrame({
        "year": list(YEARS),
        "n_missing_products": agg["size"].reindex(YEARS).fillna(0).astype(int).values,
        "published_total_ml": total.reindex(YEARS).values,
        "expected_missing_ml": agg["sum"].reindex(YEARS).fillna(0).values})
    gap_year["understated_pct"] = (
        gap_year["expected_missing_ml"]
        / (gap_year["published_total_ml"] + gap_year["expected_missing_ml"]) * 100)
    return gaps, gap_year


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

    # ── 年齢性別表の完全性 ──
    ag_rows = []
    for year in YEARS:
        path = raw_file("ndb_gaiyo_agesex", year, args.nokouhi, agesex=True)
        if not os.path.exists(path):
            continue
        print(f"  scanning {year} (age-sex) ...")
        ag_rows += scan_agesex_year(path, year)
    ag = pd.DataFrame(ag_rows)
    ag = ag[ag["code"] != "APRACLONIDINE"]
    ag.to_csv(os.path.join(out_dir, "agesex_completeness_glaucoma.csv"),
              index=False, encoding="utf-8-sig")
    ag_year = ag.groupby("year").agg(
        n_rows=("product", "size"),
        n_fully_suppressed=("fully_suppressed", "sum"),
        total_published_ml=("total_published_ml", "sum"),
        agesex_sum_ml=("agesex_sum_ml", "sum")).reset_index()
    ag_year["recovered_pct"] = (ag_year["agesex_sum_ml"]
                                / ag_year["total_published_ml"] * 100)
    ag_year["lost_ml"] = ag_year["total_published_ml"] - ag_year["agesex_sum_ml"]

    # ── 系列途中の収載欠落 ──
    gaps, gap_year = find_listing_gaps(df)
    gaps.to_csv(os.path.join(out_dir, "listing_gaps_glaucoma.csv"),
                index=False, encoding="utf-8-sig")

    # ── 単位判定の検証 ──
    chk = df[df["unit_published"] != ""].copy()
    chk["predicted"] = chk["ml_per_unit"].apply(lambda v: "ｍＬ" if v == 1.0 else "容器")
    chk["actual"] = chk["unit_published"].apply(
        lambda u: "ｍＬ" if u == "ｍＬ" else ("容器" if u in ("個", "瓶") else u))
    mismatch = chk[chk["predicted"] != chk["actual"]]

    # ── 年度×カテゴリのカバレッジ ──
    cov = df.groupby(["year", "code"]).agg(
        n_products=("product", "nunique"),
        total_published_ml=("total_published", lambda s: 0.0),
        pref_sum_ml=("pref_sum", lambda s: 0.0),
        n_censored_cells=("n_censored_pref", "sum"),
    ).reset_index()
    # mL換算は行ごとに係数が違うため別途集計する
    df["total_ml"] = df["total_published"] * df["ml_per_unit"]
    df["pref_ml"] = df["pref_sum"] * df["ml_per_unit"]
    sums = df.groupby(["year", "code"])[["total_ml", "pref_ml"]].sum().reset_index()
    cov = cov.drop(columns=["total_published_ml", "pref_sum_ml"]).merge(
        sums, on=["year", "code"])
    cov = cov.rename(columns={"total_ml": "total_published_ml", "pref_ml": "pref_sum_ml"})
    # 都道府県合計 / 全国総計。秘匿により1を下回るほど都道府県別データが欠ける
    cov["pref_coverage_ratio"] = cov["pref_sum_ml"] / cov["total_published_ml"].replace(0, pd.NA)
    cov.to_csv(os.path.join(out_dir, "coverage_by_year_glaucoma.csv"),
               index=False, encoding="utf-8-sig")

    n_prod = cov.pivot(index="year", columns="code", values="n_products").fillna(0).astype(int)

    report = os.path.join(out_dir, "coverage_summary_glaucoma.txt")
    with open(report, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write(" NDB緑内障点眼薬 収載カバレッジ・単位判定の検証\n")
        f.write("=" * 70 + "\n\n")

        f.write("1. 単位判定（品名ベース）と公表『単位』列の一致\n")
        f.write("-" * 70 + "\n")
        f.write(f" 照合対象行数（単位列のある2016〜2024年度）: {len(chk):,}\n")
        f.write(f" 不一致: {len(mismatch)} 件\n")
        if len(mismatch):
            for _, r in mismatch.drop_duplicates("product").iterrows():
                f.write(f"   ★ {r['year']} {r['product']} "
                        f"（公表={r['unit_published']} / 判定={r['predicted']}）\n")
        else:
            f.write(" → すべて一致。品名から単位を判定しmLへ統一換算する方法は妥当。\n")
        f.write("\n 容器単位（瓶・個）としてmL換算した品目:\n")
        for _, r in df[df["ml_per_unit"] != 1.0].drop_duplicates("product").iterrows():
            f.write(f"   {r['product']} → {r['ml_per_unit']} mL/数量\n")
        f.write("\n")

        f.write("2. 年度別の収載品目数（薬剤カテゴリ×年度）\n")
        f.write("-" * 70 + "\n")
        f.write("※NDBオープンデータは第10回（2022年度分）から外用薬の収録品目が大幅に増えた。\n")
        f.write("  2021年度以前に品目数が少ないカテゴリは、実態の処方量ではなく収載の制約を見ている。\n\n")
        f.write(n_prod.to_string() + "\n\n")

        f.write("3. カバレッジ判定（全期間で収載されているか）\n")
        f.write("-" * 70 + "\n")
        for code in sorted(n_prod.columns):
            yrs = [y for y in n_prod.index if n_prod.loc[y, code] > 0]
            missing = [y for y in n_prod.index if n_prod.loc[y, code] == 0]
            if not missing:
                verdict = "全年度収載"
            elif set(missing) <= {2014}:
                verdict = "2014年度のみ未収載（第1回は上位品目のみ）"
            elif min(yrs) >= 2022:
                verdict = "★2022年度以降のみ収載（経年比較・APCは不可）"
            else:
                verdict = f"★欠測年あり: {missing}"
            f.write(f" - {code:16s} 収載 {len(yrs):2d}/11年度  {verdict}\n")
        f.write("\n")

        f.write("4. 都道府県別データの捕捉率（都道府県合計 / 全国総計, mLベース）\n")
        f.write("-" * 70 + "\n")
        f.write("※秘匿（数量1,000未満）により都道府県別の合計は全国総計を下回る。\n")
        f.write("  比が著しく低いカテゴリは都道府県別解析の対象として不適切。\n\n")
        ratio = cov.pivot(index="year", columns="code", values="pref_coverage_ratio")
        f.write(ratio.round(3).to_string() + "\n\n")

        f.write("5. 年齢性別表の完全性（年齢性別セル合計 / 公表総計, mLベース）\n")
        f.write("-" * 70 + "\n")
        f.write("※公表『総計』欄に値がありながら年齢性別セルが全て秘匿されている行がある。\n")
        f.write("  セル単位の秘匿（1,000未満）では説明できない量であり、該当行は年齢層別\n")
        f.write("  解析から丸ごと失われる。回収率が低い年度は年齢層別の年次比較に使えない。\n\n")
        f.write(ag_year.assign(
            recovered_pct=ag_year["recovered_pct"].round(1),
            total_published_ml=ag_year["total_published_ml"].round(0),
            agesex_sum_ml=ag_year["agesex_sum_ml"].round(0),
            lost_ml=ag_year["lost_ml"].round(0)).to_string(index=False) + "\n\n")
        lost = ag[ag["fully_suppressed"]].nlargest(10, "total_published_ml")
        if len(lost):
            f.write(" 全面秘匿された行のうち数量の大きいもの:\n")
            for _, r in lost.iterrows():
                f.write(f"   ★ {r['year']} {r['product']}（{r['sheet']}）"
                        f" 総計 {r['total_published_ml']:,.0f} mL\n")
        worst = ag_year[ag_year["recovered_pct"] < 99]["year"].tolist()
        f.write(f"\n → 回収率99%未満の年度: {worst}\n")
        f.write("   年齢層別の年次比較はこれらの年度を除いて解釈すること。\n\n")

        f.write("6. 系列途中の収載欠落（前後の年度には収載されている品目）\n")
        f.write("-" * 70 + "\n")
        f.write("※セル単位の秘匿ではなく、品目行そのものがその年度だけ公表対象から外れている。\n")
        f.write("  該当年度の薬効群合計は品目1つ分まるごと過小になる。欠落量は前後年度の平均。\n\n")
        f.write(gap_year.assign(
            published_total_ml=gap_year["published_total_ml"].round(0),
            expected_missing_ml=gap_year["expected_missing_ml"].round(0),
            understated_pct=gap_year["understated_pct"].round(2)
        ).to_string(index=False) + "\n\n")
        if len(gaps):
            f.write(" 欠落の内訳:\n")
            for _, r in gaps.iterrows():
                f.write(f"   ★ {r['year']} {r['product']}"
                        f"（{r['prev_year']}年度 {r['prev_ml']:,.0f} mL / "
                        f"{r['next_year']}年度 {r['next_ml']:,.0f} mL）"
                        f" 推定欠落 {r['expected_missing_ml']:,.0f} mL\n")
        worst2 = gap_year[gap_year["understated_pct"] >= 1]["year"].tolist()
        f.write(f"\n → 1%以上過小な年度: {worst2}\n")
        f.write("   これらの年度をまたぐ変化を実態として解釈しないこと。\n")

    print(f"\nwrote {report}")
    print(f"wrote {os.path.join(out_dir, 'coverage_by_year_glaucoma.csv')}")
    print(f"単位判定の不一致: {len(mismatch)} 件 / 照合 {len(chk):,} 行")


if __name__ == "__main__":
    main()
