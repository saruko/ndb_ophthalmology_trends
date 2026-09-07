# -*- coding: utf-8 -*-
"""s07: unlisted_products_inventory.csv の差し替え版（v2）の生成

既存インベントリ（手作業のメーカー数調査）を、薬価基準収載品目リストとNDBの
実データ突合で置き換える。列構成は既存と互換（同名列は同じ意味で埋める）とし、
検証用の列を末尾に追加する。

計数単位: 薬価基準収載医薬品コード（12桁）。
  - 統一名収載（メーカー名空欄の価格帯集約行）は1コード=複数銘柄なので、
    銘柄数が必要な用途では n_unified 列を参照のこと。
  - 経過措置の期限が年度開始前に切れた品目は分母から除外済み（s06）。

出力:
  抗アレルギー点眼解析/05_論文成果物/公費含めない_new/未掲載薬について/
    unlisted_products_inventory_v2.csv
    修正内容と根拠.md
"""
import os
import pandas as pd

from paths import OUT_DIR, ROOT

DEST = os.path.join(ROOT, "抗アレルギー点眼解析", "05_論文成果物", "公費含めない_new",
                    "未掲載薬について")
INV = os.path.join(ROOT, "抗アレルギー点眼解析", "05_論文成果物", "公費含めない_new",
                   "unlisted_products_inventory.csv")

JP = {
    "EPINASTINE": "エピナスチン塩酸塩", "OLOPATADINE": "オロパタジン塩酸塩",
    "LEVOCASTINE": "レボカバスチン塩酸塩", "KETOTIFEN": "ケトチフェンフマル酸塩",
    "CROMOGLICATE": "クロモグリク酸ナトリウム", "PEMIROLAST": "ペミロラストカリウム",
    "TRANILAST": "トラニラスト", "ACITAZANOLAST": "アシタザノラスト水和物",
    "IBUDILAST": "イブジラスト",
}


def run():
    os.makedirs(DEST, exist_ok=True)
    items = pd.read_csv(os.path.join(OUT_DIR, "unlisted_allergy_items.csv"),
                        dtype={"yj12": str})
    pub = pd.read_csv(os.path.join(OUT_DIR, "ndb_published.csv"), dtype={"yj12": str})
    inv = pd.read_csv(INV)

    # NDB側の銘柄数（Yコード数）: 診療区分をまたぐ最大値
    brands = pub.groupby(["fiscal_year", "yj12"], as_index=False)["n_brands"].max()
    m = items.merge(brands, on=["fiscal_year", "yj12"], how="left",
                    suffixes=("", "_mx"))
    m["brands_ndb"] = m["n_brands_mx"].fillna(0).astype(int)

    def block(df):
        return pd.Series({
            "codes": len(df),
            "unified": int(df["unified_name"].sum()),
            "listed": int(df["listed"].sum()),
            "unlisted": int(len(df) - df["listed"].sum()),
            "brands_listed": int(df["brands_ndb"].sum()),
            "unlisted_names": "; ".join(
                str(x).strip() for x in df.loc[~df["listed"], "product"].fillna("")),
        })

    gen = (m[m["type"] == "後発"].groupby(["drug", "fiscal_year"])
           .apply(block, include_groups=False).reset_index())
    bra = (m[m["type"] == "先発等"].groupby(["drug", "fiscal_year"])
           .apply(block, include_groups=False).reset_index())

    g = gen.merge(bra, on=["drug", "fiscal_year"], how="outer",
                  suffixes=("_g", "_b")).fillna(0)

    rows = []
    for _, r in g.sort_values(["drug", "fiscal_year"]).iterrows():
        drug, fy = r["drug"], int(r["fiscal_year"])
        gnote = []
        if r["codes_g"] == 0:
            gnote.append("後発品の薬価基準収載なし")
        if r["unified_g"] > 0:
            gnote.append("統一名収載%d件を含む（1コード=複数銘柄）" % r["unified_g"])
        if r["unlisted_names_g"]:
            gnote.append("未掲載: " + r["unlisted_names_g"])
        bnote = []
        if r["unified_b"] > 0:
            bnote.append("統一名収載%d件を含む" % r["unified_b"])
        if r["unlisted_names_b"]:
            bnote.append("未掲載: " + r["unlisted_names_b"])
        rows.append({
            "code": drug, "drug": JP.get(drug, drug), "year": fy,
            "listed_generic_makers": int(r["listed_g"]),
            "marketed_generic_lo": int(r["codes_g"]),
            "marketed_generic_hi": (int(r["codes_g"]) if r["unified_g"] == 0 else ""),
            "unlisted_generic_lo": int(r["unlisted_g"]),
            "marketed_generic_note": " / ".join(gnote),
            "listed_brand_products": int(r["listed_b"]),
            "marketed_brand": int(r["codes_b"]),
            "unlisted_brand": int(r["unlisted_b"]),
            "marketed_brand_note": " / ".join(bnote),
            # ---- 追加の検証列 ----
            "n_unified_generic": int(r["unified_g"]),
            "n_unified_brand": int(r["unified_b"]),
            "ndb_listed_brands_generic": int(r["brands_listed_g"]),
            "unit": "薬価基準収載医薬品コード(12桁)",
            "source": "薬価基準収載品目リスト(年度開始版∪年度末版, 経過措置切れ除外)×NDB",
        })

    v2 = pd.DataFrame(rows)
    fp = os.path.join(DEST, "unlisted_products_inventory_v2.csv")
    v2.to_csv(fp, index=False, encoding="utf-8-sig")
    print("[s07] 出力: %s (%d行)" % (fp, len(v2)))

    # ---- 差分レポート ----
    old = inv.set_index(["code", "year"])
    new = v2.set_index(["code", "year"])
    L = ["# unlisted_products_inventory v2 の修正内容と根拠\n",
         "計数単位を「上市メーカー数（手作業調査）」から「薬価基準収載医薬品コード"
         "（12桁）の実データ」に変更した。分母は各年度の年度開始版と年度末版の和集合、",
         "経過措置の期限が年度開始前に切れた品目は除外。突合はNDB薬剤データの",
         "薬価基準収載医薬品コードとの完全一致による。\n",
         "## 値が変わったセル（後発品）\n",
         "| 成分 | 年度 | 旧: 上市/掲載/未掲載 | 新: 収載C/掲載/未掲載 | 分類 |",
         "|---|---|---|---|---|"]
    n_diff = 0
    for key in new.index:
        if key not in old.index:
            continue
        o, n = old.loc[key], new.loc[key]
        if (int(o["marketed_generic_lo"]) == n["marketed_generic_lo"]
                and int(o["unlisted_generic_lo"]) == n["unlisted_generic_lo"]):
            continue
        n_diff += 1
        kind = ("統一名収載による単位差" if n["n_unified_generic"] > 0
                else "品目数の修正")
        L.append("| %s | %d | %d /%d /%d | %d /%d /%d | %s |" % (
            key[0], key[1],
            o["marketed_generic_lo"], o["listed_generic_makers"],
            o["unlisted_generic_lo"],
            n["marketed_generic_lo"], n["listed_generic_makers"],
            n["unlisted_generic_lo"], kind))
    L += ["",
          "## 主な根拠\n",
          "1. **エピナスチン「ＳＥＣ」(1319762Q1150) は令和6年12月6日収載**"
          "（薬価基準リスト20250319版の備考欄）。LX後発2品目(「ＳＥＣ」「ニットー」)も同日収載。",
          "   2021〜2023年度の後発は12コード、2022年度以降の未掲載は0。",
          "2. **レボカバスチン後発は年度により9〜11コード**（既存は全年10で固定）。",
          "3. **トラニラスト後発は2014・2015・2019年度に7コード**"
          "（アレニスト・ガレシロール等の別販売名を含む）。",
          "4. **ペミロラスト後発は2017・2018年度に3コード**"
          "（「杏林」1319735Q1080が2017年に追加）。2019年度はアラジオフが経過措置切れ(H30.9.30)のため3。",
          "5. **経過措置切れの除外**: ケトテン/フマルフェン(FY2015, H26.9.30)、"
          "クモロールＰＦ(FY2019, H31.3.31)、アラジオフ(FY2019, H30.9.30)、"
          "クロモグリク酸「ファイザー」(FY2023, R5.3.31)。",
          "6. **先発品の未掲載を新規計上**: トラメラス/トラメラスＰＦ(2014〜2021)、"
          "インタール点眼液2%(2014〜2020)、ザジテン点眼液(2014〜2021)、"
          "アレギサール/ペミラストン(2014〜2021)ほか。既存のunlisted_brandは大半0だった。",
          "",
          "## 使用上の注意\n",
          "> **本v2を `build_unlisted_sensitivity.py` の入力に差し替えてはならない。**",
          "> 順位ベース上限 `公表総量 + Σ_区分(未掲載品目数 × その区分の最小公表総計)` の",
          "> 「最小公表総計」はNDBの**銘柄（Yコード）単位**の値なので、掛ける未掲載品目数も",
          "> 銘柄単位でなければならない。v2の12桁コード数は統一名収載で複数銘柄が畳まれており、",
          "> 銘柄数の**下限**にすぎない。差し替えると上限が非保守側に縮む。",
          "> 上限式の入力には既存の `unlisted_products_inventory.csv`（メーカー数≒銘柄数）を使い、",
          "> v2は「どの品目が未掲載か」の同定と収載時期の検証にのみ用いること。\n",
          "- 統一名収載（`n_unified_*`>0）の年度は、1コードに複数銘柄が畳まれている。",
          "  影響が出るのは「未掲載数>0 かつ 公表総量が存在する（NRでない）」セルに限られ、",
          "  本データでは **クロモグリク酸ナトリウム 2015〜2018年度** が該当する",
          "  （インタール点眼液UDが掲載されているため公表総量がある）。",
          "  この4年度でv2に差し替えると順位ベース上限は次のように縮む:\n",
          "  | 年度 | 未掲載数 v1/v2 | 上限 v1 | 上限 v2 | 差 |",
          "  |---|---|--:|--:|--:|",
          "  | 2015 | 14 / 12 | 111,260,676 | 95,456,346 | −14.2% |",
          "  | 2016 | 14 / 11 | 125,580,345 | 98,799,284 | −21.3% |",
          "  | 2017 | 14 / 12 | 126,976,091 | 108,918,067 | −14.2% |",
          "  | 2018 | 14 / 13 | 135,658,630 | 126,007,412 | −7.1% |\n",
          "  それ以外の統一名収載年度（ケトチフェン・トラニラスト2020〜2021・",
          "  レボカバスチン2022〜2024など）は全品目NRか未掲載0のため上限に影響しない。",
          "- 品目レベルの内訳は 未掲載薬剤解析/processed/unlisted_allergy_items.csv を参照。"]
    rp = os.path.join(DEST, "修正内容と根拠.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("[s07] 差分レポート: %s（変更セル %d件）" % (rp, n_diff))
    return v2


if __name__ == "__main__":
    run()
