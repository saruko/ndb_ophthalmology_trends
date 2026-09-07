# -*- coding: utf-8 -*-
"""s02: 薬価基準収載品目リスト Excel → 年度別名簿パネル

各年度について、年度開始時点の版(start)と年度末時点の版(end)を読み、
薬価基準収載医薬品コード(12桁)の和集合を「その年度に薬価基準にあった品目」とする。
年度途中に収載された品目(endにのみ存在)と年度途中に削除された品目(startにのみ存在)の
双方を分母に含めるため。

列位置は年度で動くため、必ずヘッダ名で解決する。
薬効分類は12桁コードの先頭3桁（NDBの足切りもこの単位で適用される）。

出力: processed/yakka_roster.csv
"""
import os
import json
import re
import pandas as pd

from paths import YAKKA_RAW, OUT_DIR

KIND_JP = {"naiyo": "内用薬", "chusha": "注射薬", "gaiyo": "外用薬", "shika": "歯科用薬剤"}
CODE_RE = re.compile(r"^\d{4}[0-9A-Z]{3}[0-9A-Z]\d{4}$")


def _pick(cols, *keys):
    for k in keys:
        for c in cols:
            if k in str(c):
                return c
    return None


def _read_one(fp):
    xl = pd.ExcelFile(fp)
    df = pd.read_excel(fp, sheet_name=xl.sheet_names[0], header=0, dtype=str)
    cols = list(df.columns)

    c_code = _pick(cols, "薬価基準収載医薬品コード", "医薬品コード")
    if c_code is None:
        raise ValueError("コード列が無い: %s (%s)" % (fp, cols[:6]))
    c_ing = _pick(cols, "成分名")
    c_std = _pick(cols, "規格")
    c_maker = _pick(cols, "メーカー")
    # 2014〜2017年の書式では「規格」がセル結合されており、ヘッダ上の「品名」の位置と
    # 実データの位置がずれる（ヘッダは4列目、データは7列目）。
    # 品名は常にメーカー名列の直前にあるため位置で取る。
    c_name = _pick(cols, "品名")
    if c_maker is not None and cols.index(c_maker) > 0:
        c_name = cols[cols.index(c_maker) - 1]
    c_sen = _pick(cols, "先発医薬品")
    c_price = _pick(cols, "薬価")
    # 「診療報酬において加算等の算定対象となる後発医薬品」列。
    # 値は主に "後発品"、ごく一部に "★"/"☆"（加算対象区分の記号）。
    c_ge = _pick(cols, "加算等の算定対象")
    c_keika = _pick(cols, "経過措置")
    c_biko = _pick(cols, "備考")

    out = pd.DataFrame({
        "yj12": df[c_code].astype(str).str.strip(),
        "ingredient": df[c_ing] if c_ing else None,
        "standard": df[c_std] if c_std else None,
        "product": df[c_name] if c_name else None,
        "maker": df[c_maker] if c_maker else None,
        "senpatsu": df[c_sen] if c_sen else None,
        "ge_mark": df[c_ge].astype(str).str.strip() if c_ge else None,
        "keika": df[c_keika] if c_keika else None,
        "biko": df[c_biko] if c_biko else None,
        "price": pd.to_numeric(df[c_price], errors="coerce") if c_price else None,
    })
    out["is_generic"] = (out["ge_mark"].isin(["後発品", "★", "☆"]).astype(int)
                         if c_ge else 0)
    return out[out["yj12"].apply(lambda s: bool(CODE_RE.match(s)))]


def _snapshot_frames(date):
    """1スナップショット(日付)配下の全剤形を読む。"""
    d = os.path.join(YAKKA_RAW, date)
    frames = []
    for fp in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        m = re.match(r"yakka_%s_(\w+)\.xls" % date, fp)
        if not m:
            continue
        kind = m.group(1)
        try:
            df = _read_one(os.path.join(d, fp))
        except Exception as e:
            print("    ERR %s: %s" % (fp, e))
            continue
        df.insert(0, "kind", KIND_JP.get(kind, kind))
        frames.append(df)
    return frames


def build():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(YAKKA_RAW, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)

    cache = {}
    rows = []
    for fy, snaps in sorted(manifest["years"].items(), key=lambda kv: int(kv[0])):
        parts = []
        for role in ("start", "end"):
            r = snaps.get(role)
            if not r:
                continue
            date = r["date"]
            if date not in cache:
                cache[date] = pd.concat(_snapshot_frames(date), ignore_index=True)
            df = cache[date].copy()
            df["role"] = role
            df["snapshot_date"] = date
            parts.append(df)
        if not parts:
            print("  FY%s: スナップショット無し" % fy)
            continue
        both = pd.concat(parts, ignore_index=True)
        # start と end の和集合。重複コードは end 側(=より新しい情報)を優先
        both["_pri"] = (both["role"] == "end").astype(int)
        both = both.sort_values("_pri", ascending=False)
        uniq = both.drop_duplicates(subset=["kind", "yj12"], keep="first").drop(columns="_pri")
        uniq.insert(0, "fiscal_year", int(fy))
        rows.append(uniq)
        n_start = sum(1 for p in parts if p["role"].iloc[0] == "start")
        print("  FY%s  %s -> %s  %6d 品目 (%d版)" % (
            fy, snaps.get("start", {}).get("date", "-"),
            snaps.get("end", {}).get("date", "-"), len(uniq), len(parts)))

    roster = pd.concat(rows, ignore_index=True)
    roster["class3"] = roster["yj12"].str[:3]
    roster["class4"] = roster["yj12"].str[:4]

    fp = os.path.join(OUT_DIR, "yakka_roster.csv")
    roster.to_csv(fp, index=False, encoding="utf-8-sig")
    print("[s02] 出力: %s (%d行)" % (fp, len(roster)))
    piv = roster.pivot_table(index="fiscal_year", columns="kind", values="yj12", aggfunc="count")
    print(piv.to_string())
    return roster


if __name__ == "__main__":
    build()
