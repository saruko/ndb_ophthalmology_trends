# -*- coding: utf-8 -*-
"""NDBオープンデータの捕捉率検証（参考解析・triangulation）。

## 目的

査読指摘①「2014〜2021年度は上位品目の足切りがあり、NDBに載っていない薬剤が
あるのに、3成分の処方シェアが多いと言えるのか」に対し、NDB**外部**のデータで
「NDBに載っていない眼科用剤がどれだけあり得るか」に上限を与える。

薬効分類131（眼科用剤）について、
    分子: NDBに掲載された全131品目の 薬価 × 処方数量（外用＋注射）
    分母: 薬事工業生産動態統計の 眼科用剤 医療用医薬品 国内出荷金額
の比（捕捉率）を年次で求める。捕捉率が高いほど、NDB非掲載の品目が持ちうる
金額（＝ひいては数量）の余地は小さい。

## 価格基準の違い（本解析の最大の注意点）

- NDB側 = **薬価**（公定価格）
- 統計側 = **販売単価**＝メーカーが卸等へ出荷する実勢単価（薬価より低い）
  厚労省FAQ Q3-1「出荷金額＝出荷数量×販売単価」、Q3-29（連結企業体外への出荷）

そのまま比を取ると捕捉率は**過大**に出る。そこで仕切価率 k（＝販売単価/薬価）を
0.7〜1.0で振り、統計側を薬価等価に引き直した
    統計_薬価等価 = 統計国内出荷 / k
に対する捕捉率を併記する（k が小さいほど分母が大きくなり捕捉率は下がる＝保守的）。

## 集計期間のずれ

統計年報は暦年（1〜12月）、NDBは年度（4月〜翌3月）。年度Yは暦年Yの9か月と
暦年Y+1の3か月からなるため、
    統計_年度換算(Y) = 0.75 × 暦年Y + 0.25 × 暦年(Y+1)
を主の分母とし、暦年そのままの値も併記する（2024年度は暦年2025が未公表のため
暦年2024をそのまま使う）。

## 出力（薬事工業生産動態統計/NDBとの比較/）

  yakuji_eye_shipment.csv        統計側: 眼科用剤131の出荷金額（暦年・用途区分別）
  ndb_131_amount_by_year.csv     NDB側: 131品目の薬価金額（年度・ファイル別・区分別）
  ndb_131_products.csv           NDB側: 品目×年度の明細（薬価・数量・金額）
  coverage_by_year.csv           捕捉率（k・期間補正の別に）
  unaccounted_volume_bound.csv   未捕捉金額から導く「NDB非掲載mL」の上限
  Fig_coverage.png               捕捉率の推移
  coverage_report.md             方法・結果・限界
"""
import csv
import glob
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402
import pandas as pd              # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(BASE)
RAW = os.path.join(PROJECT, "data", "raw")
NOKOUHI = os.path.join(RAW, "ndb_2024_nokouhi")
OUT = os.path.join(BASE, "NDBとの比較")

YEARS = list(range(2014, 2025))
TARGET_CLASS = "131"            # 眼科用剤
K_VALUES = [1.0, 0.9, 0.8, 0.7]  # 仕切価率（販売単価/薬価）の仮定

_ZEN = str.maketrans("０１２３４５６７８９．", "0123456789.")


# ----------------------------------------------------------------------
# 1. 統計側（薬事工業生産動態統計）
# ----------------------------------------------------------------------
def read_yakuji_year(year):
    """眼科用剤131の行を取り出す。

    列配置は2014〜2024年で共通:
      0番号 1薬効分類 2品目数
      3-5   出荷 総合計（計/国内/輸出）
      6-8   出荷 医療用医薬品（計/国内/輸出）
      9-11  出荷 その他の医薬品＝要指導・一般用（計/国内/輸出）
    """
    pats = glob.glob(os.path.join(BASE, str(year),
                                  f"{year}_薬効分類別用途区分別出荷・在庫金額_*"))
    if not pats:
        raise FileNotFoundError(year)
    p = pats[0]
    if p.endswith(".csv"):
        rows = list(csv.reader(open(p, encoding="utf-8-sig")))
    else:
        d = pd.read_excel(p, sheet_name=0, header=None, dtype=str)
        rows = d.fillna("").astype(str).values.tolist()

    def num(v):
        s = str(v).replace(",", "").replace("－", "").replace("-", "").strip()
        return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else np.nan

    for r in rows:
        if str(r[0]).strip() == TARGET_CLASS and "眼科用剤" in str(r[1]):
            return {
                "calendar_year": year,
                "n_products": num(r[2]),
                "ship_total": num(r[3]), "ship_total_domestic": num(r[4]),
                "ship_total_export": num(r[5]),
                "ship_rx": num(r[6]), "ship_rx_domestic": num(r[7]),
                "ship_rx_export": num(r[8]),
                "ship_otc": num(r[9]), "ship_otc_domestic": num(r[10]),
                "source_file": os.path.basename(p),
            }
    raise ValueError(f"{year}: 眼科用剤の行が見つかりません")


# ----------------------------------------------------------------------
# 2. NDB側（薬効分類131の薬価金額）
# ----------------------------------------------------------------------
def ml_per_container(name):
    """品目名末尾の容量表記からmL数を取る（点眼薬の円/mL算出用）。"""
    s = str(name).translate(_ZEN)
    hits = re.findall(r"([0-9]*\.?[0-9]+)\s*[mｍ][lLｌＬ]", s)
    return float(hits[-1]) if hits else None


def ndb_file(stem, year):
    if year == 2024:
        p = os.path.join(NOKOUHI, f"{stem}_2024_nokouhi.xlsx")
        if os.path.exists(p):
            return p
    return os.path.join(RAW, f"{stem}_{year}.xlsx")


def read_ndb_sheet(path, sheet):
    """1シートから薬効分類131の品目行を抽出する（列位置は動的に特定）。"""
    d = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
    hdr = None
    for i in range(min(8, len(d))):
        vals = [str(v) for v in d.iloc[i].tolist()]
        if any("薬効" in v and "分類" in v for v in vals) and any("薬価" == v.strip()
                                                              for v in vals):
            hdr = i
            break
    if hdr is None:
        return pd.DataFrame()
    head = [str(v).replace("\n", "") for v in d.iloc[hdr].tolist()]
    col = {}
    for j, v in enumerate(head):
        if "薬効分類" in v and "名称" not in v and "cls" not in col:
            col["cls"] = j
        elif v.strip() == "医薬品名":
            col["name"] = j
        elif v.strip() == "単位":
            col["unit"] = j
        elif v.strip() == "薬価":
            col["price"] = j
        elif v.startswith("総計"):
            col["total"] = j
    if not {"cls", "name", "price", "total"} <= set(col):
        return pd.DataFrame()

    body = d.iloc[hdr + 1:].copy()
    # 薬効分類は年度によって文字列（"131"）と数値（131.0）で読まれるため正規化する
    cls = (body[col["cls"]].ffill().astype(str).str.strip()
           .str.replace(r"\.0$", "", regex=True))
    m = body[cls == TARGET_CLASS]
    if m.empty:
        return pd.DataFrame()

    def tonum(v):
        s = str(v).replace(",", "").strip()
        return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else np.nan

    out = pd.DataFrame({
        "product_name": m[col["name"]].astype(str).str.strip(),
        "unit": (m[col["unit"]].astype(str).str.strip()
                 if "unit" in col else None),
        "price": m[col["price"]].map(tonum),
        "quantity": m[col["total"]].map(tonum),
    })
    out["total_censored"] = out.quantity.isna()
    return out[out.product_name.notna() & (out.product_name != "nan")]


def read_ndb_year(year):
    rows = []
    for stem, kind in [("ndb_gaiyo", "外用"), ("ndb_chusha", "注射")]:
        path = ndb_file(stem, year)
        if not os.path.exists(path):
            print(f"   ! {os.path.basename(path)} が無いためスキップ")
            continue
        for sheet in pd.ExcelFile(path).sheet_names:
            d = read_ndb_sheet(path, sheet)
            if d.empty:
                continue
            d["year"], d["file_kind"], d["sheet"] = year, kind, sheet
            rows.append(d)
    if not rows:
        return pd.DataFrame()
    d = pd.concat(rows, ignore_index=True)
    d["amount_yen"] = d.price * d.quantity          # 薬価金額（円）
    d["ml_per_container"] = d.product_name.map(ml_per_container)
    return d


def backfill_units(nd):
    """2014〜2015年度は「単位」列が無いため、他年度の同名品目から補完する。

    同一品目名に複数の単位が観測された場合は補完しない（曖昧なため）。
    """
    known = (nd[nd.unit.notna() & (nd.unit != "nan") & (nd.unit != "None")]
             .groupby("product_name")["unit"].agg(lambda s: set(s)))
    fill = {k: next(iter(v)) for k, v in known.items() if len(v) == 1}
    miss = nd.unit.isna() | nd.unit.isin(["nan", "None", ""])
    nd.loc[miss, "unit"] = nd.loc[miss, "product_name"].map(fill)
    nd["unit_source"] = np.where(miss & nd.unit.notna(), "backfilled", "published")
    print(f"  単位補完: {int((miss & nd.unit.notna()).sum())}行 "
          f"／未解決 {int((miss & nd.unit.isna()).sum())}行")
    return nd


# ----------------------------------------------------------------------
# 3. 突合
# ----------------------------------------------------------------------
def coverage(nd_year, yk):
    """年度×kの捕捉率。統計側は暦年→年度換算した値も用意する。"""
    y = yk.set_index("calendar_year")
    rows = []
    for year in YEARS:
        ndb = nd_year.loc[year, "amount_yen"]
        cy = y.loc[year, "ship_rx_domestic"] * 1000          # 千円→円
        nxt = (y.loc[year + 1, "ship_rx_domestic"] * 1000
               if (year + 1) in y.index else np.nan)
        fy = .75 * cy + .25 * nxt if not np.isnan(nxt) else cy
        rec = {"fiscal_year": year, "ndb_amount_yen": ndb,
               "yakuji_rx_domestic_cy_yen": cy,
               "yakuji_rx_domestic_fy_yen": fy,
               "fy_is_approximated": np.isnan(nxt)}
        for k in K_VALUES:
            rec[f"coverage_fy_k{k:g}"] = ndb / (fy / k) * 100
            rec[f"coverage_cy_k{k:g}"] = ndb / (cy / k) * 100
        rows.append(rec)
    return pd.DataFrame(rows)


ALLERGY_KEYS = ("エピナスチン", "アレジオン", "オロパタジン", "パタノール",
                "レボカバスチン", "リボスチン", "ケトチフェン", "ザジテン",
                "クロモグリク酸", "インタール", "トラニラスト", "リザベン",
                "ペミロラスト", "アレギサール", "ペミラストン",
                "イブジラスト", "ケタス", "アシタザノラスト", "ゼペリン")


def price_per_ml(nd, year):
    """その年度に掲載された点眼薬の単価（円/mL）分布。"""
    g = nd[(nd.year == year) & (nd.file_kind == "外用")
           & nd.product_name.str.contains("点眼")].copy()
    g["ml_factor"] = np.where(g.unit.isin(["ｍＬ", "mL", "ml"]), 1.0,
                              g.ml_per_container)
    g = g[g.ml_factor.notna() & (g.ml_factor > 0) & g.price.notna()]
    g["yen_per_ml"] = g.price / g.ml_factor
    a = g[g.product_name.str.contains("|".join(ALLERGY_KEYS))]
    return g, a


def unaccounted_bound(nd, cov, top3):
    """未捕捉金額を数量に読み替える（参考値）。

    未捕捉金額（薬価等価） = 統計国内出荷/k − NDB薬価金額

    これを単価で割れば「NDB非掲載の点眼薬が最大どれだけの量になりうるか」を
    出せるが、下記のとおり**この上限は実務的にほとんど情報を持たない**ため、
    参考値として複数の単価基準で併記するに留める。

    - 最低単価（人工涙液など5〜13円/mL）で割ると上限が公表量の数十倍になり無情報
    - 抗アレルギー点眼薬の中央単価で割った値のほうが、査読指摘（抗アレルギー点眼の
      未収載分）に対しては現実的な目安になる
    - いずれにせよ未捕捉金額の大半は価格基準の差（仕切価率k）に由来し、
      未収載品目の実在を意味しない
    """
    rows = []
    c = cov.set_index("fiscal_year")
    for year in YEARS:
        g, a = price_per_ml(nd, year)
        if g.empty:
            continue
        for k in K_VALUES:
            unacc = (c.loc[year, "yakuji_rx_domestic_fy_yen"] / k
                     - c.loc[year, "ndb_amount_yen"])
            pos = max(0.0, unacc)
            med_a = a.yen_per_ml.median() if not a.empty else np.nan
            rows.append({
                "fiscal_year": year, "k": k,
                "unaccounted_yen": unacc,
                "min_yen_per_ml_all": g.yen_per_ml.min(),
                "median_yen_per_ml_all": g.yen_per_ml.median(),
                "median_yen_per_ml_allergy": med_a,
                "ml_upper_at_min_price": pos / g.yen_per_ml.min(),
                "ml_upper_at_median_allergy_price":
                    pos / med_a if pd.notna(med_a) else np.nan,
                "top3_published_ml": top3.get(year, np.nan),
                "ratio_to_top3_at_median_allergy_price":
                    (pos / med_a) / top3[year]
                    if (year in top3 and top3[year] and pd.notna(med_a)) else np.nan,
            })
    return pd.DataFrame(rows)


def listing_effect(nd, cov):
    """2022年度の足切り撤廃で「見えるようになった」金額の実測。

    NDB掲載品目数は2021年度316→2022年度1492に急増した。もし足切りで
    隠れていた品目が大きな量を持つなら、この年に金額も跳ね上がるはずである。
    統計側（市場全体）は同期間ほぼ横ばいなので、両者の比＝捕捉率の変化が
    「足切りで隠れていた分が市場に占める割合」の実測値になる。
    """
    c = cov.set_index("fiscal_year")
    n = nd.groupby("year").product_name.nunique()
    rows = []
    for year in YEARS:
        rows.append({
            "fiscal_year": year,
            "n_products_ndb": int(n.get(year, 0)),
            "ndb_amount_yen": c.loc[year, "ndb_amount_yen"],
            "yakuji_rx_domestic_fy_yen": c.loc[year, "yakuji_rx_domestic_fy_yen"],
            "coverage_k1_pct": c.loc[year, "coverage_fy_k1"],
        })
    d = pd.DataFrame(rows)
    d["n_products_yoy_pct"] = d.n_products_ndb.pct_change() * 100
    d["ndb_amount_yoy_pct"] = d.ndb_amount_yen.pct_change() * 100
    d["coverage_k1_diff_pt"] = d.coverage_k1_pct.diff()
    return d


# ----------------------------------------------------------------------
# 4. 出力
# ----------------------------------------------------------------------
def figure(cov):
    plt.rcParams["font.family"] = "MS Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(11, 6))
    for k, c in zip(K_VALUES, ["tab:blue", "tab:green", "tab:orange", "tab:red"]):
        ax.plot(cov.fiscal_year, cov[f"coverage_fy_k{k:g}"], "o-", color=c,
                lw=2, label=f"仕切価率 k={k:g}（統計を薬価等価に補正）")
    ax.axhline(100, color="gray", ls="--", lw=1)
    ax.axvspan(2021.5, 2024.4, color="tab:green", alpha=.07)
    ax.set_xlabel("年度")
    ax.set_ylabel("捕捉率（NDB薬価金額 / 統計 医療用国内出荷金額）%")
    ax.set_title("NDB掲載の眼科用剤（薬効分類131）が薬事工業生産動態統計の\n"
                 "出荷金額に占める割合（参考解析）", fontsize=12, fontweight="bold")
    ax.set_xticks(YEARS)
    ax.grid(alpha=.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    p = os.path.join(OUT, "Fig_coverage.png")
    fig.savefig(p, dpi=150)
    plt.close(fig)
    return p


def report(cov, unacc, yk, nd, eff):
    L = []
    A = L.append
    A("# NDB捕捉率の外部データ検証（薬事工業生産動態統計との突合）")
    A("")
    A("生成: `build_ndb_vs_yakuji.py`（参考解析・triangulation）")
    A("")
    A("## 方法")
    A("")
    A("- 分子: NDBオープンデータに掲載された**薬効分類131（眼科用剤）の全品目**について")
    A("  `薬価 × 処方数量` を合算（外用ファイル3シート＋注射ファイル3シート、公費含まない基準）")
    A("- 分母: 薬事工業生産動態統計「医薬品薬効分類別用途区分別出荷・在庫金額」の")
    A("  眼科用剤131 **医療用医薬品・国内**出荷金額")
    A("- 統計は暦年、NDBは年度のため `0.75×暦年Y + 0.25×暦年Y+1` で年度換算")
    A("- **価格基準が異なる**（NDB=薬価、統計=メーカー販売単価）ため、仕切価率")
    A("  k=販売単価/薬価 を 1.0〜0.7 で振り、統計側を `統計/k` と薬価等価に引き直した")
    A("")
    A("## 結果: 捕捉率")
    A("")
    A("| 年度 | NDB薬価金額(億円) | 統計 医療用国内出荷(億円, 年度換算) | k=1.0 | k=0.9 | k=0.8 | k=0.7 |")
    A("|---|--:|--:|--:|--:|--:|--:|")
    for _, r in cov.iterrows():
        A(f"| {int(r.fiscal_year)} | {r.ndb_amount_yen/1e8:,.0f} "
          f"| {r.yakuji_rx_domestic_fy_yen/1e8:,.0f} "
          f"| {r.coverage_fy_k1:.1f}% | {r['coverage_fy_k0.9']:.1f}% "
          f"| {r['coverage_fy_k0.8']:.1f}% | {r['coverage_fy_k0.7']:.1f}% |")
    A("")
    pre = cov[cov.fiscal_year <= 2021]
    post = cov[cov.fiscal_year >= 2022]
    A(f"- 2014〜2021年度の捕捉率（k=0.8）: "
      f"{pre['coverage_fy_k0.8'].min():.1f}〜{pre['coverage_fy_k0.8'].max():.1f}%")
    A(f"- 2022〜2024年度の捕捉率（k=0.8）: "
      f"{post['coverage_fy_k0.8'].min():.1f}〜{post['coverage_fy_k0.8'].max():.1f}%")
    A("")
    e21 = eff[eff.fiscal_year == 2021].iloc[0]
    e22 = eff[eff.fiscal_year == 2022].iloc[0]
    A("## 最重要の所見: 足切りで隠れていた品目は金額ベースで市場の約1割")
    A("")
    A("2022年度に上位品目の足切りが撤廃され、NDBの薬効分類131の掲載品目数は")
    A(f"**{int(e21.n_products_ndb):,} → {int(e22.n_products_ndb):,}品目"
      f"（{e22.n_products_ndb/e21.n_products_ndb:.1f}倍）**に急増した"
      "（同一品目名でユニーク集計。処方区分シートの延べ行数では316→1,492行）。")
    A("もし足切りで隠れていた品目が大きな処方量を持っていたなら、この年に金額も")
    A("跳ね上がるはずである。しかし実際には:")
    A("")
    A("| 年度 | NDB掲載品目数 | NDB薬価金額(億円) | 統計 医療用国内出荷(億円) | 捕捉率(k=1.0) |")
    A("|---|--:|--:|--:|--:|")
    for _, r in eff[eff.fiscal_year.between(2020, 2024)].iterrows():
        A(f"| {int(r.fiscal_year)} | {int(r.n_products_ndb):,} "
          f"| {r.ndb_amount_yen/1e8:,.0f} "
          f"| {r.yakuji_rx_domestic_fy_yen/1e8:,.0f} | {r.coverage_k1_pct:.1f}% |")
    A("")
    A(f"**2021→2022年度で品目数は{e22.n_products_yoy_pct:+.0f}%増えたのに、")
    A(f"薬価金額は{e22.ndb_amount_yoy_pct:+.1f}%しか増えていない**")
    A(f"（統計側の市場規模はほぼ横ばいで、捕捉率の変化は{e22.coverage_k1_diff_pt:+.1f}"
      "ポイント）。")
    A("")
    A(f"すなわち**足切りで非掲載になっていた{int(e22.n_products_ndb - e21.n_products_ndb):,}"
      "品目は、合計しても市場の1割強**であり、2021年度以前のNDBは金額ベースで")
    A("市場の大宗を既に捕捉していた。これは外部データ（統計）とNDB内部の双方から")
    A("一致して確認できる。")
    A("")
    A("**ただし2014年度（第1回）は例外**である。掲載品目数が"
      f"{int(eff[eff.fiscal_year==2014].iloc[0].n_products_ndb)}品目にとどまり、"
      "捕捉率も")
    A(f"{eff[eff.fiscal_year==2014].iloc[0].coverage_k1_pct:.1f}%（k=1.0）と"
      "他年度より20〜40ポイント低い。")
    A("**2014年度単独の水準・シェアを論じる際は特段の注意を要する。**")
    A("")
    A("## 参考: 未捕捉金額を数量に読み替えた場合")
    A("")
    A("未捕捉金額（統計/k − NDB薬価金額）を単価で割れば非掲載量の目安が出るが、")
    A("**この上限はほとんど情報を持たない**（未捕捉金額の大半は未収載品目ではなく")
    A("価格基準の差 k に由来するため）。参考値として併記する。")
    A("")
    A("| 年度 | 未捕捉金額(億円, k=0.8) | 抗アレルギー点眼の中央単価(円/mL) | 換算mL上限 | 3成分公表量(mL) | 比 |")
    A("|---|--:|--:|--:|--:|--:|")
    for _, r in unacc[unacc.k == 0.8].iterrows():
        t3 = (f"{r.top3_published_ml:,.0f}" if pd.notna(r.top3_published_ml) else "—")
        ratio = (f"{r.ratio_to_top3_at_median_allergy_price:.2f}倍"
                 if pd.notna(r.ratio_to_top3_at_median_allergy_price) else "—")
        A(f"| {int(r.fiscal_year)} | {r.unaccounted_yen/1e8:,.0f} "
          f"| {r.median_yen_per_ml_allergy:.1f} "
          f"| {r.ml_upper_at_median_allergy_price:,.0f} | {t3} | {ratio} |")
    A("")
    A("## 限界")
    A("")
    A("1. **価格基準の差**が最大の不確実性。薬価と実勢販売単価の差（仕切価率k）は")
    A("   品目・年度で異なり、単一のkで代表させている。捕捉率の点推定は成立せず、")
    A("   幅を持った目安としてのみ解釈すべきである。")
    A("2. **内服の眼科用剤**はNDB内服ファイルを取得していないため分子に含まれない")
    A("   （131は点眼・眼軟膏・硝子体注射が大半であり影響は小さいと考えられるが未検証）。")
    A("3. 統計の出荷はメーカー→卸のフロー、NDBは患者への処方。流通在庫の増減、")
    af = "   自費・労災・公費単独レセプト分、院内廃棄は残差に混入する。"
    A(af)
    A("4. **2019年に調査方法が全面変更**（全数オンライン報告化）されており、")
    A("   2018年以前と2019年以降の統計値の接続には注意を要する。")
    A("5. 統計は暦年、NDBは年度。0.75/0.25の按分は月次変動を無視した近似である。")
    A("6. NDBの総計秘匿品目は分子に算入できない（金額的には微小）。")
    A("")
    A("## 位置づけ")
    A("")
    A("本解析は主解析ではなく**参考（triangulation）**である。価格基準の差により")
    A("厳密な捕捉率は確定できないが、「NDB非掲載の眼科用剤が3成分を覆すほど大量に")
    A("存在する」というシナリオが金額面から見て成立しにくいことを外部データで示す。")
    A("")
    return "\n".join(L) + "\n"


def main():
    os.makedirs(OUT, exist_ok=True)

    print("=== 統計側（薬事工業生産動態統計）===")
    yk = pd.DataFrame([read_yakuji_year(y) for y in YEARS])
    p = os.path.join(OUT, "yakuji_eye_shipment.csv")
    yk.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.basename(p)} ({len(yk)} rows)")

    print("=== NDB側（薬効分類131）===")
    nd = []
    for y in YEARS:
        d = read_ndb_year(y)
        print(f"  {y}年度: {len(d)}行 "
              f"薬価金額 {d.amount_yen.sum()/1e8:,.0f}億円 "
              f"（総計秘匿 {int(d.total_censored.sum())}行）")
        nd.append(d)
    nd = backfill_units(pd.concat(nd, ignore_index=True))
    p = os.path.join(OUT, "ndb_131_products.csv")
    nd.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.basename(p)} ({len(nd)} rows)")

    by_year = nd.groupby("year").agg(
        amount_yen=("amount_yen", "sum"), n_products=("product_name", "nunique"),
        n_total_censored=("total_censored", "sum"))
    detail = nd.groupby(["year", "file_kind", "sheet"]).agg(
        amount_yen=("amount_yen", "sum"),
        n_products=("product_name", "nunique")).reset_index()
    p = os.path.join(OUT, "ndb_131_amount_by_year.csv")
    detail.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.basename(p)} ({len(detail)} rows)")

    cov = coverage(by_year, yk)
    p = os.path.join(OUT, "coverage_by_year.csv")
    cov.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.basename(p)} ({len(cov)} rows)")

    # 3成分の公表量（mL）: 抗アレルギー点眼解析 の成果物から
    t3p = os.path.join(PROJECT, "抗アレルギー点眼解析", "05_論文成果物", "公費含めない_new",
                       "論文図表", "csv",
                       "Fig4_trends_shares_bounds__Fig4C_top3_share_bounds.csv")
    top3 = {}
    if os.path.exists(t3p):
        s = pd.read_csv(t3p)
        top3 = dict(zip(s.Year, s.top3_published_mL))

    unacc = unaccounted_bound(nd, cov, top3)
    p = os.path.join(OUT, "unaccounted_volume_bound.csv")
    unacc.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.basename(p)} ({len(unacc)} rows)")

    eff = listing_effect(nd, cov)
    p = os.path.join(OUT, "listing_threshold_effect.csv")
    eff.to_csv(p, index=False, encoding="utf-8-sig")
    print(f"-> {os.path.basename(p)} ({len(eff)} rows)")

    print(f"-> {os.path.basename(figure(cov))}")
    p = os.path.join(OUT, "coverage_report.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(report(cov, unacc, yk, nd, eff))
    print(f"-> {os.path.basename(p)}")


if __name__ == "__main__":
    main()
