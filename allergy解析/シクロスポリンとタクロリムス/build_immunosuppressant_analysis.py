# -*- coding: utf-8 -*-
"""
免疫抑制点眼薬（シクロスポリン／タクロリムス）サブ解析

親解析（allergy解析）の抗アレルギー点眼薬全体解析から、免疫抑制点眼薬2成分
（シクロスポリン点眼液＝パピロックミニ、タクロリムス点眼液＝タリムス）だけを
抜き出して、年齢性別・都道府県・年度推移の3軸で記述する。

解析手法は
  論文に使うファイルたち/公費含まない/allergy_paper_draft_kouhihukumanai.md
の Methods に準拠する。すなわち:
  - 全11年度で「公費レセプトを含まない」集計表を使用（2024年度は nokouhi 版）
  - 全国集計には秘匿されない公表「総計（処方数量）」列を使用
  - 都道府県別・年齢性別別は内訳セル（秘匿はゼロ補完）を使用
  - 秘匿セルの真値区間 [0, 1000) を利用した識別区間の感度分析（0補完 vs 999補完）
  - 人口分母は総務省人口推計（各年10月1日現在）

親解析との相違点（本サブ解析で追加した点）:
  親解析は全成分の処方数量を一律「mL」として合算しているが、免疫抑制点眼薬2剤の
  NDB上の数量単位は mL ではない（パピロックミニ＝「個」/0.4mL、タリムス＝「瓶」/5mL）。
  2成分を合算する指標では単位が混在するため、本サブ解析では各剤の
  「素の数量（個・瓶）」と「mL換算値」を併記し、2剤合計は mL換算値のみで算出する。

出力先: 本スクリプトと同じディレクトリ
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
RAW = os.path.join(ROOT, "data", "raw")
NOKOUHI = os.path.join(RAW, "ndb_2024_nokouhi")
COVARIATES = os.path.join(ROOT, "data", "covariates", "prefecture_covariates.csv")
POP_AGE_SEX = os.path.join(ROOT, "allergy解析", "02_中間データ", "population_age_sex.csv")

YEARS = list(range(2014, 2025))

# 対象2成分。ml_per_unit は NDB「単位」列1単位あたりの容量（mL）。
DRUGS = {
    "CYCLOSPORINE": {
        "name": "シクロスポリン点眼（パピロックミニ0.1% 0.4mL）",
        "patterns": ["シクロスポリン", "パピロック"],
        "unit": "個",
        "ml_per_unit": 0.4,
    },
    "TACROLIMUS": {
        "name": "タクロリムス点眼（タリムス0.1% 5mL）",
        "patterns": ["タクロリムス", "タリムス"],
        "unit": "瓶",
        "ml_per_unit": 5.0,
    },
}
IMMUNO_ML = "IMMUNO_ML"
IMMUNO_ML_NAME = "免疫抑制点眼薬2剤合計（mL換算）"

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

AGE_ORDER = ["0-4", "5-9", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39",
             "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70-74", "75-79",
             "80-84", "85-89", "90+", "90-94", "95-99", "100+"]

AGE_MIDPOINTS = {"0-4": 2, "5-9": 7, "10-14": 12, "15-19": 17, "20-24": 22,
                 "25-29": 27, "30-34": 32, "35-39": 37, "40-44": 42, "45-49": 47,
                 "50-54": 52, "55-59": 57, "60-64": 62, "65-69": 67, "70-74": 72,
                 "75-79": 77, "80-84": 82, "85-89": 87, "90-94": 92, "95-99": 97,
                 "100+": 100, "90+": 92}

MASK_TOKENS = {"-", "—", "－", ""}


def pref_file(year):
    if year == 2024:
        return os.path.join(NOKOUHI, "ndb_gaiyo_2024_nokouhi.xlsx")
    return os.path.join(RAW, f"ndb_gaiyo_{year}.xlsx")


def agesex_file(year):
    if year == 2024:
        return os.path.join(NOKOUHI, "ndb_gaiyo_agesex_2024_nokouhi.xlsx")
    return os.path.join(RAW, "ndb_age_sex", f"ndb_gaiyo_agesex_{year}.xlsx")


def classify(drug_name):
    """医薬品名から対象2成分のコードを返す。点眼液以外・対象外は None。"""
    if "点眼" not in drug_name:
        return None
    for code, meta in DRUGS.items():
        if any(p in drug_name for p in meta["patterns"]):
            return code
    return None


def clean_value(val, imputation="zero"):
    """秘匿セル（'-'）の補完。真値は区間 [0, 1000)。zero=下限, upper(999)=上限。"""
    if pd.isna(val) or str(val).strip() in MASK_TOKENS:
        return 999.0 if imputation == "upper" else 0.0
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return 0.0


def normalize_age(label):
    """「0～4歳」→「0-4」、「90歳以上」→「90+」"""
    import re
    s = re.sub(r"\s", "", str(label))
    m = re.match(r"^(\d+)～(\d+)歳$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d+)歳以上$", s)
    if m:
        return f"{m.group(1)}+"
    return None


# ── 抽出 ───────────────────────────────────────────────────────────

def load_prefecture_year(year, imputation="zero"):
    """1年度分の都道府県別シート（院内・院外・入院）から2成分を抽出する。

    Returns: (pref_records, national_records)
      pref_records:     year, prefecture, code, count
      national_records: year, code, count_published, count_detail, total_masked
    """
    path = pref_file(year)
    xl = pd.ExcelFile(path)
    pref_rows, nat_rows = [], []

    for sheet in [s for s in xl.sheet_names if "外用薬" in s]:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        row2 = [str(x) for x in df.iloc[2]]
        row3 = [str(x).strip() for x in df.iloc[3]]
        total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
        if total_col is None:
            continue

        pref_col_map = {i: row3[i] for i in range(total_col + 1, min(total_col + 48, df.shape[1]))
                        if row3[i] in PREFECTURES}
        if not pref_col_map:
            pref_col_map = {total_col + 1 + i: p for i, p in enumerate(PREFECTURES)
                            if total_col + 1 + i < df.shape[1]}

        df[0] = df[0].ffill()
        for r in range(4, len(df)):
            if str(df.iloc[r, 0]).strip() != "131":
                continue
            code = classify(str(df.iloc[r, 3]).strip())
            if code is None:
                continue

            raw_total = df.iloc[r, total_col]
            detail = 0.0
            for col, pref in pref_col_map.items():
                v = clean_value(df.iloc[r, col], imputation)
                detail += v
                pref_rows.append({"year": year, "prefecture": pref,
                                  "code": code, "count": v})
            nat_rows.append({
                "year": year, "code": code,
                "count_published": clean_value(raw_total, imputation),
                "count_detail": detail,
                "total_masked": int(pd.isna(raw_total)
                                    or str(raw_total).strip() in MASK_TOKENS),
            })
    return pref_rows, nat_rows


def load_agesex_year(year, imputation="zero"):
    """1年度分の年齢性別シートから2成分を抽出する。"""
    path = agesex_file(year)
    xl = pd.ExcelFile(path)
    rows = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        row2 = [str(x) for x in df.iloc[2]]
        row3 = [str(x) for x in df.iloc[3]]
        total_col = next((i for i, v in enumerate(row2) if "総計" in v), None)
        if total_col is None:
            continue

        import re
        sex_map, last = {}, None
        for i in range(total_col + 1, df.shape[1]):
            v = re.sub(r"\s", "", row2[i])
            if v.startswith("男"):
                last = "male"
            elif v.startswith("女"):
                last = "female"
            age = normalize_age(row3[i])
            if last and age:
                sex_map[i] = (last, age)

        df[0] = df[0].ffill()
        for r in range(4, len(df)):
            if str(df.iloc[r, 0]).strip() != "131":
                continue
            code = classify(str(df.iloc[r, 3]).strip())
            if code is None:
                continue
            for col, (sex, age) in sex_map.items():
                raw = df.iloc[r, col]
                rows.append({
                    "year": year, "code": code, "sex": sex, "age_group": age,
                    "count": clean_value(raw, imputation),
                    "masked": int(pd.isna(raw) or str(raw).strip() in MASK_TOKENS),
                })
    return rows


def extract_all(imputation="zero", verbose=True):
    """全年度の都道府県別・年齢性別・全国総計を抽出する。"""
    pref_rows, nat_rows, as_rows = [], [], []
    for year in YEARS:
        if verbose:
            print(f"  {year} ...")
        p, n = load_prefecture_year(year, imputation)
        pref_rows += p
        nat_rows += n
        as_rows += load_agesex_year(year, imputation)

    pref = (pd.DataFrame(pref_rows)
            .groupby(["year", "prefecture", "code"], as_index=False)["count"].sum())
    nat = (pd.DataFrame(nat_rows)
           .groupby(["year", "code"], as_index=False)
           .agg(count_published=("count_published", "sum"),
                count_detail=("count_detail", "sum"),
                total_masked=("total_masked", "sum")))
    ages = (pd.DataFrame(as_rows)
            .groupby(["year", "code", "sex", "age_group"], as_index=False)
            .agg(count=("count", "sum"), n_masked=("masked", "sum")))
    return pref, nat, ages


def add_ml(df, count_col="count", out_col="count_ml"):
    df = df.copy()
    df[out_col] = df[count_col] * df["code"].map({c: m["ml_per_unit"] for c, m in DRUGS.items()})
    return df


def drug_name(code):
    return IMMUNO_ML_NAME if code == IMMUNO_ML else DRUGS[code]["name"]


def drug_unit(code):
    """`count` 系の列が何の単位かを返す。出力CSVを自己記述的にするために付与する。"""
    return "mL" if code == IMMUNO_ML else DRUGS[code]["unit"]


# ── 解析 ───────────────────────────────────────────────────────────

def gini(values):
    a = np.sort(np.asarray(values, dtype=float)) + 1e-7
    n = a.size
    idx = np.arange(1, n + 1)
    return float(np.sum((2 * idx - n - 1) * a) / (n * np.sum(a)))


def apc_loglinear(years, rates):
    """対数線形回帰による年平均変化率（APC）と95%CI。"""
    rates = np.maximum(np.asarray(rates, dtype=float), 1e-3)
    res = sm.OLS(np.log(rates), sm.add_constant(np.asarray(years, dtype=float))).fit()
    b, se = res.params[1], res.bse[1]
    return {"apc": (np.exp(b) - 1) * 100,
            "apc_low": (np.exp(b - 1.96 * se) - 1) * 100,
            "apc_high": (np.exp(b + 1.96 * se) - 1) * 100,
            "p_value": res.pvalues[1], "r2": res.rsquared, "n_years": len(rates)}


def build_national(nat, cov):
    """全国トレンド（公表総計基準）。2剤合計はmL換算でのみ算出する。"""
    pop = cov.groupby("year", as_index=False).agg(
        population_total=("population_total", "sum"),
        population_65plus=("population_65plus", "sum"))

    df = nat.merge(pop, on="year", how="left")
    df["unit"] = df["code"].map({c: m["unit"] for c, m in DRUGS.items()})
    df["ml_per_unit"] = df["code"].map({c: m["ml_per_unit"] for c, m in DRUGS.items()})
    df["count_ml"] = df["count_published"] * df["ml_per_unit"]
    df["count_per_100k"] = df["count_published"] / df["population_total"] * 1e5
    df["count_ml_per_100k"] = df["count_ml"] / df["population_total"] * 1e5
    df["censoring_loss"] = df["count_published"] - df["count_detail"]
    df["censoring_loss_pct"] = np.where(df["count_published"] > 0,
                                        df["censoring_loss"] / df["count_published"] * 100, np.nan)

    # 2剤合計（mL換算のみ）
    tot = df.groupby("year", as_index=False).agg(
        count_ml=("count_ml", "sum"),
        population_total=("population_total", "first"),
        population_65plus=("population_65plus", "first"))
    tot["code"] = IMMUNO_ML
    tot["unit"] = "mL"
    tot["count_ml_per_100k"] = tot["count_ml"] / tot["population_total"] * 1e5

    out = pd.concat([df, tot], ignore_index=True)
    out["procedure_name"] = out["code"].map(drug_name)
    cols = ["year", "code", "procedure_name", "unit", "ml_per_unit",
            "count_published", "count_detail", "total_masked",
            "censoring_loss", "censoring_loss_pct", "count_ml",
            "population_total", "population_65plus",
            "count_per_100k", "count_ml_per_100k"]
    return out[[c for c in cols if c in out.columns]].sort_values(["code", "year"])


def build_prefecture(pref, cov):
    df = pref.merge(cov, on=["year", "prefecture"], how="left")
    df = add_ml(df)
    df["count_per_100k"] = df["count"] / df["population_total"] * 1e5
    df["count_ml_per_100k"] = df["count_ml"] / df["population_total"] * 1e5
    df["aging_rate"] = df["population_65plus"] / df["population_total"]
    df["docs_per_100k"] = df["ophthalmologists"] / df["population_total"] * 1e5
    df["facilities_per_100k"] = df["facilities"] / df["population_total"] * 1e5

    # 2剤合計（mL換算）
    tot = df.groupby(["year", "prefecture"], as_index=False).agg(
        count_ml=("count_ml", "sum"),
        population_total=("population_total", "first"),
        population_65plus=("population_65plus", "first"),
        ophthalmologists=("ophthalmologists", "first"),
        facilities=("facilities", "first"))
    tot["code"] = IMMUNO_ML
    tot["count"] = np.nan
    tot["count_per_100k"] = np.nan
    tot["count_ml_per_100k"] = tot["count_ml"] / tot["population_total"] * 1e5
    tot["aging_rate"] = tot["population_65plus"] / tot["population_total"]
    tot["docs_per_100k"] = tot["ophthalmologists"] / tot["population_total"] * 1e5
    tot["facilities_per_100k"] = tot["facilities"] / tot["population_total"] * 1e5

    out = pd.concat([df, tot], ignore_index=True)
    out["procedure_name"] = out["code"].map(drug_name)
    out["unit"] = out["code"].map(drug_unit)
    return out.sort_values(["code", "year", "prefecture"])


def build_age_sex(ages, pop_as):
    df = ages.merge(pop_as, on=["year", "sex", "age_group"], how="left")
    if df["population"].isna().any():
        bad = df[df["population"].isna()][["year", "sex", "age_group"]].drop_duplicates()
        raise ValueError(f"人口分母が結合できません:\n{bad}")
    df = add_ml(df)
    df["count_per_100k"] = df["count"] / df["population"] * 1e5
    df["count_ml_per_100k"] = df["count_ml"] / df["population"] * 1e5

    both = df.groupby(["year", "code", "age_group"], as_index=False).agg(
        count=("count", "sum"), count_ml=("count_ml", "sum"),
        population=("population", "sum"), n_masked=("n_masked", "sum"))
    both["sex"] = "both"
    both["count_per_100k"] = both["count"] / both["population"] * 1e5
    both["count_ml_per_100k"] = both["count_ml"] / both["population"] * 1e5

    out = pd.concat([df, both[df.columns]], ignore_index=True)
    out["procedure_name"] = out["code"].map(drug_name)
    out["unit"] = out["code"].map(drug_unit)
    order = {a: i for i, a in enumerate(AGE_ORDER)}
    out["_o"] = out["age_group"].map(order)
    if out["_o"].isna().any():
        raise ValueError(f"未知の年齢区分: {sorted(out[out._o.isna()].age_group.unique())}")
    return out.sort_values(["code", "year", "sex", "_o"]).drop(columns="_o")


def build_mf_ratio(rates):
    """男女比は同一剤内の比であり、単位換算に対して不変（比で相殺される）。"""
    df = rates[rates["sex"].isin(["male", "female"])]
    wide = df.pivot_table(index=["year", "code", "procedure_name", "age_group"],
                          columns="sex", values=["count", "count_per_100k"])
    wide.columns = [f"{v}_{s}" for v, s in wide.columns]
    wide = wide.reset_index()
    wide["mf_ratio_count"] = wide["count_male"] / wide["count_female"]
    wide["mf_ratio_rate"] = wide["count_per_100k_male"] / wide["count_per_100k_female"]
    wide["unit"] = wide["code"].map(drug_unit)
    order = {a: i for i, a in enumerate(AGE_ORDER)}
    wide["_o"] = wide["age_group"].map(order)
    return wide.sort_values(["code", "year", "_o"]).drop(columns="_o")


def build_age_distribution(rates):
    """年齢分布シェアと加重平均処方年齢（男女合算）。

    いずれも同一剤内の構成比・加重平均であり、単位換算（正の定数倍）に対して不変。
    """
    both = rates[rates["sex"] == "both"].copy()
    both["share_pct"] = both.groupby(["year", "code"])["count"].transform(
        lambda s: s / s.sum() * 100 if s.sum() > 0 else np.nan)
    both["midpoint"] = both["age_group"].map(AGE_MIDPOINTS)

    both["unit"] = both["code"].map(drug_unit)
    dist = both[["year", "code", "procedure_name", "unit", "age_group", "count",
                 "population", "count_per_100k", "share_pct"]]

    def wma(g):
        t = g["count"].sum()
        return (g["count"] * g["midpoint"]).sum() / t if t > 0 else np.nan

    w = (both.groupby(["year", "code", "procedure_name"])[["count", "midpoint"]]
         .apply(wma).reset_index(name="weighted_mean_age"))
    return dist, w.sort_values(["code", "year"])


def build_disparity(pref_df):
    rows = []
    for (year, code), g in pref_df.groupby(["year", "code"]):
        col = "count_ml_per_100k"
        r = g[col].to_numpy(dtype=float)
        if np.all(r == 0) or np.isnan(r).any():
            continue
        mean = r.mean()
        imin, imax = int(np.argmin(r)), int(np.argmax(r))
        # 秘匿ゼロ補完により最小値が0になる県があるため、最大/最小比は
        # 0の県を除いた「非ゼロ最小」に対する比も併記する。
        nz = r[r > 0]
        rows.append({
            "year": year, "code": code, "procedure_name": drug_name(code),
            "metric": col,
            "mean_rate": mean,
            "cv": r.std(ddof=1) / mean if mean > 0 else np.nan,
            "gini": gini(r),
            "min_prefecture": g["prefecture"].iloc[imin], "min_rate": r[imin],
            "max_prefecture": g["prefecture"].iloc[imax], "max_rate": r[imax],
            "max_to_min_ratio": r[imax] / r[imin] if r[imin] > 0 else np.nan,
            "max_to_min_ratio_nonzero": r[imax] / nz.min() if nz.size else np.nan,
            "top5_mean": np.sort(r)[-5:].mean(),
            "bottom5_mean": np.sort(r)[:5].mean(),
            "top5_to_bottom5_ratio": (np.sort(r)[-5:].mean() / np.sort(r)[:5].mean()
                                      if np.sort(r)[:5].mean() > 0 else np.nan),
            "n_zero_prefectures": int((r == 0).sum()),
        })
    return pd.DataFrame(rows).sort_values(["code", "year"])


def build_correlation(pref_df):
    rows = []
    for (year, code), g in pref_df.groupby(["year", "code"]):
        v = g[["count_ml_per_100k", "aging_rate", "docs_per_100k",
               "facilities_per_100k", "population_total"]].dropna()
        if len(v) < 5 or v["count_ml_per_100k"].std() == 0:
            continue
        rate = v["count_ml_per_100k"]
        # Spearman順位相関は単調変換に不変であり、素の数量ベースでもmL換算ベースでも
        # 値は完全に一致する（単位換算は正の定数倍のため）。
        rec = {"year": year, "code": code, "procedure_name": drug_name(code),
               "metric": "count_ml_per_100k", "n_prefectures": len(v)}
        for var in ["aging_rate", "docs_per_100k", "facilities_per_100k", "population_total"]:
            rho, p = spearmanr(rate, v[var])
            rec[f"rho_{var}"] = rho
            rec[f"p_{var}"] = p
        rows.append(rec)
    return pd.DataFrame(rows).sort_values(["code", "year"])


def build_apc(nat_df):
    rows = []
    for code, g in nat_df.groupby("code"):
        g = g[g["count_ml_per_100k"] > 0].sort_values("year")
        if len(g) < 3:
            continue
        r = apc_loglinear(g["year"].to_numpy(), g["count_ml_per_100k"].to_numpy())
        r.update({"code": code, "procedure_name": drug_name(code),
                  "start_year": int(g["year"].min()), "end_year": int(g["year"].max()),
                  "years_observed": ";".join(str(int(y)) for y in g["year"]),
                  "metric": "count_ml_per_100k"})
        rows.append(r)
    cols = ["code", "procedure_name", "metric", "start_year", "end_year", "n_years",
            "years_observed", "apc", "apc_low", "apc_high", "p_value", "r2"]
    return pd.DataFrame(rows)[cols]


def build_panel(pref_df, out_dir):
    """被説明変数は count_ml_per_100k（mL換算）。回帰係数はスケールに依存するため、
    どの指標に対する係数かを `dependent_variable` 列に明記する。"""
    rows = []
    for code, g in pref_df.groupby("code"):
        panel = g.set_index(["prefecture", "year"])[
            ["count_ml_per_100k", "aging_rate", "docs_per_100k", "facilities_per_100k"]].dropna()
        if panel.index.get_level_values("year").nunique() < 3:
            print(f"  panel skip {code}: 年度数不足")
            continue
        try:
            res = PanelOLS(panel["count_ml_per_100k"],
                           panel[["aging_rate", "docs_per_100k", "facilities_per_100k"]],
                           entity_effects=True, time_effects=True
                           ).fit(cov_type="clustered", cluster_entity=True)
        except Exception as e:  # noqa: BLE001
            print(f"  panel failed {code}: {e}")
            continue
        for var in ["aging_rate", "docs_per_100k", "facilities_per_100k"]:
            rows.append({"code": code, "procedure_name": drug_name(code),
                         "dependent_variable": "count_ml_per_100k", "variable": var,
                         "coefficient": res.params[var], "std_err": res.std_errors[var],
                         "t_stat": res.tstats[var], "p_value": res.pvalues[var],
                         "r2_within": res.rsquared_within, "n_obs": res.nobs})
        with open(os.path.join(out_dir, f"panel_regression_{code}_report.txt"),
                  "w", encoding="utf-8") as f:
            f.write(str(res))
    return pd.DataFrame(rows)


def build_sensitivity(nat_zero, pref_zero, ages_zero, nat_up, pref_up, ages_up, cov):
    """秘匿セルの識別区間（0補完＝下限, 999補完＝上限）。"""
    rows = []
    for code in DRUGS:
        for year in sorted(nat_zero["year"].unique()):
            def get(df, keys, col):
                s = df
                for k, v in keys.items():
                    s = s[s[k] == v]
                return float(s[col].sum())

            pub = get(nat_zero, {"year": year, "code": code}, "count_published")
            if pub == 0:
                continue
            rows.append({
                "year": year, "code": code, "procedure_name": drug_name(code),
                "unit": drug_unit(code),
                "national_published": pub,
                "pref_detail_zero": get(pref_zero, {"year": year, "code": code}, "count"),
                "pref_detail_upper": get(pref_up, {"year": year, "code": code}, "count"),
                "agesex_detail_zero": get(ages_zero, {"year": year, "code": code}, "count"),
                "agesex_detail_upper": get(ages_up, {"year": year, "code": code}, "count"),
            })
    df = pd.DataFrame(rows)
    df["pref_interval_width_pct"] = (df["pref_detail_upper"] / df["pref_detail_zero"] - 1) * 100
    df["agesex_interval_width_pct"] = (df["agesex_detail_upper"] / df["agesex_detail_zero"] - 1) * 100
    df["pref_capture_rate_pct"] = df["pref_detail_zero"] / df["national_published"] * 100
    df["agesex_capture_rate_pct"] = df["agesex_detail_zero"] / df["national_published"] * 100
    return df.sort_values(["code", "year"])


def build_disparity_sensitivity(pref_zero, pref_up, cov):
    """地域格差指標の秘匿補完感度（0補完 vs 999補完）。"""
    dz = build_disparity(build_prefecture(pref_zero, cov))
    du = build_disparity(build_prefecture(pref_up, cov))
    m = dz.merge(du, on=["year", "code"], suffixes=("_zero", "_upper"))
    return m[["year", "code", "procedure_name_zero",
              "max_to_min_ratio_zero", "max_to_min_ratio_upper",
              "max_to_min_ratio_nonzero_zero", "max_to_min_ratio_nonzero_upper",
              "cv_zero", "cv_upper", "gini_zero", "gini_upper",
              "n_zero_prefectures_zero", "n_zero_prefectures_upper"]].rename(
        columns={"procedure_name_zero": "procedure_name"})


# ── 出力 ───────────────────────────────────────────────────────────

def save(df, name):
    # 出力はフォルダ直下。実行後に organize_outputs.py で 01〜04 へ振り分ける
    path = os.path.join(BASE, name)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  → {name} ({len(df)} rows)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 64)
    print(" 免疫抑制点眼薬（シクロスポリン／タクロリムス）サブ解析")
    print(" データ: NDBオープンデータ 第1〜11回（全年度 公費レセプトを含まない）")
    print("=" * 64)

    cov = pd.read_csv(COVARIATES)
    cov["prefecture"] = cov["prefecture"].str.strip()
    pop_as = pd.read_csv(POP_AGE_SEX)

    print("\n[1/3] 主解析データ抽出（秘匿セル: ゼロ補完）")
    pref_z, nat_z, ages_z = extract_all("zero")

    print("\n[2/3] 感度分析データ抽出（秘匿セル: 999補完＝識別区間の上限）")
    pref_u, nat_u, ages_u = extract_all("upper")

    print("\n[3/3] 解析・出力")
    national = build_national(nat_z, cov)
    prefecture = build_prefecture(pref_z, cov)
    rates = build_age_sex(ages_z, pop_as)
    mf = build_mf_ratio(rates)
    dist, wma = build_age_distribution(rates)

    save(national, "national_trends_immuno.csv")
    save(build_apc(national), "apc_immuno.csv")
    save(rates, "age_sex_rates_immuno.csv")
    save(mf, "mf_ratio_by_age_immuno.csv")
    save(dist, "age_distribution_immuno.csv")
    save(wma, "weighted_mean_age_immuno.csv")
    save(prefecture, "prefecture_immuno.csv")

    # 都道府県ピボット（人口10万対, mL換算）
    piv = prefecture.pivot_table(index=["prefecture", "code", "procedure_name"],
                                 columns="year", values="count_ml_per_100k")
    piv.columns = [f"{int(y)}年_人口10万対mL" for y in piv.columns]
    piv = piv.reset_index()
    save(piv, "prefecture_per_capita_pivot_immuno.csv")

    rank = prefecture[prefecture["year"] == 2024][
        ["prefecture", "code", "procedure_name", "unit", "count", "count_ml",
         "population_total", "count_ml_per_100k"]].copy()
    rank["rank_2024"] = rank.groupby("code")["count_ml_per_100k"].rank(
        ascending=False, method="min").astype(int)
    rank = rank.sort_values(["code", "rank_2024"])
    save(rank, "prefecture_ranking_2024_immuno.csv")

    save(build_disparity(prefecture), "geographic_disparity_immuno.csv")
    save(build_correlation(prefecture), "covariate_correlation_immuno.csv")

    panel = build_panel(prefecture, BASE)
    if not panel.empty:
        save(panel, "panel_regression_summary_immuno.csv")

    save(build_sensitivity(nat_z, pref_z, ages_z, nat_u, pref_u, ages_u, cov),
         "censoring_sensitivity_immuno.csv")
    save(build_disparity_sensitivity(pref_z, pref_u, cov),
         "censoring_sensitivity_disparity_immuno.csv")

    print("\n完了。出力先:", BASE)


if __name__ == "__main__":
    main()
