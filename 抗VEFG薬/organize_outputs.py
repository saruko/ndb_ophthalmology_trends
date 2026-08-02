"""抗VEGF薬解析のフォルダを整理する。

フォルダ直下と processed/ に散在するファイルを、src/paths.py の構成へ振り分ける。
何度実行しても同じ結果になる（既に正しい場所にあるファイルは動かさない）。
解析パイプラインを実行したあとに本スクリプトを実行する運用を想定している。

    python 抗VEFG薬/organize_outputs.py --dry-run
    python 抗VEFG薬/organize_outputs.py
    python 抗VEFG薬/organize_outputs.py --nokouhi

**ファイルは削除しない。** 移動先に同名ファイルがある場合も上書きせず据え置く。
"""

import argparse
import filecmp
import os
import shutil
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import (ANTIVEGF_DIR, INPUT_SUBDIR, INTERIM_SUBDIR,  # noqa: E402
                   RESULT_SUBDIR, FIGURE_SUBDIR, KABATA_SUBDIR)

RESULT = RESULT_SUBDIR


def classify(name):
    """ファイル名から配置先の相対フォルダを返す。None は移動しない。"""
    low = name.lower()

    # Excelの一時ロックファイル等は触らない
    if name.startswith("~$") or name.startswith("."):
        return None
    if low.endswith((".md", ".py")):
        return KABATA_SUBDIR if low.startswith("kabata") and low.endswith(".md") else ""

    # 先行研究再現
    if low.startswith("kabata"):
        return KABATA_SUBDIR

    # 図表
    if low.endswith((".png", ".xlsx", ".docx", ".pptx", ".pdf")):
        return FIGURE_SUBDIR

    # 抽出データ（解析の入力）
    if name in ("ophthalmic_injection_prefecture.csv",
                "ophthalmic_injection_agesex.csv",
                "g016_prefecture.csv", "g016_agesex.csv",
                "g016_data_availability.csv"):
        return INPUT_SUBDIR

    # 中間データ
    if name.startswith(("processed_", "panel_zero", "panel_five", "panel_random")):
        return INTERIM_SUBDIR

    # 解析結果（テーマ別）
    if name.startswith("cost_"):
        return os.path.join(RESULT, "医療費")
    if name.startswith("g016_"):
        return os.path.join(RESULT, "G016硝子体内注射")
    if name.startswith(("product_", "formulation_", "biosimilar_")):
        return os.path.join(RESULT, "製品_剤形_バイオシミラー")
    if name.startswith("agesex_"):
        return os.path.join(RESULT, "年齢性別")
    if name.startswith(("prefecture_", "geographic_disparity",
                        "covariates_correlation", "panel_regression")):
        return os.path.join(RESULT, "都道府県_地域格差")
    if name.startswith(("masking_qc", "sensitivity_")):
        return os.path.join(RESULT, "品質管理_感度分析")
    if name.startswith("national_"):
        return os.path.join(RESULT, "全国トレンド")
    if name.startswith("antivegf_summary_report"):
        return RESULT
    return None


# 走査から除外するサブフォルダ
# 「公費含まない」は独立したデータセットであり、親フォルダの整理対象に含めない
# （含めると 公費含まない/01_抽出データ/ の中身が親へ吸い上げられてしまう）
EXCLUDE_DIRS = {"plots", "公費含まない", "src", "__pycache__", ".git"}


def iter_files(root):
    """整理対象のファイルを列挙する（直下・processed/・既存サブフォルダ）。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            yield os.path.join(dirpath, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nokouhi", action="store_true",
                    help="公費レセプトを含まないデータのフォルダを整理する")
    ap.add_argument("--dry-run", action="store_true", help="移動せず一覧のみ表示")
    args = ap.parse_args()
    root = os.path.join(ANTIVEGF_DIR, "公費含まない") if args.nokouhi else ANTIVEGF_DIR
    print(f"整理対象: {root}")

    processed = os.path.join(root, "processed")
    moved, replaced, skipped, conflicts, failed = 0, 0, 0, [], []
    for src in list(iter_files(root)):
        name = os.path.basename(src)
        dest_rel = classify(name)
        if dest_rel is None:
            skipped += 1
            continue
        dest_dir = os.path.join(root, dest_rel) if dest_rel else root
        dest = os.path.join(dest_dir, name)
        if os.path.abspath(src) == os.path.abspath(dest):
            continue
        if os.path.exists(dest):
            # processed/ 配下（plots/ 等のサブフォルダを含む）は今回のパイプライン実行が
            # 生成した最新の出力なので、整理先の古い同名ファイルを置き換える。
            # それ以外（既に整理済みの場所や手作業で置いたファイル）は据え置く。
            if not os.path.abspath(src).startswith(os.path.abspath(processed) + os.sep):
                conflicts.append((os.path.relpath(src, root),
                                  filecmp.cmp(src, dest, shallow=False)))
                continue
            replaced += 1
        if args.dry_run:
            print(f"  {os.path.relpath(src, root)} -> {os.path.relpath(dest, root)}")
            moved += 1
            continue
        os.makedirs(dest_dir, exist_ok=True)
        try:
            if os.path.exists(dest):
                os.replace(src, dest)  # 最新の出力で置き換える
            else:
                shutil.move(src, dest)
            moved += 1
        except Exception as e:  # Excelで開いている等
            failed.append((os.path.relpath(src, root), str(e)))

    # 図（png）は plots/ ごと 04_図表 の下へ
    old_plots = os.path.join(root, "processed", "plots")
    new_plots = os.path.join(root, FIGURE_SUBDIR, "plots")
    if os.path.isdir(old_plots) and not args.dry_run:
        os.makedirs(os.path.dirname(new_plots), exist_ok=True)
        if os.path.isdir(new_plots):
            for f in os.listdir(old_plots):
                dst = os.path.join(new_plots, f)
                if not os.path.exists(dst):
                    shutil.move(os.path.join(old_plots, f), dst)
            if not os.listdir(old_plots):
                os.rmdir(old_plots)
        else:
            shutil.move(old_plots, new_plots)
        print("  plots/ を 04_図表/plots へ移動")

    print(f"移動 {moved} 件（うち更新 {replaced} 件） / 対象外 {skipped} 件 "
          f"/ 据置 {len(conflicts)} 件")
    for f, same in conflicts:
        print(f"  [据置] {f} （移動先に既存: {'内容同一' if same else '★内容が異なる'}）")
    for f, e in failed:
        print(f"  [失敗] {f}: {e}")


if __name__ == "__main__":
    main()
