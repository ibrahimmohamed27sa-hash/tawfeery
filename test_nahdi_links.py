from app import scrape_nahdi
results = scrape_nahdi('panadol')
print(f'Found {len(results)} results')
for r in results[:5]:
    name = r["name"]
    link = r["link"]
    print(f'  Name: {name[:50]}')
    print(f'  Link: {link}')
    print()
