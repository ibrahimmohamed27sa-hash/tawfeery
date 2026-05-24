import requests
from bs4 import BeautifulSoup
import urllib.parse

query = 'panadol'
url = f'https://www.al-dawaa.com/ar/search/{urllib.parse.quote(query)}'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Upgrade-Insecure-Requests': '1'
}

r = requests.get(url, headers=headers)
print("Status:", r.status_code)

soup = BeautifulSoup(r.text, 'html.parser')
products = soup.select('cx-product-grid-item')
print(f"Found {len(products)} products")

for p in products[:3]:
    name_elem = p.select_one('.product-name, .name, a.cx-product-name')
    price_elem = p.select_one('.price-section, .price, div.price')
    img_elem = p.select_one('cx-media img, img')
    link_elem = p.select_one('a[href]')
    
    name = name_elem.text.strip() if name_elem else 'No name'
    price = price_elem.text.strip() if price_elem else 'No price'
    img = img_elem.get('src') if img_elem else 'No image'
    link = link_elem.get('href') if link_elem else 'No link'
    print(f"Name: {name}, Price: {price}, Img: {img}, Link: {link}")

