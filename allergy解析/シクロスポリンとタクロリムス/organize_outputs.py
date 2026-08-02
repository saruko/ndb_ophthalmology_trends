"""免疫抑制点眼薬サブ解析のフォルダを整理する。

build_immunosuppressant_analysis.py はフォルダ直下（processed/）へ出力するので、
実行後に本スクリプトで 01〜04 のフォルダへ振り分ける。
何度実行しても同じ結果になる。**ファイルは一切削除しない**（同名衝突時は据え置き）。

    python allergy解析/シクロスポリンとタクロリムス/organize_outputs.py --dry-run
    python allergy解析/シクロスポリンとタクロリムス/organize_outputs.py
"""

import argparse
import filecmp
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))

INPUT_SUBDIR = "01_抽出データ"
RESULT_SUBDIR = "03_解析結果"
FIGURE_SUBDIR = "04_図表"
RESULT = RESULT_SUBDIR

NATIONAL_PREFIXES = ("national_trends", "apc_")
PREFECTURE_PREFIXES = ("prefecture_per_capita", "prefecture_ranking",
                       "geographic_disparity", "covariate_correlation",
                       "panel_regression")
AGESEX_PREFIXES = ("age_distribution", "age_sex_rates", "mf_ratio_by_age",
                   "weighted_mean_age")
QC_PREFIXES = ("censoring_sensitivity",)

EXCLUDE_DIRS = {"__pycache__", ".git", INPUT_SUBDIR, RESULT_SUBDIR, FIGURE_SUBDIR}


def classify(name):
    """ファイル名から配置先の相対フォルダを返す。None は移動しない。"""
    low = name.lower()
    if name.startswith("~$") or name.startswith("."):
        return None
    if low.endswith((".md", ".py")):
        return ""
    if low.endswith((".xlsx", ".docx", ".pptx", ".png")):
        return FIGURE_SUBDIR
    if name == "prefecture_immuno.csv":
        return INPUT_SUBDIR
    if name.startswith(QC_PREFIXES):
        return os.path.join(RESULT, "品質管理_感度分析")
    if name.startswith(AGESEX_PREFIXES):
        return os.path.join(RESULT, "年齢性別")
    if name.startswith(PREFECTURE_PREFIXES):
        return os.path.join(RESULT, "都道府県_地域格差")
    if name.startswith(NATIONAL_PREFIXES):
        return os.path.join(RESULT, "全国トレンド")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="移動せず一覧のみ表示")
    args = ap.parse_args()
    print(f"整理対象: {BASE}")

    moved, skipped, conflicts = 0, 0, []
    for dirpath, dirnames, filenames in os.walk(BASE):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            src = os.path.join(dirpath, name)
            dest_rel = classify(name)
            if dest_rel is None:
                skipped += 1
                continue
            dest_dir = os.path.join(BASE, dest_rel) if dest_rel else BASE
            dest = os.path.join(dest_dir, name)
            if os.path.abspath(src) == os.path.abspath(dest):
                continue
            # フォルダ直下は build_immunosuppressant_analysis.py の最新出力なので
            # 整理先の古い同名ファイルを置き換える。それ以外は据え置く。
            if os.path.exists(dest) and os.path.abspath(dirpath) != os.path.abspath(BASE):
                conflicts.append((os.path.relpath(src, BASE),
                                  filecmp.cmp(src, dest, shallow=False)))
                continue
            if args.dry_run:
                print(f"  {os.path.relpath(src, BASE)} -> {os.path.relpath(dest, BASE)}")
                moved += 1
                continue
            os.makedirs(dest_dir, exist_ok=True)
            if os.path.exists(dest):
                os.replace(src, dest)
            else:
                shutil.move(src, dest)
            moved += 1

    print(f"移動 {moved} 件 / 対象外 {skipped} 件 / 衝突 {len(conflicts)} 件")
    for s, same in conflicts:
        print(f"  [据置] {s} （移動先に既存: {'内容同一' if same else '★内容が異なる'}）")


if __name__ == "__main__":
    main()
