"""本体解析の出力フォルダ（data/processed/）を整理する。

直下に平積みになった解析結果を、src/paths.py の構成へテーマ別に振り分ける。
何度実行しても同じ結果になる（既に正しい場所にあるファイルは動かさない）。
パイプラインを実行したあとに本スクリプトを実行する運用を想定している。

    python organize_outputs.py --dry-run
    python organize_outputs.py

**ファイルは削除しない。** data/processed/ 直下（＝今回の実行が生成した最新の出力）は
整理先の古い同名ファイルを置き換えるが、それ以外は上書きせず据え置く。
sub_analysis/ は親と同名で内容の違うCSVを持つため、ばらさずフォルダごと維持する。
"""

import argparse
import filecmp
import os
import shutil
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import (PROCESSED_DIR, INTERIM_SUBDIR, RESULT_SUBDIR,  # noqa: E402
                   FIGURE_SUBDIR, SUB_ANALYSIS_SUBDIR)

RESULT = RESULT_SUBDIR
PLOTS = os.path.join(FIGURE_SUBDIR, "plots")

# 01_中間データ（前処理済みの統合データ）
INTERIM_PREFIXES = ("ndb_processed_", "ndb_age_sex_")
# 02_解析結果/全国トレンド
NATIONAL_PREFIXES = ("national_",)
# 02_解析結果/都道府県_地域格差
PREFECTURE_PREFIXES = ("geographic_disparity", "covariates_correlation",
                       "panel_regression")
# 02_解析結果/論文図表データ（export_excel_figures.py が出すFig用CSV）
FIGDATA_PREFIXES = ("fig1_", "fig2_", "fig3_", "fig4_", "fig5_", "fig6_")


def classify(name):
    """ファイル名から配置先の相対フォルダを返す。None は移動しない。"""
    low = name.lower()

    # Excelの一時ロックファイル等は触らない
    if name.startswith("~$") or name.startswith("."):
        return None

    if low.endswith(".png"):
        return PLOTS
    if low.endswith((".xlsx", ".docx", ".pptx")):
        return FIGURE_SUBDIR

    if name.startswith(INTERIM_PREFIXES):
        return INTERIM_SUBDIR
    if name.startswith(FIGDATA_PREFIXES):
        return os.path.join(RESULT, "論文図表データ")
    if name.startswith(PREFECTURE_PREFIXES):
        return os.path.join(RESULT, "都道府県_地域格差")
    if name.startswith(NATIONAL_PREFIXES):
        return os.path.join(RESULT, "全国トレンド")
    if name.startswith("analysis_summary_report"):
        return RESULT
    return None


# 走査から除外するサブフォルダ
# sub_analysis は親と同名で内容の違うCSVを持つため、フォルダごと維持する
EXCLUDE_DIRS = {"__pycache__", ".git", SUB_ANALYSIS_SUBDIR}


def iter_files(root):
    """整理対象のファイルを列挙する。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            yield os.path.join(dirpath, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="移動せず一覧のみ表示")
    args = ap.parse_args()
    root = PROCESSED_DIR
    if not os.path.isdir(root):
        print(f"出力フォルダがありません: {root}")
        return
    print(f"整理対象: {root}")

    # パイプラインが直接書き出す場所（＝今回の実行の最新出力とみなす）
    global FRESH_DIRS
    FRESH_DIRS = {os.path.abspath(root), os.path.abspath(os.path.join(root, "plots"))}

    moved, replaced, skipped, conflicts, failed = 0, 0, 0, [], []
    for src in list(iter_files(root)):
        name = os.path.basename(src)
        dest_rel = classify(name)
        if dest_rel is None:
            skipped += 1
            continue
        dest = os.path.join(root, dest_rel, name)
        if os.path.abspath(src) == os.path.abspath(dest):
            continue
        if os.path.exists(dest):
            # パイプラインの出力先（data/processed/ 直下と plots/）は今回の実行が生成した
            # 最新の出力なので古い同名ファイルを置き換える。
            # 既に整理済みの場所にあるものは据え置く。
            if os.path.dirname(os.path.abspath(src)) not in FRESH_DIRS:
                conflicts.append((os.path.relpath(src, root),
                                  filecmp.cmp(src, dest, shallow=False)))
                continue
            replaced += 1
        if args.dry_run:
            print(f"  {os.path.relpath(src, root)} -> {os.path.relpath(dest, root)}")
            moved += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            if os.path.exists(dest):
                os.replace(src, dest)
            else:
                shutil.move(src, dest)
            moved += 1
        except Exception as e:  # Excelで開いている等
            failed.append((os.path.relpath(src, root), str(e)))

    # 図（png）は plots/ ごと 03_図表 の下へ
    old_plots = os.path.join(root, "plots")
    new_plots = os.path.join(root, PLOTS)
    if os.path.isdir(old_plots) and not args.dry_run:
        os.makedirs(os.path.dirname(new_plots), exist_ok=True)
        if os.path.isdir(new_plots):
            for f in os.listdir(old_plots):
                dst = os.path.join(new_plots, f)
                if os.path.exists(dst):
                    os.replace(os.path.join(old_plots, f), dst)
                else:
                    shutil.move(os.path.join(old_plots, f), dst)
            if not os.listdir(old_plots):
                os.rmdir(old_plots)
        else:
            shutil.move(old_plots, new_plots)
        print("  plots/ を 03_図表/plots へ移動")

    print(f"移動 {moved} 件（うち更新 {replaced} 件） / 対象外 {skipped} 件 "
          f"/ 据置 {len(conflicts)} 件")
    for f, same in conflicts:
        print(f"  [据置] {f} （移動先に既存: {'内容同一' if same else '★内容が異なる'}）")
    for f, e in failed:
        print(f"  [失敗] {f}: {e}")


if __name__ == "__main__":
    main()
