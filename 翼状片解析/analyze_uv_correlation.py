# -*- coding: utf-8 -*-
"""
紫外線（JMA UVインデックス / Open-Meteo 日射量）と翼状片手術（K224）の相関解析

解析A: 都道府県ごとの時系列相関
  各都道府県内で、年次の紫外線量と手術率（人口10万対）の相関（Pearson/Spearman）
  ※Nは最大10-11年と小さいため、参考解析（多重比較はBH法でFDR補正）

解析B: 年ごとの横断相関
  各年度で、47都道府県の紫外線量と手術率の相関（Pearson/Spearman）

対象setting: outpatient(2015-2024) / inpatient(2015-2024, 2017欠測) / total(2014-2024, 2017欠測)
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import find, uv_path, output_dir  # noqa: E402

OUT_DIR = output_dir()

UV_SOURCES = {
    "jma_uv": {
        "path": uv_path("jma_uv_index_annual_mean.csv"),
        "value_col": "uv_index_annual_mean",
        "label": "JMA UVインデックス(年平均)",
    },
    "openmeteo_radiation": {
        "path": uv_path("openmeteo_radiation_annual_mean.csv"),
        "value_col": "radiation_annual_mean",
        "label": "Open-Meteo 全天日射量(年平均)",
    },
}

SETTINGS = ["outpatient", "inpatient", "total"]


def bh_fdr(pvals):
    """Benjamini-Hochberg法によるFDR補正q値"""
    p = np.asarray(pvals, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    # 単調性の担保
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(n)
    q[order] = np.minimum(ranked, 1.0)
    return q


def load_merged():
    """手術率データと紫外線データをマージした縦持ちDataFrameを返す"""
    df_rate = pd.read_csv(find("pterygium_rate_per100k.csv"))
    df_rate = df_rate[["year", "prefecture", "setting", "count", "count_per_100k"]]

    merged = {}
    for src, cfg in UV_SOURCES.items():
        df_uv = pd.read_csv(cfg["path"])[["year", "prefecture", cfg["value_col"]]]
        df_uv = df_uv.rename(columns={cfg["value_col"]: "uv_value"})
        df = pd.merge(df_rate, df_uv, on=["year", "prefecture"], how="inner")
        merged[src] = df
    return merged


def analysis_a_prefecture_timeseries(merged):
    """解析A: 都道府県ごとに年次の紫外線量と手術率の時系列相関"""
    results = []
    for src, df in merged.items():
        for setting in SETTINGS:
            df_s = df[df["setting"] == setting]
            for pref, g in df_s.groupby("prefecture"):
                g = g.dropna(subset=["uv_value", "count_per_100k"])
                if len(g) < 5:
                    continue
                r_p, p_p = stats.pearsonr(g["uv_value"], g["count_per_100k"])
                r_s, p_s = stats.spearmanr(g["uv_value"], g["count_per_100k"])
                results.append({
                    "uv_source": src, "setting": setting, "prefecture": pref,
                    "n_years": len(g),
                    "pearson_r": r_p, "pearson_p": p_p,
                    "spearman_rho": r_s, "spearman_p": p_s,
                })
    df_res = pd.DataFrame(results)
    # uv_source × setting ごとに47県分のp値をBH補正
    df_res["pearson_q"] = np.nan
    df_res["spearman_q"] = np.nan
    for (src, setting), idx in df_res.groupby(["uv_source", "setting"]).groups.items():
        df_res.loc[idx, "pearson_q"] = bh_fdr(df_res.loc[idx, "pearson_p"].values)
        df_res.loc[idx, "spearman_q"] = bh_fdr(df_res.loc[idx, "spearman_p"].values)
    return df_res


def analysis_b_yearly_crosssection(merged):
    """解析B: 年ごとに47都道府県の紫外線量と手術率の横断相関"""
    results = []
    for src, df in merged.items():
        for setting in SETTINGS:
            df_s = df[df["setting"] == setting]
            for year, g in df_s.groupby("year"):
                g = g.dropna(subset=["uv_value", "count_per_100k"])
                if len(g) < 30:
                    continue
                r_p, p_p = stats.pearsonr(g["uv_value"], g["count_per_100k"])
                r_s, p_s = stats.spearmanr(g["uv_value"], g["count_per_100k"])
                results.append({
                    "uv_source": src, "setting": setting, "year": year,
                    "n_prefectures": len(g),
                    "pearson_r": r_p, "pearson_p": p_p,
                    "spearman_rho": r_s, "spearman_p": p_s,
                })
    return pd.DataFrame(results)


def write_summary(df_a, df_b, out_path):
    lines = []
    w = lines.append
    w("=" * 60)
    w(" 紫外線量と翼状片手術（K224）の相関解析 サマリー")
    w("=" * 60)
    w("")
    w("【解析A】都道府県ごとの時系列相関（年次UV vs 手術率, N=9-11年）")
    w("-" * 60)
    for (src, setting), g in df_a.groupby(["uv_source", "setting"]):
        n_sig_raw = (g["spearman_p"] < 0.05).sum()
        n_sig_fdr = (g["spearman_q"] < 0.05).sum()
        w(f"[{src} × {setting}] 対象{len(g)}県")
        w(f"  Spearman rho 中央値: {g['spearman_rho'].median():+.3f} "
          f"(範囲 {g['spearman_rho'].min():+.3f} ~ {g['spearman_rho'].max():+.3f})")
        w(f"  p<0.05: {n_sig_raw}県 / FDR補正後 q<0.05: {n_sig_fdr}県")
        if n_sig_fdr > 0:
            for _, row in g[g["spearman_q"] < 0.05].iterrows():
                w(f"    - {row['prefecture']}: rho={row['spearman_rho']:+.3f} "
                  f"(p={row['spearman_p']:.4f}, q={row['spearman_q']:.4f})")
        w("")
    w("※ 注意: 各県N=9-11年の小標本であり検出力が低い。またUV・手術率の双方に")
    w("  経年トレンドがあると見かけの相関が生じうる（時系列の擬似相関）。参考解析。")
    w("")
    w("【解析B】年ごとの横断相関（47都道府県のUV vs 手術率）")
    w("-" * 60)
    for (src, setting), g in df_b.groupby(["uv_source", "setting"]):
        w(f"[{src} × {setting}]")
        for _, row in g.sort_values("year").iterrows():
            sig = "*" if row["spearman_p"] < 0.05 else " "
            w(f"  {int(row['year'])}: Pearson r={row['pearson_r']:+.3f} (p={row['pearson_p']:.2e}) | "
              f"Spearman rho={row['spearman_rho']:+.3f} (p={row['spearman_p']:.2e}) {sig}")
        w(f"  → 全年度平均: Pearson r={g['pearson_r'].mean():+.3f}, "
          f"Spearman rho={g['spearman_rho'].mean():+.3f}")
        w("")
    w("※ UVデータは暦年、NDBは年度（4月-3月）集計のため約3ヶ月のズレがある。")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Saved {out_path}")


def main():
    merged = load_merged()
    for src, df in merged.items():
        n = df.groupby("setting")["year"].agg(["min", "max", "count"])
        print(f"[{src}] merged rows:\n{n}")

    df_a = analysis_a_prefecture_timeseries(merged)
    df_b = analysis_b_yearly_crosssection(merged)

    out_a = os.path.join(OUT_DIR, "uv_correlation_by_prefecture.csv")
    out_b = os.path.join(OUT_DIR, "uv_correlation_by_year.csv")
    df_a.to_csv(out_a, index=False, encoding="utf-8-sig")
    df_b.to_csv(out_b, index=False, encoding="utf-8-sig")
    print(f"Saved {out_a} ({len(df_a)} rows)")
    print(f"Saved {out_b} ({len(df_b)} rows)")

    write_summary(df_a, df_b, os.path.join(OUT_DIR, "uv_correlation_summary.txt"))


if __name__ == "__main__":
    main()
