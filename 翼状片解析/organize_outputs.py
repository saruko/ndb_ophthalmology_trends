"""翼状片解析のフォルダを整理する。

フォルダ直下と processed/ に散在するファイルを、src/paths.py の構成へ振り分ける。
何度実行しても同じ結果になる（既に正しい場所にあるファイルは動かさない）。
解析パイプラインを実行したあとに本スクリプトを実行する運用を想定している。

    python 翼状片解析/organize_outputs.py --dry-run
    python 翼状片解析/organize_outputs.py
"""

import argparse
import os
import shutil
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import (BASE_DIR, INPUT_SUBDIR, INTERIM_SUBDIR,  # noqa: E402
                   RESULT_SUBDIR, FIGURE_SUBDIR, UV_SUBDIR)

RESULT = RESULT_SUBDIR
PLOTS = os.path.join(FIGURE_SUBDIR, "plots")

# 紫外線・日射量の収集データ（ファイル名の接頭辞で判定）
UV_PREFIXES = ("jma_uv", "openmeteo_")


def classify(name):
    """ファイル名から配置先の相対フォルダを返す。None は移動しない。"""
    low = name.lower()

    # Excelの一時ロックファイル等は触らない
    if name.startswith("~$") or name.startswith("."):
        return None
    # ドキュメントはフォルダ直下に置く
    if low.endswith(".md"):
        return ""

    # 紫外線・日射量の収集データ（csv/xlsx とも）
    if low.startswith(UV_PREFIXES):
        return UV_SUBDIR

    # 図
    if low.endswith(".png"):
        return PLOTS
    # Excel・Word（紫外線データは上で分岐済み）
    if low.endswith((".xlsx", ".docx")):
        return FIGURE_SUBDIR

    # 抽出データ（解析の入力）
    if name == "pterygium_long.csv":
        return INPUT_SUBDIR

    # 中間データ（人口10万対換算済み）
    if name == "pterygium_rate_per100k.csv":
        return INTERIM_SUBDIR

    # 解析結果（テーマ別）
    if name.startswith("uv_correlation"):
        return os.path.join(RESULT, "紫外線相関")
    if name.startswith("pterygium_apc"):
        return os.path.join(RESULT, "全国トレンド")
    if name.startswith("prefecture_") or name.startswith("pterygium_gini"):
        return os.path.join(RESULT, "都道府県_地域格差")
    if name.startswith("pterygium_summary_report"):
        return RESULT
    return None


# 走査から除外するサブフォルダ
EXCLUDE_DIRS = {"src", "__pycache__", ".git", "jma_images"}


def iter_files(root):
    """整理対象のファイルを列挙する（直下・processed/・既存サブフォルダ）。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            yield os.path.join(dirpath, f)


def move_dir(src, dest, dry_run):
    """ディレクトリを dest へ移動する（dest が既にあれば中身をマージ）。"""
    if not os.path.isdir(src) or os.path.abspath(src) == os.path.abspath(dest):
        return False
    if dry_run:
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isdir(dest):
        for f in os.listdir(src):
            shutil.move(os.path.join(src, f), os.path.join(dest, f))
        os.rmdir(src)
    else:
        shutil.move(src, dest)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="移動せず一覧のみ表示")
    args = ap.parse_args()
    root = BASE_DIR
    print(f"整理対象: {root}")

    # 気象庁の元画像は枚数が多いのでフォルダごと移動する
    for parent in ("紫外線", ""):
        old = os.path.join(root, parent, "jma_images") if parent else os.path.join(root, "jma_images")
        if move_dir(old, os.path.join(root, UV_SUBDIR, "jma_images"), args.dry_run):
            print("  jma_images/ を 05_紫外線データ/jma_images へ移動")

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
        except Exception as e:  # Excelで開いている等
            failed.append((os.path.relpath(src, root), str(e)))

    # 空になったフォルダを削除
    if not args.dry_run:
        for d in [os.path.join(root, "processed", "plots"),
                  os.path.join(root, "processed"),
                  os.path.join(root, "紫外線")]:
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)
                print(f"  空フォルダを削除: {os.path.relpath(d, root)}")

    print(f"移動 {moved} 件 / 対象外 {skipped} 件")
    for f, e in failed:
        print(f"  [失敗] {f}: {e}")


if __name__ == "__main__":
    main()
