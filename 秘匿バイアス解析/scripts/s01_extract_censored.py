# -*- coding: utf-8 -*-
"""
s01: 秘匿フラグ付きデータ抽出
既存 src/preprocess.py のローダーを zero補完 / five補完 の2回呼び出し、
値が異なるセルを「秘匿セル」として特定する（zero/fiveは決定的で行順序も同一）。
K281（既存解析で除外）も含めて全コードを保持する。
"""
import os
import sys
import glob
import re
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.preprocess import load_mapping_config, load_ndb_year  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "processed")


def extract():
    raw_dir = os.path.join(ROOT, "data", "raw")
    config = load_mapping_config(os.path.join(ROOT, "configs", "ndb_mapping.json"))

    files = glob.glob(os.path.join(raw_dir, "ndb_shujutsu_*.*")) + \
        glob.glob(os.path.join(raw_dir, "ndb_shochi_*.*"))

    frames = []
    for f in sorted(files):
        m = re.search(r"ndb_(?:shujutsu|shochi)_(\d{4})\.(?:xlsx|xls)", os.path.basename(f))
        if not m:
            continue
        year = int(m.group(1))
        df_zero = load_ndb_year(year, f, config, "zero")
        df_five = load_ndb_year(year, f, config, "five")
        if df_zero.empty:
            continue
        assert len(df_zero) == len(df_five), f"row mismatch in {f}"
        assert (df_zero["prefecture"].values == df_five["prefecture"].values).all()
        df = df_zero.copy()
        df["is_censored"] = (df_zero["count"].values != df_five["count"].values)
        # 秘匿セルの count は未知（区間[1,9]）なので NaN にする
        df.loc[df["is_censored"], "count"] = pd.NA
        frames.append(df)
        print(f"  {os.path.basename(f)}: {len(df)} rows, censored {df['is_censored'].sum()}")

    out = pd.concat(frames, ignore_index=True)
    out["prefecture"] = out["prefecture"].str.strip()
    # 同一 year×code×prefecture に複数行がある場合、行順はシート順（外来→入院）を
    # 反映するため、出現順を層 stratum として記録する（0=外来, 1=入院 が典型）
    out["stratum"] = out.groupby(["year", "code", "prefecture"]).cumcount()
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "cells_with_censoring_flag.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"saved: {path} ({len(out)} rows, censored {out['is_censored'].sum()})")
    return out


if __name__ == "__main__":
    extract()
