"""眼腫瘍解析のフォルダを整理する。

フォルダ直下と processed/ に散在するファイルを、src/paths.py の構成へ振り分ける。
何度実行しても同じ結果になる（既に正しい場所にあるファイルは動かさない）。
解析パイプラインを実行したあとに本スクリプトを実行する運用を想定している。

    python 眼腫瘍解析/organize_outputs.py --dry-run
    python 眼腫瘍解析/organize_outputs.py
"""

import argparse
import os
import shutil
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import (BASE_DIR, INPUT_SUBDIR, INTERIM_SUBDIR,  # noqa: E402
                   RESULT_SUBDIR, FIGURE_SUBDIR, ARCHIVE_SUBDIR)


def classify(name):
    """ファイル名から配置先の相対フォルダを返す。None は移動しない。"""
    low = name.lower()

    # Excelの一時ロックファイル等は触らない
    if name.startswith("~$") or name.startswith("."):
        return None

    # 2023年度までで作成した旧版はまとめて退避（原稿mdより先に判定する）
    if "2014_2023" in name:
        return ARCHIVE_SUBDIR

    # ドキュメント（論文ドラフト等）はフォルダ直下に置く
    if low.endswith(".md"):
        return ""

    # 図表
    if low.endswith((".docx", ".png", ".pptx")):
        return FIGURE_SUBDIR

    # 抽出データ（解析の入力）
    if name.startswith(("眼腫瘍手術トレンド_", "眼腫瘍手術_年齢階級別_", "人口_4群層別化_")):
        return INPUT_SUBDIR

    # 中間データ（層別化・整合性チェック）
    if name.startswith(("眼腫瘍手術_4群層別化_", "眼腫瘍手術_年齢別合計_")):
        return INTERIM_SUBDIR

    # 解析結果
    if name.startswith(("rate_per_100k", "poisson_trend_test")):
        return RESULT_SUBDIR
    return None


# 走査から除外するサブフォルダ
# 参考文献・旧版は整理済みの置き場なので触らない
EXCLUDE_DIRS = {"src", "__pycache__", ".git", "参考文献", ARCHIVE_SUBDIR}


def iter_files(root):
    """整理対象のファイルを列挙する（直下・processed/・既存サブフォルダ）。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            yield os.path.join(dirpath, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="移動せず一覧のみ表示")
    args = ap.parse_args()
    root = BASE_DIR
    print(f"整理対象: {root}")

    moved, skipped, failed = 0, 0, []
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
        if args.dry_run:
            print(f"  {os.path.relpath(src, root)} -> {os.path.relpath(dest, root)}")
            moved += 1
            continue
        os.makedirs(dest_dir, exist_ok=True)
        try:
            shutil.move(src, dest)
            moved += 1
        except Exception as e:  # Wordで開いている等
            failed.append((os.path.relpath(src, root), str(e)))

    # 空になったフォルダを削除
    if not args.dry_run:
        d = os.path.join(root, "processed")
        if os.path.isdir(d) and not os.listdir(d):
            os.rmdir(d)
            print(f"  空フォルダを削除: {os.path.relpath(d, root)}")

    print(f"移動 {moved} 件 / 対象外 {skipped} 件")
    for f, e in failed:
        print(f"  [失敗] {f}: {e}")


if __name__ == "__main__":
    main()
