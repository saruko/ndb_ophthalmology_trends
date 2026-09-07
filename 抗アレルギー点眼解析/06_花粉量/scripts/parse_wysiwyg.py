import urllib.request
from bs4 import BeautifulSoup
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.env.go.jp/chemi/anzen/kafun/kakohisan.html"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(html, 'html.parser')
    
    wysiwyg = soup.find('div', class_='wysiwyg')
    if wysiwyg:
        print("--- WYSIWYG Content ---")
        # Print children names and text
        for child in wysiwyg.children:
            if child.name:
                print(f"Child Tag: {child.name}")
                # print a preview of text
                txt = child.get_text(strip=True)
                if len(txt) > 200:
                    txt = txt[:200] + "..."
                print(f"  Text: {txt}")
                # If there are links, print them
                links = child.find_all('a', href=True)
                for a in links:
                    print(f"    Link: {a.get_text(strip=True)} -> {a['href']}")
except Exception as e:
    print(f"Error: {e}")
