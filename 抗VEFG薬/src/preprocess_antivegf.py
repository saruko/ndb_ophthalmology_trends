"""抽出済みCSVを解析用のロングデータに整形する。

- 秘匿セル（処方数量が空欄・秘匿フラグ=1）を指定方法で補完
- 薬剤マスタを付与し、成分レベル／グループレベルの集計行を追加
- 共変量（人口・眼科医師数・眼科施設数）を結合して人口10万対を算出
"""

import os
import numpy as np
import pandas as pd

from drug_master import DRUG_MASTER, GROUPS, MOLECULE_NAMES

AGE_ORDER = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳", "25～29歳",
    "30～34歳", "35～39歳", "40～44歳", "45～49歳", "50～54歳", "55～59歳",
    "60～64歳", "65～69歳", "70～74歳", "75～79歳", "80～84歳", "85～89歳",
    "90歳以上",
]


def impute(df, strategy, seed=42):
    """秘匿セル（秘匿フラグ=1）を補完した quantity 列を作る。"""
    rng = np.random.default_rng(seed)
    q = pd.to_numeric(df["処方数量"], errors="coerce")
    masked = df["秘匿フラグ"] == 1
    if strategy == "zero":
        fill = 0.0
    elif strategy == "five":
        fill = 5.0
    elif strategy == "random":
        fill = rng.integers(1, 10, size=int(masked.sum())).astype(float)
    else:
        raise ValueError(f"unknown imputation: {strategy}")
    q = q.copy()
    q[masked] = fill
    return q.fillna(0.0)


def _attach_master(df):
    m = df["医薬品コード"].astype(str).map(DRUG_MASTER)
    if m.isna().any():
        missing = sorted(df.loc[m.isna(), "医薬品コード"].unique())
        raise ValueError(f"薬剤マスタ未定義の医薬品コード: {missing}")
    df["product_name"] = m.map(lambda x: x[0])
    df["molecule"] = m.map(lambda x: x[1])
    df["molecule_name"] = m.map(lambda x: x[2])
    df["formulation"] = m.map(lambda x: x[3])
    df["brand_type"] = m.map(lambda x: x[4])
    df["category"] = m.map(lambda x: x[5])
    return df


def _normalize_age(s):
    """2014年度は90歳以上までのため、全年度を90歳以上に統合する。"""
    return s.replace({"90～94歳": "90歳以上", "95～99歳": "90歳以上",
                      "100歳以上": "90歳以上"})


def load_prefecture(csv_path, strategy):
    df = pd.read_csv(csv_path, dtype={"医薬品コード": str})
    df = _attach_master(df)
    df["quantity"] = impute(df, strategy)
    df["price"] = pd.to_numeric(df["薬価"], errors="coerce")
    df["cost"] = df["quantity"] * df["price"]
    df = df.rename(columns={"年度": "year", "区分": "setting", "都道府県": "prefecture"})
    return df[[
        "year", "setting", "prefecture", "医薬品コード", "product_name", "molecule",
        "molecule_name", "formulation", "brand_type", "category", "price",
        "quantity", "cost", "秘匿フラグ",
    ]].rename(columns={"医薬品コード": "drug_code", "秘匿フラグ": "masked"})


def load_national(csv_path):
    """全国値は公表総計（秘匿なし）から作る。

    都道府県内訳を合計すると秘匿分だけ過小になり、薄く広がる薬剤ほど欠落が大きい。
    NDBは全国総計を秘匿せずに公表しているため、全国レベルの集計はこちらを使う。
    """
    df = pd.read_csv(csv_path, dtype={"医薬品コード": str})
    df = _attach_master(df)
    df = df.rename(columns={"年度": "year", "区分": "setting"})
    # 総計は行ごとに繰り返されているため、年度×区分×医薬品コードで1件に畳む
    nat = df.groupby(
        ["year", "setting", "医薬品コード", "product_name", "molecule", "molecule_name",
         "formulation", "brand_type", "category"], as_index=False
    ).agg(quantity=("総計_処方数量", "first"), price=("薬価", "first"))
    nat = nat.rename(columns={"医薬品コード": "drug_code"})
    nat["quantity"] = pd.to_numeric(nat["quantity"], errors="coerce").fillna(0.0)
    nat["price"] = pd.to_numeric(nat["price"], errors="coerce")
    nat["cost"] = nat["quantity"] * nat["price"]
    return nat


def load_agesex(csv_path, strategy):
    df = pd.read_csv(csv_path, dtype={"医薬品コード": str})
    df = _attach_master(df)
    df["quantity"] = impute(df, strategy)
    df["price"] = pd.to_numeric(df["薬価"], errors="coerce")
    df = df.rename(columns={"年度": "year", "区分": "setting", "性別": "sex"})
    df["age_group"] = _normalize_age(df["年齢階級"])
    df["age_group_detail"] = df["年齢階級"]
    return df[[
        "year", "setting", "sex", "age_group", "age_group_detail", "医薬品コード",
        "product_name", "molecule", "molecule_name", "formulation", "brand_type",
        "category", "price", "quantity", "秘匿フラグ",
    ]].rename(columns={"医薬品コード": "drug_code", "秘匿フラグ": "masked"})


def build_panel(df_pref, covariates_path):
    """都道府県×年×解析単位（成分／グループ）のパネルを作る（外来＋入院の合算）。"""
    anti = df_pref[df_pref["category"] == "ANTI_VEGF"]

    # 成分レベル
    mol = anti.groupby(["year", "prefecture", "molecule"], as_index=False)["quantity"].sum()
    mol = mol.rename(columns={"molecule": "code"})

    # グループレベル
    frames = [mol]
    for gcode, (gname, members) in GROUPS.items():
        sub = anti[anti["molecule"].isin(members)]
        g = sub.groupby(["year", "prefecture"], as_index=False)["quantity"].sum()
        g["code"] = gcode
        frames.append(g)

    panel = pd.concat(frames, ignore_index=True)
    names = dict(MOLECULE_NAMES)
    names.update({k: v[0] for k, v in GROUPS.items()})
    panel["name"] = panel["code"].map(names)

    # 全都道府県×全年の枠を作り、未収載年（データなし）と0を区別せず0埋め
    cov = pd.read_csv(covariates_path)
    panel = panel.merge(cov, on=["year", "prefecture"], how="left")
    panel["count_per_100k"] = panel["quantity"] / panel["population_total"] * 100000
    panel["aging_rate"] = panel["population_65plus"] / panel["population_total"] * 100
    panel["docs_per_100k"] = panel["ophthalmologists"] / panel["population_total"] * 100000
    panel["facilities_per_100k"] = panel["facilities"] / panel["population_total"] * 100000
    return panel


def preprocess_all(input_dir, output_dir, covariates_path, strategy):
    os.makedirs(output_dir, exist_ok=True)
    pref_csv = os.path.join(input_dir, "ophthalmic_injection_prefecture.csv")
    pref = load_prefecture(pref_csv, strategy)
    nat = load_national(pref_csv)
    agesex = load_agesex(os.path.join(input_dir, "ophthalmic_injection_agesex.csv"),
                         strategy)
    panel = build_panel(pref, covariates_path)

    pref.to_csv(os.path.join(output_dir, f"processed_prefecture_{strategy}.csv"),
                index=False, encoding="utf-8-sig")
    nat.to_csv(os.path.join(output_dir, "processed_national_published_total.csv"),
               index=False, encoding="utf-8-sig")
    agesex.to_csv(os.path.join(output_dir, f"processed_agesex_{strategy}.csv"),
                  index=False, encoding="utf-8-sig")
    panel.to_csv(os.path.join(output_dir, f"panel_{strategy}.csv"),
                 index=False, encoding="utf-8-sig")
    print(f"  preprocessed ({strategy}): pref={len(pref)}, national={len(nat)}, "
          f"agesex={len(agesex)}, panel={len(panel)}")
    return pref, nat, agesex, panel
