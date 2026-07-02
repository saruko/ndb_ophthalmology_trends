import urllib.request
from bs4 import BeautifulSoup
import re
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.env.go.jp/chemi/anzen/kafun/kakohisan.html"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(html, 'html.parser')
    
    print("--- Detailed Links in MOE Kakohisan ---")
    # Find tables or list items where links reside
    # Typically they are in tables or lists. Let's print out the text context around links.
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        full_url = urllib.parse.urljoin(url, href)
        
        # Get some parent or sibling text to understand the context
        parent = a.find_parent()
        parent_text = parent.get_text(strip=True) if parent else ""
        # truncate parent text if too long
        if len(parent_text) > 100:
            parent_text = parent_text[:100] + "..."
            
        if any(term in href.lower() for term in ['hisan', 'kafun', 'pdf', 'xlsx', 'xls', 'csv', 'page_00209']) or any(term in text for term in ['飛散', '花粉', 'データ', 'Excel', 'PDF']):
            print(f"Context: {parent_text}")
            print(f"  Link Text: {text}")
            print(f"  URL: {full_url}\n")
except Exception as e:
    print(f"Error: {e}")
