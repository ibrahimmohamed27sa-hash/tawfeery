import requests

# Test search and alternative URL formats
test_urls = [
    # Search for that specific product
    "https://www.nahdionline.com/ar-sa/search?query=panadol",
    # Old format that might still work
    "https://www.nahdionline.com/ar-sa/panadol-extra-tablet-24-pcs",
    # Using catalog URL pattern
    "https://www.nahdionline.com/ar-sa/catalog/product/view/id/100015980",
    # try en-sa locale
    "https://www.nahdionline.com/en-sa/panadol-extra-tablet-24-pcs/pdp/100015980",
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

for url in test_urls:
    try:
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        print(f"URL: {url}")
        print(f"  Status: {r.status_code} | Final: {r.url}")
        print(f"  Has product/error: {'__next_error__' in r.text[:500]} | {'product' in r.text[:3000].lower()}")
        print()
    except Exception as e:
        print(f"URL: {url} -> ERROR: {e}\n")
