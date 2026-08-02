# -*- coding: utf-8 -*-
"""薬剤コード → 英語名／日本語名の対応表（論文用成果物で使う）。"""

GROUP_EN = {
    "PGA": "Prostaglandin analogues",
    "BETA": "Beta-blockers",
    "ALPHA1BETA": "Alpha1-beta blockers",
    "ALPHA1": "Alpha1 blockers",
    "ALPHA2": "Alpha2 agonists",
    "SYMPATHO": "Non-selective sympathomimetics",
    "PARASYMPATHO": "Parasympathomimetics",
    "CAI": "Carbonic anhydrase inhibitors",
    "ROCK": "Rho-kinase inhibitors",
    "FDC_TOTAL": "Fixed-dose combinations",
    "GLAUCOMA_EYE_TOTAL": "All glaucoma eye drops",
}

SUBGROUP_EN = {
    "PGA_FP": "PGA: FP receptor agonists",
    "PGA_EP2": "PGA: EP2 receptor agonist",
    "PGA_ION": "PGA: ion channel opener",
    "BETA_NONSEL": "Beta-blockers: non-selective",
    "BETA_B1SEL": "Beta-blockers: beta1-selective",
    "PARASYM_DIR": "Parasympathomimetics: direct-acting",
    "PARASYM_IND": "Parasympathomimetics: indirect-acting",
}

DRUG_EN = {
    "LATANOPROST": "Latanoprost",
    "TRAVOPROST": "Travoprost",
    "TAFLUPROST": "Tafluprost",
    "BIMATOPROST": "Bimatoprost",
    "OMIDENEPAG": "Omidenepag isopropyl",
    "UNOPROSTONE": "Isopropyl unoprostone",
    "TIMOLOL": "Timolol",
    "CARTEOLOL": "Carteolol",
    "BETAXOLOL": "Betaxolol",
    "LEVOBUNOLOL": "Levobunolol",
    "NIPRADILOL": "Nipradilol",
    "DORZOLAMIDE": "Dorzolamide",
    "BRINZOLAMIDE": "Brinzolamide",
    "BRIMONIDINE": "Brimonidine",
    "RIPASUDIL": "Ripasudil",
    "BUNAZOSIN": "Bunazosin",
    "PILOCARPINE": "Pilocarpine",
    "DIPIVEFRINE": "Dipivefrine",
    "DISTIGMINE": "Distigmine",
    "APRACLONIDINE": "Apraclonidine (listed separately)",
    "FDC_PG_BETA": "PGA/beta-blocker FDC",
    "FDC_CAI_BETA": "CAI/beta-blocker FDC",
    "FDC_A2_BETA": "Alpha2/beta-blocker FDC",
    "FDC_A2_CAI": "Alpha2/CAI FDC",
    "FDC_ROCK_A2": "ROCK/alpha2 FDC",
}

INGREDIENT_EN = {
    "ING_PGA": "Prostaglandin analogues (ingredient basis)",
    "ING_BETA": "Beta-blockers (ingredient basis)",
    "ING_CAI": "Carbonic anhydrase inhibitors (ingredient basis)",
    "ING_ALPHA2": "Alpha2 agonists (ingredient basis)",
    "ING_ROCK": "Rho-kinase inhibitors (ingredient basis)",
}

DRUG_TYPE_EN = {
    "先発品": "Originator",
    "後発品（銘柄別収載）": "Generic (branded)",
    "後発品（統一名収載）": "Generic (unbranded)",
}

PREFECTURE_EN = {
    "北海道": "Hokkaido", "青森県": "Aomori", "岩手県": "Iwate", "宮城県": "Miyagi",
    "秋田県": "Akita", "山形県": "Yamagata", "福島県": "Fukushima", "茨城県": "Ibaraki",
    "栃木県": "Tochigi", "群馬県": "Gunma", "埼玉県": "Saitama", "千葉県": "Chiba",
    "東京都": "Tokyo", "神奈川県": "Kanagawa", "新潟県": "Niigata", "富山県": "Toyama",
    "石川県": "Ishikawa", "福井県": "Fukui", "山梨県": "Yamanashi", "長野県": "Nagano",
    "岐阜県": "Gifu", "静岡県": "Shizuoka", "愛知県": "Aichi", "三重県": "Mie",
    "滋賀県": "Shiga", "京都府": "Kyoto", "大阪府": "Osaka", "兵庫県": "Hyogo",
    "奈良県": "Nara", "和歌山県": "Wakayama", "鳥取県": "Tottori", "島根県": "Shimane",
    "岡山県": "Okayama", "広島県": "Hiroshima", "山口県": "Yamaguchi", "徳島県": "Tokushima",
    "香川県": "Kagawa", "愛媛県": "Ehime", "高知県": "Kochi", "福岡県": "Fukuoka",
    "佐賀県": "Saga", "長崎県": "Nagasaki", "熊本県": "Kumamoto", "大分県": "Oita",
    "宮崎県": "Miyazaki", "鹿児島県": "Kagoshima", "沖縄県": "Okinawa",
}


def en(code, default=None):
    """コードから英語名を引く（群・下位分類・薬剤・成分の順に探す）。"""
    for m in (GROUP_EN, SUBGROUP_EN, DRUG_EN, INGREDIENT_EN):
        if code in m:
            return m[code]
    return default if default is not None else code
