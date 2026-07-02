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
    
    # Typically, the page contains headings like "令和７年シーズンの飛散結果" and then a table or block below it.
    # Let's find all headers and see their siblings.
    for heading in soup.find_all(['h3', 'h4', 'p', 'div']):
        text = heading.get_text(strip=True)
        if "シーズンの飛散結果" in text and len(text) < 40:
            print(f"\nHeader: {text}")
            # Find the next sibling that is a table or list, or has links
            sibling = heading.find_next_sibling()
            while sibling:
                if sibling.name in ['table', 'ul', 'ol', 'div']:
                    # Extract links
                    links = sibling.find_all('a', href=True)
                    if links:
                        for a in links:
                            link_text = a.get_text(strip=True)
                            href = a['href']
                            full_url = urllib.parse.urljoin(url, href)
                            print(f"  {link_text}: {full_url}")
                    break
                sibling = sibling.find_next_sibling()
except Exception as e:
    print(f"Error: {e}")
