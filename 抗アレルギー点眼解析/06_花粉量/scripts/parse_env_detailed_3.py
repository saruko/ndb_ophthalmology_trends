import urllib.request
from bs4 import BeautifulSoup
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.env.go.jp/chemi/anzen/kafun/kakohisan.html"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(html, 'html.parser')
    
    # Print the outer HTML or text of elements containing "シーズンの飛散結果"
    # To understand their exact structure
    for element in soup.find_all(text=True):
        if "シーズンの飛散結果" in element:
            parent = element.parent
            print(f"Tag: {parent.name}, Attributes: {parent.attrs}")
            print(f"Parent's parent: {parent.parent.name}, Attributes: {parent.parent.attrs}")
            print(f"Content: {parent.prettify()[:500]}\n")
except Exception as e:
    print(f"Error: {e}")
