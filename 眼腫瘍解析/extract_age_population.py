#!/usr/bin/env python3
"""
extract_age_population.py
総務省統計局「人口推計」各年10月1日現在（全国：年齢各歳、男女別人口）から
4群（小児 0-14 / AYA 15-39 / 成人 40-64 / 高齢者 65+）別の全国人口を算出する。

データソース: https://www.stat.go.jp/data/jinsui/{year}np/zuhyou/05k**-1.xls(x)
2015年・2020年は国勢調査年のため「人口推計」個別ページが存在しない。
本スクリプトでは前後年（2014/2016, 2019/2021）の線形補間で代用する
（build_real_covariates.py で採用済みの補間方針に合わせたもの）。

入力: data/real_covariates/raw_download/age_pop/pop_by_age_{year}.xls(x)
出力: 眼腫瘍解析/人口_4群層別化_2014_2024.csv
      （単位: 千人。総務省人口推計の値をそのまま使用）
"""
import os
import sys
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import output_dir  # noqa: E402

RAW_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "real_covariates", "raw_download", "age_pop"
)
OUT_DIR = output_dir()  # 眼腫瘍解析/processed （organize_outputs.pyで振り分ける）

FILES = {
    2014: "pop_by_age_2014.xls",
    2016: "pop_by_age_2016.xls",
    2017: "pop_by_age_2017.xls",
    2018: "pop_by_age_2018.xls",
    2019: "pop_by_age_2019.xlsx",
    2021: "pop_by_age_2021.xlsx",
    2022: "pop_by_age_2022.xlsx",
    2023: "pop_by_age_2023.xlsx",
    2024: "pop_by_age_2024.xlsx",
}

def age_to_group(age):
    if age <= 14:
        return "小児(0-14)"
    if age <= 39:
        return "AYA(15-39)"
    if age <= 64:
        return "成人(40-64)"
    return "高齢者(65+)"


def parse_year(year, filename):
    """1年分のExcel（第1表：年齢各歳、男女別人口）から年齢×人口（総人口・男女計、千人）を抽出する。"""
    fpath = os.path.join(RAW_DIR, filename)
    df = pd.read_excel(fpath, sheet_name=0, header=None)

    records = []
    # ブロック1: 列0=年齢ラベル, 列1=総人口(男女計) -> 年齢 0〜49歳
    # ブロック2: 列9=年齢ラベル, 列10=総人口(男女計) -> 年齢 50〜100歳以上
    for label_col, val_col in [(0, 1), (9, 10)]:
        for r in range(9, df.shape[0]):
            label = df.iloc[r, label_col]
            if pd.isna(label):
                continue
            label_str = str(label).strip()
            if "100" in label_str and "以上" in label_str:
                age = 100
            else:
                digits = "".join(ch for ch in label_str if ch.isdigit())
                if not digits:
                    continue
                age = int(digits)
            val = df.iloc[r, val_col]
            if pd.isna(val):
                continue
            if isinstance(val, str) and not val.strip():
                continue
            try:
                records.append({"age": age, "population_thousands": float(val)})
            except (ValueError, TypeError):
                continue

    df_year = pd.DataFrame(records)
    df_year["year"] = year
    return df_year


def main():
    all_years = {}
    for year, fname in FILES.items():
        print(f"Processing {year} from {fname} ...")
        all_years[year] = parse_year(year, fname)

    df_all = pd.concat(all_years.values(), ignore_index=True)
    df_all["age_group_4"] = df_all["age"].apply(age_to_group)

    df_grouped = (
        df_all.groupby(["year", "age_group_4"], as_index=False)["population_thousands"].sum()
    )

    # ── 2015・2020（国勢調査年、人口推計の個別ページなし）は前後年の線形補間で代用 ──
    pivot = df_grouped.pivot(index="year", columns="age_group_4", values="population_thousands")
    for missing_year, (y0, y1) in [(2015, (2014, 2016)), (2020, (2019, 2021))]:
        pivot.loc[missing_year] = (pivot.loc[y0] + pivot.loc[y1]) / 2
    pivot = pivot.sort_index()

    df_out = pivot.reset_index().melt(id_vars="year", var_name="age_group_4", value_name="population_thousands")
    df_out["is_interpolated"] = df_out["year"].isin([2015, 2020])
    df_out = df_out.sort_values(["age_group_4", "year"])

    out_path = os.path.join(OUT_DIR, "人口_4群層別化_2014_2024.csv")
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Saved: {out_path} (shape={df_out.shape})")

    # 検算: 全年齢合計が総務省公表の総人口（千人）と概ね一致するか
    check = df_out.groupby("year")["population_thousands"].sum()
    print("\n年別 総人口（4群合計, 千人）:")
    print(check)


if __name__ == "__main__":
    main()
