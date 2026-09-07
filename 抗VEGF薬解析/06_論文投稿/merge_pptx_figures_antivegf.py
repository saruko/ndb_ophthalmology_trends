# -*- coding: utf-8 -*-
"""
投稿用/Figure1.pptx 〜 Figure6.pptx を 1 ファイル（6 スライド）にまとめる。

`build_pptx_figures_antivegf.py` が 1 図 = 1 pptx で書き出したものを、
図番号順に 1 プレゼンテーションへ連結する。グラフはネイティブグラフのまま
（埋め込み Excel も含めて）コピーするので、統合後も編集できる。

実行:  .venv\\Scripts\\python.exe 抗VEGF薬解析/06_論文投稿/merge_pptx_figures_antivegf.py
"""
from __future__ import annotations

import copy
from pathlib import Path

from pptx import Presentation
from pptx.opc.packuri import PackURI

HERE = Path(__file__).resolve().parent
OUT = HERE / "投稿用"
SOURCES = [OUT / f"Figure{i}.pptx" for i in range(1, 7)]
DEST = OUT / "Figures1-6.pptx"

# スライドから辿る先のうち、レイアウトはコピー先のものを使うので除外する
LAYOUT_RELTYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
)


def clone_part(part, dest_package, used_partnames, cloned):
    """part（およびその参照先）をコピー先パッケージ用に partname を振り直して複製する。"""
    if part in cloned:
        return cloned[part]

    stem, _, ext = part.partname.rpartition(".")
    n = 1
    while True:
        candidate = PackURI(f"{stem}_m{n}.{ext}")
        if candidate not in used_partnames:
            break
        n += 1
    part.partname = candidate
    used_partnames.add(candidate)
    part._package = dest_package
    part.__dict__.pop("package", None)
    cloned[part] = part

    for rel in list(part.rels.values()):
        if not rel.is_external:
            clone_part(rel.target_part, dest_package, used_partnames, cloned)
    return part


def copy_slide(src_slide, dest_prs, used_partnames, cloned):
    layout = dest_prs.slide_layouts[6]  # Blank
    new_slide = dest_prs.slides.add_slide(layout)

    rid_map = {}
    for rel in list(src_slide.part.rels.values()):
        if rel.reltype == LAYOUT_RELTYPE:
            continue
        if rel.is_external:
            rid_map[rel.rId] = new_slide.part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        else:
            target = clone_part(rel.target_part, dest_prs.part.package, used_partnames, cloned)
            rid_map[rel.rId] = new_slide.part.relate_to(target, rel.reltype)

    dest_tree = new_slide.shapes._spTree
    for el in src_slide.shapes._spTree:
        if el.tag.endswith("}nvGrpSpPr") or el.tag.endswith("}grpSpPr"):
            continue
        new_el = copy.deepcopy(el)
        for node in new_el.iter():
            for attr in list(node.attrib):
                if attr.endswith("}id") or attr.endswith("}embed") or attr.endswith("}link"):
                    old = node.attrib[attr]
                    if old in rid_map:
                        node.attrib[attr] = rid_map[old]
        dest_tree.append(new_el)
    return new_slide


def main():
    missing = [p for p in SOURCES if not p.exists()]
    if missing:
        raise SystemExit("見つからないファイル: " + ", ".join(p.name for p in missing))

    dest_prs = Presentation()
    first = Presentation(str(SOURCES[0]))
    dest_prs.slide_width = first.slide_width
    dest_prs.slide_height = first.slide_height

    used_partnames = {p.partname for p in dest_prs.part.package.iter_parts()}
    cloned = {}

    for path in SOURCES:
        src = Presentation(str(path))
        for slide in src.slides:
            copy_slide(slide, dest_prs, used_partnames, cloned)
        print(f"  + {path.name} ({len(src.slides._sldIdLst)} slide)")

    dest_prs.save(str(DEST))
    print(f"saved: {DEST}  ({len(dest_prs.slides._sldIdLst)} slides)")


if __name__ == "__main__":
    main()
