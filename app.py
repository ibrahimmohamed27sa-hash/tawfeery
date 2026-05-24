from flask import Flask, render_template, request, Response, stream_with_context
import requests
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import concurrent.futures
import json
import re

app = Flask(__name__)


# ── United Pharmacy via Algolia JSON API ──────────────────────────────────────

def scrape_united(query):
    results = []
    try:
        headers = {
            'X-Algolia-API-Key': 'NGFkYzM5MDgzYjA0YmI2YzdlYjk4YjIwNDFjZjQzZTg2ZDQ4M2Q0ZGM5ZTVjYTgxYTNjZWRlMjllZDg0YTg3Y3RhZ0ZpbHRlcnM9',
            'X-Algolia-Application-Id': 'Y1GOQ9DTV8'
        }
        url = 'https://Y1GOQ9DTV8-dsn.algolia.net/1/indexes/*/queries'
        payload = {
            "requests": [{
                "indexName": "unitedpharmacy_livear_products",
                "params": f"query={urllib.parse.quote(query)}&hitsPerPage=50"
            }]
        }
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            hits = res.json().get('results', [{}])[0].get('hits', [])
            for h in hits:
                name = h.get('name', '')
                price_val = h.get('price', 0)
                if isinstance(price_val, dict):
                    price_val = price_val.get('SAR', {}).get('default', 0)
                elif isinstance(price_val, list):
                    price_val = price_val[0] if price_val else 0
                img_url = h.get('image_url') or h.get('thumbnail_url', '')
                link = h.get('url', '')
                if price_val and name:
                    try:
                        offer_text = ''
                        if h.get('isOfferApplicable'):
                            offer_text = h.get('offerApplicableLabel', '')
                        
                        results.append({
                            'store': 'United Pharmacy',
                            'name': name,
                            'price': float(price_val),
                            'image': img_url,
                            'link': link,
                            'offer': offer_text
                        })
                    except Exception:
                        pass
    except Exception as e:
        print(f"United error: {e}")
    return results


# ── Nahdi via Cloudscraper + Embedded JSON ────────────────────────────────────

def scrape_nahdi(query):
    """
    Nahdi embeds Algolia search results directly in the page HTML as:
    window[Symbol.for("InstantSearchInitialResults")] = {...}
    We extract and parse this JSON without needing a headless browser.
    """
    results = []
    try:
        scraper = cloudscraper.create_scraper()
        url = f"https://www.nahdionline.com/ar-sa/search?query={urllib.parse.quote(query)}"
        res = scraper.get(url, timeout=20)
        if res.status_code != 200:
            print(f"Nahdi HTTP error: {res.status_code}")
            return results

        soup = BeautifulSoup(res.text, 'html.parser')
        marker = 'window[Symbol.for("InstantSearchInitialResults")] = '

        for script in soup.find_all('script'):
            if not script.string or marker not in script.string:
                continue

            raw = script.string
            idx = raw.find(marker)
            if idx == -1:
                continue

            json_str = raw[idx + len(marker):]
            # Find balanced braces to extract valid JSON
            depth, end = 0, 0
            for i, c in enumerate(json_str):
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if not end:
                continue

            data = json.loads(json_str[:end])

            # The key may vary — find whichever has hits
            for key, val in data.items():
                results_list = val.get('results', [])
                if not results_list:
                    continue
                hits = results_list[0].get('hits', [])
                for h in hits[:50]:
                    name = h.get('name', '')
                    price_val = h.get('price', {})
                    if isinstance(price_val, dict):
                        price_val = price_val.get('SAR', {}).get('default', 0)
                    img_url = h.get('image_url') or h.get('thumbnail_url', '')
                    link = h.get('url', '')
                    sku = h.get('sku', '')
                    # Nahdi product pages (/pdp/{sku}) return HTTP 500 for many products
                    # (Next.js SSR bug on their end). Search URL is 100% reliable.
                    search_q = urllib.parse.quote(name) if name else (sku or '')
                    link = f"https://www.nahdionline.com/ar-sa/search?query={search_q}"

                    if name and price_val:
                        try:
                            offer_text = ''
                            if h.get('item_has_offer') == 'Yes':
                                promo = h.get('promo_type', '')
                                if promo:
                                    if "Buy 2  For" in promo:
                                        price = promo.replace("Buy 2  For", "").replace("SAR", "").strip()
                                        offer_text = f"اشتري 2 بسعر {price} ريال"
                                    elif "1 + 1 with 50 %" in promo:
                                        offer_text = "خصم 50% على الحبة الثانية"
                                    elif "2 + 1" in promo:
                                        offer_text = "اشتري 2 واحصل على 1 مجاناً"
                                    elif "1 + 1" in promo:
                                        offer_text = "اشتري 1 واحصل على 1 مجاناً"
                                    else:
                                        offer_text = promo

                            results.append({
                                'store': 'Nahdi Online',
                                'name': name,
                                'price': float(price_val),
                                'image': img_url,
                                'link': link,
                                'offer': offer_text
                            })
                        except Exception:
                            pass
            break  # Only process the first matching script
    except Exception as e:
        print(f"Nahdi error: {e}")
    return results


# ── Al-Dawaa via OCC REST API ─────────────────────────────────────────────────

def scrape_aldawaa(query):
    results = []
    try:
        url = 'https://stgprevapi.al-dawaa.com/occ/v2/aldawaa/products/search'
        params = {
            'query': query,
            'pageSize': 50,
            'lang': 'ar',
            'curr': 'SAR'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
            'Connection': 'keep-alive'
        }
        res = requests.get(url, params=params, headers=headers, timeout=20)
        if res.status_code != 200:
            print(f"Al-Dawaa OCC HTTP error: {res.status_code}")
            return results

        data = res.json()
        products = data.get('products', [])

        for p in products:
            name = p.get('name', '')
            if not name:
                continue

            # ── Price: always use price.value as the displayed (in-store) price
            original_price = p.get('price', {}).get('value')
            if original_price is None:
                continue

            price_val = original_price

            # simulatedDiscountPrice is the delivery-only discounted price
            # We show it as an informational offer, NOT as the main price
            simulated = p.get('simulatedDiscountPrice', {})
            sim_val = simulated.get('value') if simulated else None
            delivery_discount_text = ''
            if sim_val and sim_val < original_price:
                saving = round(original_price - sim_val, 2)
                delivery_discount_text = f"سعر التوصيل: {sim_val:.2f} ريال (وفّر {saving:.2f} ريال)"

            # Image processing
            img_url = ''
            image_urls = p.get('imageUrl', [])
            if isinstance(image_urls, list) and len(image_urls) > 0:
                ar_img = next((img.get('value') for img in image_urls if img.get('key') == 'ar'), None)
                if ar_img:
                    img_url = ar_img
                else:
                    img_url = image_urls[0].get('value', '')

            if img_url and img_url.startswith('/'):
                img_url = 'https://stgprevapi.al-dawaa.com' + img_url

            # Product link
            link = p.get('url', '')
            if link and not link.startswith('http'):
                link = 'https://www.al-dawaa.com' + link

            try:
                # Build offer text from promotions
                promo_text = ''
                potential = p.get('potentialPromotions', [])
                if isinstance(potential, list) and len(potential) > 0:
                    promo_code = potential[0].get('code', '').strip()
                    # Only show promo code if it's meaningful (not just "توصيل فقط" type)
                    if promo_code and 'توصيل' not in promo_code:
                        promo_text = promo_code

                # Combine promo text + delivery discount info
                if promo_text and delivery_discount_text:
                    offer_text = f"{promo_text} | {delivery_discount_text}"
                elif promo_text:
                    offer_text = promo_text
                elif delivery_discount_text:
                    offer_text = delivery_discount_text
                else:
                    offer_text = ''

                results.append({
                    'store': 'Al-Dawaa',
                    'name': name,
                    'price': float(price_val),
                    'image': img_url,
                    'link': link,
                    'offer': offer_text
                })
            except Exception:
                pass
    except Exception as e:
        print(f"Al-Dawaa error: {e}")
    return results


# ── Flask Routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/search')
def search():
    """Server-Sent Events endpoint — streams results per-pharmacy as they complete."""
    query = request.args.get('q', '').strip()
    if not query:
        return Response("data: DONE\n\n", mimetype='text/event-stream')

    def generate():
        scrapers = [
            ('United Pharmacy', scrape_united),
            ('Nahdi Online',    scrape_nahdi),
            ('Al-Dawaa',        scrape_aldawaa),
        ]

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(fn, query): name
                    for name, fn in scrapers
                }

                for future in concurrent.futures.as_completed(futures, timeout=35):
                    store_name = futures[future]
                    try:
                        results = future.result(timeout=30)
                        payload = json.dumps(
                            {'store': store_name, 'results': results},
                            ensure_ascii=False
                        )
                        yield f"data: {payload}\n\n"
                    except concurrent.futures.TimeoutError:
                        print(f"Timeout [{store_name}]")
                        yield f"data: {json.dumps({'store': store_name, 'results': [], 'error': 'timeout'})}\n\n"
                    except Exception as e:
                        print(f"Future error [{store_name}]: {e}")
                        yield f"data: {json.dumps({'store': store_name, 'results': [], 'error': str(e)})}\n\n"
        except concurrent.futures.TimeoutError:
            print("Overall executor timeout")
        except Exception as e:
            print(f"Generator error: {e}")

        yield "data: DONE\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*'
        }
    )


# ── Best Deals / Featured Endpoint ────────────────────────────────────────────

POPULAR_QUERIES = [
    # مسكنات وخافضات حرارة
    'Panadol', 'بنادول', 'فيفادول', 'ادفيل', 'بروفين',
    'نوروفين', 'سولبادين', 'دولوبران', 'البرازولام',
    'بنادول نايت', 'بنادول اكسترا', 'الريلين',
    'كيتولاك', 'ديكلوفيناك', 'naproxen',
    # مضادات حيوية
    'اموكسيسيلين', 'اوجمنتين', 'ازيثرومايسين',
    'سيفالكسين', 'كلاريثروميسين', 'ميترونيدازول',
    # حساسية
    'كلاريتين', 'سيتريزين', 'لوراتادين', 'فيكسوفينادين',
    'زيرتيك', 'زاديتن', 'تيليفاست',
    # جهاز هضمي
    'جافيسكون', 'اوميبرازول', 'بانتوبرازول', 'اسوميبرازول',
    'موتيليوم', 'ميتوكلوبراميد', 'لانسوبرازول',
    # فيتامينات ومكملات
    'فيتامين د', 'فيتامين سي', 'فيتامين ب12', 'اوميغا 3',
    'سنتروم', 'سوبرادين', 'بيوكال', 'كالسيوم', 'حديد',
    'مغنيسيوم', 'زنك', 'فيتامين e',
    # برد وانفلونزا
    'كونجستيل', 'داي', 'فلوتاب', 'بانادول كولد',
    'ستوب كوف', 'بروسبان', 'توسيفان',
    # جهاز تنفسي
    'فينتولين', 'سيريتايد', 'بلميكورت', 'اوكسيس',
    'سنقولاير', 'مونتيلوكاست',
    # جلدية
    'كلوتريمازول', 'ميكونازول', 'فيوسيدين', 'بيتاديرم',
    'اكرتين', 'ادابالين',
    # سكري
    'ميتفورمين', 'جلوكوفاج', 'دياميكرون', 'جمبيدي',
    'لانتوس', 'نوفورابيد',
    # ضغط وقلب
    'املوديبين', 'ليسينوبريل', 'اتورفاستاتين',
    'كارديوبايرين', 'اسبرين', 'ميتوبرولول',
    # عروض خاصة
    'عرض', 'تخفيضات', 'خصم', 'sale',
    'best price', 'offer',
]
_deals_cache = None
_deals_cache_time = 0

@app.route('/api/deals')
def deals():
    """Returns a curated list of best deals across all pharmacies."""
    import time
    global _deals_cache, _deals_cache_time

    now = time.time()
    if _deals_cache and (now - _deals_cache_time) < 300:  # 5 min cache
        return Response(json.dumps(_deals_cache, ensure_ascii=False), mimetype='application/json')

    all_items = []
    seen_links = set()

    def run_popular(query):
        items = []
        for scraper_fn in (scrape_united, scrape_nahdi, scrape_aldawaa):
            try:
                results = scraper_fn(query)
                items.extend(results)
            except Exception:
                continue
        return items

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(run_popular, q): q for q in POPULAR_QUERIES}
        for f in concurrent.futures.as_completed(futures, timeout=90):
            try:
                items = f.result(timeout=80)
                for item in items:
                    if item['link'] not in seen_links:
                        seen_links.add(item['link'])
                        all_items.append(item)
            except Exception:
                continue

    # Separate items with offers vs without
    offer_items = []
    regular_items = []
    seen_offer_names = set()
    seen_regular_names = set()

    for item in all_items:
        key = item['name'].split(' ')[0].lower().replace('ـ', '')
        has_offer = bool(item.get('offer'))
        if has_offer:
            if key not in seen_offer_names:
                seen_offer_names.add(key)
                offer_items.append(item)
        else:
            if key not in seen_regular_names:
                seen_regular_names.add(key)
                regular_items.append(item)

    # Sort offers: best discount value first (price descending = bigger saving potential)
    offer_items.sort(key=lambda x: x['price'], reverse=True)

    # Sort regular: cheapest first
    regular_items.sort(key=lambda x: x['price'])

    # Final list: all offers + regular items
    deals_list = offer_items[:100]
    for ri in regular_items:
        if len(deals_list) >= 200:
            break
        deals_list.append(ri)

    _deals_cache = deals_list
    _deals_cache_time = time.time()

    return Response(json.dumps(deals_list, ensure_ascii=False), mimetype='application/json')


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True, use_reloader=False)
