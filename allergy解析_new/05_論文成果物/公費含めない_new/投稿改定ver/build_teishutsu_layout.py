# -*- coding: utf-8 -*-
"""Rebuild 提出風 deck: portrait pages, panels from matome.pptx merged per figure."""
import copy, os, shutil, zipfile
from lxml import etree

EMU = 914400
NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}
R = '{%s}' % NS['r']
P = '{%s}' % NS['p']
A = '{%s}' % NS['a']
REL = '{%s}' % NS['rel']

SRC = 'matome.pptx'
WORK = 'work'
OUT = 'out_teishutsu.pptx'

if os.path.exists(WORK):
    shutil.rmtree(WORK)
zipfile.ZipFile(SRC).extractall(WORK)

def parse(path):
    return etree.parse(path)

def slide_path(n):
    return os.path.join(WORK, 'ppt', 'slides', 'slide%d.xml' % n)

def rels_path(n):
    return os.path.join(WORK, 'ppt', 'slides', '_rels', 'slide%d.xml.rels' % n)

def in_(v):
    return int(round(v * EMU))

# ---- layout definitions ----
# page: Fig label + list of panels; each panel = source slide number + geometry
def std_panel(i):
    T = 2.3 + i * 9.0
    return {
        'title':   (0.6, T, 12.5, 0.55),
        'chart':   (0.6, T + 0.6, 12.1, 6.8),
        'caption': (0.6, T + 7.5, 12.5, 0.95),
    }

PAGES = [
    {'label': 'Fig. 1', 'base': 1, 'panels': [(1, std_panel(0)), (2, std_panel(1)), (3, std_panel(2))]},
    {'label': 'Fig. 2', 'base': 4, 'panels': [(4, std_panel(0))]},
    {'label': 'Fig. 3', 'base': 5, 'panels': [
        (5, {'title': (0.6, 2.3, 9.0, 0.9), 'chart': (0.46, 3.35, 8.7, 20.5), 'caption': (0.6, 24.05, 8.6, 1.3)}),
        (6, {'title': (9.8, 2.3, 11.0, 0.6), 'chart': (9.8, 3.35, 10.2, 10.74), 'caption': (9.8, 14.3, 11.0, 1.3)}),
    ]},
    {'label': 'Fig. 4', 'base': 7, 'panels': [(7, std_panel(0)), (8, std_panel(1))]},
    {'label': 'Fig. 5', 'base': 9, 'panels': [(9, std_panel(0)), (10, std_panel(1))]},
    {'label': 'Fig. 6', 'base': 11, 'panels': [(11, std_panel(0)), (12, std_panel(1))]},
    {'label': 'Fig. 7', 'base': 13, 'panels': [(13, std_panel(0)), (14, std_panel(1))]},
]

def classify(sp):
    """Return 'title'/'caption'/'chart' for a shape element."""
    tag = etree.QName(sp).localname
    if tag in ('graphicFrame', 'pic'):
        return 'chart'
    if tag == 'sp':
        name = sp.find('.//p:nvSpPr/p:cNvPr', NS).get('name')
        if name == 'TextBox 1':
            return 'title'
        if name == 'TextBox 2':
            return 'caption'
    return None

def set_xfrm(sp, geom):
    x, y, w, h = geom
    tag = etree.QName(sp).localname
    if tag == 'graphicFrame':
        xfrm = sp.find('p:xfrm', NS)
    else:
        xfrm = sp.find('.//a:xfrm', NS)
    off = xfrm.find('a:off', NS)
    ext = xfrm.find('a:ext', NS)
    off.set('x', str(in_(x))); off.set('y', str(in_(y)))
    ext.set('cx', str(in_(w))); ext.set('cy', str(in_(h)))

def load_rels(n):
    return parse(rels_path(n))

def max_rid(rels_tree):
    m = 0
    for rel in rels_tree.getroot():
        rid = rel.get('Id')
        if rid.startswith('rId'):
            m = max(m, int(rid[3:]))
    return m

FIG_LABEL_XML = '''<p:sp xmlns:p="{p}" xmlns:a="{a}">
 <p:nvSpPr><p:cNvPr id="900" name="FigLabel"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
 <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
  <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
 <p:txBody><a:bodyPr wrap="none" rtlCol="0"><a:spAutoFit/></a:bodyPr><a:lstStyle/>
  <a:p><a:r><a:rPr lang="en-US" sz="2800" dirty="0"><a:latin typeface="+mn-lt"/></a:rPr><a:t>{text}</a:t></a:r></a:p>
 </p:txBody></p:sp>'''

for page in PAGES:
    base = page['base']
    base_tree = parse(slide_path(base))
    base_rels = load_rels(base)
    sp_tree = base_tree.getroot().find('.//p:cSpTree' if False else './/p:spTree', NS)
    rid_counter = max_rid(base_rels)

    for src_n, geom in page['panels']:
        if src_n == base:
            for sp in list(sp_tree):
                kind = classify(sp)
                if kind:
                    set_xfrm(sp, geom[kind])
        else:
            donor_tree = parse(slide_path(src_n))
            donor_rels = load_rels(src_n)
            donor_relmap = {rel.get('Id'): rel for rel in donor_rels.getroot()}
            donor_sptree = donor_tree.getroot().find('.//p:spTree', NS)
            for sp in donor_sptree:
                kind = classify(sp)
                if not kind:
                    continue
                new_sp = copy.deepcopy(sp)
                # remap relationship ids in the copied subtree
                for el in new_sp.iter():
                    for attr in list(el.attrib):
                        if attr.startswith(R):
                            old = el.get(attr)
                            if old in donor_relmap:
                                rid_counter += 1
                                new_id = 'rId%d' % rid_counter
                                src_rel = donor_relmap[old]
                                new_rel = etree.SubElement(base_rels.getroot(), REL + 'Relationship')
                                new_rel.set('Id', new_id)
                                new_rel.set('Type', src_rel.get('Type'))
                                new_rel.set('Target', src_rel.get('Target'))
                                if src_rel.get('TargetMode'):
                                    new_rel.set('TargetMode', src_rel.get('TargetMode'))
                                el.set(attr, new_id)
                set_xfrm(new_sp, geom[kind])
                sp_tree.append(new_sp)

    # add Fig label
    label = etree.fromstring(FIG_LABEL_XML.format(
        p=NS['p'], a=NS['a'], x=in_(0.95), y=in_(0.85), cx=in_(2.2), cy=in_(0.7),
        text=page['label']))
    sp_tree.append(label)

    # renumber shape ids uniquely
    i = 1
    for cnv in sp_tree.iter(P + 'cNvPr'):
        i += 1
        cnv.set('id', str(i))

    base_tree.write(slide_path(base), xml_declaration=True, encoding='UTF-8', standalone=True)
    base_rels.write(rels_path(base), xml_declaration=True, encoding='UTF-8', standalone=True)

# ---- presentation.xml: slide size + keep only base slides ----
pres_path = os.path.join(WORK, 'ppt', 'presentation.xml')
pres = parse(pres_path)
sldsz = pres.getroot().find('p:sldSz', NS)
sldsz.set('cx', '20574000')
sldsz.set('cy', '27432000')
if sldsz.get('type'):
    del sldsz.attrib['type']

pres_rels_path = os.path.join(WORK, 'ppt', '_rels', 'presentation.xml.rels')
pres_rels = parse(pres_rels_path)
# map rId -> slide number
rid_to_slide = {}
for rel in pres_rels.getroot():
    tgt = rel.get('Target')
    if tgt.startswith('slides/slide'):
        rid_to_slide[rel.get('Id')] = int(tgt.replace('slides/slide', '').replace('.xml', ''))

keep = [pg['base'] for pg in PAGES]
sldlst = pres.getroot().find('p:sldIdLst', NS)
for sld in list(sldlst):
    n = rid_to_slide.get(sld.get(R + 'id'))
    if n not in keep:
        sldlst.remove(sld)
pres.write(pres_path, xml_declaration=True, encoding='UTF-8', standalone=True)

print('merged; kept slides:', keep)
