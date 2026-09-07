"""
Open-Meteo Historical Weather APIから47都道府県庁所在地の
日積算全天日射量（shortwave_radiation_sum）を取得し、
年度別・月別の紫外線proxy変数データを生成する。
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error
import pandas as pd
import numpy as np

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from paths import BASE_DIR, UV_SUBDIR  # noqa: E402

# 47都道府県庁所在地の緯度・経度
PREFECTURE_CAPITALS = {
    "北海道":    (43.0642, 141.3469),
    "青森県":    (40.8244, 140.7400),
    "岩手県":    (39.7036, 141.1527),
    "宮城県":    (38.2689, 140.8719),
    "秋田県":    (39.7186, 140.1025),
    "山形県":    (38.2406, 140.3633),
    "福島県":    (37.7503, 140.4678),
    "茨城県":    (36.3419, 140.4467),
    "栃木県":    (36.5658, 139.8836),
    "群馬県":    (36.3911, 139.0608),
    "埼玉県":    (35.8569, 139.6489),
    "千葉県":    (35.6047, 140.1233),
    "東京都":    (35.6895, 139.6917),
    "神奈川県":  (35.4478, 139.6425),
    "新潟県":    (37.9022, 139.0236),
    "富山県":    (36.6953, 137.2114),
    "石川県":    (36.5947, 136.6256),
    "福井県":    (36.0652, 136.2217),
    "山梨県":    (35.6642, 138.5683),
    "長野県":    (36.2333, 138.1811),
    "岐阜県":    (35.3912, 136.7222),
    "静岡県":    (34.9756, 138.3828),
    "愛知県":    (35.1803, 136.9067),
    "三重県":    (34.7303, 136.5086),
    "滋賀県":    (35.0045, 135.8686),
    "京都府":    (35.0214, 135.7556),
    "大阪府":    (34.6864, 135.5200),
    "兵庫県":    (34.6913, 135.1830),
    "奈良県":    (34.6851, 135.8049),
    "和歌山県":  (34.2261, 135.1675),
    "鳥取県":    (35.5039, 134.2378),
    "島根県":    (35.4723, 133.0505),
    "岡山県":    (34.6617, 133.9350),
    "広島県":    (34.3966, 132.4596),
    "山口県":    (34.1861, 131.4706),
    "徳島県":    (34.0658, 134.5593),
    "香川県":    (34.3401, 134.0434),
    "愛媛県":    (33.8416, 132.7657),
    "高知県":    (33.5597, 133.5311),
    "福岡県":    (33.6064, 130.4181),
    "佐賀県":    (33.2494, 130.2988),
    "長崎県":    (32.7448, 129.8737),
    "熊本県":    (32.7898, 130.7417),
    "大分県":    (33.2382, 131.6126),
    "宮崎県":    (31.9111, 131.4239),
    "鹿児島県":  (31.5602, 130.5581),
    "沖縄県":    (26.2124, 127.6809),
}

def fetch_openmeteo_year(prefecture, lat, lon, year):
    """1都道府県・1年度分のデータを取得する"""
    # NDB年度は4月〜翌3月だが、暦年のUV/日射量と対比するため暦年で取得
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date}&end_date={end_date}"
        f"&daily=shortwave_radiation_sum"
        f"&timezone=Asia%2FTokyo"
    )
    
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"  Error fetching {prefecture} {year}: {e}")
        return None
    
    if "daily" not in data:
        print(f"  Warning: No daily data returned for {prefecture} {year}")
        return None
    
    dates = data["daily"]["time"]
    values = data["daily"]["shortwave_radiation_sum"]
    
    df = pd.DataFrame({"date": dates, "radiation_sum": values})
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.month
    df["prefecture"] = prefecture
    df["year"] = year
    
    return df

def main():
    output_dir = os.path.join(BASE_DIR, UV_SUBDIR)
    os.makedirs(output_dir, exist_ok=True)
    
    all_daily = []
    total_requests = len(PREFECTURE_CAPITALS) * 11  # 2014-2024
    current = 0
    
    print(f"Open-Meteo: {len(PREFECTURE_CAPITALS)}都道府県 × 11年 = {total_requests} リクエスト")
    
    for prefecture, (lat, lon) in PREFECTURE_CAPITALS.items():
        for year in range(2014, 2025):
            current += 1
            print(f"  [{current}/{total_requests}] {prefecture} {year}...", end="")
            
            df = fetch_openmeteo_year(prefecture, lat, lon, year)
            if df is not None:
                all_daily.append(df)
                print(f" OK ({len(df)} days)")
            else:
                print(" FAILED")
            
            time.sleep(0.3)  # レート制限対策
    
    if not all_daily:
        print("Error: No data was retrieved.")
        return
    
    df_all = pd.concat(all_daily, ignore_index=True)
    
    # 月別平均を算出
    df_monthly = df_all.groupby(["year", "prefecture", "month"]).agg(
        radiation_mean=("radiation_sum", "mean"),
        radiation_sum_total=("radiation_sum", "sum"),
        n_days=("radiation_sum", "count")
    ).reset_index()
    
    # 年度平均を算出
    df_annual = df_all.groupby(["year", "prefecture"]).agg(
        radiation_annual_mean=("radiation_sum", "mean"),
        radiation_annual_sum=("radiation_sum", "sum"),
        n_days=("radiation_sum", "count")
    ).reset_index()
    
    # Excel保存（月別）
    xlsx_path = os.path.join(output_dir, "openmeteo_radiation_monthly.xlsx")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_monthly.to_excel(writer, sheet_name="monthly", index=False)
        df_annual.to_excel(writer, sheet_name="annual", index=False)
    print(f"Saved {xlsx_path}")
    
    # CSV保存（年度平均サマリー）
    csv_path = os.path.join(output_dir, "openmeteo_radiation_annual_mean.csv")
    df_annual.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Saved {csv_path}")
    
    # 基本的な妥当性チェック: 沖縄 vs 北海道
    for year in [2014, 2024]:
        okinawa = df_annual[(df_annual["prefecture"] == "沖縄県") & (df_annual["year"] == year)]
        hokkaido = df_annual[(df_annual["prefecture"] == "北海道") & (df_annual["year"] == year)]
        if not okinawa.empty and not hokkaido.empty:
            ok_val = okinawa["radiation_annual_mean"].values[0]
            hk_val = hokkaido["radiation_annual_mean"].values[0]
            print(f"Sanity check {year}: 沖縄={ok_val:.1f} MJ/m^2 vs 北海道={hk_val:.1f} MJ/m^2 (ratio={ok_val/hk_val:.2f})")
    
    print("Done.")

if __name__ == "__main__":
    main()
