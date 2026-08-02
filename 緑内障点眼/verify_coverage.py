"""NDBオープンデータの収載品目カバレッジと単位判定を検証する。

NDBオープンデータは第10回（2022年度分）から外用薬の収録品目が大幅に増えており、
2021年度以前は各薬効分類の上位品目しか都道府県別表に載っていない。この制約を
薬剤カテゴリごとに可視化しないと、2021→2022の増加を実態の増加と誤読してしまう。

あわせて、処方数量の単位（ｍＬ / 瓶 / 個）を品名から判定する ml_per_unit() の
規則が、単位列（2016年度以降のみ存在）と一致することを全行で検証する。

    python 緑内障点眼/verify_coverage.py

出力（一次出力先 processed*/ 配下）:
    coverage_by_year_glaucoma.csv        年度×カテゴリの収載品目数・全国数量・都道府県合計
    coverage_summary_glaucoma.txt        人間可読なカバレッジ要約と単位判定の検証結果
"""

import argparse
import os
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
        f.write(ratio.round(3).to_string() + "\n")

    print(f"\nwrote {report}")
    print(f"wrote {os.path.join(out_dir, 'coverage_by_year_glaucoma.csv')}")
    print(f"単位判定の不一致: {len(mismatch)} 件 / 照合 {len(chk):,} 行")


if __name__ == "__main__":
    main()
