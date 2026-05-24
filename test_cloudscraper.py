import cloudscraper
from bs4 import BeautifulSoup
import re
import json

scraper = cloudscraper.create_scraper()
res = scraper.get('https://www.nahdionline.com/ar-sa/search?query=panadol')
soup = BeautifulSoup(res.text, 'html.parser')

for s in soup.find_all('script'):
    if s.string and 'InstantSearchInitialResults' in s.string:
        raw = s.string
        # Find the marker position and grab from there
        marker = 'window[Symbol.for("InstantSearchInitialResults")] = '
        idx = raw.find(marker)
        if idx == -1:
            continue
        json_str = raw[idx + len(marker):]
        # Remove trailing ; and anything after the balanced braces
        # Use a counter to find the end of the JSON object
        depth = 0
        end = 0
        for i, c in enumerate(json_str):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        json_str = json_str[:end]
        data = json.loads(json_str)
        
        # The index key might vary - search for any key with 'hits'
        for key, val in data.items():
            results_list = val.get('results', [])
            if results_list:
                hits = results_list[0].get('hits', [])
                print(f'Key: {key}, Hits: {len(hits)}')
                for h in hits[:3]:
                    name = h.get('name', '')
                    price = None
                    p = h.get('price', {})
                    if isinstance(p, dict):
                        price = p.get('SAR', {}).get('default')
                    img = h.get('image_url', '') or h.get('thumbnail_url', '')
                    url = h.get('url', '')
                    print(f'  Name: {name}')
                    print(f'  Price: {price}')
                    print(f'  Image: {img}')
                    print(f'  URL: {url}')
