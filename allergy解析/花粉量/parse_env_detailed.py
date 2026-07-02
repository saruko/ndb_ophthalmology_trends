import urllib.request
from bs4 import BeautifulSoup
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.env.go.jp/chemi/anzen/kafun/kakohisan.html"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(html, 'html.parser')
    
    # Let's inspect the block with "過去の飛散結果一覧"
    # Find h2, h3, h4 tags or table cells
    # We will print out the structure of the list/table that contains R7, R6 seasons
    main_content = soup.find('body')
    # Print the text and structure around "令和７年シーズン"
    for element in main_content.find_all(text=True):
        if "シーズン" in element:
            parent = element.parent
            # Find closest ancestor list or table
            ancestor = parent
            for _ in range(5):
                if ancestor.name in ['table', 'ul', 'ol', 'div'] and ancestor.get('class') != 'l-body':
                    break
                ancestor = ancestor.parent
            print(f"--- Section for text: {element.strip()} ---")
            # print links inside this ancestor
            for a in ancestor.find_all('a', href=True):
                print(f"  Link: {a.get_text(strip=True)} -> {urllib.parse.urljoin(url, a['href'])}")
except Exception as e:
    print(f"Error: {e}")
