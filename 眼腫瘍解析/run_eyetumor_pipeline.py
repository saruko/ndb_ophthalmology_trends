"""眼腫瘍手術（16術式）解析パイプライン。

抽出 → rate換算 → Poisson trend test を順に実行する。
出力はすべて processed/ に集約され、organize_outputs.py で 01〜04 のフォルダへ振り分ける。

使い方:
    python 眼腫瘍解析/run_eyetumor_pipeline.py            # 抽出から解析まで一括
    python 眼腫瘍解析/run_eyetumor_pipeline.py --skip-extract  # 抽出済みなら解析のみ
"""

import argparse
import os
import runpy
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE, "src"))
from paths import output_dir  # noqa: E402


def run(script):
    """同フォルダのスクリプトを __main__ として実行する。"""
    print(f"\n--- {script} ---")
    runpy.run_path(os.path.join(BASE, script), run_name="__main__")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-extract", action="store_true",
                    help="生Excelからの抽出を省略し、解析のみ実行する")
    args = ap.parse_args()

    print("=== 眼腫瘍手術 解析パイプライン ===")

    if args.skip_extract:
        print("[1/3, 2/3] 抽出はスキップ")
    else:
        print("[1/3] NDB性年齢別ファイルから年齢階級別件数を抽出")
        run("extract_age_stratified.py")
        print("[2/3] 人口推計から4群別の全国人口を算出")
        run("extract_age_population.py")

    print("[3/3] 人口10万対rate換算とPoisson trend test")
    run("rate_and_trend_analysis.py")

    print(f"\n完了: {output_dir()}")
    print("次に `python 眼腫瘍解析/organize_outputs.py` を実行すると 01〜04 のフォルダへ振り分けられます。")


if __name__ == "__main__":
    main()
