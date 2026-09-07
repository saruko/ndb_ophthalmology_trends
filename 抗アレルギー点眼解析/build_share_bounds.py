# -*- coding: utf-8 -*-
"""シェア（構成比）の識別区間を計算する（Supplementary Table S8）。

秘匿セルにより各成分の数量は [lower, upper] の区間でしか同定できない。分子と分母が
同じ秘匿セルを共有するシェアにも、したがって理論上の最小・最大が存在する。

  share_lower_i = x_lo_i / (x_lo_i + Σ_{j≠i} x_hi_j)
  share_upper_i = x_hi_i / (x_hi_i + Σ_{j≠i} x_lo_j)

自成分を下限・他成分を上限に置いたとき最小、その逆で最大になる。build_bounded_outputs.py
の GE シェア、build_share_table_ge_fig.py の Table 3、build_submission_files.py の
Fig 4B・Fig 1C と同一の式（`bounds()` を共有）。

入力: 論文図表/csv/Tables_123_bounds__Table1_FY2024.csv（Table 1: 2024年度の9成分）
      論文図表/csv/Fig4_trends_shares_bounds__Fig4A_per100k.csv（Fig 4B: 主要3成分×年度）
      論文図表/csv/Fig1_age_sex_profile_bounds__Fig1B_{drug}.csv（Fig 1C: 年齢階級別）
出力: 論文図表/csv/SupplTable_S8_share_bounds.xlsx
      （投稿用へは build_submission_files.py が SupplTableS8.xlsx としてコピーする）
"""
import os

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE, "05_論文成果物", "公費含めない_new", "論文図表", "csv")
DRUGS = ["Epinastine", "Olopatadine", "Levocabastine"]


def bounds(lo, hi):
    """lo/hi: それぞれ 系列名 -> 値 の dict。構成比（%）の下限・上限を返す。"""
    out = {}
    for k in lo:
        others_hi = sum(v for j, v in hi.items() if j != k)
        others_lo = sum(v for j, v in lo.items() if j != k)
        out[k] = (lo[k] / (lo[k] + others_hi) * 100,
                  hi[k] / (hi[k] + others_lo) * 100)
    return out


def _rows(lo, hi, key, label):
    b = bounds(lo, hi)
    tot = sum(lo.values())
    for k in lo:
        s_lo, s_hi = b[k]
        yield {label: key, "Drug": k, "Value_lower": lo[k], "Value_upper": hi[k],
               "Share_pct_point": lo[k] / tot * 100,
               "Share_pct_min": s_lo, "Share_pct_max": s_hi,
               "Share_width_pp": s_hi - s_lo}


def table1_9agents():
    """2024年度、9成分合計に占める各成分の構成比（Table 1 の「9成分中シェア」列）。"""
    t = pd.read_csv(os.path.join(CSV, "Tables_123_bounds__Table1_FY2024.csv"),
                    encoding="utf-8-sig")
    t = t[~t.Drug.isin(["Top 3 total", "All 9 agents"])]
    lo = dict(zip(t.Drug, t.Volume_mL_lower))
    hi = dict(zip(t.Drug, t.Volume_mL_upper))
    out = pd.DataFrame(_rows(lo, hi, 2024, "Fiscal year")).drop(columns="Fiscal year")
    out = out.rename(columns={"Value_lower": "Volume_mL_lower",
                              "Value_upper": "Volume_mL_upper",
                              "Share_pct_point": "Share_of_9_agents_pct_point",
                              "Share_pct_min": "Share_of_9_agents_pct_min",
                              "Share_pct_max": "Share_of_9_agents_pct_max"})
    ge = t[["Drug", "GE_share_pct_lower", "GE_share_pct_upper"]].copy()
    ge["GE_share_width_pp"] = ge.GE_share_pct_upper - ge.GE_share_pct_lower
    return out.merge(ge, on="Drug")


def fig4b_top3():
    """2014〜2024年度、主要3成分合計に占める各成分の構成比（Fig 4B の数値版）。"""
    r = pd.read_csv(os.path.join(CSV, "Fig4_trends_shares_bounds__Fig4A_per100k.csv"),
                    encoding="utf-8-sig")
    rows = []
    for _, x in r.iterrows():
        lo = {d: x[d + "_lower"] for d in DRUGS}
        hi = {d: x[d + "_upper"] for d in DRUGS}
        rows += list(_rows(lo, hi, int(x["Year"]), "Fiscal year"))
    out = pd.DataFrame(rows).rename(columns={"Value_lower": "Per100k_lower",
                                             "Value_upper": "Per100k_upper"})
    return out.sort_values(["Drug", "Fiscal year"],
                           key=lambda s: s.map({d: i for i, d in enumerate(DRUGS)}).fillna(s))


def fig1c_age():
    """2024年度、年齢階級別の主要3成分構成比（Fig 1C・§3.2 の数値版）。"""
    age = {}
    for drug in DRUGS:
        d = pd.read_csv(os.path.join(
            CSV, "Fig1_age_sex_profile_bounds__Fig1B_%s.csv" % drug), encoding="utf-8-sig")
        for _, x in d.iterrows():
            age.setdefault(x["Age Group"], {})[drug] = (x["Total_lower"], x["Total_upper"])
    rows = []
    for a, d in age.items():
        rows += list(_rows({k: v[0] for k, v in d.items()},
                           {k: v[1] for k, v in d.items()}, a, "Age group"))
    return pd.DataFrame(rows).rename(columns={"Value_lower": "Per100k_lower",
                                              "Value_upper": "Per100k_upper"})


NOTES = [
    "シェア（構成比）の識別区間 — Supplementary Table S8",
    "",
    "NDB オープンデータでは 1,000 未満のセルが秘匿されるため、各成分の処方数量は",
    "点推定ではなく区間 [lower, upper] としてしか同定できない。分子と分母が同じ",
    "秘匿セルを共有するシェアも、したがって理論上の最小値・最大値をもつ。",
    "",
    "  Share_min_i = x_lo_i / (x_lo_i + Σ_{j≠i} x_hi_j)",
    "  Share_max_i = x_hi_i / (x_hi_i + Σ_{j≠i} x_lo_j)",
    "",
    "自成分を下限・他成分を上限に置いたとき最小、その逆で最大になる。",
    "本研究のシェアはすべてこの式で算出している（Table 1・Table 3、Fig 1C・4B・5A・5B・6A・6B）。",
    "",
    "Share_pct_point は図に描いた値（全成分を下限＝公表値として計算した比）で、",
    "最小と最大の中間に位置する。",
    "",
    "Table1_9agents: 2024年度、9成分合計に占める各成分の構成比（Table 1 の該当列）。",
    "  GE_share_pct_lower/upper は先発/後発シェアの区間（Table 1 由来）。",
    "Fig4B_top3: 2014〜2024年度、主要3成分合計に占める各成分の構成比（Fig 4B の数値版）。",
    "  2021年度以前は品目非掲載の影響で区間が広い（2014年度で最大37.7ポイント）。",
    "Fig1C_age: 2024年度、年齢階級別の主要3成分構成比（Fig 1C・本文§3.2 の数値版）。",
    "  Fig 1C は100歳以上を除いて描いている（区間が広すぎるため。Fig 1A・1B と同じ扱い）。",
    "",
    "生成: build_share_bounds.py",
]


def main():
    out = os.path.join(CSV, "SupplTable_S8_share_bounds.xlsx")
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        pd.DataFrame({"Note": NOTES}).to_excel(w, sheet_name="Notes", index=False)
        table1_9agents().to_excel(w, sheet_name="Table1_9agents", index=False)
        fig4b_top3().to_excel(w, sheet_name="Fig4B_top3", index=False)
        fig1c_age().to_excel(w, sheet_name="Fig1C_age", index=False)
    print("-> %s" % out)


if __name__ == "__main__":
    main()
