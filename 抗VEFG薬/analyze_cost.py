"""抗VEGF薬の医療費解析（要因分解・治療総額・反実仮想・感度分析）。

    python 抗VEFG薬/analyze_cost.py
    python 抗VEFG薬/analyze_cost.py --nokouhi

入力（run_antivegf_pipeline.py と analyze_g016.py の出力）:
    product_trends_antivegf.csv   年度×製品の数量・薬剤費・薬価
    biosimilar_national_share.csv 年度×先発/BSの数量・シェア
    biosimilar_share_by_prefecture.csv 都道府県×年度のBSシェア
    g016_prefecture.csv           G016の年度別点数（01_抽出データ/）
    g016_national_trends.csv      G016の年度×区分の算定回数

出力（processed/ → organize_outputs.py で 03_解析結果/医療費/ へ）:
    cost_decomposition_yearly.csv        費用変化の年次要因分解
    cost_decomposition_cumulative.csv    同上の累計
    cost_total_with_procedure.csv        薬剤費＋手技料の治療総額
    cost_counterfactual_scenarios.csv    反実仮想（BS非参入／薬価据置）
    cost_biosimilar_regional_potential.csv BSシェアの地域差解消による削減余地
    cost_price_gap_sensitivity.csv       実勢価格乖離を仮定した感度分析

【注意】薬価×数量は**薬価基準額**であり、実際の償還額ではない。
実勢価格は薬価を下回るため、cost_price_gap_sensitivity.csv で乖離0/5/10%の幅を示している。
転帰データがないため費用対効果分析は算出できない。
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import find, input_path  # noqa: E402

ANTIVEGF_DIR = os.path.dirname(os.path.abspath(__file__))

# 先発／バイオシミラーの対応（ラニビズマブのみBSが存在する）
# product_trends_antivegf.csv の drug_code は医薬品コードなので、成分名で束ねる
ORIG_MOLECULE = "ラニビズマブ（先発）"
BS_MOLECULE = "ラニビズマブBS"

# 実勢価格乖離の仮定（%）
PRICE_GAP_PCTS = [0, 5, 10]


# ── 入力の読み込み ────────────────────────────────────────────────

def load_products(data_dir):
    """年度×製品の数量・薬剤費・薬価。"""
    df = pd.read_csv(find(data_dir, "product_trends_antivegf.csv"))
    return df[["year", "drug_code", "product_name", "molecule_name",
               "brand_type", "quantity", "cost", "price"]]


def molecule_yearly(products, molecule):
    """成分単位の年度別 数量・薬剤費・薬価。

    先発ラニビズマブは剤形が2つ（注射液・キット）あり薬価が異なる。
    BSとの比較には **先発の最高薬価（＝ルセンティス注射液10mg/mL）** を用いる。

    【前提に注意】ラニビズマブBSはキット製剤であり、同じキットの先発
    （ルセンティスキット）の薬価は注射液より低い。注射液を比較対象にすると
    削減額は大きく出る（2024年度: 単価差 46,069円 vs キット比較なら 23,228円で約2倍）。
    ここでは既存の解析と同じ「注射液比較」を採用しているが、キット同士で比較すれば
    削減額はおよそ半分になる点は結果の解釈で留意すること。
    """
    g = products[products["molecule_name"] == molecule]
    out = g.groupby("year", as_index=False).agg(
        quantity=("quantity", "sum"), cost=("cost", "sum"), price=("price", "max"))
    return out


def load_g016(data_dir):
    """年度別のG016算定回数（外来＋入院）と点数を返す。"""
    nat = pd.read_csv(find(data_dir, "g016_national_trends.csv"))
    # setting には 外来／入院 に加えて「合計」行がある。二重計上を避けて合計行を使う
    proc = nat[nat["setting"] == "合計"][["year", "count"]].copy()
    proc = proc.rename(columns={"count": "g016_procedures"})

    # 点数は年度で改定される（2024年度に580→600）。抽出データから年度別に取る
    raw = pd.read_csv(input_path(data_dir, "g016_prefecture.csv"))
    pts = raw.groupby("年度", as_index=False)["点数"].first()
    pts = pts.rename(columns={"年度": "year", "点数": "points"})
    return proc.merge(pts, on="year", how="left")


# ── 1. 費用変化の要因分解 ────────────────────────────────────────

def decompose(products, out_dir):
    """ΔC を 数量効果・構成効果・価格効果 に厳密分解する（残差0）。

    C = Q * Σ s_i p_i （Q=総数量, s_i=製品iの数量シェア, p_i=薬価）とおくと

        数量効果 = (Q_cur - Q_prev) * p̄_prev
        構成効果 = Q_cur * (Σ s_i,cur p_i,prev - p̄_prev)
        価格効果 = Σ q_i,cur * (p_i,cur - p_i,prev)

    の3項の和が ΔC に一致する（下の residual で検算している）。
    新規収載薬は前年薬価が存在しないため当年薬価で代用する。
    その結果、参入の影響は価格効果ではなく構成効果に計上される。
    """
    years = sorted(products["year"].unique())
    rows = []
    for prev_y, cur_y in zip(years[:-1], years[1:]):
        prev = products[products["year"] == prev_y].set_index("drug_code")
        cur = products[products["year"] == cur_y].set_index("drug_code")

        q_prev, q_cur = prev["quantity"], cur["quantity"]
        Q_prev, Q_cur = q_prev.sum(), q_cur.sum()
        cost_prev, cost_cur = prev["cost"].sum(), cur["cost"].sum()

        # 当年の製品について前年薬価を引く（新規収載は当年薬価で代用）
        price_prev_for_cur = prev["price"].reindex(cur.index)
        n_new = int(price_prev_for_cur.isna().sum())
        price_prev_for_cur = price_prev_for_cur.fillna(cur["price"])

        mean_price_prev = cost_prev / Q_prev if Q_prev else np.nan
        mean_price_cur = cost_cur / Q_cur if Q_cur else np.nan

        # 当年の構成のまま前年薬価で評価した平均単価
        mean_price_cur_at_prev = float((q_cur * price_prev_for_cur).sum() / Q_cur)

        volume = (Q_cur - Q_prev) * mean_price_prev
        mix = Q_cur * (mean_price_cur_at_prev - mean_price_prev)
        price = float((q_cur * (cur["price"] - price_prev_for_cur)).sum())
        change = cost_cur - cost_prev

        rows.append({
            "year": cur_y,
            "cost_prev": cost_prev, "cost_current": cost_cur,
            "cost_change": change,
            "volume_effect": volume, "mix_effect": mix, "price_effect": price,
            "residual": change - (volume + mix + price),
            "n_new_products": n_new,
            "mean_price_prev": mean_price_prev,
            "mean_price_current": mean_price_cur,
        })

    yearly = pd.DataFrame(rows)
    yearly.to_csv(os.path.join(out_dir, "cost_decomposition_yearly.csv"),
                  index=False, encoding="utf-8-sig")

    cum = pd.DataFrame([{
        "period": f"{years[0]}-{years[-1]}",
        "cost_change": yearly["cost_change"].sum(),
        "volume_effect": yearly["volume_effect"].sum(),
        "mix_effect": yearly["mix_effect"].sum(),
        "price_effect": yearly["price_effect"].sum(),
        "residual": yearly["residual"].sum(),
    }])
    cum.to_csv(os.path.join(out_dir, "cost_decomposition_cumulative.csv"),
               index=False, encoding="utf-8-sig")
    print(f"  cost_decomposition_yearly.csv ({len(yearly)} rows)")
    print(f"  cost_decomposition_cumulative.csv")
    return yearly


# ── 2. 薬剤費＋手技料の治療総額 ───────────────────────────────────

def total_with_procedure(products, g016, out_dir):
    """治療総額 = 薬剤費 + 手技料（G016算定回数 × 点数 × 10円）。"""
    drug = products.groupby("year", as_index=False)["cost"].sum()
    drug = drug.rename(columns={"cost": "drug_cost"})

    df = g016.merge(drug, on="year", how="inner")
    df["procedure_cost"] = df["g016_procedures"] * df["points"] * 10
    df["total_cost"] = df["procedure_cost"] + df["drug_cost"]
    df["drug_share_pct"] = df["drug_cost"] / df["total_cost"] * 100
    df = df[["year", "g016_procedures", "points", "procedure_cost",
             "drug_cost", "total_cost", "drug_share_pct"]].sort_values("year")
    df.to_csv(os.path.join(out_dir, "cost_total_with_procedure.csv"),
              index=False, encoding="utf-8-sig")
    print(f"  cost_total_with_procedure.csv ({len(df)} rows)")
    return df


# ── 3. 反実仮想シナリオ ──────────────────────────────────────────

def counterfactuals(products, out_dir):
    """バイオシミラー非参入／薬価据置の2シナリオ。"""
    rows = []

    # (1) BS非参入: BSの数量を先発薬価で換算していたら
    bs = molecule_yearly(products, BS_MOLECULE)
    orig = molecule_yearly(products, ORIG_MOLECULE).set_index("year")
    for _, r in bs.iterrows():
        if r["year"] not in orig.index:
            continue
        cf = r["quantity"] * orig.loc[r["year"], "price"]
        rows.append({"scenario": "バイオシミラー非参入", "year": r["year"],
                     "actual_cost": r["cost"], "counterfactual_cost": cf,
                     "difference": cf - r["cost"]})

    # (2) 薬価据置: 各製品を収載時（最初に観測された年度）の薬価のまま据え置いたら
    first_price = (products.sort_values("year")
                   .groupby("drug_code")["price"].first())
    for year, g in products.groupby("year"):
        cf = float((g["quantity"] * g["drug_code"].map(first_price)).sum())
        actual = g["cost"].sum()
        rows.append({"scenario": "薬価据置（各製品の収載時薬価）", "year": year,
                     "actual_cost": actual, "counterfactual_cost": cf,
                     "difference": cf - actual})

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "cost_counterfactual_scenarios.csv"),
              index=False, encoding="utf-8-sig")
    print(f"  cost_counterfactual_scenarios.csv ({len(df)} rows)")
    return df


# ── 4. BSシェアの地域差解消による追加削減余地 ─────────────────────

def biosimilar_regional_potential(products, data_dir, out_dir):
    """全国のBSシェアを、上位10%の県の水準（P90）まで引き上げた場合の削減余地。

    県別シェアと突き合わせるため、分母には**都道府県別集計の合計**を用いる
    （公表総計より秘匿分だけ小さい）。県別シェアの分母と揃えるための選択である。

    【旧実装との差】2026年7月時点の cost_biosimilar_regional_potential.csv は、
    シェア列と追加切替数量で**分母が食い違っていた**（2022年度: シェアの分母
    152,702 に対し数量の分母 158,072、2024年度は逆に 150,115 対 145,054）。
    本実装は同一の分母で統一しているため、追加切替数量・追加削減額が旧出力より
    2022年度で -3.4%、2023年度で -2.0%、2024年度で +3.8% 変わる。
    """
    pref = pd.read_csv(find(data_dir, "biosimilar_share_by_prefecture.csv"))
    share_cols = [c for c in pref.columns if c.endswith("_BSシェア(%)")]

    panel = pd.read_csv(find(data_dir, "processed_prefecture_zero.csv"))
    rani = panel[panel["molecule"].isin(["RANIBIZUMAB_ORIG", "RANIBIZUMAB_BS"])]

    orig = molecule_yearly(products, ORIG_MOLECULE).set_index("year")
    bs = molecule_yearly(products, BS_MOLECULE).set_index("year")

    rows = []
    for col in share_cols:
        year = int(col.split("年度")[0])
        if year not in bs.index or year not in orig.index:
            continue
        g = rani[rani["year"] == year]
        total_q = g["quantity"].sum()
        q_bs = g[g["molecule"] == "RANIBIZUMAB_BS"]["quantity"].sum()
        national = q_bs / total_q * 100 if total_q else 0.0
        p90 = float(np.percentile(pref[col].dropna(), 90))
        gap = max(p90 - national, 0.0)
        add_q = total_q * gap / 100
        unit = int(round(orig.loc[year, "price"] - bs.loc[year, "price"]))
        rows.append({"year": year,
                     "target_bs_share_p90": p90,
                     "current_national_bs_share_pct": national,
                     "additional_bs_switch_quantity": add_q,
                     "unit_saving_yen": unit,
                     "additional_saving": add_q * unit})

    df = pd.DataFrame(rows).sort_values("year")
    df.to_csv(os.path.join(out_dir, "cost_biosimilar_regional_potential.csv"),
              index=False, encoding="utf-8-sig")
    print(f"  cost_biosimilar_regional_potential.csv ({len(df)} rows)")
    return df


# ── 5. 実勢価格乖離の感度分析 ────────────────────────────────────

def price_gap_sensitivity(total, out_dir):
    """薬価基準額は実勢価格を上回る。乖離0/5/10%を仮定した幅を示す。"""
    rows = []
    for gap in PRICE_GAP_PCTS:
        for _, r in total.iterrows():
            adj = r["drug_cost"] * (1 - gap / 100)
            rows.append({"price_gap_pct": gap, "year": int(r["year"]),
                         "drug_cost_list_price": r["drug_cost"],
                         "drug_cost_adjusted": adj,
                         "total_cost_adjusted": adj + r["procedure_cost"]})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "cost_price_gap_sensitivity.csv"),
              index=False, encoding="utf-8-sig")
    print(f"  cost_price_gap_sensitivity.csv ({len(df)} rows)")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nokouhi", action="store_true",
                    help="公費レセプトを含まないデータ（抗VEFG薬/公費含まない）で解析する")
    args = ap.parse_args()

    data_dir = os.path.join(ANTIVEGF_DIR, "公費含まない") if args.nokouhi else ANTIVEGF_DIR
    out_dir = os.path.join(data_dir, "processed")
    os.makedirs(out_dir, exist_ok=True)
    print(f"=== 抗VEGF薬 医療費解析 ===\n入力/出力: {out_dir}")

    products = load_products(data_dir)
    g016 = load_g016(data_dir)

    decompose(products, out_dir)
    total = total_with_procedure(products, g016, out_dir)
    counterfactuals(products, out_dir)
    biosimilar_regional_potential(products, data_dir, out_dir)
    price_gap_sensitivity(total, out_dir)
    print("完了")


if __name__ == "__main__":
    main()
