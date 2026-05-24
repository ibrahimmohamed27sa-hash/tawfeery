import requests

# Test different URL formats for Nahdi product pages
test_urls = [
    # Current format we're generating
    "https://www.nahdionline.com/ar-sa/panadol-extra-tablet-24-pcs/pdp/100015980",
    # Without /pdp/
    "https://www.nahdionline.com/ar-sa/panadol-extra-tablet-24-pcs/100015980",
    # Direct SKU URL
    "https://www.nahdionline.com/ar-sa/pdp/100015980",
    # Product page format  
    "https://www.nahdionline.com/ar-sa/p/100015980",
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
}

for url in test_urls:
    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        ct = r.headers.get('content-type', '')
        final_url = r.url
        # Check if HTML has product info
        has_product = 'product' in r.text[:2000].lower() or 'panadol' in r.text[:2000].lower()
        is_json = r.text.strip().startswith('[') or r.text.strip().startswith('{')
        print(f"URL: {url}")
        print(f"  Status: {r.status_code}")
        print(f"  Final URL: {final_url}")
        print(f"  Content-Type: {ct[:60]}")
        print(f"  Is JSON: {is_json}")
        print(f"  Has product info: {has_product}")
        print(f"  First 200 chars: {r.text[:200]!r}")
        print()
    except Exception as e:
        print(f"URL: {url} -> ERROR: {e}")
        print()
