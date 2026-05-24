import requests
import json

url = 'https://stgprevapi.al-dawaa.com/occ/v2/aldawaa/products/search'
params = {
    'query': 'babyjoy',
    'pageSize': 5,
    'lang': 'ar',
    'curr': 'SAR',
    'fields': 'FULL'  # Request all fields
}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}
res = requests.get(url, params=params, headers=headers, timeout=20)
data = res.json()
products = data.get('products', [])
print(f"Found {len(products)} products")

for p in products[:3]:
    name = p.get('name', '')
    print(f"\n=== {name[:60]} ===")
    # Print ALL price-related fields
    for k, v in p.items():
        if 'price' in k.lower() or 'discount' in k.lower() or 'promo' in k.lower() or 'promot' in k.lower():
            print(f"  {k}: {json.dumps(v, ensure_ascii=False)[:200]}")
    
    # Also print potentialPromotions full structure
    if 'potentialPromotions' in p:
        print(f"  potentialPromotions FULL: {json.dumps(p['potentialPromotions'], ensure_ascii=False)[:500]}")
