import urllib.request
from bs4 import BeautifulSoup
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.fukushihoken.metro.tokyo.lg.jp/allergy/pollen/archive/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache'
}

try:
    req = urllib.request.Request(url, headers=headers)
    html = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(html, 'html.parser')
    
    print("--- Tokyo Pollen Archive Links ---")
    links_found = 0
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        full_url = urllib.parse.urljoin(url, href)
        if any(term in href.lower() for term in ['csv', 'pdf', 'archive', 'pollen']) or any(term in text for term in ['過去', 'データ', '飛散', 'ダウンロード']):
            print(f"Text: {text} | URL: {full_url}")
            links_found += 1
    if links_found == 0:
        print("No matching links found.")
except Exception as e:
    print(f"Error: {e}")
