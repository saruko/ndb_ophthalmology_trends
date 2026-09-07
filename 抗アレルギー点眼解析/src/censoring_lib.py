# -*- coding: utf-8 -*-
"""秘匿レポート生成の共通ロジック（都道府県軸・年齢性別軸で共用）。

両軸は「総計列から Σ開示セル を引いて欠落量を求める」という算出方法と、
秘匿パターンの4分類（秘匿なし／部分秘匿／ブロック秘匿／総計秘匿）が同一である。
違うのは「対象セルの総数」だけ（都道府県軸は常に47、年齢性別軸は年度により
38または42）。この違いを AxisSpec に閉じ込め、レポート本文の生成ロジックは
共通化する。
"""
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src"))

from drug_master import DRUG_NAME_JA, DRUG_ORDER, GE_FIRST_LISTING  # noqa: E402
from ndb_reader import CENSOR_THRESHOLD, SHEET_ORDER  # noqa: E402

SHEET_KEY = {s: i for i, s in enumerate(SHEET_ORDER)}


class AxisSpec:
    """軸ごとの列名・表示ラベルをまとめたもの。"""

    def __init__(self, key, csv_name, n_censored_col, n_total_col_or_const,
                censored_list_col, entity_label, entity_label_full,
                phrase_all_disclosed, block_condition_text):
        self.key = key
        self.csv_name = csv_name
        self.n_censored_col = n_censored_col
        self.n_total_col_or_const = n_total_col_or_const  # 列名(str) or 定数(int)
        self.censored_list_col = censored_list_col
        self.entity_label = entity_label            # 「都道府県」/「セル」
        self.entity_label_full = entity_label_full   # 「47都道府県」/「年齢×性別42セル」
        self.phrase_all_disclosed = phrase_all_disclosed
        self.block_condition_text = block_condition_text

    def n_total(self, row_or_df):
        if isinstance(self.n_total_col_or_const, int):
            return self.n_total_col_or_const
        return row_or_df[self.n_total_col_or_const]


PREF_AXIS = AxisSpec(
    key="pref", csv_name="product_level_censoring.csv",
    n_censored_col="n_pref_censored", n_total_col_or_const=47,
    censored_list_col="censored_prefs",
    entity_label="都道府県", entity_label_full="47都道府県",
    phrase_all_disclosed="全47都道府県 開示（秘匿なし）",
    block_condition_text="総計は公表されているのに47都道府県すべてが「-」")

AGESEX_AXIS = AxisSpec(
    key="agesex", csv_name="product_agesex_censoring.csv",
    n_censored_col="n_cells_censored", n_total_col_or_const="n_cells_total",
    censored_list_col="censored_cells",
    entity_label="年齢×性別セル", entity_label_full="年齢×性別セル（2014〜2015年度は38、2016年度以降は42）",
    phrase_all_disclosed="全セル 開示（秘匿なし）",
    block_condition_text="総計は公表されているのに全セルが「-」")


def load(axis: AxisSpec, input_dir: str) -> pd.DataFrame:
    p = os.path.join(input_dir, axis.csv_name)
    d = pd.read_csv(p)
    d[axis.censored_list_col] = d[axis.censored_list_col].fillna("")
    d["sheet_ord"] = d["sheet"].map(SHEET_KEY).fillna(99)
    return d


def fmt(v, dec=0):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{dec}f}"


def agg_group(g: pd.DataFrame, axis: AxisSpec) -> dict:
    """成分×年度×シートの集計。総計秘匿の品目は総量に算入せず別に数える。"""
    known = g[~g.total_censored]
    n_tc = int(g.total_censored.sum())
    total = known["total"].sum()
    missing = known["missing"].sum()
    cens_cells = int(g[axis.n_censored_col].sum())
    if isinstance(axis.n_total_col_or_const, int):
        all_cells = len(g) * axis.n_total_col_or_const
    else:
        all_cells = int(g[axis.n_total_col_or_const].sum())
    classes = g["censor_class"].value_counts().to_dict()
    return {
        "n_products": len(g),
        "n_total_censored": n_tc,
        "total": total,
        "missing": missing,
        "missing_pct": (missing / total * 100) if total else None,
        "cens_cells": cens_cells,
        "all_cells": all_cells,
        "cell_pct": cens_cells / all_cells * 100 if all_cells else None,
        "n_block": classes.get("ブロック秘匿", 0),
        "max_missing_bound": cens_cells * (CENSOR_THRESHOLD - 1),
    }


def rate_matrix_lines(d: pd.DataFrame, axis: AxisSpec) -> list:
    """成分×年度の欠落率マトリクス（Markdownの行リスト）。"""
    L = []
    years = sorted(d.year.unique())
    L.append("| 成分 | " + " | ".join(str(y) for y in years) + " |")
    L.append("|---" * (len(years) + 1) + "|")
    for code in DRUG_ORDER:
        cells = []
        for y in years:
            g = d[(d.code == code) & (d.year == y)]
            if g.empty:
                cells.append("—")
                continue
            a = agg_group(g, axis)
            cells.append("—" if a["missing_pct"] is None
                         else f"{a['missing_pct']:.2f}%")
        L.append(f"| {DRUG_NAME_JA[code]} | " + " | ".join(cells) + " |")
    return L


def block_table_lines(d: pd.DataFrame, axis: AxisSpec) -> list:
    """ブロック秘匿の全件一覧（Markdown行リスト）。年度→処方区分→成分→品目名→総計→欠落量。"""
    blk = d[d.censor_class == "ブロック秘匿"].sort_values(["year", "sheet_ord"])
    L = []
    if blk.empty:
        L.append("該当なし。")
        return L
    L.append("| 年度 | 処方区分 | 成分 | 品目名 | 公表総計 | 欠落量 |")
    L.append("|---|---|---|---|--:|--:|")
    for _, r in blk.iterrows():
        L.append(f"| {r.year} | {r.sheet} | {DRUG_NAME_JA[r.code]} | {r.product_name} "
                 f"| {fmt(r.total)} | {fmt(r.missing)} |")
    return L


def total_censored_table_lines(d: pd.DataFrame) -> list:
    """総計秘匿の年度×処方区分別 集計（Markdown行リスト）。都道府県軸・年齢性別軸で完全共通。"""
    tc = d[d.total_censored]
    L = []
    if tc.empty:
        L.append("該当なし。")
        return L
    L.append("| 年度 | 処方区分 | 該当行数 | 数量の上限（行数×999） |")
    L.append("|---|---|--:|--:|")
    for (y, s), g in tc.groupby(["year", "sheet"], sort=False):
        L.append(f"| {y} | {s} | {len(g)} | {fmt(len(g) * (CENSOR_THRESHOLD - 1))} |")
    L.append("")
    L.append(f"合計 {len(tc)} 行（全 {len(d)} 行中 {len(tc) / len(d) * 100:.1f}%）。")
    return L


def drug_detail_lines(d: pd.DataFrame, axis: AxisSpec) -> list:
    """成分別・年度別・処方区分別の詳細テーブル（Markdown行リスト、9成分ぶん連結）。"""
    L = []
    for code in DRUG_ORDER:
        sub = d[d.code == code]
        L.append(f"### {DRUG_NAME_JA[code]}")
        L.append("")
        first, note = GE_FIRST_LISTING[code]
        L.append(f"後発品の初収載: {note}")
        L.append("")
        if sub.empty:
            L.append("全年度でNDB非掲載（NR）。")
            L.append("")
            continue
        L.append(f"| 年度 | 処方区分 | 掲載品目数 | 公表総量 | 欠落量 | 欠落率 | "
                 f"秘匿{axis.entity_label}数 | 総計秘匿の品目数 | 備考 |")
        L.append("|---|---|--:|--:|--:|--:|--:|--:|---|")
        for (y, s), g in sub.sort_values(["year", "sheet_ord"]).groupby(
                ["year", "sheet"], sort=False):
            a = agg_group(g, axis)
            notes = []
            if a["n_block"]:
                notes.append(f"ブロック秘匿{a['n_block']}品目")
            if a["missing_pct"] is not None and a["missing_pct"] >= 50:
                notes.append("欠落率50%超")
            mp = "—" if a["missing_pct"] is None else f"{a['missing_pct']:.2f}%"
            cells = f"{a['cens_cells']} / {a['all_cells']} ({a['cell_pct']:.1f}%)"
            L.append(f"| {y} | {s} | {a['n_products']} | {fmt(a['total'])} | {fmt(a['missing'])} "
                     f"| {mp} | {cells} | {a['n_total_censored']} "
                     f"| {'、'.join(notes) or '—'} |")
        L.append("")
    return L
