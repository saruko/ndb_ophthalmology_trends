"""抗VEGF薬（薬効分類131 眼科用剤・注射）の薬剤マスタ。

医薬品コード単位で、成分・剤形（注射液=バイアル / キット=プレフィルドシリンジ）・
先発/バイオシミラーの別を定義する。
NDBの「後発品区分」は本分類では全品目0のため、製品名ベースで分類している。
"""

# code: (製品略称, 成分コード, 成分名, 剤形, ブランド区分, 分類)
DRUG_MASTER = {
    "622199401": ("アイリーア2mg 注射液", "AFLIBERCEPT", "アフリベルセプト",
                  "注射液", "先発", "ANTI_VEGF"),
    "629906401": ("アイリーア2mg キット", "AFLIBERCEPT", "アフリベルセプト",
                  "キット", "先発", "ANTI_VEGF"),
    "629928401": ("アイリーア8mg 注射液", "AFLIBERCEPT_8MG", "アフリベルセプト8mg",
                  "注射液", "先発", "ANTI_VEGF"),
    "629918901": ("バビースモ 注射液", "FARICIMAB", "ファリシマブ",
                  "注射液", "先発", "ANTI_VEGF"),
    "629907201": ("ベオビュ キット", "BROLUCIZUMAB", "ブロルシズマブ",
                  "キット", "先発", "ANTI_VEGF"),
    "620008448": ("マクジェン キット", "PEGAPTANIB", "ペガプタニブ",
                  "キット", "先発", "ANTI_VEGF"),
    "621894901": ("ルセンティス 注射液(10mg/mL)", "RANIBIZUMAB_ORIG", "ラニビズマブ（先発）",
                  "注射液", "先発", "ANTI_VEGF"),
    "620009103": ("ルセンティス 注射液(2.3/0.23)", "RANIBIZUMAB_ORIG", "ラニビズマブ（先発）",
                  "注射液", "先発", "ANTI_VEGF"),
    "622352001": ("ルセンティス キット", "RANIBIZUMAB_ORIG", "ラニビズマブ（先発）",
                  "キット", "先発", "ANTI_VEGF"),
    "629916701": ("ラニビズマブBS キット", "RANIBIZUMAB_BS", "ラニビズマブBS",
                  "キット", "バイオシミラー", "ANTI_VEGF"),
    # 参考（抗VEGF薬ではない）
    "622019901": ("マキュエイド 硝子体内注用", "TRIAMCINOLONE", "トリアムシノロン",
                  "注射液", "先発", "REFERENCE"),
    "622019902": ("マキュエイド 眼注用", "TRIAMCINOLONE", "トリアムシノロン",
                  "注射液", "先発", "REFERENCE"),
    # 全身投与（静注）のため硝子体注射解析からは除外
    "620001909": ("ビスダイン 静注用", "VERTEPORFIN", "ベルテポルフィン",
                  "静注", "先発", "SYSTEMIC"),
}

# 成分レベルの表示順
MOLECULE_ORDER = [
    "AFLIBERCEPT", "AFLIBERCEPT_8MG", "RANIBIZUMAB_ORIG", "RANIBIZUMAB_BS",
    "FARICIMAB", "BROLUCIZUMAB", "PEGAPTANIB",
]

# 集計グループ（成分コードの集合）
GROUPS = {
    "ANTI_VEGF_TOTAL": ("抗VEGF薬（合計）", MOLECULE_ORDER),
    "RANIBIZUMAB_ALL": ("ラニビズマブ（先発＋BS）", ["RANIBIZUMAB_ORIG", "RANIBIZUMAB_BS"]),
    "AFLIBERCEPT_ALL": ("アフリベルセプト（2mg＋8mg）", ["AFLIBERCEPT", "AFLIBERCEPT_8MG"]),
}

MOLECULE_NAMES = {
    "AFLIBERCEPT": "アフリベルセプト2mg（アイリーア）",
    "AFLIBERCEPT_8MG": "アフリベルセプト8mg（アイリーア8mg）",
    "RANIBIZUMAB_ORIG": "ラニビズマブ先発（ルセンティス）",
    "RANIBIZUMAB_BS": "ラニビズマブBS",
    "FARICIMAB": "ファリシマブ（バビースモ）",
    "BROLUCIZUMAB": "ブロルシズマブ（ベオビュ）",
    "PEGAPTANIB": "ペガプタニブ（マクジェン）",
    "TRIAMCINOLONE": "トリアムシノロン（マキュエイド）",
    "VERTEPORFIN": "ベルテポルフィン（ビスダイン）",
}
