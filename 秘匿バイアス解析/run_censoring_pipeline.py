# -*- coding: utf-8 -*-
"""秘匿バイアス解析パイプライン一括実行"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import s01_extract_censored
import s02_censoring_census
import s03_bounds_analysis
import s04_artificial_censoring
import s05_censored_mle
import s06_experiment_mle
import s07_figures
import s08_sharp_bounds
import s09_bayes_mi

if __name__ == "__main__":
    print("### s01: 秘匿フラグ付き抽出 ###")
    s01_extract_censored.extract()
    print("\n### s02: 秘匿率センサス ###")
    s02_censoring_census.run()
    print("\n### s03: bounds analysis ###")
    s03_bounds_analysis.run()
    print("\n### s04: 人工秘匿実験（単一代入3法） ###")
    s04_artificial_censoring.run()
    print("\n### s05: 区間打ち切りMLE（実データ適用） ###")
    s05_censored_mle.run()
    print("\n### s06: 人工秘匿実験（MLE追加比較） ###")
    s06_experiment_mle.run()
    print("\n### s07: 論文用図表 ###")
    s07_figures.run()
    print("\n### s08: シャープ識別区間 ###")
    s08_sharp_bounds.run()
    print("\n### s09: 多重代入によるGini不確実性伝播 ###")
    s09_bayes_mi.run()
