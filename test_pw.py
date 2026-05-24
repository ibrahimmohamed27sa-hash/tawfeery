from playwright.sync_api import sync_playwright
import urllib.parse
import time

query = 'panadol'

def test_nahdi():
    print("Testing Nahdi...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(f"https://www.nahdionline.com/ar-sa/search?query={urllib.parse.quote(query)}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector('.product-item', timeout=15000)
            items = page.locator('.product-item').all()
            print(f"Nahdi Found {len(items)} items")
            for item in items[:2]:
                print(item.inner_text())
        except Exception as e:
            print(f"Nahdi Error: {e}")
        finally:
            browser.close()

def test_aldawaa():
    print("\nTesting Al-Dawaa...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto(f"https://www.al-dawaa.com/ar/search/{urllib.parse.quote(query)}", wait_until="domcontentloaded", timeout=30000)
            # SAP Commerce uses cx-product-grid-item or .product-item
            try:
                page.wait_for_selector('cx-product-grid-item, .product-item', timeout=15000)
            except:
                print("Selector wait timeout. Checking page content...")
                print(page.title())
            
            items = page.locator('cx-product-grid-item').all()
            if not items:
                items = page.locator('.product-item').all()
            
            print(f"Al-Dawaa Found {len(items)} items")
            for item in items[:2]:
                print(item.inner_text()[:100])
        except Exception as e:
            print(f"Al-Dawaa Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_nahdi()
    test_aldawaa()
