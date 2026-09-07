# -*- coding: utf-8 -*-
"""公表済み集計表（`05_論文成果物/公費含まない_旧版凍結/` の各CSV）を、秘匿セルの
識別区間（下限・上限）つきで再生成する。

## 旧版との違い

`05_論文成果物/公費含まない_旧版凍結/censoring_sensitivity_allergy.csv` は既に秘匿感度分析を
一度行っているが、次の2点で本スクリプトとは異なる。

1. **粒度が国内合計のみ**。都道府県別・年齢性別の内訳には秘匿区間を持たせていない。
   国内合計は秘匿の影響がほぼ無視できるほど小さい（本スクリプトのⅠ章で確認）一方、
   都道府県別・年齢性別の内訳は品目によっては秘匿の影響が無視できない。
2. **各秘匿セルを一律 0〜999 で補完**していた。本スクリプトは公表されている
   「総計」列を使い、**同じ行の中の秘匿セルの合計値**（`missing`）を先に確定させる。
3. **単位を無視して成分をまたいで合算**していた。本スクリプトは全量をmLに
   正規化してから合算する（下記）。

## 算出方法

対象データはすべて `01_抽出データ/product_pref_long.csv`・`product_agesex_long.csv`・
`product_level_censoring.csv`・`product_agesex_censoring.csv`（build_extract.py が生成）。

- **下限**: 秘匿セルを0とみなす。
- **上限**: 秘匿セル1つあたり `missing`（総計 − 公表済みセルの合計）。
  総計自体が秘匿の行（「総計秘匿」）は `missing` が不明なため、
  代わりに `999 − 公表済みセルの合計` を上限として使う（総計<1,000という
  事実は分かっているため、これでも真の上限を上回ることはない）。

上限に999を使わない理由は、NDBが補完的秘匿（complementary suppression）を
行っているため。実データでも「秘匿セルがちょうど1個」の行は都道府県軸・
年齢性別軸とも0行で、`missing` が 秘匿セル数×999 を超える行が都道府県軸に8行・
年齢性別軸に41行ある（＝閾値1,000を超えるセルが巻き添えで伏せられている）。
したがって「秘匿セルは必ず1,000未満」という前提は使えず、
「各セルは非負」「行内の秘匿セルの合計は missing に一致」という2つの事実だけから
各セルの真値を [0, missing] と押さえる。

**単位の正規化**: 9成分の処方数量の単位は ｍＬ（エピナスチン・オロパタジン・
レボカバスチン）、瓶＝5mL（他6成分）、個＝0.35mL（インタールUD）が混在する。
成分をまたぐ集計（ALLERGY_EYE_TOTAL 等）は必ずmL換算後に行う。詳細は src/units.py。

**軸ごとの `missing` の違い**: 都道府県軸と年齢性別軸では同じ品目でも `missing` が
異なる（例: 2016年度のアレジオンは都道府県軸では全県開示だが年齢性別軸では
全42セルがブロック秘匿）。各軸の縦持ちには必ず同じ軸の品目レベルCSVを使う。

出力: 05_論文成果物/公費含めない_new/
  national_trends_bounds.csv        全国トレンド（成分×年度）の件数・人口10万対の下限/上限
  prefecture_per_capita_bounds.csv  都道府県別・成分×年度の人口10万対の下限/上限（縦持ち）
  prefecture_ranking_bounds.csv     都道府県別・全体合計の人口10万対ランキング（下限/上限つき）
  agesex_bounds.csv                 年齢階級・性別・成分×年度の件数・人口10万対の下限/上限
  brand_generic_share_bounds.csv    先発/後発シェアの下限/上限
  bounded_outputs_report.md         算出方法・妥当性・旧ファイルとの対応の解説
"""
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from drug_master import (ANTI_HIST_CODES, DRUG_NAME_JA, DRUG_ORDER,  # noqa: E402
                         MED_RELEASE_CODES)
from ndb_reader import CENSOR_THRESHOLD, PREFECTURES  # noqa: E402
from paths import BASE_DIR, COVARIATE_PATH, INPUT_DIR, INTERIM_DIR, ensure  # noqa: E402

OUT = os.path.join(BASE_DIR, "05_論文成果物", "公費含めない_new")
CAP = CENSOR_THRESHOLD - 1  # 999

AGG_CODES = [
    ("ALLERGY_EYE_TOTAL", "抗アレルギー点眼薬（全体合計）", DRUG_ORDER),
    ("ANTI_HIST", "抗ヒスタミン点眼薬（合計）", ANTI_HIST_CODES),
    ("MED_RELEASE", "メディエーター遊離抑制点眼薬（合計）", MED_RELEASE_CODES),
    ("TOP3_TOTAL", "主要3成分合計（エピナスチン・オロパタジン・レボカバスチン）",
     ("EPINASTINE", "OLOPATADINE", "LEVOCASTINE")),
]
ALL_CODE_NAMES = {c: DRUG_NAME_JA[c] for c in DRUG_ORDER}
ALL_CODE_NAMES.update({c: n for c, n, _ in AGG_CODES})


def load_level(csv_name="product_level_censoring.csv"):
    """品目レベルの秘匿情報を読み、秘匿セル1個あたりの上限を付与する。

    都道府県軸（product_level_censoring.csv）と年齢性別軸
    （product_agesex_censoring.csv）は **missing が別物** なので、
    それぞれの軸の縦持ちには必ず同じ軸のファイルを渡すこと。
    例: 2016年度のアレジオンは都道府県軸では全県開示（missing=0）だが、
    年齢性別軸では全42セルがブロック秘匿（missing=2,950万）である。
    """
    d = pd.read_csv(os.path.join(INPUT_DIR, csv_name))

    # 秘匿セル1個あたりの上限（原単位）。
    #
    # 以前は min(999, missing) を使っていたが、これは誤りだった。NDBは
    # 補完的秘匿（complementary suppression）を行っており、閾値1,000を
    # 上回るセルでも「単独秘匿だと総計から逆算できてしまう」場合に
    # 巻き添えで伏せられる。実データでも部分秘匿行に「秘匿セルがちょうど1個」
    # の行は一件も存在せず（都道府県軸・年齢性別軸とも0行）、
    # missing が 秘匿セル数×999 を超える行が都道府県軸8行・年齢性別軸41行ある。
    # したがって「秘匿セルは必ず1,000未満」という前提は成立しない。
    #
    # 正しい上限は次の2つの事実だけから導く（追加の仮定を置かない）。
    #   ・各秘匿セルは非負
    #   ・同じ行の秘匿セルの合計は missing にちょうど一致する
    # よって各セルの真値は [0, missing] に収まる。集計時は1つの出力行
    # （例: ある都道府県）が各品目行から高々1セルしか受け取らないため、
    # この上限をそのまま加算してよい。
    #
    # 総計秘匿の行は missing が不明だが、総計 < 1,000 は確定しているので
    # 「999 − 公表済みセル合計」を上限に使える。
    d["per_cell_cap"] = np.where(
        d.total_censored,
        (CAP - d.sum_disclosed).clip(lower=0),
        d.missing.clip(lower=0))
    return d


def _attach_bounds(l, level, key):
    """縦持ちセルに下限・上限を付け、mL換算値も用意する。"""
    l = l.merge(level[key + ["per_cell_cap", "ml_factor"]], on=key, how="left",
                suffixes=("", "_lvl"))
    if "ml_factor_lvl" in l.columns:
        l["ml_factor"] = l["ml_factor"].fillna(l["ml_factor_lvl"])
        l = l.drop(columns=["ml_factor_lvl"])
    l["lower"] = l["value"].fillna(0.0)
    l["upper"] = np.where(l["censored"], l["per_cell_cap"], l["value"])
    # 成分をまたぐ集計は必ずmL換算値で行う（単位が ｍＬ／瓶／個 で混在するため）
    l["lower_ml"] = l["lower"] * l["ml_factor"]
    l["upper_ml"] = l["upper"] * l["ml_factor"]
    return l


def load_pref_long(level):
    l = pd.read_csv(os.path.join(INPUT_DIR, "product_pref_long.csv"))
    return _attach_bounds(l, level, ["year", "sheet", "code", "product_name"])


def load_agesex_long(level):
    l = pd.read_csv(os.path.join(INPUT_DIR, "product_agesex_long.csv"))
    return _attach_bounds(l, level, ["year", "sheet", "code", "product_name"])


def add_aggregates(df, group_cols, code_col="code"):
    """9成分の下限/上限を合算して集計カテゴリ（ALLERGY_EYE_TOTAL等）を追加する。

    独立な行の下限どうし・上限どうしを単純合算するのは妥当
    （それぞれの行の真値が区間内のどこにあっても、合計の真値は
    Σ下限〜Σ上限の中に必ず収まる）。

    ただし成分をまたぐ合算は**必ずmL換算値**で行う。9成分の単位は
    ｍＬ（エピナスチン・オロパタジン・レボカバスチン）と
    瓶＝5mL（他6成分）、個＝0.35mL（インタールUD）が混在しており、
    原単位のまま足すと「mL＋瓶」という無意味な量になる。
    """
    out = [df]
    for agg_code, agg_name, members in AGG_CODES:
        sub = df[df[code_col].isin(members)]
        g = (sub.groupby([c for c in group_cols if c != code_col], as_index=False)
             [["lower", "upper"]].sum())
        g[code_col] = agg_code
        out.append(g)
    return pd.concat(out, ignore_index=True)


def fmt_pct(lower, upper):
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = np.where(lower > 0, (upper - lower) / lower * 100, np.nan)
    return w


# ----------------------------------------------------------------------
# 1. 全国トレンド
# ----------------------------------------------------------------------
def build_national(level):
    """全国合計（成分×年度）の下限・上限。

    総計が既知の行はその値をそのまま lower/upper 両方に使う（都道府県セルの
    秘匿は総計列には影響しないため、全国合計では確定値）。総計自体が秘匿の
    行（total_censored）だけが不確実性を持ち、その行1件の上限は
    `per_cell_cap`（= 999 − 公表済みセル合計。行の総計自体の上限であり、
    都道府県ごとに×47するものではない）を使う。
    """
    level = level.copy()
    # 成分をまたぐ集計に備え、すべてmL換算で扱う。
    level["total_ml_f"] = level["total"] * level["ml_factor"]
    level["cap_ml"] = level["per_cell_cap"] * level["ml_factor"]

    lower = (level.groupby(["year", "code"], as_index=False)
            .agg(lower=("total_ml_f", lambda s: s.fillna(0).sum())))

    known_upper = (level[~level.total_censored]
                  .groupby(["year", "code"], as_index=False)["total_ml_f"].sum()
                  .rename(columns={"total_ml_f": "known_upper"}))
    tc_upper_add = (level[level.total_censored]
                    .groupby(["year", "code"], as_index=False)
                    .agg(tc_upper_add=("cap_ml", "sum")))

    nat = lower.merge(known_upper, on=["year", "code"], how="left")
    nat = nat.merge(tc_upper_add, on=["year", "code"], how="left")
    nat[["known_upper", "tc_upper_add"]] = nat[["known_upper", "tc_upper_add"]].fillna(0.0)
    nat["upper"] = nat["known_upper"] + nat["tc_upper_add"]
    # 秘匿ゼロの成分では lower と upper が同一の値になるが、浮動小数点の
    # 加算順序の違いで upper がごく僅かに（1e-14%オーダー）下回ることがある。
    nat["upper"] = nat[["lower", "upper"]].max(axis=1)
    nat = nat[["year", "code", "lower", "upper"]]

    nat = add_aggregates(nat, ["year", "code"])

    cov = pd.read_csv(COVARIATE_PATH)
    pop_by_year = cov.groupby("year", as_index=False)["population_total"].sum()
    nat = nat.merge(pop_by_year, on="year", how="left")
    nat["per100k_lower"] = nat["lower"] / nat["population_total"] * 1e5
    nat["per100k_upper"] = nat["upper"] / nat["population_total"] * 1e5
    nat["count_width_pct"] = fmt_pct(nat["lower"], nat["upper"])
    nat["per100k_width_pct"] = fmt_pct(nat["per100k_lower"], nat["per100k_upper"])
    nat["drug"] = nat["code"].map(ALL_CODE_NAMES)
    nat = nat.rename(columns={"lower": "count_lower", "upper": "count_upper"})
    cols = ["year", "code", "drug", "count_lower", "count_upper", "count_width_pct",
           "per100k_lower", "per100k_upper", "per100k_width_pct"]
    return nat[cols].sort_values(["code", "year"])


# ----------------------------------------------------------------------
# 2. 都道府県別・成分×年度
# ----------------------------------------------------------------------
def build_prefecture(pref_long):
    g = (pref_long.groupby(["year", "code", "prefecture"], as_index=False)
        [["lower_ml", "upper_ml"]].sum()
        .rename(columns={"lower_ml": "lower", "upper_ml": "upper"}))
    g = add_aggregates(g, ["year", "code", "prefecture"])

    cov = pd.read_csv(COVARIATE_PATH)[["year", "prefecture", "population_total"]]
    g = g.merge(cov, on=["year", "prefecture"], how="left")
    g["per100k_lower"] = g["lower"] / g["population_total"] * 1e5
    g["per100k_upper"] = g["upper"] / g["population_total"] * 1e5
    g["width_pct"] = fmt_pct(g["per100k_lower"], g["per100k_upper"])
    g["drug"] = g["code"].map(ALL_CODE_NAMES)
    g = g.rename(columns={"lower": "count_lower", "upper": "count_upper"})
    cols = ["year", "code", "drug", "prefecture", "count_lower", "count_upper",
           "per100k_lower", "per100k_upper", "width_pct"]
    return g[cols].sort_values(["code", "year", "prefecture"])


def build_prefecture_ranking(pref_bounds):
    """全体合計（ALLERGY_EYE_TOTAL）の都道府県ランキングを、公表版と同じワイド形式で。"""
    d = pref_bounds[pref_bounds.code == "ALLERGY_EYE_TOTAL"]
    rows = []
    for pref, g in d.groupby("prefecture"):
        row = {"prefecture": pref}
        for _, r in g.iterrows():
            row[f"{r.year}年_人口10万対_下限"] = round(r.per100k_lower, 1)
            row[f"{r.year}年_人口10万対_上限"] = round(r.per100k_upper, 1)
        rows.append(row)
    out = pd.DataFrame(rows)
    last_year = d.year.max()
    out[f"{last_year}年_順位_下限基準"] = (
        out[f"{last_year}年_人口10万対_下限"].rank(ascending=False, method="min").astype(int))
    return out.sort_values(f"{last_year}年_人口10万対_下限", ascending=False)


# ----------------------------------------------------------------------
# 3. 年齢階級・性別・成分×年度
# ----------------------------------------------------------------------
def norm_age(label):
    s = label.replace("歳以上", "+").replace("歳", "")
    return s.replace("～", "-").replace("〜", "-").replace("~", "-")


SEX_MAP = {"男": "male", "女": "female"}


def build_agesex(agesex_long):
    l = agesex_long.copy()
    l["age_group_norm"] = l["age_group"].map(norm_age)
    l["sex_en"] = l["sex"].map(SEX_MAP)

    g = (l.groupby(["year", "code", "sex_en", "age_group_norm"], as_index=False)
        [["lower_ml", "upper_ml"]].sum()
        .rename(columns={"lower_ml": "lower", "upper_ml": "upper"}))
    g = add_aggregates(g, ["year", "code", "sex_en", "age_group_norm"])

    pop = pd.read_csv(os.path.join(INTERIM_DIR, "population_age_sex.csv"))
    pop = pop.rename(columns={"sex": "sex_en", "age_group": "age_group_norm"})
    g = g.merge(pop, on=["year", "sex_en", "age_group_norm"], how="left")
    g["per100k_lower"] = g["lower"] / g["population"] * 1e5
    g["per100k_upper"] = g["upper"] / g["population"] * 1e5
    g["width_pct"] = fmt_pct(g["per100k_lower"], g["per100k_upper"])
    g["drug"] = g["code"].map(ALL_CODE_NAMES)
    g = g.rename(columns={"lower": "count_lower", "upper": "count_upper",
                          "sex_en": "sex", "age_group_norm": "age_group"})
    cols = ["year", "code", "drug", "sex", "age_group", "count_lower", "count_upper",
           "population", "per100k_lower", "per100k_upper", "width_pct"]
    return g[cols].sort_values(["code", "year", "sex", "age_group"])


# ----------------------------------------------------------------------
# 4. 先発/後発シェア
# ----------------------------------------------------------------------
def build_brand_generic(level):
    """先発/後発の数量下限・上限。都道府県セル単位ではなく品目の総計秘匿のみが不確実性の源。"""
    l = level.copy()
    l["is_generic"] = l.product_type.str.startswith("generic")
    # 数量はmL換算で持つ（同一成分・同一年度なら単位は揃うのでシェア自体は
    # 換算の有無に依らないが、数量列の意味をファイル全体でmLに統一する）。
    tot_ml = l["total"] * l["ml_factor"]
    l["lower"] = tot_ml.fillna(0.0)
    l["upper"] = np.where(l.total_censored, CAP * l["ml_factor"], tot_ml)

    rows = []
    for code in DRUG_ORDER:
        for year in sorted(l.year.unique()):
            g = l[(l.code == code) & (l.year == year)]
            if g.empty:
                continue
            b = g[~g.is_generic]
            ge = g[g.is_generic]
            b_lo, b_hi = b.lower.sum(), b.upper.sum()
            g_lo, g_hi = ge.lower.sum(), ge.upper.sum()
            tot_lo, tot_hi = b_lo + g_lo, b_hi + g_hi
            # シェア = 後発/(後発+先発) の下限・上限。分子・分母は独立に動けるので、
            # 下限は「後発を最小・先発を最大」、上限は「後発を最大・先発を最小」で
            # 組む（分母を tot_hi/tot_lo と組むと分子だけ動かした形になり、
            # 上限が100%を超えるなど非整合な値になるため誤り）。
            share_lo = g_lo / (g_lo + b_hi) * 100 if (g_lo + b_hi) else None
            share_hi = g_hi / (g_hi + b_lo) * 100 if (g_hi + b_lo) else None
            rows.append({
                "year": year, "code": code, "drug": DRUG_NAME_JA[code],
                "quantity_brand_lower": b_lo, "quantity_brand_upper": b_hi,
                "quantity_generic_lower": g_lo, "quantity_generic_upper": g_hi,
                "total_lower": tot_lo, "total_upper": tot_hi,
                "share_pct_generic_lower": share_lo, "share_pct_generic_upper": share_hi,
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# レポート
# ----------------------------------------------------------------------
def fmt(v, dec=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.{dec}f}"


def build_report(nat, pref, agesex, bg):
    L = []
    A = L.append
    A("# 秘匿区間つき集計表の再生成")
    A("")
    A("`05_論文成果物/公費含まない_旧版凍結/` にある公表済み集計表（全国トレンド・都道府県別・")
    A("年齢性別・先発/後発シェア）を、秘匿セルの識別区間（下限・上限）つきで再生成した。")
    A("")
    A("- **データ基準**: 公費レセプトを含まない集計（2024年度は `ndb_gaiyo_2024_nokouhi.xlsx`）")
    A("- **対象**: 9成分＋集計カテゴリ4種（全体合計・抗ヒスタミン・メディエーター遊離抑制・主要3成分）")
    A("- **生成**: `build_extract.py` → `build_bounded_outputs.py`")
    A("")
    A("## 既存ファイルとの対応")
    A("")
    A("| 旧版（公費含まない_旧版凍結/） | 本再生成版（公費含めない_new/） | 何が変わったか |")
    A("|---|---|---|")
    A("| national_trends_allergy.csv | national_trends_bounds.csv | 各年度・成分に下限/上限を追加 |")
    A("| prefecture_per_capita_by_drug_allergy.csv | prefecture_per_capita_bounds.csv | 同上（都道府県別） |")
    A("| prefecture_per_capita_ranking_allergy.csv | prefecture_ranking_bounds.csv | ランキングに下限/上限を併記 |")
    A("| age_sex_rates_allergy.csv | agesex_bounds.csv | 同上（年齢階級・性別） |")
    A("| brand_generic_share.csv | brand_generic_share_bounds.csv | GE比率に下限/上限を追加 |")
    A("| censoring_sensitivity_allergy.csv | national_trends_bounds.csv で代替 | 下記Ⅰ章参照 |")
    A("")
    A("---")
    A("")
    A("## Ⅰ. 算出方法と、旧 `censoring_sensitivity_allergy.csv` との違い")
    A("")
    A("外用薬の処方数量は**1,000未満のセルが「-」で秘匿**される。品目単位（品目×年度×")
    A("処方区分）で見ると、公表されている「総計」列から公表済みセルの合計を引けば、")
    A("**その行の秘匿セル全部を合わせた真の合計値（`missing`）が exact に分かる**。")
    A("")
    A("```")
    A("missing = 総計 − Σ(公表済みセル)")
    A("行内の秘匿セル1個あたりの上限 = missing")
    A("```")
    A("")
    A("旧 `censoring_sensitivity_allergy.csv` はこの `missing` を使わず、秘匿セルを")
    A("一律999で補完していた。しかし**999という上限は使えない**。NDBは")
    A("補完的秘匿（complementary suppression）を行っており、閾値1,000を上回るセルでも")
    A("「単独秘匿だと総計から逆算できてしまう」場合に巻き添えで伏せられるためである。")
    A("")
    A("実データでもそれが確認できる。")
    A("")
    A("- 部分秘匿の行で「秘匿セルがちょうど1個」の行は**都道府県軸・年齢性別軸とも0行**")
    A("  （単独秘匿は必ず回避されている＝補完的秘匿の直接的な証拠）")
    A("- `missing` が 秘匿セル数×999 を超える行が**都道府県軸に8行・年齢性別軸に41行**")
    A("  存在する（例: 2022年度 外来（院外）のパタノールは秘匿2セルで `missing`=11,380）")
    A("")
    A("そこで本スクリプトは999を使わず、次の2つの事実だけから上限を導く。")
    A("")
    A("- 各秘匿セルは非負")
    A("- 同じ行の秘匿セルの合計は `missing` にちょうど一致する")
    A("")
    A("したがって各セルの真値は `[0, missing]` に収まる。集計時は1つの出力行")
    A("（例: ある都道府県、ある年齢階級）が各品目行から高々1セルしか受け取らないため、")
    A("この上限をそのまま加算してよい。")
    A("")
    A("総計自体が秘匿の行（総計秘匿）は `missing` が計算できないため、代わりに")
    A("「999 − 公表済みセルの合計」を上限とする（総計が1,000未満という事実だけは")
    A("分かっているため、これでも真の上限を上回ることはない）。")
    A("")
    A("下限は全ファイル共通で「秘匿セル＝0」。独立な行の下限どうし・上限どうしを")
    A("単純合算しても、真値は必ずその区間に収まる（合算の下限・上限としての性質は")
    A("保存される）ため、都道府県別・年齢性別の値をさらに9成分で合算した")
    A("集計カテゴリ（全体合計等）にもそのまま適用できる。")
    A("")
    A("**検証**: 都道府県別・年齢性別の下限/上限を全区分にわたって合計すると、")
    A("公表「総計」から直接計算できる真の全国値を必ず挟む。成分×年度の61組すべてで")
    A("両軸ともこれが成立することを確認済み。")
    A("")
    A("### 単位の正規化（成分をまたぐ合算の前提）")
    A("")
    A("9成分の処方数量は単位が揃っていない。**正規化せずに合算すると値が成立しない。**")
    A("")
    A("| 単位 | 該当成分 | mL換算 |")
    A("|---|---|--:|")
    A("| ｍＬ | エピナスチン・オロパタジン・レボカバスチン | ×1 |")
    A("| 瓶 | ケトチフェン・クロモグリク酸Na・トラニラスト・ペミロラスト・イブジラスト・アシタザノラスト | ×5 |")
    A("| 個 | クロモグリク酸Na（インタール点眼液UD、2016〜2018年度） | ×0.35 |")
    A("")
    A("本スクリプトは全量をmLに正規化してから合算する。正規化しないと")
    A("ALLERGY_EYE_TOTAL は2022〜2024年度で約13〜15%、2016〜2018年度で約3〜7%")
    A("過小評価され、さらに瓶単位の6成分が一斉収載された2021→2022年度に")
    A("見かけ上の断絶が生じる。")
    A("")
    A("2014〜2015年度のExcelには単位列そのものが無いが、当該年度の8品目はすべて")
    A("2016年度以降にも同一品目名で登場するため、後年度の単位を引き当てて補完している。")
    A("")
    A("---")
    A("")
    A("## Ⅱ. 全国トレンドの区間幅（旧ファイルとの比較）")
    A("")
    A("処方規模の大きい成分（エピナスチン・オロパタジン等）は全国合計の区間幅が")
    A("極小（0.1%未満）である。都道府県間の秘匿は「総計」列に反映済みのため、")
    A("全国合計まで足し上げれば都道府県間の秘匿は互いに打ち消し合う。")
    A("")
    A("一方、**処方規模の小さい成分（ペミロラスト・ケトチフェン・クロモグリク酸Na）は")
    A("全国合計でも区間幅がやや大きくなる**（2024年度のペミロラストで+1.6%など。")
    A("それでも都道府県別・年齢性別の内訳と比べれば桁違いに小さい）。")
    A("これは都道府県間の打ち消し合いとは別の要因で、これらの成分は後発品が")
    A("11〜13銘柄に分散しており、各銘柄が入院シートなどで**品目の総計自体が")
    A("1,000未満（総計秘匿）になりやすい**ため。総計秘匿の品目は真の総量が")
    A("分からず、多数の小規模銘柄が積み重なると全国合計への影響もわずかに残る。")
    A("")
    top = nat.nlargest(10, "count_width_pct")
    A("区間幅が大きい上位10件:")
    A("")
    A("| 年度 | 成分 | 件数下限 | 件数上限 | 区間幅 |")
    A("|---|---|--:|--:|--:|")
    for _, r in top.iterrows():
        A(f"| {r.year} | {r.drug} | {fmt(r.count_lower,0)} | {fmt(r.count_upper,0)} "
          f"| +{r.count_width_pct:.3f}% |")
    A("")
    A("---")
    A("")
    A("## Ⅲ. 都道府県別・年齢性別の区間幅（全国トレンドとの違い）")
    A("")
    A("都道府県別・年齢性別に分解すると、区間幅が無視できない品目・年度・区分が現れる。")
    A("")
    pref_top = pref.nlargest(10, "width_pct")
    A("### 都道府県別 上位10件（人口10万対）")
    A("")
    A("| 年度 | 成分 | 都道府県 | 人口10万対下限 | 人口10万対上限 | 区間幅 |")
    A("|---|---|---|--:|--:|--:|")
    for _, r in pref_top.iterrows():
        A(f"| {r.year} | {r.drug} | {r.prefecture} | {fmt(r.per100k_lower)} "
          f"| {fmt(r.per100k_upper)} | +{r.width_pct:.1f}% |")
    A("")
    age_top = agesex.nlargest(10, "width_pct")
    A("### 年齢性別 上位10件（人口10万対）")
    A("")
    A("| 年度 | 成分 | 性別 | 年齢階級 | 人口10万対下限 | 人口10万対上限 | 区間幅 |")
    A("|---|---|---|---|--:|--:|--:|")
    for _, r in age_top.iterrows():
        sx = "男" if r.sex == "male" else "女"
        A(f"| {r.year} | {r.drug} | {sx} | {r.age_group} | {fmt(r.per100k_lower)} "
          f"| {fmt(r.per100k_upper)} | +{r.width_pct:.1f}% |")
    A("")
    A("**都道府県別・年齢性別の値を使う際は、対象年度・成分・区分の区間幅を")
    A("必ず確認すること。** 区間幅が大きいのは主に小規模な後発品銘柄・小規模な")
    A("都道府県／年齢層の組み合わせであり、値そのものが小さいところで相対誤差が")
    A("拡大する（絶対量への影響は小さい）。")
    A("")
    A("---")
    A("")
    A("## Ⅳ. 先発/後発シェアの区間幅")
    A("")
    A("先発/後発の量は都道府県・年齢のセル単位の秘匿ではなく、**品目の総計自体が")
    A("秘匿（総計秘匿）される場合のみ**不確実性を持つ。総計秘匿の品目はすべて")
    A("小規模な後発品銘柄のため、GE比率は実態よりわずかに過小評価される方向に")
    A("偏っている（上限側に真値がある可能性が高い）。")
    A("")
    bg_top = bg.copy()
    bg_top["gap"] = bg_top.share_pct_generic_upper - bg_top.share_pct_generic_lower
    bg_top = bg_top.nlargest(10, "gap")
    A("| 年度 | 成分 | GE比率下限 | GE比率上限 |")
    A("|---|---|--:|--:|")
    for _, r in bg_top.iterrows():
        A(f"| {r.year} | {r.drug} | {fmt(r.share_pct_generic_lower)}% "
          f"| {fmt(r.share_pct_generic_upper)}% |")
    A("")
    A("後発品比率の解釈可能性（A/B/C/D区分）と合わせて使うこと。")
    A("詳細は `03_解析結果/後発品_剤形/ge_share_report.md` を参照。")
    A("")
    return "\n".join(L) + "\n"


def main():
    ensure(OUT)
    level = load_level()
    # 年齢性別軸は missing が都道府県軸と異なるため、専用の品目レベルを使う。
    level_agesex = load_level("product_agesex_censoring.csv")
    pref_long = load_pref_long(level)
    agesex_long = load_agesex_long(level_agesex)

    nat = build_national(level)
    p1 = os.path.join(OUT, "national_trends_bounds.csv")
    nat.to_csv(p1, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p1, BASE)} ({len(nat)} rows)")

    pref = build_prefecture(pref_long)
    p2 = os.path.join(OUT, "prefecture_per_capita_bounds.csv")
    pref.to_csv(p2, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p2, BASE)} ({len(pref)} rows)")

    rank = build_prefecture_ranking(pref)
    p3 = os.path.join(OUT, "prefecture_ranking_bounds.csv")
    rank.to_csv(p3, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p3, BASE)} ({len(rank)} rows)")

    age = build_agesex(agesex_long)
    p4 = os.path.join(OUT, "agesex_bounds.csv")
    age.to_csv(p4, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p4, BASE)} ({len(age)} rows)")

    bg = build_brand_generic(level)
    p5 = os.path.join(OUT, "brand_generic_share_bounds.csv")
    bg.to_csv(p5, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.relpath(p5, BASE)} ({len(bg)} rows)")

    p6 = os.path.join(OUT, "bounded_outputs_report.md")
    with open(p6, "w", encoding="utf-8") as f:
        f.write(build_report(nat, pref, age, bg))
    print(f"-> {os.path.relpath(p6, BASE)}")


if __name__ == "__main__":
    main()
