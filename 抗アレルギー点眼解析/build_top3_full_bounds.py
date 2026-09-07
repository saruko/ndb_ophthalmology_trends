# -*- coding: utf-8 -*-
"""主要3成分（エピナスチン・オロパタジン・レボカバスチン）の2014〜2024年度について、
公開データの総量と、NDB未収載（非掲載）品目まで含めた最小・最大処方量を1枚のCSVにまとめる。

入力（いずれも既存パイプラインの生成物。生Excelは読まない）:
  05_論文成果物/公費含めない_new/national_trends_bounds.csv
      count_lower = 公表総量（総計秘匿の品目は0扱い）
      count_upper = 公表総量 + 総計秘匿品目の上限（999×mL換算係数）
  05_論文成果物/公費含めない_new/unlisted_sensitivity.csv
      upper1 = 公表総量 + 未収載品目数×最小公表総計（順位ベース・仮定ゼロ）
      upper2 = 2022年度シェアからの逆推計（要仮定。算出不能年度は空欄）

出力:
  05_論文成果物/公費含めない_new/top3_full_range_2014_2024.csv
      min_total_mL          = 公表総量（秘匿品目・未収載品目をすべて0とみなす下限）
      max_total_mL_rank     = 公表総量 + 総計秘匿の上限加算 + 順位ベースの未収載上限加算
      max_total_mL_backcast = 同上だが未収載上限に逆推計（シナリオ②）を使用（空欄=算出不能）
"""
import os
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "05_論文成果物", "公費含めない_new")

TOP3 = ["EPINASTINE", "OLOPATADINE", "LEVOCASTINE"]

nat = pd.read_csv(os.path.join(OUT_DIR, "national_trends_bounds.csv"))
uns = pd.read_csv(os.path.join(OUT_DIR, "unlisted_sensitivity.csv"), comment="#")

nat = nat[nat.code.isin(TOP3)][["year", "code", "drug", "count_lower", "count_upper"]]
uns = uns[uns.code.isin(TOP3)][["year", "code", "published_total", "n_unlisted_lo",
                                "upper1", "upper2", "upper1_note", "upper2_note"]]

m = nat.merge(uns, on=["year", "code"], how="outer")

# 整合チェック: 公表総量は両ファイルで一致するはず
chk = (m.count_lower - m.published_total).abs()
assert (chk < 1e-6).all(), "national_trends_bounds と unlisted_sensitivity の公表総量が不一致"

tc_add = m.count_upper - m.count_lower          # 総計秘匿品目の上限加算
unl_add1 = m.upper1 - m.published_total          # 未収載の順位ベース上限加算
unl_add2 = m.upper2 - m.published_total          # 未収載の逆推計上限加算（NaNあり）

out = pd.DataFrame({
    "code": m.code,
    "drug": m.drug,
    "year": m.year,
    "published_total_mL": m.published_total,
    "min_total_mL": m.published_total,
    "max_total_mL_rank": m.published_total + tc_add + unl_add1,
    "max_total_mL_backcast": m.published_total + tc_add + unl_add2,
    "n_unlisted_products_lo": m.n_unlisted_lo,
    "censored_total_cap_add_mL": tc_add,
    "unlisted_cap_add_rank_mL": unl_add1,
    "note_rank": m.upper1_note,
    "note_backcast": m.upper2_note,
})
out = out.sort_values(["code", "year"], key=lambda s: s.map(
    {c: i for i, c in enumerate(TOP3)}) if s.name == "code" else s)

path = os.path.join(OUT_DIR, "top3_full_range_2014_2024.csv")
_readme = [
    "# ============ README（この行はデータではない。読込時は comment='#' を指定） ============",
    '# 主要3成分（エピナスチン・オロパタジン・レボカバスチン）の公表総量と、',
    '# NDB未収載（非掲載）品目まで含めた最小・最大処方量（2014〜2024年度）。',
    '# code / drug              : 成分コード / 成分名',
    '# year                     : 年度',
    '# published_total_mL       : 公表総量（NDB掲載品目の合算。総計秘匿の品目は除く）',
    '# min_total_mL             : 識別区間の下限 = published_total_mL（秘匿・未収載を0とみなす）',
    '# max_total_mL_rank        : 上限①（順位ベース・仮定ゼロ）= 公表総量',
    '#                            + 総計秘匿品目の上限加算 + 未収載品目数×その年度の最小公表総計',
    '#                            未収載品目は必ずランク外なので最小公表総計を超えられない、という論理のみで成立',
    '# max_total_mL_backcast    : 上限②（逆推計・要仮定）= 公表総量 + 総計秘匿品目の上限加算',
    '#                            + 未収載分の逆推計加算。逆推計は「品目の市場シェアは',
    '#                            年度をまたいで安定」という仮定のもと、未収載が解消された',
    '#                            2022年度の実績シェアから当時の未収載分を逆算する（要仮定・参考値）。',
    '#                            算出不能な年度（例: 照合できる品目が無い、2022年度以降で不要）は空欄。',
    '# n_unlisted_products_lo   : 未収載品目数の下限（上市品目数の下限 − NDB掲載数）',
    '# censored_total_cap_add_mL: 総計秘匿品目の上限加算分（mL）',
    '# unlisted_cap_add_rank_mL : 未収載品目の順位ベース上限加算分（mL、上限①に対応）',
    '# note_rank                : 上限①の計算内訳（品目数×1品目あたり上限、mL換算係数）',
    '# note_backcast            : 上限②の算出根拠。「照合N品目、Σシェア=0.xxx」の場合、',
    '#                            その年度に掲載されていた品目のうちN品目が2022年度にも同一品目',
    '#                            として存在し、その品目群が2022年度の同成分全体に占めていた',
    '#                            シェア（未収載なしの完全な実績に対する割合）がΣシェアだった、',
    '#                            という意味。公表総量をこのΣシェアで割り戻して上限②を逆算する',
    '#                            （照合品目数が少ないほど、その年のシェア構成から外れていた場合の',
    '#                            誤差が大きく、推計の信頼性は下がる）。算出できない場合はその理由',
    '#                            （未収載品目なし／収載初年度でシェア不安定／ブロック秘匿で実績不明／',
    '#                            市場構造の断絶／2022年度以降は不要\u3000など）を記載。',
    '# 真値は必ず [min_total_mL, max_total_mL_rank] に含まれ、多くの場合',
    '# [min_total_mL, max_total_mL_backcast] にも含まれると考えられる（本文の識別区間は上限①を採用）。',
    '# ======================================================================================',
]
with open(path, "w", encoding="utf-8-sig", newline="") as f:
    f.write("\n".join(_readme) + "\n")
    out.to_csv(f, index=False)
print(f"wrote {path}  ({len(out)} rows)")
print(out[["code", "year", "published_total_mL", "min_total_mL",
           "max_total_mL_rank"]].to_string(index=False))
