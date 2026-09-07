# -*- coding: utf-8 -*-
"""docx の変更履歴を確定し、コメントを取り除く。

投稿用の clean 版を作るための共通処理。査読者・共著者に回した原稿には
w:ins / w:del とWordコメントが残るため、そのまま投稿すると変換ツールによっては
削除テキストと挿入テキストが連結されて表示される（実際、外部の模擬査読で
「0.0842024年度…」のような存在しない誤植が報告された）。

  accept_revisions(doc)  … w:ins を展開、w:del を除去、削除された段落を落とす
  strip_comments(path)   … コメント関連パートと参照要素を zip ごと除去する
"""
import os
import re
import shutil
import zipfile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _q(tag):
    return "{%s}%s" % (W, tag)


def accept_revisions(doc):
    """python-docx の Document の変更履歴を確定する。戻り値は (削除段落数, ins数, del数)。"""
    body = doc.element.body
    dropped = 0
    for para in list(body.iter(_q("p"))):
        pPr = para.find(_q("pPr"))
        if pPr is None:
            continue
        rPr = pPr.find(_q("rPr"))
        if rPr is None or rPr.find(_q("del")) is None:
            continue
        parent = para.getparent()
        if parent is not None:
            parent.remove(para)
            dropped += 1
    n_del = 0
    for el in list(body.iter(_q("del"))):
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
            n_del += 1
    n_ins = 0
    for el in list(body.iter(_q("ins"))):
        parent = el.getparent()
        if parent is None:
            continue
        idx = list(parent).index(el)
        for k, ch in enumerate(list(el)):
            el.remove(ch)
            parent.insert(idx + k, ch)
        parent.remove(el)
        n_ins += 1
    # 段落プロパティに残った ins/del マーカー（段落記号の履歴）も落とす
    for pPr in body.iter(_q("pPr")):
        rPr = pPr.find(_q("rPr"))
        if rPr is None:
            continue
        for stale in rPr.findall(_q("ins")) + rPr.findall(_q("del")):
            rPr.remove(stale)
    return dropped, n_ins, n_del


COMMENT_PARTS = ("word/comments.xml", "word/commentsExtended.xml",
                 "word/commentsIds.xml", "word/commentsExtensible.xml",
                 "word/people.xml")


def strip_comments(path, dest=None):
    """docx（zip）からコメント関連パートと本文中の参照要素を取り除く。"""
    dest = dest or path
    tmp = dest + ".tmp"
    zin = zipfile.ZipFile(path)
    names = zin.namelist()
    drop_rels = set()

    rels = zin.read("word/_rels/document.xml.rels").decode("utf-8")
    rroot = etree.fromstring(rels.encode("utf-8"))
    RNS = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
    for rel in list(rroot):
        if rel.tag != RNS:
            continue
        tgt = rel.get("Target", "")
        if any(tgt.endswith(os.path.basename(p)) for p in COMMENT_PARTS):
            drop_rels.add(rel.get("Id"))
            rroot.remove(rel)
    new_rels = etree.tostring(rroot, xml_declaration=True,
                              encoding="UTF-8", standalone=True)

    ct = zin.read("[Content_Types].xml").decode("utf-8")
    croot = etree.fromstring(ct.encode("utf-8"))
    CNS = "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
    for ov in list(croot):
        if ov.tag == CNS and ov.get("PartName", "").lstrip("/") in COMMENT_PARTS:
            croot.remove(ov)
    new_ct = etree.tostring(croot, xml_declaration=True,
                            encoding="UTF-8", standalone=True)

    docxml = zin.read("word/document.xml")
    droot = etree.fromstring(docxml)
    n = 0
    for tag in ("commentRangeStart", "commentRangeEnd"):
        for el in list(droot.iter(_q(tag))):
            el.getparent().remove(el)
            n += 1
    for el in list(droot.iter(_q("commentReference"))):
        run = el.getparent()
        gp = run.getparent() if run is not None else None
        if gp is not None:
            gp.remove(run)
        elif run is not None:
            run.remove(el)
        n += 1
    new_doc = etree.tostring(droot, xml_declaration=True,
                             encoding="UTF-8", standalone=True)

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in COMMENT_PARTS:
                continue
            if item.filename == "word/_rels/document.xml.rels":
                zout.writestr(item, new_rels)
            elif item.filename == "[Content_Types].xml":
                zout.writestr(item, new_ct)
            elif item.filename == "word/document.xml":
                zout.writestr(item, new_doc)
            else:
                zout.writestr(item, zin.read(item.filename))
    zin.close()
    shutil.move(tmp, dest)
    return n


def audit(path):
    """残っている履歴・コメントの数を返す（検証用）。"""
    z = zipfile.ZipFile(path)
    x = z.read("word/document.xml").decode("utf-8")
    parts = set(z.namelist())
    return {
        "w:ins": len(re.findall(r"<w:ins[ >]", x)),
        "w:del": len(re.findall(r"<w:del[ >]", x)),
        "commentReference": x.count("commentReference"),
        "comment_parts": sorted(p for p in COMMENT_PARTS if p in parts),
    }
