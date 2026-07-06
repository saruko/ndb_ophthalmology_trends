import os
import urllib.request
from bs4 import BeautifulSoup
import urllib.parse
import re
import pandas as pd
import argparse
from utils import clean_prefecture_name

# NPO parser のロジックを再利用するためインポート（同一ディレクトリなので可能）
from npo_pollen import parse_npo_excel

def get_env_pollen_urls():
    """
    環境省の過去飛散結果ページを解析し、年度・花粉種別のExcel/PDFリンクの辞書を取得する。
    """
    url = "https://www.env.go.jp/chemi/anzen/kafun/kakohisan.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 403 Forbiddenなどの可能性を想定し、フォールバックデータを定義しておく（WAF対策）
    # 万が一アクセスできない場合でも動作するようにハードコードされたURLリストを定義
    fallback_urls = {
        (2025, "sugi", "xlsx"): "https://www.env.go.jp/content/000377128.xlsx",
        (2025, "sugi", "pdf"): "https://www.env.go.jp/content/000378661.pdf",
        (2025, "hinoki", "xlsx"): "https://www.env.go.jp/content/000378664.xlsx",
        (2025, "hinoki", "pdf"): "https://www.env.go.jp/content/000378662.pdf",
        
        (2024, "sugi", "xlsx"): "https://www.env.go.jp/content/000377138.xlsx",
        (2024, "sugi", "pdf"): "https://www.env.go.jp/content/000377136.pdf",
        (2024, "hinoki", "xlsx"): "https://www.env.go.jp/content/000377140.xlsx",
        (2024, "hinoki", "pdf"): "https://www.env.go.jp/content/000377139.pdf",
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html = response.read()
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        print(f"Warning: Could not fetch MOE web page directly ({e}). Using hardcoded fallback URLs.")
        return fallback_urls

    wysiwyg = soup.find('div', class_='wysiwyg')
    if not wysiwyg:
        print("Warning: div.wysiwyg not found. Using fallback URLs.")
        return fallback_urls
        
    urls = {}
    current_season_year = None
    
    # wysiwyg直下のフラットな構造を走査する
    a_tag_count_in_section = 0
    for child in wysiwyg.children:
        if not child.name:
            continue
            
        if child.name in ['h3', 'h4']:
            text = child.get_text(strip=True)
            # 「令和７年シーズンの飛散結果」や「2024年シーズンの飛散結果」などから西暦を特定する
            match = re.search(r'(令和|平成|20)\s*([０-９0-9一二三四五六七八九十]+)\s*年', text)
            if match:
                era = match.group(1)
                num_str = match.group(2)
                # 全角数字を半角に変換
                num_str = num_str.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
                
                # 漢数字の簡易対応
                kanji_map = {"一":1, "二":2, "三":3, "四":4, "五":5, "六":6, "七":7, "八":8, "九":9, "十":10}
                if num_str in kanji_map:
                    year_num = kanji_map[num_str]
                else:
                    try:
                        year_num = int(num_str)
                    except ValueError:
                        year_num = None
                
                if year_num:
                    if era == "令和":
                        current_season_year = 2018 + year_num
                    elif era == "平成":
                        current_season_year = 1988 + year_num
                    else:
                        current_season_year = year_num
                    print(f"Detected season section for year: {current_season_year}")
                    a_tag_count_in_section = 0
            else:
                # シーズン年が特定できない見出しはリセット
                current_season_year = None
                
        elif child.name == 'a' and current_season_year:
            href = child['href']
            full_url = urllib.parse.urljoin(url, href)
            # リンクの拡張子
            ext = "xlsx" if "xlsx" in href.lower() or "xls" in href.lower() else "pdf" if "pdf" in href.lower() else None
            
            if ext:
                # 順序に基づくマッピング
                # 1番目と2番目のa: スギ (PDF, Excel)
                # 3番目と4番目のa: ヒノキ (PDF, Excel)
                # 5番目と6番目のa: 合計 (PDF, Excel)
                pollen_types = ["sugi", "sugi", "hinoki", "hinoki", "total", "total"]
                if a_tag_count_in_section < len(pollen_types):
                    p_type = pollen_types[a_tag_count_in_section]
                    urls[(current_season_year, p_type, ext)] = full_url
                a_tag_count_in_section += 1
                
    # 取得できたリンク数が少なすぎる場合は fallback と統合する
    for k, v in fallback_urls.items():
        if k not in urls:
            urls[k] = v
            
    return urls

def download_env_file(url, year, pollen_type, ext):
    os.makedirs("tmp", exist_ok=True)
    dest = f"tmp/env_{pollen_type}{year}.{ext}"
    if os.path.exists(dest):
        return dest
    print(f"Downloading {url} to {dest}...")
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        with open(dest, 'wb') as f:
            f.write(response.read())
    return dest

def parse_env_pdf(file_path, year, pollen_type):
    """
    pdfplumber を用いて、環境省の報道発表資料PDFからデータを抽出する。
    """
    import pdfplumber
    
    results = []
    with pdfplumber.open(file_path) as pdf:
        # 通常、最初のページにテーブルがある
        page = pdf.pages[0]
        tables = page.extract_tables()
        
        if not tables:
            raise Exception(f"No tables found in PDF {file_path}")
            
        # 都道府県名が含まれるテーブルと、合計が含まれるテーブルを探す
        pref_table = None
        pref_row_idx = -1
        
        for t in tables:
            for r_idx, row in enumerate(t):
                # row の要素に "都道府県" が含まれているか
                if any("都道府県" in str(val) for val in row if val):
                    pref_table = t
                    pref_row_idx = r_idx
                    break
            if pref_table:
                break
                
        if not pref_table:
            raise Exception("Could not find table containing '都道府県' in PDF")
            
        # 都道府県名と地点名の抽出
        col_mapping = []
        for col_idx in range(len(pref_table[pref_row_idx])):
            val = pref_table[pref_row_idx][col_idx]
            if not val:
                continue
            pref_name = clean_prefecture_name(str(val))
            if pref_name:
                # 地点名は次の行
                station_name = pref_table[pref_row_idx + 1][col_idx]
                if station_name:
                    station_name = str(station_name).strip().replace("\n", "").replace("　", "")
                else:
                    station_name = "不明"
                col_mapping.append((col_idx, pref_name, station_name))
                
        # 合計値テーブル（通常は同じテーブルの下部か、次のテーブルにある）
        # テーブル全体を走査して、合計行（「期間中合計」や「累計」など）を探す
        total_vals = None
        
        # 1. 同じテーブル内で探す
        for row in pref_table:
            if any(("期間中合計" in str(val) or "累計" in str(val) or "合計" in str(val)) for val in row if val):
                # 合計行の数値列をマッピング
                # ただし、この行が都道府県列と並んでいるか
                total_vals = row
                break
                
        # 2. 別のテーブルにある場合（pdfplumberが分割してしまった場合など）
        if total_vals is None and tables:
            # 最後のテーブルの最終行をチェック
            last_table = tables[-1]
            last_row = last_table[-1]
            
            # last_row の要素が大半数値に変換可能かチェック
            num_count = 0
            for val in last_row:
                if val is None:
                    continue
                try:
                    val_clean = str(val).replace(",", "").strip()
                    if val_clean:
                        float(val_clean)
                        num_count += 1
                except ValueError:
                    pass
            
            if len(last_row) > 0 and (num_count / len(last_row)) > 0.5:
                total_vals = last_row
                
        if total_vals is None:
            raise Exception("Could not find total values row in PDF tables")
            
        # マッピングして結果を構築
        # 列数がずれている場合を考慮
        # 例：都道府県テーブルは27列（最初の3列はラベル）、合計値テーブルは24列（ラベルなし）
        # そのため、合計値テーブルのインデックスは、都道府県テーブルのインデックス - 差分 になる
        col_diff = len(pref_table[0]) - len(total_vals)
        
        for col_idx, pref_name, station_name in col_mapping:
            target_idx = col_idx - col_diff
            if 0 <= target_idx < len(total_vals):
                val_str = total_vals[target_idx]
                try:
                    if isinstance(val_str, str):
                        val_str = val_str.replace(",", "").strip()
                    total_val = float(val_str)
                except Exception:
                    total_val = 0.0
            else:
                total_val = 0.0
                
            results.append({
                "year": year,
                "source": "MOE",
                "prefecture": pref_name,
                "station": station_name,
                "pollen_type": "スギ" if pollen_type == "sugi" else "ヒノキ",
                "total_scattering": total_val
            })
            
    return results

def get_env_pollen(year, pollen_type, force_pdf=False):
    urls = get_env_pollen_urls()
    
    # 指定された年度・花粉種・拡張子のURLがあるか確認
    # Excelを最優先で使用する
    ext = "pdf" if force_pdf else "xlsx"
    url_key = (year, pollen_type, ext)
    
    # Excel がなくて PDF ならある場合、あるいはその逆
    if url_key not in urls:
        alt_ext = "pdf" if ext == "xlsx" else "xlsx"
        alt_key = (year, pollen_type, alt_ext)
        if alt_key in urls:
            url_key = alt_key
            ext = alt_ext
            print(f"Note: Requested format {ext} not available. Falling back to {alt_ext}.")
            
    if url_key not in urls:
        raise Exception(f"No URL found for MOE pollen data: year={year}, type={pollen_type}")
        
    url = urls[url_key]
    file_path = download_env_file(url, year, pollen_type, ext)
    
    if ext in ["xlsx", "xls"]:
        data = parse_npo_excel(file_path, year, pollen_type)
        # ソース名を MOE に書き換える
        for d in data:
            d["source"] = "MOE"
        return data
    else:
        return parse_env_pdf(file_path, year, pollen_type)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MOE Pollen Data Gatherer")
    parser.add_argument("--year", type=int, default=2024, help="Target year")
    parser.add_argument("--type", type=str, default="sugi", choices=["sugi", "hinoki"], help="Pollen type")
    parser.add_argument("--pdf", action="store_true", help="Force PDF parsing even if Excel is available")
    args = parser.parse_args()
    
    try:
        data = get_env_pollen(args.year, args.type, force_pdf=args.pdf)
        df = pd.DataFrame(data)
        out_path = f"tmp/env_{args.type}_{args.year}.csv"
        df.to_csv(out_path, index=False, encoding='utf-8-sig')
        print(f"Successfully processed MOE data. Output saved to {out_path}")
        print(df.head(5))
    except Exception as e:
        print(f"Error processing MOE data: {e}")
