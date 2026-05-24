import sys
import json
import urllib.parse
from playwright.sync_api import sync_playwright

def scrape_nahdi(query):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ar-SA"
        )
        page = ctx.new_page()
        url = f"https://www.nahdionline.com/ar-sa/search?query={urllib.parse.quote(query)}"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(4000)
        page.evaluate("window.scrollTo(0, 600)")
        page.wait_for_timeout(2000)
        page.screenshot(path=f"screenshot_{store}.png")

        items = page.locator('div[class*="product"]').all()
        seen_links = set()
        for item in items:
            try:
                link_loc = item.locator('a[href*="/pdp/"]')
                if link_loc.count() == 0:
                    continue
                link = link_loc.first.get_attribute('href') or ''
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                if not link.startswith('http'):
                    link = 'https://www.nahdionline.com' + link

                name_loc = item.locator('p, h2, h3, span[class*="name"], span[class*="title"]')
                name = ''
                for i in range(name_loc.count()):
                    txt = name_loc.nth(i).inner_text(timeout=2000).strip()
                    if len(txt) > 5:
                        name = txt
                        break
                if not name:
                    continue

                price_loc = item.locator('[class*="price"], [class*="Price"]')
                price_text = ''
                for i in range(price_loc.count()):
                    txt = price_loc.nth(i).inner_text(timeout=2000).strip()
                    digits = ''.join(c for c in txt if c.isdigit() or c == '.')
                    if digits and float(digits) > 0:
                        price_text = digits
                        break
                if not price_text:
                    continue

                img_loc = item.locator('img')
                img_url = ''
                if img_loc.count() > 0:
                    img_url = (img_loc.first.get_attribute('data-src') or img_loc.first.get_attribute('src') or '')

                results.append({
                    'store': 'Nahdi Online',
                    'name': name,
                    'price': float(price_text),
                    'image': img_url,
                    'link': link
                })
                if len(results) >= 20:
                    break
            except Exception:
                continue
        browser.close()
    return results

def scrape_aldawaa(query):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="ar-SA"
        )
        page = ctx.new_page()
        url = f"https://www.al-dawaa.com/ar/search/{urllib.parse.quote(query)}"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector('cx-product-grid-item', timeout=12000)
        except Exception:
            pass
        page.screenshot(path=f"screenshot_{store}.png")

        items = page.locator('cx-product-grid-item').all()
        for item in items[:20]:
            try:
                name_loc = item.locator('.name, a.cx-product-name, h3, a[href*="/p/"]').first
                price_loc = item.locator('.price, div.price').first

                if name_loc.count() == 0 or price_loc.count() == 0:
                    continue

                name = name_loc.inner_text(timeout=3000).strip()
                price_text = price_loc.inner_text(timeout=3000).strip()
                trans = str.maketrans('٠١٢٣٤٥٦٧٨٩٫', '0123456789.')
                price_text = price_text.translate(trans)
                price = ''.join(c for c in price_text if c.isdigit() or c == '.')
                if not price:
                    continue

                img_loc = item.locator('img').first
                img_url = ''
                if img_loc.count() > 0:
                    img_url = (img_loc.get_attribute('data-src') or img_loc.get_attribute('src') or '')
                if img_url and not img_url.startswith('http'):
                    img_url = 'https://www.al-dawaa.com' + img_url

                link_loc = item.locator('a[href]').first
                link = link_loc.get_attribute('href') if link_loc.count() > 0 else url
                if link and not link.startswith('http'):
                    link = 'https://www.al-dawaa.com' + link

                results.append({
                    'store': 'Al-Dawaa',
                    'name': name,
                    'price': float(price),
                    'image': img_url,
                    'link': link
                })
            except Exception:
                continue
        browser.close()
    return results

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(1)
    
    store = sys.argv[1]
    query = sys.argv[2]
    
    if store == 'nahdi':
        data = scrape_nahdi(query)
    elif store == 'aldawaa':
        data = scrape_aldawaa(query)
    else:
        data = []
        
    print(json.dumps(data))
