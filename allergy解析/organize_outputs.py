"""抗アレルギー点眼薬解析のフォルダを整理する。

一次出力先（processed*/）とフォルダ直下に散在するファイルを、src/paths.py の構成へ
振り分ける。何度実行しても同じ結果になる（既に正しい場所にあるファイルは動かさない）。
解析パイプラインを実行したあとに本スクリプトを実行する運用を想定している。

    python allergy解析/organize_outputs.py --dry-run     # 主解析（公費含まない）
    python allergy解析/organize_outputs.py
    python allergy解析/organize_outputs.py --kouhi       # 公費含む版

**ファイルは一切削除しない。** 移動先に同名ファイルが既にある場合も上書きせず、
元の場所に残したうえで警告する（凍結済みの成果物を壊さないため）。
05_論文成果物/・旧版/・類似研究/・花粉量/・シクロスポリンとタクロリムス/ は対象外。
"""

import argparse
import filecmp
import os
import shutil
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import (BASE_DIR, INPUT_SUBDIR, INTERIM_SUBDIR,  # noqa: E402
                   RESULT_SUBDIR, FIGURE_SUBDIR, PAPER_SUBDIR, KOUHI_SUBDIR,
                   ARCHIVE_SUBDIR, add_nokouhi_arg, data_root, output_dir)

RESULT = RESULT_SUBDIR
PLOTS = os.path.join(FIGURE_SUBDIR, "plots")

# 01_抽出データ（生Excelから抽出した解析の入力）
INPUT_FILES = {
    "ndb_processed_allergy_zero.csv",
    "ndb_processed_injection_allergy_zero.csv",
}
# 02_中間データ
INTERIM_FILES = {
    "ndb_allergy_age_sex_zero.csv",
    "population_age_sex.csv",
}
# 03_解析結果/全国トレンド
NATIONAL_PREFIXES = ("national_", "drug_share_by_year", "market_hhi",
                     "convergence_analysis")
# 03_解析結果/都道府県_地域格差
PREFECTURE_PREFIXES = ("prefecture_", "geographic_disparity", "covariates_correlation",
                       "panel_regression", "theil_index", "specialization_disparity")
# 03_解析結果/年齢性別
AGESEX_PREFIXES = ("age_sex_rates", "mf_ratio_by_age")
# 03_解析結果/後発品_剤形
GENERIC_PREFIXES = ("brand_generic", "ge_", "epinastine_lx")
# 03_解析結果/代替性分析
SUBSTITUTION_PREFIXES = ("substitution_",)
# 03_解析結果/品質管理_感度分析
QC_PREFIXES = ("censoring_sensitivity", "methods_claims_verification")


def classify(name):
    """ファイル名から配置先の相対フォルダを返す。None は移動しない。"""
    low = name.lower()

    # Excelの一時ロックファイル等は触らない
    if name.startswith("~$") or name.startswith("."):
        return None
    # ドキュメント・スクリプトはフォルダ直下に置く
    if low.endswith((".md", ".py")):
        return ""

    # 図
    if low.endswith(".png"):
        return PLOTS
    # Excel・Word・PowerPoint
    if low.endswith((".xlsx", ".docx", ".pptx")):
        return FIGURE_SUBDIR

    if name in INPUT_FILES:
        return INPUT_SUBDIR
    if name in INTERIM_FILES:
        return INTERIM_SUBDIR

    # 解析結果（テーマ別）。接頭辞の判定順は重複しないよう限定的なものから並べる
    if name.startswith(QC_PREFIXES):
        return os.path.join(RESULT, "品質管理_感度分析")
    if name.startswith(SUBSTITUTION_PREFIXES):
        return os.path.join(RESULT, "代替性分析")
    if name.startswith(GENERIC_PREFIXES):
        return os.path.join(RESULT, "後発品_剤形")
    if name.startswith(AGESEX_PREFIXES):
        return os.path.join(RESULT, "年齢性別")
    if name.startswith(PREFECTURE_PREFIXES):
        return os.path.join(RESULT, "都道府県_地域格差")
    if name.startswith(NATIONAL_PREFIXES):
        return os.path.join(RESULT, "全国トレンド")
    if name.startswith("allergy_summary_report"):
        return RESULT
    return None


# 走査から除外するサブフォルダ
# 05_論文成果物 と 旧版 は凍結された別世代の同名ファイルを含むため絶対に触らない
EXCLUDE_DIRS = {
    "src", "__pycache__", ".git", "data",
    PAPER_SUBDIR, ARCHIVE_SUBDIR,
    "類似研究", "花粉量", "シクロスポリンとタクロリムス",
    # 手作業で作った提示用のまとまり。ばらすと同名別内容のxlsxが衝突するためフォルダごと運ぶ
    "提示データ",
}


def iter_files(roots, extra_exclude):
    """整理対象のファイルを列挙する。"""
    seen = set()
    exclude = EXCLUDE_DIRS | extra_exclude
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in exclude]
            for f in filenames:
                p = os.path.join(dirpath, f)
                if p not in seen:
                    seen.add(p)
                    yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="移動せず一覧のみ表示")
    add_nokouhi_arg(ap)
    args = ap.parse_args()

    dest_root = data_root(args.nokouhi)
    out = output_dir(args.nokouhi, create=False)
    # 主解析（公費含まない）の整理では 公費含む/ を巻き込まない
    extra_exclude = {KOUHI_SUBDIR} if args.nokouhi else set()
    label = "公費含まない（主解析）" if args.nokouhi else "公費含む（参考）"
    print(f"整理対象: {dest_root}  [{label}]")

    # 提示データ/ はフォルダごと 04_図表 の下へ運ぶ（中身をばらさない）
    old_teiji = os.path.join(out, "提示データ")
    new_teiji = os.path.join(dest_root, FIGURE_SUBDIR, "提示データ")
    if os.path.isdir(old_teiji) and not os.path.exists(new_teiji):
        if args.dry_run:
            print(f"  {os.path.relpath(old_teiji, BASE_DIR)}\\ -> "
                  f"{os.path.relpath(new_teiji, BASE_DIR)}\\")
        else:
            os.makedirs(os.path.dirname(new_teiji), exist_ok=True)
            shutil.move(old_teiji, new_teiji)
            print("  提示データ/ をフォルダごと 04_図表 へ移動")

    moved, replaced, skipped, conflicts, failed = 0, 0, 0, [], []
    for src in list(iter_files([out, dest_root], extra_exclude)):
        name = os.path.basename(src)
        dest_rel = classify(name)
        if dest_rel is None:
            skipped += 1
            continue
        dest_dir = os.path.join(dest_root, dest_rel) if dest_rel else dest_root
        dest = os.path.join(dest_dir, name)
        if os.path.abspath(src) == os.path.abspath(dest):
            continue
        if os.path.exists(dest):
            # processed*/ 配下（plots/ 等のサブフォルダを含む）は今回のパイプライン実行が
            # 生成した最新の出力なので、整理先の古い同名ファイルを置き換える。
            # それ以外（既に整理済みの場所や手作業で置いたファイル）は据え置く。
            if not os.path.abspath(src).startswith(os.path.abspath(out) + os.sep):
                same = filecmp.cmp(src, dest, shallow=False)
                conflicts.append((os.path.relpath(src, BASE_DIR),
                                  os.path.relpath(dest, BASE_DIR), same))
                continue
            replaced += 1
        if args.dry_run:
            print(f"  {os.path.relpath(src, BASE_DIR)} -> {os.path.relpath(dest, BASE_DIR)}")
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
            failed.append((os.path.relpath(src, BASE_DIR), str(e)))

    print(f"移動 {moved} 件（うち更新 {replaced} 件） / 対象外 {skipped} 件 "
          f"/ 据置 {len(conflicts)} 件")
    for s, d, same in conflicts:
        note = "内容同一" if same else "★内容が異なる"
        print(f"  [据置] {s}\n         移動先に既存 ({note}): {d}")
    for f, e in failed:
        print(f"  [失敗] {f}: {e}")


if __name__ == "__main__":
    main()
