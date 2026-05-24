from playwright.sync_api import sync_playwright
import urllib.parse, json

query = 'panadol'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        locale="ar-SA"
    )
    page = ctx.new_page()
    url = f"https://www.nahdionline.com/ar-sa/search?query={urllib.parse.quote(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=35000)
    # Scroll to trigger lazy-loading
    page.wait_for_timeout(3000)
    page.evaluate("window.scrollTo(0, 500)")
    page.wait_for_timeout(2000)

    # Try every possible product selector
    selectors_to_try = [
        '.product-item', '.grid-item', '.product-card',
        '[data-testid="product-card"]', '[data-testid="product-item"]',
        'article', 'li[class*="product"]', 'div[class*="product"]',
        'a[href*="/pdp/"]', '[class*="ProductCard"]', '[class*="productCard"]',
    ]
    with open("nahdi_debug.txt", "w", encoding="utf-8") as f:
        f.write(f"Page title: {page.title()}\n")
        f.write(f"URL: {page.url}\n\n")
        for sel in selectors_to_try:
            count = page.locator(sel).count()
            f.write(f"  {sel}: {count}\n")
        
        # Dump first product link href to understand URL structure
        links = page.locator('a[href*="/pdp/"]').all()
        f.write(f"\nFound {len(links)} pdp links\n")
        for l in links[:3]:
            try:
                f.write(f"  Link: {l.get_attribute('href')}\n")
                f.write(f"  Text: {l.inner_text()[:80]}\n\n")
            except: pass
        
        # Get first 500 chars of body to understand structure
        f.write("\n--- Body snippet (first 3000 chars) ---\n")
        body = page.locator('main, #__next, body').first.inner_html()
        f.write(body[:3000])
    
    browser.close()

print("Done! Check nahdi_debug.txt")
