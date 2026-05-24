import sys
sys.path.insert(0, '.')
from app import scrape_nahdi, scrape_aldawaa

print("=== TESTING NAHDI LINKS ===")
n = scrape_nahdi('panadol')
print(f"Found {len(n)} results")
for r in n[:3]:
    print(f"  Name: {r['name'][:50]}")
    print(f"  Link: {r['link']}")
    print()

print()
print("=== TESTING AL-DAWAA PRICES ===")
d = scrape_aldawaa('babyjoy pants jumbo')
print(f"Found {len(d)} results")
for r in d[:5]:
    print(f"  Name: {r['name'][:50]}")
    print(f"  Price (final): SAR {r['price']}")
    print(f"  Offer: {r['offer'] or 'None'}")
    print()
