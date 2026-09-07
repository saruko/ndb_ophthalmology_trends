# -*- coding: utf-8 -*-
"""処方数量の単位をmLに正規化する。

## なぜ必要か

NDBオープンデータの処方数量は品目ごとに単位が異なる。薬効分類131の点眼薬でも
9成分の間で3種類が混在している。

  ｍＬ … エピナスチン・オロパタジン・レボカバスチン（容量そのもの）
  瓶   … ケトチフェン・クロモグリク酸Na・トラニラスト・ペミロラスト・
          イブジラスト・アシタザノラスト（全て5mL入り）
  個   … インタール点眼液UD（0.35mL入りの1回使い切り）

単位を無視して足し合わせると「100mL + 50瓶」のような無意味な量になる。
本解析の集計カテゴリ（ALLERGY_EYE_TOTAL / ANTI_HIST / MED_RELEASE）は
成分をまたいで合算するため、正規化なしでは値が成立しない。

実際、正規化しないと ALLERGY_EYE_TOTAL は 2022〜2024年度で 11〜13%、
2016〜2018年度で 2.6〜6.1% 過小評価される。さらに2021→2022年度の
「急増」の一部は、瓶単位の6成分が2022年度に一斉収載されたことによる
見かけ上の変化（単位の混入）であり、実態ではない。

## 換算方法

「瓶」「個」の品目は、品目名の末尾に必ず1容器あたりの容量が入っている
（例:「ザジテン点眼液０．０５％　３．４５ｍｇ５ｍＬ」→ 5mL/瓶）。
本モジュールはこれを全角数字を含めて解析し、mL換算係数を返す。
対象9成分の全品目（瓶44品目・個1品目）で容量の取得に成功することを
検証済み（監査スクリプト参照）。

## 2014〜2015年度の扱い

第1回・第2回（2014〜2015年度）のExcelには「単位」列そのものが存在しない。
ただし当該年度に登場する8品目はすべて2016年度以降にも同一の品目名で
登場するため、後年度の単位を品目名で引き当てて補完する
（`backfill_units()`）。同一品目の総計が年度間で連続していることから、
2014〜2015年度も同じ単位で集計されていると判断できる。
"""
import re

# 全角数字・記号を半角へ
_ZEN = str.maketrans("０１２３４５６７８９．", "0123456789.")

# 単位そのものが容量（mL）である表記
ML_UNITS = {"ｍＬ", "mL", "ml", "ＭＬ"}

# 容器単位（1容器あたりの容量を品目名から取る必要がある）
CONTAINER_UNITS = {"瓶", "個", "本", "管", "筒"}


def parse_container_ml(product_name: str):
    """品目名から1容器あたりのmL数を取り出す。

    「ザジテン点眼液０．０５％　３．４５ｍｇ５ｍＬ」→ 5.0
    「インタール点眼液ＵＤ２％　７ｍｇ０．３５ｍＬ」→ 0.35

    品目名には「有効成分量ｍｇ + 容量ｍＬ」の順で入るため、最後に現れる
    mL表記を採る。見つからなければ None。
    """
    s = str(product_name).translate(_ZEN)
    hits = re.findall(r"([0-9]*\.?[0-9]+)\s*[mｍ][lLｌＬ]", s)
    return float(hits[-1]) if hits else None


def ml_factor(unit, product_name: str):
    """処方数量をmLに換算する係数を返す。換算不能なら None。

    unit が None（2014〜2015年度は単位列が無い）の場合も None を返すので、
    呼び出し側で backfill_units() を使って単位を埋めてから使うこと。
    """
    if unit is None:
        return None
    u = str(unit).strip()
    if u in ML_UNITS:
        return 1.0
    if u in CONTAINER_UNITS:
        return parse_container_ml(product_name)
    return None


def backfill_units(records):
    """単位列が無い年度（2014〜2015）のレコードに、他年度の単位を補完する。

    品目名をキーに、単位が判明している年度の値を引き当てる。同一品目名に
    複数の単位が観測された場合は補完しない（曖昧なため）。

    records は 'product_name' と 'unit' を持つ dict のリスト。破壊的に更新する。
    戻り値は (補完した件数, 補完できなかった品目名の集合)。
    """
    known = {}
    for r in records:
        u = r.get("unit")
        if u is None:
            continue
        known.setdefault(r["product_name"], set()).add(str(u).strip())

    filled, unresolved = 0, set()
    for r in records:
        if r.get("unit") is not None:
            continue
        cand = known.get(r["product_name"])
        if cand and len(cand) == 1:
            r["unit"] = next(iter(cand))
            r["unit_source"] = "backfilled"
            filled += 1
        else:
            unresolved.add(r["product_name"])
    return filled, unresolved


def annotate(records):
    """records に unit / ml_factor / total_ml を付与する（backfill 済み前提）。

    ml_factor が取れない品目は total_ml を None にし、集計から除外できるようにする。
    """
    unconvertible = set()
    for r in records:
        f = ml_factor(r.get("unit"), r["product_name"])
        r["ml_factor"] = f
        if f is None:
            unconvertible.add(r["product_name"])
        t = r.get("total")
        r["total_ml"] = None if (f is None or t is None) else t * f
    return unconvertible
