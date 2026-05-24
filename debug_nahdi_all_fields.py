import cloudscraper
import json
import urllib.parse
from bs4 import BeautifulSoup
import requests

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
        print(f"Checking all URL-related fields from first 5 hits:")
        for h in hits[:5]:
            name = h.get('name', '')
            sku = h.get('sku', '')
            url_field = h.get('url', '')
            # Print ALL keys
            print(f"\n  Product: {name[:40]}")
            print(f"  SKU: {sku}")
            print(f"  url: {url_field}")
            # Check all keys that might have URL info
            for k, v in h.items():
                if isinstance(v, str) and ('http' in v or '/' in v) and k not in ('url', 'image_url', 'thumbnail_url', 'redbox_pl_custom_image_url'):
                    print(f"  {k}: {v[:80]}")
        break
    break
