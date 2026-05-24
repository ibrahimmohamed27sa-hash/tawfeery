import requests
import json

url = 'https://stgprevapi.al-dawaa.com/occ/v2/aldawaa/products/search'
params = {
    'query': 'babyjoy pants jumbo',
    'pageSize': 5,
    'lang': 'ar',
    'curr': 'SAR',
    'fields': 'FULL'
}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
}
res = requests.get(url, params=params, headers=headers, timeout=20)
data = res.json()
products = data.get('products', [])

for p in products[:5]:
    name = p.get('name', '')
    price = p.get('price', {}).get('value', 0)
    sim_price = p.get('simulatedDiscountPrice', {})
    sim_val = sim_price.get('value') if sim_price else None
    promos = p.get('potentialPromotions', [])
    print(f"Product: {name[:55]}")
    print(f"  price.value (original): {price}")
    print(f"  simulatedDiscountPrice: {sim_val}")
    print(f"  Saving: {round(price - sim_val, 2) if sim_val else 'N/A'}")
    print(f"  potentialPromotions codes: {[p2.get('code','') for p2 in promos]}")
    print()
