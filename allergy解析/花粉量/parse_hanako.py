import urllib.request
from bs4 import BeautifulSoup
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.env.go.jp/page_00209.html"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(html, 'html.parser')
    
    print("--- Hanako Past Data Page ---")
    # Let's find links
    main_div = soup.find('div', id='main') or soup.find('body')
    for a in main_div.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        full_url = urllib.parse.urljoin(url, href)
        if any(term in href.lower() for term in ['zip', 'csv', 'xlsx', 'xls']) or any(term in text for term in ['データ', '過去', 'ダウンロード', '飛散']):
            print(f"Text: {text} | URL: {full_url}")
except Exception as e:
    print(f"Error: {e}")
