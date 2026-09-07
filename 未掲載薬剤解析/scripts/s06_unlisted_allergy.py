# -*- coding: utf-8 -*-
"""s06: 抗アレルギー点眼薬（9成分）の「薬価基準収載だがNDB未掲載」品目リスト

抗アレルギー点眼解析/05_論文成果物/公費含めない_new/unlisted_products_inventory.csv は
上市メーカー数を手作業で調べて未収載数を推計している。本スクリプトは
薬価基準収載品目リストとの突合により、**どの品目が未掲載か**を品名・メーカー単位で確定し、
併せて既存インベントリとの差異を照合する。

対象: 薬効分類131（眼科用剤）の外用薬に限る（内服錠・点鼻液は除く）。

出力:
  processed/unlisted_allergy_items.csv    品目×年度の掲載/未掲載（長形式）
  processed/unlisted_allergy_summary.csv  成分×年度の上市数・掲載数・未掲載数
  processed/unlisted_allergy_crosscheck.csv 既存インベントリとの差異
  未掲載品目リスト_抗アレルギー点眼薬.md    可読レポート
"""
import os
import re
import pandas as pd

from paths import OUT_DIR, ROOT

# 既存インベントリの code 表記に合わせる（レボカバスチンは LEVOCASTINE）
TARGETS = {
    "エピナスチン": "EPINASTINE",
    "オロパタジン": "OLOPATADINE",
    "レボカバスチン": "LEVOCASTINE",
    "ケトチフェン": "KETOTIFEN",
    "クロモグリク酸": "CROMOGLICATE",
    "ペミロラスト": "PEMIROLAST",
    "トラニラスト": "TRANILAST",
    "アシタザノラスト": "ACITAZANOLAST",
    "イブジラスト": "IBUDILAST",
}

INVENTORY = os.path.join(ROOT, "抗アレルギー点眼解析", "05_論文成果物", "公費含めない_new",
                         "unlisted_products_inventory.csv")
REPORT = os.path.join(os.path.dirname(OUT_DIR), "未掲載品目リスト_抗アレルギー点眼薬.md")


def _load():
    roster = pd.read_csv(os.path.join(OUT_DIR, "yakka_roster.csv"), dtype={"yj12": str})
    pub = pd.read_csv(os.path.join(OUT_DIR, "ndb_published.csv"), dtype={"yj12": str})
    roster["class3"] = roster["yj12"].str[:3]

    pat = "|".join(TARGETS)
    r = roster[(roster["kind"] == "外用薬") & (roster["class3"] == "131") &
               roster["ingredient"].astype(str).str.contains(pat, na=False)].copy()
    r["drug"] = r["ingredient"].astype(str).apply(
        lambda s: next((v for k, v in TARGETS.items() if k in s), None))

    p = (pub.groupby(["fiscal_year", "kind", "yj12"], as_index=False)
            .agg(total_qty=("total_qty", "sum"),
                 n_brands=("n_brands", "max"),
                 settings=("setting", lambda s: "/".join(sorted(set(s))))))

    m = r.merge(p, on=["fiscal_year", "kind", "yj12"], how="left")
    m["listed"] = m["total_qty"].notna()
    m["type"] = m["is_generic"].map({1: "後発", 0: "先発等"})
    # 統一名収載（価格帯集約）行はメーカー名が空欄で、複数銘柄を1コードに代表する
    m["unified_name"] = m["maker"].isna()

    # 経過措置の期限が年度開始(4/1)より前の品目は、その年度には使用できないため
    # 分母から除外する（年度開始版と年度末版の和集合を分母にした副作用の補正）。
    era = {"R": 2018, "H": 1988, "S": 1925}

    def _expiry(s):
        if not isinstance(s, str):
            return None
        mm = re.search(r"([RHS])\s*(\d+)\s*[.\-/年]\s*(\d+)\s*[.\-/月]\s*(\d+)", s)
        if not mm:
            return None
        return ((era[mm.group(1)] + int(mm.group(2))) * 10000
                + int(mm.group(3)) * 100 + int(mm.group(4)))

    exp = m["keika"].apply(_expiry)
    expired = exp.notna() & (exp < m["fiscal_year"] * 10000 + 401)
    n_drop = int(expired.sum())
    if n_drop:
        print("[s06] 経過措置切れで分母から除外: %d件" % n_drop)
        for _, x in m[expired].iterrows():
            print("       FY%d %s (%s)" % (x["fiscal_year"],
                                           str(x["product"]).strip(), x["keika"]))
    return m[~expired].copy()


def run():
    m = _load()

    items = m[["drug", "fiscal_year", "type", "yj12", "product", "maker", "price",
               "listed", "unified_name", "total_qty", "n_brands", "settings",
               "biko", "keika"]] \
        .sort_values(["drug", "fiscal_year", "type", "product"])
    items.to_csv(os.path.join(OUT_DIR, "unlisted_allergy_items.csv"),
                 index=False, encoding="utf-8-sig")

    summary = (m.groupby(["drug", "fiscal_year", "type"], as_index=False)
                 .agg(n_marketed=("yj12", "size"), n_listed=("listed", "sum"),
                      n_unified=("unified_name", "sum")))
    summary["n_unlisted"] = summary["n_marketed"] - summary["n_listed"]
    summary.to_csv(os.path.join(OUT_DIR, "unlisted_allergy_summary.csv"),
                   index=False, encoding="utf-8-sig")

    # --- 既存インベントリとの照合（後発品） ---
    cross = None
    if os.path.exists(INVENTORY):
        inv = pd.read_csv(INVENTORY)
        gen = summary[summary["type"] == "後発"].rename(
            columns={"drug": "code", "fiscal_year": "year"})
        cross = inv.merge(
            gen[["code", "year", "n_marketed", "n_unified", "n_listed", "n_unlisted"]],
            on=["code", "year"], how="left")
        cross["差_上市"] = cross["n_marketed"] - cross["marketed_generic_lo"]
        cross["差_未掲載"] = cross["n_unlisted"] - cross["unlisted_generic_lo"]
        cross.to_csv(os.path.join(OUT_DIR, "unlisted_allergy_crosscheck.csv"),
                     index=False, encoding="utf-8-sig")

    _write_report(m, summary, cross)
    print("[s06] 出力: unlisted_allergy_items.csv / _summary.csv / _crosscheck.csv")
    print("[s06] レポート: %s" % REPORT)

    print("\n成分×年度 の後発品 上市/掲載/未掲載（薬価基準収載品目リスト基準）")
    piv = (summary[summary["type"] == "後発"]
           .pivot_table(index="fiscal_year", columns="drug", values="n_unlisted",
                        fill_value=0))
    print("未掲載品目数:")
    print(piv.to_string())
    return items


def _write_report(m, summary, cross):
    L = []
    L.append("# NDB未掲載の抗アレルギー点眼薬 品目リスト\n")
    L.append("薬価基準収載品目リスト（各年度の年度開始版と年度末版の和集合）を分母として、")
    L.append("NDBオープンデータ薬剤データ（外用薬・3診療区分のいずれか）に")
    L.append("行そのものが存在しない品目を特定した。\n")
    L.append("対象は薬効分類131（眼科用剤）の外用薬のみ。内服錠・点鼻液は含まない。\n")
    L.append("公費を含む通常ファイルと `_nokouhi` ファイルで、対象成分の掲載品目コードは")
    L.append("完全に一致することを2024年度で確認済み（掲載/未掲載の判定は公費の扱いに依存しない）。\n")

    L.append("計数単位は薬価基準収載医薬品コード（12桁）である。統一名収載（価格帯集約）の")
    L.append("行はメーカー名が空欄で複数銘柄を1コードで代表するため、")
    L.append("**コード数は銘柄数より少なくなる**（`unified_name` 列と下表の「うち統一名」で識別できる）。\n")

    L.append("## 1. 成分×年度の集計（後発品）\n")
    L.append("| 成分 | 年度 | 薬価収載コード | うち統一名 | NDB掲載 | **未掲載** |")
    L.append("|---|---|---|---|---|---|")
    gen = summary[summary["type"] == "後発"].sort_values(["drug", "fiscal_year"])
    for _, r in gen.iterrows():
        if r["n_marketed"] == 0:
            continue
        L.append("| %s | %d | %d | %d | %d | **%d** |" % (
            r["drug"], r["fiscal_year"], r["n_marketed"], r["n_unified"],
            r["n_listed"], r["n_unlisted"]))

    L.append("\n## 2. 未掲載だった品目（後発品・品名/メーカー単位）\n")
    un = m[(~m["listed"]) & (m["is_generic"] == 1)]
    for drug, d in un.groupby("drug"):
        L.append("### %s\n" % drug)
        for fy, dd in d.groupby("fiscal_year"):
            L.append("**%d年度（%d品目）**\n" % (fy, len(dd)))
            L.append("| 薬価基準収載医薬品コード | 品名 | メーカー | 薬価 |")
            L.append("|---|---|---|---|")
            for _, x in dd.sort_values("product").iterrows():
                L.append("| %s | %s | %s | %s |" % (
                    x["yj12"], str(x["product"]).strip(), str(x["maker"]).strip(),
                    x["price"]))
            L.append("")

    L.append("\n## 3. 未掲載だった品目（先発等）\n")
    unb = m[(~m["listed"]) & (m["is_generic"] == 0)]
    if len(unb) == 0:
        L.append("該当なし（先発品はすべての年度でNDBに掲載されていた）。\n")
    else:
        L.append("| 成分 | 年度 | コード | 品名 | メーカー |")
        L.append("|---|---|---|---|---|")
        for _, x in unb.sort_values(["drug", "fiscal_year"]).iterrows():
            L.append("| %s | %d | %s | %s | %s |" % (
                x["drug"], x["fiscal_year"], x["yj12"],
                str(x["product"]).strip(), str(x["maker"]).strip()))

    if cross is not None:
        L.append("\n## 4. 既存 unlisted_products_inventory.csv との照合\n")
        L.append("既存は上市**メーカー数**の手作業調査、本表は薬価基準収載品目リストの")
        L.append("**12桁コード数**。差の原因は2種類あり、性質が異なる。\n")
        L.append("- **A: 統一名収載による集約**（「うち統一名」が1以上の行）。")
        L.append("  両者は単位が違うだけで、どちらも誤りではない。")
        L.append("  NDBとの突合には12桁コード単位が正しく、")
        L.append("  「市場に何銘柄あったか」を言うにはメーカー数が近い。")
        L.append("- **B: 既存リストの収載時期の誤り**。実データの備考欄で収載日を確認できる。\n")
        L.append("| 成分 | 年度 | 既存 上市 | 本突合 コード | うち統一名 | 既存 未掲載 | 本突合 未掲載 | 差 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for _, r in cross.iterrows():
            if pd.isna(r["n_marketed"]) or r["差_未掲載"] == 0:
                continue
            L.append("| %s | %d | %s | %d | %d | %s | %d | %+d |" % (
                r["code"], r["year"], r["marketed_generic_lo"], r["n_marketed"],
                r["n_unified"], r["unlisted_generic_lo"], r["n_unlisted"],
                r["差_未掲載"]))
        L.append("\n### 確認できた収載時期の誤り（種別B）\n")
        L.append("- エピナスチン「ＳＥＣ」（参天アイケア, 1319762Q1150）は")
        L.append("  **令和6年12月6日収載**（20250319版の備考欄に `R6.12.6収載`）。")
        L.append("  既存リストは2021年度から13社として計上しているが、")
        L.append("  2021〜2023年度の実在は12コードである。")
        L.append("  この結果、2022・2023年度の後発品未掲載は既存の1品目ではなく **0品目**。")
        L.append("- エピナスチンLXの後発品も同日収載の2品目（「ＳＥＣ」「ニットー」）のみで、")
        L.append("  既存の「LX 5社以上」は過大。2024年度の未掲載は既存の3品目ではなく **0品目**。")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
