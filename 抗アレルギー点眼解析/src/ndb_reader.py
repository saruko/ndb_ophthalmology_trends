# -*- coding: utf-8 -*-
"""NDBオープンデータ「処方薬（外用薬）都道府県別」Excelの読み取り。

旧レポート（censoring_detailed_report.md / pref_censoring_readable.md）の数値が
壊れていた原因は、この読み取り層が無かったことにある。具体的には
  - 総計列を固定インデックスで取り、年度による列ずれで薬効分類コード「131」を
    総計として拾っていた
  - 「秘匿セル」を47の都道府県列ではなく、ヘッダの文字列列
    （薬価基準収載医薬品コード・単位）から数えていた
の2点。本モジュールは列を毎シート動的に特定し、都道府県列だけを秘匿判定の
対象とすることでこれを防ぐ。

秘匿の定義（外用薬・処方数量）:
  数量1,000未満のセルは「-」で伏せられる。したがって秘匿セルの真値は区間
  [0, 1000) にある。総計列には秘匿セルの値も含めた真の合計が入るため、
      欠落量 = 総計 − Σ(開示された都道府県セル)
  で秘匿分の総量が復元できる。総計そのものが「-」の行は成分全体が1,000未満で
  あり、欠落量は算出できない（total_censored=True として区別する）。
"""
import os
import re

import pandas as pd

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
    "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]

CENSOR_TOKENS = {"-", "—", "－", "ー", "–", ""}

# 秘匿閾値（外用薬の処方数量）。真値は [0, CENSOR_THRESHOLD) に入る。
CENSOR_THRESHOLD = 1000

SHEET_ORDER = ["外来（院外）", "外来（院内）", "入院"]

# 眼科用剤の薬効分類コード
YAKKO_EYE = "131"


def normalize_sheet(sheet_name: str) -> str | None:
    """'外用薬 外来 (院内)' → '外来（院内）'。外用薬以外のシートは None。"""
    if "外用薬" not in sheet_name:
        return None
    s = sheet_name.replace("外用薬", "").strip()
    s = s.replace("(", "（").replace(")", "）").replace(" ", "").replace("　", "")
    if "院外" in s:
        return "外来（院外）"
    if "院内" in s:
        return "外来（院内）"
    if "入院" in s:
        return "入院"
    return s or None


def is_censored(val) -> bool:
    """セルが秘匿（'-'）か。空欄も秘匿として扱う。"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return True
    return str(val).strip() in CENSOR_TOKENS


def to_number(val):
    """数値セルを float に。秘匿・非数値は None。"""
    if is_censored(val):
        return None
    s = str(val).replace(",", "").replace("　", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _find_total_col(df) -> int | None:
    """総計列のインデックスを探す（年度で位置が動くため動的に）。

    シート先頭の表題セル（例:「診療年月：H28年04月～H29年03月　外用薬 外来（院内）
    （総計）」）にも「総計」が含まれるため、部分一致で拾うと列0＝薬効分類を
    総計と誤認する。旧レポートで総計が「131」になっていたのはこの誤りである。
    ヘッダセルは「総計」単独（2014〜2021年度）または「総計\\n(処方数量)」
    （2022年度以降）なので、改行前の1行目が「総計」に一致する列を採る。
    """
    for r in range(min(6, len(df))):
        for c in range(df.shape[1]):
            head = str(df.iloc[r, c]).strip().split("\n")[0].strip()
            if head == "総計":
                return c
    return None


def _find_unit_col(df) -> int | None:
    """「単位」列のインデックスを探す。

    2014〜2015年度（第1回・第2回）のExcelには単位列そのものが無く None を返す。
    その年度の単位は src/units.py の backfill_units() で品目名から補完する。
    """
    for r in range(min(6, len(df))):
        for c in range(df.shape[1]):
            head = str(df.iloc[r, c]).strip().split("\n")[0].strip()
            if head == "単位":
                return c
    return None


def _find_pref_cols(df, total_col: int) -> dict:
    """総計列の右側から47都道府県の列を特定する。

    ヘッダ行に都道府県名が入っていればそれを使い、無ければ総計列の直後から
    47列を順番に割り当てる（NDBの列順は全年度で固定）。
    """
    for r in range(min(6, len(df))):
        row = [str(df.iloc[r, c]).strip() for c in range(df.shape[1])]
        hit = {c: row[c] for c in range(total_col + 1, df.shape[1])
               if row[c] in PREFECTURES}
        if len(hit) == 47:
            return hit
    return {total_col + 1 + i: p for i, p in enumerate(PREFECTURES)
            if total_col + 1 + i < df.shape[1]}


CENSOR_CLASSES = ["秘匿なし", "部分秘匿", "ブロック秘匿", "総計秘匿"]


def classify_censoring(total, n_censored: int) -> str:
    """行単位の秘匿パターンを分類する。

      秘匿なし     47都道府県すべて開示
      部分秘匿     一部の県が「-」。欠落量 = 総計 − Σ開示 で復元でき、
                   ただしNDBは補完的秘匿を行うため、個々の秘匿セルが
                   1,000未満とは限らない（欠落量の合計だけが確定する）
      ブロック秘匿 総計は公表されているのに47都道府県すべてが「-」。
                   閾値則では説明できず、都道府県内訳が丸ごと失われている
      総計秘匿     総計自体が「-」。品目全体が1,000未満で、欠落量は算出不能
    """
    if total is None:
        return "総計秘匿"
    if n_censored == 0:
        return "秘匿なし"
    if n_censored >= len(PREFECTURES):
        return "ブロック秘匿"
    return "部分秘匿"


def read_sheet(path: str, sheet_name: str, year: int, classify, product_type):
    """1シートから対象品目の行を読み、秘匿情報つきレコードのリストを返す。

        classify(name)          -> 成分コード or None
        product_type(code, name) -> 'brand' / 'generic_maker' / 'generic_unified'
    """
    kind = normalize_sheet(sheet_name)
    if kind is None:
        return []

    df = pd.read_excel(path, sheet_name=sheet_name, header=None)
    total_col = _find_total_col(df)
    if total_col is None:
        return []
    pref_cols = _find_pref_cols(df, total_col)
    unit_col = _find_unit_col(df)

    # 薬効分類コード列は品目ごとに1回しか書かれないため前方補完する。
    df[0] = df[0].ffill()

    records = []
    for r in range(len(df)):
        if str(df.iloc[r, 0]).strip() != YAKKO_EYE:
            continue
        name = str(df.iloc[r, 3]).strip()
        # 眼軟膏・眼耳鼻科用液など点眼以外の剤形は対象外
        if "点眼" not in name:
            continue
        code = classify(name)
        if code is None:
            continue

        total_raw = df.iloc[r, total_col]
        total = to_number(total_raw)

        disclosed, censored_prefs = {}, []
        for c, pref in pref_cols.items():
            v = to_number(df.iloc[r, c])
            if v is None:
                censored_prefs.append(pref)
            else:
                disclosed[pref] = v

        sum_disclosed = sum(disclosed.values())
        # 総計が秘匿の行は欠落量を算出できない（品目全体が1,000未満）。
        missing = None if total is None else round(total - sum_disclosed, 3)
        n_cens = len(censored_prefs)

        records.append({
            "year": year,
            "sheet": kind,
            "code": code,
            "product_name": name,
            "product_type": product_type(code, name),
            # 単位は成分によって ｍＬ／瓶／個 が混在する。集計前に
            # src/units.py で mL に正規化すること（2014〜2015年度は
            # 単位列自体が無いため None になり、後段で補完される）。
            "unit": (str(df.iloc[r, unit_col]).strip()
                     if unit_col is not None else None),
            "total": total,
            "total_censored": total is None,
            "sum_disclosed": sum_disclosed,
            "missing": missing,
            "n_pref_disclosed": len(disclosed),
            "n_pref_censored": n_cens,
            "censor_class": classify_censoring(total, n_cens),
            # 閾値則（各秘匿セル < 1,000）で欠落量を説明できるか。
            # 説明できない行はブロック秘匿など別事由による。
            "exceeds_threshold": (missing is not None
                                  and missing > n_cens * (CENSOR_THRESHOLD - 1) + 1),
            "censored_prefs": censored_prefs,
            "disclosed": disclosed,
        })
    return records


def read_year(path: str, year: int, classify, product_type):
    """1年度分のExcelから外用薬3シートを読む。"""
    xl = pd.ExcelFile(path)
    out = []
    for sheet in xl.sheet_names:
        out += read_sheet(path, sheet, year, classify, product_type)
    return out


SEXES = ["男", "女"]
# 2016年度以降の年齢階級（21区分。90歳以上を90-94/95-99/100+に細分化）。
AGE_GROUPS = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳", "25～29歳", "30～34歳",
    "35～39歳", "40～44歳", "45～49歳", "50～54歳", "55～59歳", "60～64歳", "65～69歳",
    "70～74歳", "75～79歳", "80～84歳", "85～89歳", "90～94歳", "95～99歳", "100歳以上",
]
# 2014〜2015年度の年齢階級（19区分。90歳以上はまとめて1区分）。
AGE_GROUPS_LEGACY = [
    "0～4歳", "5～9歳", "10～14歳", "15～19歳", "20～24歳", "25～29歳", "30～34歳",
    "35～39歳", "40～44歳", "45～49歳", "50～54歳", "55～59歳", "60～64歳", "65～69歳",
    "70～74歳", "75～79歳", "80～84歳", "85～89歳", "90歳以上",
]
N_AGE_SEX_CELLS = len(SEXES) * len(AGE_GROUPS)  # 42（2016年度以降の基準）


def _find_sex_header_cols(df, total_col: int) -> list[int]:
    """総計列の右側で「男」「男性」「女」「女性」ヘッダの列位置を探す。"""
    hits = []
    for r in range(min(6, len(df))):
        for c in range(total_col + 1, df.shape[1]):
            v = str(df.iloc[r, c]).strip()
            if v in ("男", "男性", "女", "女性"):
                hits.append(c)
        if hits:
            return sorted(hits)
    return hits


def _find_agesex_cols(df, total_col: int) -> dict:
    """総計列の右側から「男」ブロック＋「女」ブロックの年齢×性別セルを特定する。

    2014〜2015年度は19年齢階級（90歳以上はまとめて1区分）、2016年度以降は
    21年齢階級（90〜94/95〜99/100歳以上に細分化）で列数が異なる。ブロック幅を
    ヘッダ位置から動的に決め、年齢ラベルは row3 の実値をそのまま使う
    （固定リストの長さを前提にすると2014〜2015年度が読めなくなる）。
    """
    sex_cols = _find_sex_header_cols(df, total_col)
    if len(sex_cols) != 2:
        return {}
    male_start, female_start = sex_cols
    end = df.shape[1]

    cols = {}
    for start, sex, stop in [(male_start, "男", female_start),
                             (female_start, "女", end)]:
        for c in range(start, stop):
            label = str(df.iloc[3, c]).strip()
            if not label or label == "nan":
                continue
            cols[c] = (sex, label)
    return cols


def read_agesex_sheet(path: str, sheet_name: str, year: int, classify, product_type):
    """1シートから対象品目の行を読み、年齢×性別42セルの秘匿情報つきレコードを返す。

    都道府県版 read_sheet() と同じ算出方法（欠落量 = 総計 − Σ開示セル）・
    同じ秘匿4分類（秘匿なし／部分秘匿／ブロック秘匿／総計秘匿）を用いる。
    ブロック秘匿の判定基準は「42セルすべてが-」に変わる。
    """
    kind = normalize_sheet(sheet_name)
    if kind is None:
        return []

    df = pd.read_excel(path, sheet_name=sheet_name, header=None)
    total_col = _find_total_col(df)
    if total_col is None:
        return []
    cell_cols = _find_agesex_cols(df, total_col)
    n_cells_total = len(cell_cols)
    if n_cells_total == 0:
        return []
    unit_col = _find_unit_col(df)

    df[0] = df[0].ffill()

    records = []
    for r in range(len(df)):
        if str(df.iloc[r, 0]).strip() != YAKKO_EYE:
            continue
        name = str(df.iloc[r, 3]).strip()
        if "点眼" not in name:
            continue
        code = classify(name)
        if code is None:
            continue

        total = to_number(df.iloc[r, total_col])

        disclosed, censored_cells = {}, []
        for c, (sex, age) in cell_cols.items():
            v = to_number(df.iloc[r, c])
            key = f"{sex}{age}"
            if v is None:
                censored_cells.append(key)
            else:
                disclosed[key] = v

        sum_disclosed = sum(disclosed.values())
        missing = None if total is None else round(total - sum_disclosed, 3)
        n_cens = len(censored_cells)

        records.append({
            "year": year,
            "sheet": kind,
            "code": code,
            "product_name": name,
            "product_type": product_type(code, name),
            "unit": (str(df.iloc[r, unit_col]).strip()
                     if unit_col is not None else None),
            "total": total,
            "total_censored": total is None,
            "sum_disclosed": sum_disclosed,
            "missing": missing,
            "n_cells_total": n_cells_total,
            "n_cells_disclosed": len(disclosed),
            "n_cells_censored": n_cens,
            "censor_class": classify_agesex_censoring(total, n_cens, n_cells_total),
            "exceeds_threshold": (missing is not None
                                  and missing > n_cens * (CENSOR_THRESHOLD - 1) + 1),
            "censored_cells": censored_cells,
            "disclosed": disclosed,
        })
    return records


def classify_agesex_censoring(total, n_censored: int, n_cells_total: int) -> str:
    """年齢性別ファイルの行単位の秘匿パターン分類。判定基準は都道府県版と同じ4分類。

    ブロック秘匿の閾値は「全セルが-」（2014〜2015年度は38セル、
    2016年度以降は42セルが対象セル総数）。
    """
    if total is None:
        return "総計秘匿"
    if n_censored == 0:
        return "秘匿なし"
    if n_censored >= n_cells_total:
        return "ブロック秘匿"
    return "部分秘匿"


def read_agesex_year(path: str, year: int, classify, product_type):
    """1年度分の年齢性別Excelから外用薬3シートを読む。"""
    xl = pd.ExcelFile(path)
    out = []
    for sheet in xl.sheet_names:
        out += read_agesex_sheet(path, sheet, year, classify, product_type)
    return out


def count_eye_products(path: str) -> dict:
    """薬効分類131（眼科用剤）の公開品目数をシート別に数える（足切り検証用）。

    品目名ベースと薬価基準収載医薬品コードベースの両方を返す。旧版Ⅴ章は
    どちらで数えたかが明記されておらず、値が再現できなかった。

    併せて、シート内で公表されている総計の最小値（min_total）も返す。
    未収載品目は必ずランク外＝最小公表総計を超えないため、未収載品目まで
    拡張した秘匿感度分析（順位ベース上限）の根拠として使う。
    """
    xl = pd.ExcelFile(path)
    by_sheet, names_all, codes_all = {}, set(), set()
    for sheet in xl.sheet_names:
        kind = normalize_sheet(sheet)
        if kind is None:
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        total_col = _find_total_col(df)
        df[0] = df[0].ffill()
        names, codes, totals = set(), set(), []
        for r in range(len(df)):
            if str(df.iloc[r, 0]).strip() != YAKKO_EYE:
                continue
            names.add(str(df.iloc[r, 3]).strip())
            m = re.search(r"\d{9,}", str(df.iloc[r, 2]))
            if m:
                codes.add(m.group(0))
            if total_col is not None:
                v = to_number(df.iloc[r, total_col])
                if v is not None:
                    totals.append(v)
        by_sheet[kind] = {"names": len(names), "codes": len(codes),
                          "min_total": min(totals) if totals else None}
        names_all |= names
        codes_all |= codes
    return {"by_sheet": by_sheet, "unique_names": len(names_all),
            "unique_codes": len(codes_all)}
