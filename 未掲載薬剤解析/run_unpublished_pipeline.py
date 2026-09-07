# -*- coding: utf-8 -*-
"""未掲載薬剤（上位N位足切り）解析パイプライン 一括実行

data/ が無い環境では環境変数でデータルートを指定する:
    NDB_DATA_ROOT=/path/to/.../data python 未掲載薬剤解析/run_unpublished_pipeline.py

s01 はネットワーク取得を伴う。manifest.json があればキャッシュを使う（--refresh で再取得）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import s01_fetch_yakka_lists
import s02_build_roster
import s03_ndb_published
import s04_coverage
import s05_ge_share_bounds
import s06_unlisted_allergy
import s07_build_corrected_inventory

if __name__ == "__main__":
    refresh = "--refresh" in sys.argv
    print("### s01: 薬価基準収載品目リストの取得 ###")
    s01_fetch_yakka_lists.fetch(refresh=refresh)
    print("\n### s02: 名簿パネル構築 ###")
    s02_build_roster.build()
    print("\n### s03: NDB掲載品目パネル ###")
    s03_ndb_published.build()
    print("\n### s04: 突合・カバレッジ・識別区間 ###")
    s04_coverage.run()
    print("\n### s05: GEシェアの識別区間 ###")
    s05_ge_share_bounds.run()
    print("\n### s06: 抗アレルギー点眼薬の未掲載品目リスト ###")
    s06_unlisted_allergy.run()
    print("\n### s07: インベントリ差し替え版(v2) ###")
    s07_build_corrected_inventory.run()
