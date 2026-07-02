#!/usr/bin/env python3
"""
build_real_covariates.py
公的統計データ（e-Stat）から実共変量CSVを構築する。

データソース:
  1. 人口推計（総務省統計局）: 都道府県別 総人口・65歳以上人口（各年10月1日現在）
  2. 医師・歯科医師・薬剤師統計（厚生労働省）: 都道府県別 眼科医師数（隔年）
  3. 医療施設調査（厚生労働省）: 都道府県別 眼科標榜施設数（3年周期静態調査）

出力:
  data/covariates/prefecture_covariates.csv
"""
import os
import sys
import time
import re
import urllib.request
import numpy as np
import pandas as pd

RAW_DIR = "data/real_covariates/raw_download"
OUT_DIR = "data/covariates"

PREFECTURES_47 = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

PREF_CODE_MAP = {f"{i+1:02d}000": PREFECTURES_47[i] for i in range(47)}

PREF_EN_MAP = {
    "Hokkaido": "北海道", "Aomori": "青森県", "Iwate": "岩手県",
    "Miyagi": "宮城県", "Akita": "秋田県", "Yamagata": "山形県",
    "Fukushima": "福島県", "Ibaraki": "茨城県", "Tochigi": "栃木県",
    "Gunma": "群馬県", "Saitama": "埼玉県", "Chiba": "千葉県",
    "Tokyo": "東京都", "Kanagawa": "神奈川県", "Niigata": "新潟県",
    "Toyama": "富山県", "Ishikawa": "石川県", "Fukui": "福井県",
    "Yamanashi": "山梨県", "Nagano": "長野県", "Gifu": "岐阜県",
    "Shizuoka": "静岡県", "Aichi": "愛知県", "Mie": "三重県",
    "Shiga": "滋賀県", "Kyoto": "京都府", "Osaka": "大阪府",
    "Hyogo": "兵庫県", "Nara": "奈良県", "Wakayama": "和歌山県",
    "Tottori": "鳥取県", "Shimane": "島根県", "Okayama": "岡山県",
    "Hiroshima": "広島県", "Yamaguchi": "山口県", "Tokushima": "徳島県",
    "Kagawa": "香川県", "Ehime": "愛媛県", "Kochi": "高知県",
    "Fukuoka": "福岡県", "Saga": "佐賀県", "Nagasaki": "長崎県",
    "Kumamoto": "熊本県", "Oita": "大分県", "Miyazaki": "宮崎県",
    "Kagoshima": "鹿児島県", "Okinawa": "沖縄県",
}

# ── statInfId 一覧（全てe-Stat: https://www.e-stat.go.jp/ ）──

PHYSICIAN_IDS = {
    # 医師・歯科医師・薬剤師統計 → 都道府県×主たる診療科別 医療施設従事医師数
    2014: ("000031336084", "ishi_2014.csv"),    # 平成26年 表41
    2016: ("000031653233", "ishi_2016.csv"),    # 平成28年 表41
    2018: ("000031889171", "ishi_2018.csv"),    # 平成30年 表21
    2020: ("000032179783", "ishi_2020_t34.csv"),# 令和2年 表7（就業形態別あり）
    2022: ("000040155804", "ishi_2022_t34.csv"),# 令和4年 表34
}

POPULATION_IDS = {
    # 人口推計 → 都道府県×年齢3区分別人口（各年10月1日現在）
    # XLS形式 (2014-2019), XLSX形式 (2021-2023)
    2014: ("000029026260", "pop_2014.xlsx"),
    2015: ("000031594311", "pop_2015.xlsx"),     # 新規: 国勢調査
    2016: ("000031560320", "pop_2016.xlsx"),
    2017: ("000031690324", "pop_2017.xlsx"),
    2018: ("000031807148", "pop_2018.xlsx"),
    2019: ("000031921680", "pop_2019.xlsx"),
    2020: ("000032166849", "pop_2015_2020.xlsx"), # 新規: 補間補正人口
    2021: ("000032191052", "pop_2021.xlsx"),
    2022: ("000040045497", "pop_2022.xlsx"),
    2023: ("000040166083", "pop_2023.xlsx"),
}

FACILITY_IDS = {
    # 医療施設調査（静態調査）→ 一般診療所数（重複計上）診療科目×都道府県別
    2014: ("000031336352", "facility_2014_overlap.csv"),  # 新規
    2017: ("000031780646", "facility_2017_overlap.csv"),  # 新規
    2020: ("000032191948", "facility_2020_overlap.csv"),  # 令和2年 表T90
    2023: ("000040222860", "facility_2023_overlap.csv"),  # 令和5年 表89
}

# ── ダウンロード ──

def _download(stat_inf_id, filename, file_kind=1):
    filepath = os.path.join(RAW_DIR, filename)
    if os.path.exists(filepath):
        return filepath
    url = (f"https://www.e-stat.go.jp/stat-search/file-download"
           f"?statInfId={stat_inf_id}&fileKind={file_kind}")
    print(f"  DL {filename} (statInfId={stat_inf_id}, fileKind={file_kind})")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    with open(filepath, "wb") as f:
        f.write(data)
    print(f"     → {len(data):,} bytes")
    time.sleep(1)
    return filepath


def download_all():
    os.makedirs(RAW_DIR, exist_ok=True)
    print("=== 医師統計 (CSV, fileKind=1) ===")
    for year, (sid, fname) in PHYSICIAN_IDS.items():
        _download(sid, fname, file_kind=1)
    print("=== 人口推計 (Excel, fileKind=0) ===")
    for year, (sid, fname) in POPULATION_IDS.items():
        _download(sid, fname, file_kind=0)
    print("=== 医療施設調査 (CSV, fileKind=1) ===")
    for year, (sid, fname) in FACILITY_IDS.items():
        _download(sid, fname, file_kind=1)


# ── 都道府県名の正規化 ──

def _normalize_pref(text):
    """文字列から都道府県名を抽出（全角数字プレフィクスや空白を除去）"""
    if not isinstance(text, str):
        return None
    s = re.sub(r"[０-９0-9\s　]+", "", text.strip())
    for pref in PREFECTURES_47:
        base = pref.rstrip("県府都")
        if base in s:
            return pref
    return None


# ── 医師統計パーサー ──

def parse_physician_csv(filepath, year):
    """医師統計CSVから都道府県別の眼科医師数を抽出"""
    with open(filepath, "rb") as f:
        raw = f.read()
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    else:
        raise RuntimeError(f"Cannot decode {filepath}")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # ヘッダー行で「眼科」列を探す
    ganka_col = None
    header_row = None
    for i, line in enumerate(lines):
        cols = line.split(",")
        for j, c in enumerate(cols):
            if c.strip() == "眼科":
                ganka_col = j
                header_row = i
                break
        if ganka_col is not None:
            break
    if ganka_col is None:
        raise ValueError(f"「眼科」列が見つかりません: {filepath}")

    results = {}
    for line in lines[header_row + 1:]:
        cols = line.split(",")
        if len(cols) <= ganka_col:
            continue
        pref = None
        for c in cols[:6]:
            pref = _normalize_pref(c)
            if pref:
                break
        if pref is None or pref in results:
            continue
        val_str = cols[ganka_col].strip().replace(" ", "").replace("　", "")
        if val_str in ("-", "…", ""):
            val = 0
        else:
            try:
                val = int(val_str)
            except ValueError:
                continue
        results[pref] = val
    return results


def build_physician_df():
    """全年度の眼科医師数DataFrameを構築（隔年→線形補間）"""
    print("\n=== 医師統計パース ===")
    records = []
    for year, (_, fname) in sorted(PHYSICIAN_IDS.items()):
        fp = os.path.join(RAW_DIR, fname)
        data = parse_physician_csv(fp, year)
        print(f"  {year}: {len(data)} prefectures, 全国眼科医={sum(data.values())}")
        for pref, val in data.items():
            records.append({"year": year, "prefecture": pref, "ophthalmologists": val})
    df = pd.DataFrame(records)

    # 2014-2023の全都道府県×年を作り、線形補間
    idx = pd.MultiIndex.from_product(
        [range(2014, 2024), PREFECTURES_47], names=["year", "prefecture"]
    )
    df_full = pd.DataFrame(index=idx).reset_index()
    df_full = df_full.merge(df, on=["year", "prefecture"], how="left")
    df_full = df_full.sort_values(["prefecture", "year"])
    df_full["ophthalmologists"] = (
        df_full.groupby("prefecture")["ophthalmologists"]
        .transform(lambda s: s.interpolate(method="linear").ffill().bfill())
    )
    df_full["ophthalmologists"] = df_full["ophthalmologists"].round().astype(int)
    return df_full


# ── 人口推計パーサー ──

def parse_population_xls(filepath, year):
    """XLS形式（2014-2019）の人口推計を解析。単位: 千人"""
    df = pd.read_excel(filepath, header=None, engine="xlrd")
    results = {}
    for i, row in df.iterrows():
        vals = [v if pd.notna(v) else "" for v in row]
        # 日本語都道府県名は col 7（全国行）または col 9（都道府県行）
        pref = None
        for c in (7, 9):
            if len(vals) > c:
                pref = _normalize_pref(str(vals[c]))
                if pref:
                    break
        if pref is None or pref in results:
            continue
        try:
            total = int(float(vals[12])) * 1000
            over65 = int(float(vals[15])) * 1000
        except (ValueError, IndexError):
            continue
        results[pref] = (total, over65)
    return results


def parse_population_xlsx(filepath, year):
    """XLSX形式（2021-2023）の人口推計を解析。単位: 千人"""
    df = pd.read_excel(filepath, header=None, engine="openpyxl")
    results = {}
    for i, row in df.iterrows():
        vals = [v if pd.notna(v) else "" for v in row]
        code = str(vals[10]).strip() if len(vals) > 10 else ""
        if code in PREF_CODE_MAP:
            pref = PREF_CODE_MAP[code]
            try:
                total = int(float(vals[14])) * 1000
                over65 = int(float(vals[17])) * 1000
            except (ValueError, IndexError):
                continue
            if pref not in results:
                results[pref] = (total, over65)
    return results


def parse_population_2015(filepath):
    """2015年国勢調査（pop_2015.xlsx）を解析。単位: 人（そのまま使用）"""
    df = pd.read_excel(filepath, header=None)
    results = {}
    col_code = 1
    col_name = 6
    col_total = None
    col_over65 = None
    
    for c in range(df.shape[1]):
        val_r6 = str(df.iloc[6, c]).strip()
        val_r8 = str(df.iloc[8, c]).strip()
        if ("人口総数" in val_r6 or "総数" in val_r8) and col_total is None:
            if "人口総数" in val_r6:
                col_total = c
        if ("65歳以上" in val_r6 or "65歳以上" in val_r8) and col_over65 is None:
            if "世帯" not in val_r6 and "世帯" not in val_r8:
                col_over65 = c
                
    if col_total is None: col_total = 8
    if col_over65 is None: col_over65 = 19
    
    for idx, row in df.iterrows():
        code_val = str(row[col_code]).strip()
        if len(code_val) == 5 and code_val.endswith("000") and code_val != "00000":
            pref = _normalize_pref(str(row[col_name]))
            if pref:
                try:
                    tot = int(row[col_total])
                    o65 = int(row[col_over65])
                    results[pref] = (tot, o65)
                except (ValueError, TypeError):
                    continue
    return results


def parse_population_2020(filepath):
    """2020年人口推計補正（pop_2015_2020.xlsx）から2020年時点の総人口・65歳以上人口を抽出。単位: 千人"""
    df = pd.read_excel(filepath, header=None)
    results = {}
    for idx, row in df.iterrows():
        time_val = str(row[1]).strip()
        pop_type = str(row[2]).strip()
        code_val = str(row[3]).strip()
        region = str(row[4]).strip()
        
        if "2020年" in time_val and pop_type == "総人口":
            if len(code_val) == 5 and code_val.endswith("000") and code_val != "00000":
                pref = _normalize_pref(region)
                if pref:
                    try:
                        tot = int(float(row[7]) * 1000)
                        o65 = int(float(row[10]) * 1000)
                        results[pref] = (tot, o65)
                    except (ValueError, TypeError):
                        continue
    return results


def build_population_df():
    """全年度の人口DataFrameを構築（欠損年は線形補間）"""
    print("\n=== 人口推計パース ===")
    records = []
    for year, (_, fname) in sorted(POPULATION_IDS.items()):
        fp = os.path.join(RAW_DIR, fname)
        if year == 2015:
            data = parse_population_2015(fp)
        elif year == 2020:
            data = parse_population_2020(fp)
        else:
            with open(fp, "rb") as f:
                sig = f.read(4)
            is_xls = (sig == bytes.fromhex("d0cf11e0"))
            if is_xls:
                data = parse_population_xls(fp, year)
            else:
                data = parse_population_xlsx(fp, year)
                
        total_pop = sum(v[0] for v in data.values())
        print(f"  {year}: {len(data)} prefectures, 総人口={total_pop:,}")
        for pref, (tot, o65) in data.items():
            records.append({
                "year": year, "prefecture": pref,
                "population_total": tot, "population_65plus": o65,
            })
    df = pd.DataFrame(records)

    idx = pd.MultiIndex.from_product(
        [range(2014, 2024), PREFECTURES_47], names=["year", "prefecture"]
    )
    df_full = pd.DataFrame(index=idx).reset_index()
    df_full = df_full.merge(df, on=["year", "prefecture"], how="left")
    df_full = df_full.sort_values(["prefecture", "year"])
    for col in ["population_total", "population_65plus"]:
        df_full[col] = (
            df_full.groupby("prefecture")[col]
            .transform(lambda s: s.interpolate(method="linear").ffill().bfill())
        )
        df_full[col] = df_full[col].round().astype(int)
    return df_full


# ── 医療施設調査パーサー ──

def parse_facility_csv(filepath, year):
    """医療施設調査CSVから都道府県別の眼科標榜施設数を抽出"""
    with open(filepath, "rb") as f:
        raw = f.read()
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    else:
        raise RuntimeError(f"Cannot decode {filepath}")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # ヘッダー行で「眼科」列を探す
    ganka_col = None
    header_row = None
    for i, line in enumerate(lines):
        cols = line.split(",")
        for j, c in enumerate(cols):
            if c.strip() == "眼科":
                ganka_col = j
                header_row = i
                break
        if ganka_col is not None:
            break

    if ganka_col is None:
        print(f"  WARNING: 「眼科」列が見つかりません: {filepath}")
        return {}

    results = {}
    for line in lines[header_row + 1:]:
        cols = line.split(",")
        if len(cols) <= ganka_col:
            continue
        pref = None
        for c in cols[:6]:
            pref = _normalize_pref(c)
            if pref:
                break
        if pref is None or pref in results:
            continue
        val_str = cols[ganka_col].strip().replace(" ", "").replace("　", "")
        if val_str in ("-", "…", ""):
            val = 0
        else:
            try:
                val = int(val_str)
            except ValueError:
                continue
        results[pref] = val
    return results


def build_facility_df():
    """施設数DataFrameを構築（補間あり）"""
    print("\n=== 医療施設調査パース ===")
    records = []
    for year, (_, fname) in sorted(FACILITY_IDS.items()):
        fp = os.path.join(RAW_DIR, fname)
        if not os.path.exists(fp):
            print(f"  {year}: ファイルなし、スキップ")
            continue
        data = parse_facility_csv(fp, year)
        if data:
            total = sum(data.values())
            print(f"  {year}: {len(data)} prefectures, 全国眼科施設={total}")
            for pref, val in data.items():
                records.append({"year": year, "prefecture": pref, "facilities": val})
        else:
            print(f"  {year}: パース失敗")

    if not records:
        print("  施設データなし → 全て0で埋めます")
        for y in range(2014, 2024):
            for p in PREFECTURES_47:
                records.append({"year": y, "prefecture": p, "facilities": 0})
        return pd.DataFrame(records)

    df = pd.DataFrame(records)
    idx = pd.MultiIndex.from_product(
        [range(2014, 2024), PREFECTURES_47], names=["year", "prefecture"]
    )
    df_full = pd.DataFrame(index=idx).reset_index()
    df_full = df_full.merge(df, on=["year", "prefecture"], how="left")
    df_full = df_full.sort_values(["prefecture", "year"])
    df_full["facilities"] = (
        df_full.groupby("prefecture")["facilities"]
        .transform(lambda s: s.interpolate(method="linear").ffill().bfill())
    )
    df_full["facilities"] = df_full["facilities"].round().astype(int)
    return df_full


# ── メイン ──

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1. ダウンロード
    print("=" * 60)
    print("STEP 1: ダウンロード")
    print("=" * 60)
    download_all()

    # 2. パース & 結合
    print("\n" + "=" * 60)
    print("STEP 2: パース & 結合")
    print("=" * 60)
    df_pop = build_population_df()
    df_doc = build_physician_df()
    df_fac = build_facility_df()

    df = df_pop.merge(df_doc, on=["year", "prefecture"], how="left")
    df = df.merge(df_fac, on=["year", "prefecture"], how="left")
    df = df.sort_values(["year", "prefecture"]).reset_index(drop=True)

    # 3. 出力
    out_path = os.path.join(OUT_DIR, "prefecture_covariates.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n=== 出力: {out_path} ===")
    print(f"  行数: {len(df)}")
    print(f"  年範囲: {df['year'].min()} - {df['year'].max()}")
    print(f"  都道府県数: {df['prefecture'].nunique()}")
    print(f"  列: {list(df.columns)}")
    print(f"\n  2023年 全国合計:")
    d23 = df[df["year"] == 2023]
    print(f"    人口: {d23['population_total'].sum():,}")
    print(f"    65歳以上: {d23['population_65plus'].sum():,}")
    print(f"    眼科医師: {d23['ophthalmologists'].sum():,}")
    print(f"    眼科施設: {d23['facilities'].sum():,}")


if __name__ == "__main__":
    main()
