"""
気象庁 UVインデックス解析値の年間推移グラフ画像をダウンロードし、
画像解析で月別数値データを抽出する。

データソース: https://www.data.jma.go.jp/env/uvhp/link_uvindex_month54.html
画像URL規則: https://www.data.jma.go.jp/env/uvhp/ana/{YYYY}/{PPP}_a_a_{YYYY}_max.png
"""
import os
import time
import urllib.request
import urllib.error
import numpy as np
import pandas as pd

# JMA地点番号と地点名のマッピング（全56地点）
JMA_POINTS = {
    "001": "稚内",   "002": "旭川",   "003": "網走",   "004": "釧路",   "005": "札幌",
    "006": "室蘭",   "007": "函館",   "008": "青森",   "009": "盛岡",   "010": "秋田",
    "011": "仙台",   "012": "山形",   "013": "福島",   "014": "水戸",   "015": "宇都宮",
    "016": "前橋",   "017": "千葉",   "018": "さいたま", "019": "東京",   "020": "横浜",
    "021": "新潟",   "022": "富山",   "023": "金沢",   "024": "福井",   "025": "甲府",
    "026": "長野",   "027": "岐阜",   "028": "静岡",   "029": "名古屋", "030": "津",
    "031": "大津",   "032": "京都",   "033": "大阪",   "034": "奈良",   "035": "和歌山",
    "036": "神戸",   "037": "鳥取",   "038": "松江",   "039": "岡山",   "040": "広島",
    "041": "山口",   "042": "徳島",   "043": "高松",   "044": "松山",   "045": "高知",
    "046": "福岡",   "047": "佐賀",   "048": "長崎",   "049": "熊本",   "050": "大分",
    "051": "宮崎",   "052": "鹿児島", "053": "名瀬",   "054": "那覇",   "055": "宮古島",
    "056": "石垣島",
}

# JMA地点 → 都道府県名のマッピング（都道府県庁所在地に対応する47地点を選択）
JMA_POINT_TO_PREFECTURE = {
    "005": "北海道",    "008": "青森県",    "009": "岩手県",    "011": "宮城県",
    "010": "秋田県",    "012": "山形県",    "013": "福島県",    "014": "茨城県",
    "015": "栃木県",    "016": "群馬県",    "018": "埼玉県",    "017": "千葉県",
    "019": "東京都",    "020": "神奈川県",  "021": "新潟県",    "022": "富山県",
    "023": "石川県",    "024": "福井県",    "025": "山梨県",    "026": "長野県",
    "027": "岐阜県",    "028": "静岡県",    "029": "愛知県",    "030": "三重県",
    "031": "滋賀県",    "032": "京都府",    "033": "大阪府",    "036": "兵庫県",
    "034": "奈良県",    "035": "和歌山県",  "037": "鳥取県",    "038": "島根県",
    "039": "岡山県",    "040": "広島県",    "041": "山口県",    "042": "徳島県",
    "043": "香川県",    "044": "愛媛県",    "045": "高知県",    "046": "福岡県",
    "047": "佐賀県",    "048": "長崎県",    "049": "熊本県",    "050": "大分県",
    "051": "宮崎県",    "052": "鹿児島県",  "054": "沖縄県",
}

# UVインデックスの色→値マッピング（JMAの標準カラーバー）
# JMAのUVインデックス棒グラフは以下の色分けを使用:
#   紫(11+), 赤(8-10), 橙(6-7), 黄(3-5), 緑(1-2)
# 棒グラフの高さからUV値を読み取るため、Y軸のピクセル位置を基準とする


def download_images(output_dir, years=range(2014, 2025)):
    """JMA UVインデックス画像を一括ダウンロードする"""
    img_dir = os.path.join(output_dir, "jma_images")
    os.makedirs(img_dir, exist_ok=True)
    
    base_url = "https://www.data.jma.go.jp/env/uvhp/ana"
    
    # 都道府県マッピングに含まれる地点のみダウンロード
    target_points = list(JMA_POINT_TO_PREFECTURE.keys())
    total = len(target_points) * len(years)
    current = 0
    downloaded = 0
    failed = 0
    
    print(f"JMA: {len(target_points)}地点 × {len(years)}年 = {total} 画像をダウンロード")
    
    for year in years:
        year_dir = os.path.join(img_dir, str(year))
        os.makedirs(year_dir, exist_ok=True)
        
        for point_num in target_points:
            current += 1
            point_name = JMA_POINTS[point_num]
            prefecture = JMA_POINT_TO_PREFECTURE[point_num]
            
            url = f"{base_url}/{year}/{point_num}_a_a_{year}_max.png"
            out_path = os.path.join(year_dir, f"{point_num}_{point_name}_{prefecture}.png")
            
            if os.path.exists(out_path):
                print(f"  [{current}/{total}] {prefecture}({point_name}) {year} - Already exists, skipping")
                downloaded += 1
                continue
            
            print(f"  [{current}/{total}] {prefecture}({point_name}) {year}...", end="")
            
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    img_data = resp.read()
                with open(out_path, "wb") as f:
                    f.write(img_data)
                downloaded += 1
                print(f" OK ({len(img_data)} bytes)")
            except urllib.error.URLError as e:
                failed += 1
                print(f" FAILED ({e})")
            
            time.sleep(0.3)
    
    print(f"\nDownload complete: {downloaded} succeeded, {failed} failed out of {total}")
    return img_dir


def analyze_bar_chart(img_path):
    """
    JMA UVインデックス棒グラフ画像から月別の数値を抽出する。
    
    画像構造（400×300 px）:
    - X軸: 12本の棒（1月〜12月）
    - Y軸: UVインデックス値（0〜最大14程度）
    - 背景: 白色、棒の色はUV値に応じた段階色
    """
    try:
        from PIL import Image
    except ImportError:
        print("Warning: Pillow is not installed. Cannot analyze images.")
        return None
    
    img = Image.open(img_path).convert("RGB")
    pixels = np.array(img)
    
    height, width, _ = pixels.shape
    
    # グラフ領域の検出:
    # Y軸の0ラインと最大ラインのピクセル位置を特定する
    # JMAのグラフは一定のフォーマットに従っており、
    # プロット領域は大体 x: 55-380, y: 25-250 程度
    
    # グラフの軸線（黒い線）を検出してプロット領域を特定
    # 黒に近いピクセル（RGB各チャネルが50未満）をスキャン
    is_dark = np.all(pixels < 80, axis=2)
    
    # Y軸の位置（左端の縦線）を検出
    left_margin = 50  # おおよその左マージン
    for x in range(30, min(100, width)):
        dark_count = np.sum(is_dark[:, x])
        if dark_count > height * 0.5:
            left_margin = x
            break
    
    # X軸の位置（下端の横線）を検出
    bottom_line = height - 50  # おおよその下マージン
    for y in range(height - 20, max(height // 2, 100), -1):
        dark_count = np.sum(is_dark[y, left_margin:width - 20])
        if dark_count > (width - left_margin - 20) * 0.3:
            bottom_line = y
            break
    
    # Y軸の最上部（グラフ領域の上端）
    top_line = 20
    for y in range(10, height // 2):
        dark_count = np.sum(is_dark[y, left_margin:left_margin + 5])
        if dark_count > 0:
            top_line = y
            break
    
    # Y軸のスケールを推定
    # JMAのグラフではY軸目盛りが0, 2, 4, 6, 8, 10, 12, 14 などとなる
    # 棒の最大高さからスケールを逆算する
    # まず、Y軸の目盛り数字を読むのは困難なので、
    # 標準的なスケール（最大値12または14）を仮定する
    y_max_value = 12.0  # デフォルト。高い地点では14を使う場合もある
    
    plot_height = bottom_line - top_line
    plot_width = width - left_margin - 30  # 右マージンを考慮
    
    # 12ヶ月の棒の位置を推定
    bar_width_approx = plot_width / 12
    monthly_values = []
    
    for month in range(12):
        # 各月の棒の中心X座標
        bar_center_x = int(left_margin + bar_width_approx * (month + 0.5))
        
        # X方向に数ピクセル幅でサンプリング
        x_start = max(left_margin + 1, bar_center_x - 5)
        x_end = min(width - 1, bar_center_x + 5)
        
        # 棒の頂部を検出: 上から走査して、白でも黒でもないピクセル（=棒の色）を探す
        bar_top = bottom_line  # デフォルト（棒なし = 値0）
        
        for y in range(top_line, bottom_line):
            # サンプリング領域のピクセルを確認
            strip = pixels[y, x_start:x_end, :]
            
            # 白背景でなく、黒軸線でもないピクセルがあるか
            is_white = np.all(strip > 220, axis=1)
            is_black = np.all(strip < 80, axis=1)
            is_colored = ~is_white & ~is_black
            
            if np.sum(is_colored) >= 3:  # 3ピクセル以上が色付き
                bar_top = y
                break
        
        # 棒の高さからUV値を計算
        bar_height_px = bottom_line - bar_top
        if bar_height_px <= 1:
            uv_value = 0.0
        else:
            uv_value = (bar_height_px / plot_height) * y_max_value
        
        monthly_values.append(round(uv_value, 1))
    
    return monthly_values


def analyze_all_images(img_dir, output_dir, years=range(2014, 2025)):
    """全画像を解析し、月別UVインデックスデータを生成する"""
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow is required for image analysis. Install with: pip install Pillow")
        return None
    
    records = []
    errors = []
    
    for year in years:
        year_dir = os.path.join(img_dir, str(year))
        if not os.path.exists(year_dir):
            print(f"  Warning: {year_dir} does not exist, skipping year {year}")
            continue
        
        for point_num, prefecture in JMA_POINT_TO_PREFECTURE.items():
            point_name = JMA_POINTS[point_num]
            img_path = os.path.join(year_dir, f"{point_num}_{point_name}_{prefecture}.png")
            
            if not os.path.exists(img_path):
                print(f"  Warning: {img_path} not found")
                errors.append({"year": year, "prefecture": prefecture, "error": "file_not_found"})
                continue
            
            values = analyze_bar_chart(img_path)
            if values is None:
                errors.append({"year": year, "prefecture": prefecture, "error": "analysis_failed"})
                continue
            
            for month_idx, uv_val in enumerate(values):
                records.append({
                    "year": year,
                    "prefecture": prefecture,
                    "jma_point": point_name,
                    "month": month_idx + 1,
                    "uv_index_monthly_mean": uv_val,
                })
    
    if not records:
        print("Error: No data extracted from images.")
        return None
    
    df = pd.DataFrame(records)
    
    # 年間平均を算出
    df_annual = df.groupby(["year", "prefecture", "jma_point"]).agg(
        uv_index_annual_mean=("uv_index_monthly_mean", "mean")
    ).reset_index()
    
    # Excel保存
    xlsx_path = os.path.join(output_dir, "jma_uv_index_monthly.xlsx")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="monthly", index=False)
        df_annual.to_excel(writer, sheet_name="annual", index=False)
    print(f"Saved {xlsx_path}")
    
    # CSV保存（年度平均）
    csv_path = os.path.join(output_dir, "jma_uv_index_annual_mean.csv")
    df_annual.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Saved {csv_path}")
    
    # エラーがあれば報告
    if errors:
        print(f"\nWarning: {len(errors)} errors occurred during analysis:")
        for e in errors[:10]:
            print(f"  {e}")
    
    # 妥当性チェック
    for year in [2014, 2024]:
        okinawa = df_annual[(df_annual["prefecture"] == "沖縄県") & (df_annual["year"] == year)]
        hokkaido = df_annual[(df_annual["prefecture"] == "北海道") & (df_annual["year"] == year)]
        if not okinawa.empty and not hokkaido.empty:
            ok_val = okinawa["uv_index_annual_mean"].values[0]
            hk_val = hokkaido["uv_index_annual_mean"].values[0]
            print(f"Sanity check {year}: 沖縄={ok_val:.1f} vs 北海道={hk_val:.1f} (ratio={ok_val/hk_val:.2f})")
    
    return df


def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=" * 60)
    print("  JMA UVインデックス解析値 画像ダウンロード＆数値抽出")
    print("=" * 60)
    
    # Step 1: 画像ダウンロード
    print("\n[Step 1] Downloading JMA UV index images...")
    img_dir = download_images(output_dir, years=range(2014, 2025))
    
    # Step 2: 画像解析
    print("\n[Step 2] Analyzing bar charts to extract monthly UV index values...")
    df = analyze_all_images(img_dir, output_dir, years=range(2014, 2025))
    
    if df is not None:
        print(f"\n[SUCCESS] Extracted {len(df)} records.")
    else:
        print("\n[WARNING] Image analysis failed. Images are saved in jma_images/.")
        print("Manual inspection of the images may be required.")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
