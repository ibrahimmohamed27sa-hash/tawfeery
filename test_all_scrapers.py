import sys
sys.path.insert(0, '.')
from app import scrape_united, scrape_nahdi, scrape_aldawaa

query = 'panadol'

print('=== UNITED PHARMACY ===')
u = scrape_united(query)
print(f'Found: {len(u)} results')
if u:
    item = u[0]
    print(f'  Name: {item["name"][:60]}')
    print(f'  Price: SAR {item["price"]}')
    print(f'  Image: {item["image"][:60] if item["image"] else "N/A"}')
    print(f'  Offer: {item["offer"] or "None"}')

print()
print('=== AL-DAWAA ===')
d = scrape_aldawaa(query)
print(f'Found: {len(d)} results')
if d:
    item = d[0]
    print(f'  Name: {item["name"][:60]}')
    print(f'  Price: SAR {item["price"]}')
    print(f'  Image: {item["image"][:60] if item["image"] else "N/A"}')
    print(f'  Offer: {item["offer"] or "None"}')

print()
print('=== NAHDI ONLINE ===')
n = scrape_nahdi(query)
print(f'Found: {len(n)} results')
if n:
    item = n[0]
    print(f'  Name: {item["name"][:60]}')
    print(f'  Price: SAR {item["price"]}')
    print(f'  Image: {item["image"][:60] if item["image"] else "N/A"}')
    print(f'  Offer: {item["offer"] or "None"}')

print()
print('=== SUMMARY ===')
total = len(u) + len(d) + len(n)
print(f'Total results: {total}')
print(f'United: {len(u)} | Al-Dawaa: {len(d)} | Nahdi: {len(n)}')
