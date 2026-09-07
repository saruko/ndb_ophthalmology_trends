import urllib.request
from bs4 import BeautifulSoup
import urllib.parse
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.env.go.jp/page_00209.html"
try:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    soup = BeautifulSoup(html, 'html.parser')
    
    print("--- Hanako Page Link Analysis ---")
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.get_text(strip=True)
        full_url = urllib.parse.urljoin(url, href)
        
        # Check if the text or URL is related to "花粉数" or "飛散量" and has Excel/CSV
        if any(term in href.lower() for term in ['zip', 'csv', 'xlsx', 'xls']):
            # Print the context (parent paragraph or table cell)
            parent = a.find_parent()
            parent_text = parent.get_text(strip=True) if parent else ""
            if len(parent_text) > 150:
                parent_text = parent_text[:150] + "..."
            print(f"Context: {parent_text}")
            print(f"  Text: {text} | URL: {full_url}\n")
except Exception as e:
    print(f"Error: {e}")
