import cloudscraper
import json
import re
import urllib.parse
from bs4 import BeautifulSoup

scraper = cloudscraper.create_scraper()
query = 'panadol'
url = f"https://www.nahdionline.com/ar-sa/search?query={urllib.parse.quote(query)}"
res = scraper.get(url, timeout=20)

soup = BeautifulSoup(res.text, 'html.parser')
marker = 'window[Symbol.for("InstantSearchInitialResults")] = '

for script in soup.find_all('script'):
    if not script.string or marker not in script.string:
        continue
    raw = script.string
    idx = raw.find(marker)
    json_str = raw[idx + len(marker):]
    depth, end = 0, 0
    for i, c in enumerate(json_str):
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    data = json.loads(json_str[:end])
    for key, val in data.items():
        results_list = val.get('results', [])
        if not results_list:
            continue
        hits = results_list[0].get('hits', [])
        print(f"Found {len(hits)} hits in key: {key}")
        for h in hits[:5]:
            sku = h.get('sku', '')
            url_field = h.get('url', '')
            name = h.get('name', '')
            print(f"\n  Name: {name[:50]}")
            print(f"  SKU: {sku}")
            print(f"  url field: {url_field}")
            # Current logic
            if url_field and sku:
                slug = url_field.split('/')[-1]
                constructed = f"https://www.nahdionline.com/ar-sa/{slug}/pdp/{sku}"
                print(f"  Constructed URL: {constructed}")
            # All keys in hit
            print(f"  All url-related keys: {[k for k in h.keys() if 'url' in k.lower() or 'link' in k.lower() or 'slug' in k.lower() or 'path' in k.lower()]}")
        break
    break
