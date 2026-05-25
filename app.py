from flask import Flask, render_template, request, Response, stream_with_context
import requests
import cloudscraper
from bs4 import BeautifulSoup
import urllib.parse
import concurrent.futures
import json
import re
import math
import threading
import cache
import time
import os
import secrets

app = Flask(__name__)

# ── Security: CSP & Headers ──────────────────────────────────────────────────
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.path.startswith('/api/') or request.path == '/':
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
    return response

# ── Input Sanitization ────────────────────────────────────────────────────────
def sanitize_query(q):
    if not q:
        return ''
    q = q.strip()[:100]  # max 100 chars
    # Allow Arabic/English letters, digits, spaces, common pharmacy terms
    q = re.sub(r'[^\w\s\-أ-يإآةؤئىء]+', '', q)
    return q.strip()

# Rate limiting: max 20 search requests per minute per IP, 10 deals fetches per minute
def check_rate(ip, endpoint, limit, window=60):
    allowed = cache.check_rate_limit(ip, endpoint, limit, window)
    if not allowed:
        return False
    return True

def client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()


# ── Quantity Extraction & Unit Price Normalization ───────────────────────────

def extract_quantity(name):
    """Extract item count from a product name (e.g. 'عدد 30', '30 حبة', '30 Tablets')."""
    if not name:
        return None
    text = name.replace('ـ', '').replace(',', '').strip()

    # Patterns: عدد 30, quantity 30, 30's, 30+1
    patterns = [
        # Arabic: عدد 30
        r'عدد\s*(\d+)',
        # Arabic: 30 حبة, 30 حبّة, 30 قرص, 30 كبسولة, 30 كبسولة, 30 حفاض, 30 حفاضة, 30 قطعة
        r'(\d+)\s*(حبة|حبّة|حبات|قرص|اقراص|كبسولة|كبسولات|حفاض|حفاضة|حفائض|قطعة|قطعه|قطع|شريط|شرائط|ملعقة|ملىء|حقنة|امبول|امبولات|لبوس|تحميلة)',
        # English: 30 Tablets, 30 Capsules, 30 Pills, 30 Diapers, 30 Pieces, 30's
        r'(\d+)\s*(Tablets?|Capsules?|Pills?|Diapers?|Pieces?|Count|Pack|Tabs?|Caps?|Pcs|ML|Mg|G|KG)',
        # Pack of 30
        r'(?:Pack|pack|عبوة|علبة)\s*(?:of|OF|)\s*(\d+)',
        # 30+1, 30+1 Free
        r'(\d+)\s*\+\s*\d+',
        # 30x, 30 X (but NOT مقاس 3 / Size 3)
        r'(\d+)\s*[xX×](?!\s*مقاس|\s*Size)',
        # 30's, 30ct
        r'(\d+)[\'\u2019]?[sS]\b',
        r'(\d+)\s*[cC][tT]\b',
    ]

    # Skip if it's a size pattern (مقاس 3, Size 3, مقاس كبير, etc.)
    if re.search(r'(مقاس|size|large|medium|small|كبير|وسط|صغير)', text, re.I):
        # Still try to extract if there's a clear count AND size mention
        pass

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            val = int(m.group(1))
            if 1 < val <= 500:  # Sanity check
                return val
    return None


def compute_unit_price(price, quantity):
    """Return unit price (price per item) if quantity is valid, else None."""
    if quantity and quantity > 0:
        return round(price / quantity, 4)
    return None


def enrich_item(item, raw_hit=None):
    """Add quantity and unit_price fields to a scraper result.
    If raw_hit is provided, check for additional price/promo fields."""
    # Quantity: try raw hit's quantity field first (e.g. Nahdi's "24 حبة")
    qty = item.get('quantity')
    if not qty and raw_hit:
        raw_qty = raw_hit.get('quantity') if isinstance(raw_hit, dict) else None
        if raw_qty:
            # "24 حبة" -> 24  or  "30 حفاض" -> 30
            import re as _re
            m = _re.search(r'(\d+)', str(raw_qty))
            if m:
                qty = int(m.group(1))
    if not qty:
        qty = extract_quantity(item.get('name', ''))
    item['quantity'] = qty

    # Unit price
    if 'unit_price' not in item or not item['unit_price']:
        item['unit_price'] = compute_unit_price(item['price'], item['quantity'])

    # Check for special/offer price from raw hit (only if scraper found NO offer)
    if raw_hit and isinstance(raw_hit, dict) and not item.get('offer'):
        # Discount percentage (e.g. خصم 21%)
        discount_pct = raw_hit.get('discount', 0)
        if discount_pct and discount_pct < 100:
            item['offer'] = f"خصم {discount_pct}%"
        # Clearance
        elif raw_hit.get('clearance_offer') == 'Yes':
            item['offer'] = 'تخفيضات التصفية'

    return item


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
                        
                        sku = h.get('objectID') or h.get('sku') or ''
                        item = {
                            'store': 'United Pharmacy',
                            'name': name,
                            'price': float(price_val),
                            'image': img_url,
                            'link': link,
                            'offer': offer_text,
                            'sku': sku,
                        }
                        enrich_item(item, raw_hit=h)
                        results.append(item)
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
                    price_val = h.get('price', 0)
                    if isinstance(price_val, dict):
                        sar = price_val.get('SAR', {})
                        price_val = sar.get('default', 0)
                        # Check for active special price
                        sp = sar.get('special_price')
                        if sp and sar.get('special_from_date') and sar.get('special_to_date'):
                            price_val = sp
                    elif not isinstance(price_val, (int, float)):
                        price_val = 0
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
                            # Detect offers from multiple fields
                            if h.get('item_has_offer') == 'Yes' or h.get('isOfferApplicable') or h.get('promo_type'):
                                promo = h.get('promo_type') or h.get('offer_text') or h.get('offerApplicableLabel', '')
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
                                    elif re.search(r'\d+', promo):
                                        offer_text = promo

                            sku = h.get('sku', '')
                            item = {
                                'store': 'Nahdi Online',
                                'name': name,
                                'price': float(price_val),
                                'image': img_url,
                                'link': link,
                                'offer': offer_text,
                                'sku': sku,
                            }
                            enrich_item(item, raw_hit=h)
                            results.append(item)
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
                # Build offer text from promotions (multiple sources)
                promo_text = ''
                potential = p.get('potentialPromotions', [])
                if isinstance(potential, list) and len(potential) > 0:
                    promo_code = potential[0].get('code', '').strip()
                    if promo_code and 'توصيل' not in promo_code:
                        promo_text = promo_code

                # Check other promotion fields
                if not promo_text:
                    desc = p.get('promotionalDescriptions') or p.get('productPromotions') or p.get('promotionDescription') or ''
                    if isinstance(desc, list):
                        desc = ' '.join(str(d) for d in desc)
                    if isinstance(desc, str) and desc.strip():
                        desc = desc.strip()[:100]
                        # Only accept as offer if it looks like a real promotion
                        if any(k in desc.lower() for k in ['%', 'خصم', 'وفر', 'ريال', 'مجان', '1+', '2+', '+1', 'اشتر', 'سعر']):
                            promo_text = desc

                # Check volume pricing / bulk buy
                volume = p.get('volumePrices', [])
                if isinstance(volume, list) and len(volume) > 0 and not promo_text:
                    vp = volume[0]
                    vp_price = vp.get('price', {}).get('value') if isinstance(vp.get('price'), dict) else vp.get('value')
                    vp_qty = vp.get('minimumQuantity', 2)
                    if vp_price and vp_price < price_val:
                        promo_text = f"سعر الكمية: اشتر {vp_qty}+ بسعر {vp_price:.2f} ريال للقطعة"

                # Combine promo text + delivery discount info
                if promo_text and delivery_discount_text:
                    offer_text = f"{promo_text} | {delivery_discount_text}"
                elif promo_text:
                    offer_text = promo_text
                elif delivery_discount_text:
                    offer_text = delivery_discount_text
                else:
                    offer_text = ''

                sku = p.get('code', '')
                item = {
                    'store': 'Al-Dawaa',
                    'name': name,
                    'price': float(price_val),
                    'image': img_url,
                    'link': link,
                    'offer': offer_text,
                    'sku': sku,
                }
                enrich_item(item, raw_hit=p)
                results.append(item)
            except Exception:
                pass
    except Exception as e:
        print(f"Al-Dawaa error: {e}")
    return results


# ── Flask Routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    cache.track_visit(client_ip(), 'home', user_agent=request.headers.get('User-Agent', ''), referrer=request.headers.get('Referer', ''))
    deals_data = cache.get_deals_cache()
    deals = deals_data[0] if deals_data and deals_data[0] else []
    search_query = sanitize_query(request.args.get('q', ''))
    search_results = {}
    if search_query:
        for store in ['Nahdi Online', 'United Pharmacy', 'Al-Dawaa']:
            cached = cache.get_search_cache(search_query, store, max_age=600)
            if cached is not None:
                search_results[store] = cached
    return render_template('index.html', deals=deals, search_query=search_query, search_results=search_results)


@app.route('/api/search')
def search():
    query = sanitize_query(request.args.get('q', ''))
    if not query:
        return Response("data: DONE\n\n", mimetype='text/event-stream')

    # Track search
    cache.track_visit(client_ip(), 'search', query=query, user_agent=request.headers.get('User-Agent', ''))

    # Rate limiting
    ip = client_ip()
    if not check_rate(ip, 'search', 20, 60):
        return Response("data: " + json.dumps({'error': 'rate_limit', 'message': 'طلبات كثيرة جداً. انتظر دقيقة.'}) + "\n\ndata: DONE\n\n", mimetype='text/event-stream')

    def generate():
        scrapers = [
            ('United Pharmacy', scrape_united),
            ('Nahdi Online',    scrape_nahdi),
            ('Al-Dawaa',        scrape_aldawaa),
        ]

        # Check cache first for each store
        cached_all = True
        for name, _ in scrapers:
            cached = cache.get_search_cache(query, name, max_age=600)
            if cached is not None:
                yield f"data: {json.dumps({'store': name, 'results': cached}, ensure_ascii=False)}\n\n"
            else:
                cached_all = False

        if cached_all:
            yield "data: DONE\n\n"
            return

        # Scrape only stores not cached
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(fn, query): name
                    for name, fn in scrapers
                }

                for future in concurrent.futures.as_completed(futures, timeout=35):
                    store_name = futures[future]
                    # Skip if already served from cache
                    cached = cache.get_search_cache(query, store_name, max_age=600)
                    if cached is not None:
                        continue
                    try:
                        results = future.result(timeout=30)
                        # Store in cache
                        cache.set_search_cache(query, store_name, results)
                        yield f"data: {json.dumps({'store': store_name, 'results': results}, ensure_ascii=False)}\n\n"
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
    'Panadol', 'فيفادول', 'بروفين', 'سولبادين',
    'كلاريتين', 'جافيسكون', 'حفاضات', 'سنتروم',
    'اوميغا 3', 'عرض'
]
_deals_refreshing_lock = threading.Lock()

@app.route('/api/deals')
def deals():
    ip = client_ip()
    cache.track_visit(ip, 'deals', user_agent=request.headers.get('User-Agent', ''))
    if not check_rate(ip, 'deals', 10, 60):
        return Response(json.dumps({'error': 'rate_limit'}, ensure_ascii=False), mimetype='application/json')

    data, _ts = cache.get_deals_cache(max_age=3600)
    if data and len(data) > 0:
        # Background refresh if stale (>15 min)
        if time.time() - _ts > 900:
            threading.Thread(target=_refresh_deals, daemon=True).start()
        return Response(json.dumps(data, ensure_ascii=False), mimetype='application/json')

    # No cache — trigger refresh
    threading.Thread(target=_refresh_deals, daemon=True).start()
    return Response(json.dumps([], ensure_ascii=False), mimetype='application/json')


def _refresh_deals():
    with _deals_refreshing_lock:
        # Check if another thread already refreshed
        data, _ = cache.get_deals_cache(max_age=3600)
        if data and time.time() - cache.get_deals_cache(max_age=3600)[1] < 120:
            return
        try:
            seen_links = set()

            def run_popular(query):
                items = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as _ex:
                    _futs = {_ex.submit(fn, query): fn.__name__ for fn in (scrape_united, scrape_nahdi, scrape_aldawaa)}
                    for _f in concurrent.futures.as_completed(_futs, timeout=45):
                        try:
                            r = _f.result()
                            if r:
                                items.extend(r)
                        except Exception:
                            continue
                return items

            def rebuild_cache(all_items):
                def item_key(item):
                    tokens = item['name'].split(' ')
                    brand = tokens[0].lower().replace('ـ', '') if tokens else ''
                    qty = item.get('quantity') or ''
                    return f"{brand}_{qty}"
                offer_items = []
                seen_keys = set()
                for item in all_items:
                    key = item_key(item)
                    store_key = f"{item.get('store','')}_{key}"
                    if item.get('offer') and store_key not in seen_keys:
                        seen_keys.add(store_key)
                        offer_items.append(item)
                offer_items.sort(key=lambda i: i.get('unit_price') or i['price'])
                return offer_items[:300]

            all_items = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                futures = {ex.submit(run_popular, q): q for q in POPULAR_QUERIES}
                for f in concurrent.futures.as_completed(futures):
                    try:
                        items = f.result()
                        for item in items:
                            if item['link'] not in seen_links:
                                seen_links.add(item['link'])
                                all_items.append(item)
                        cache.set_deals_cache(rebuild_cache(all_items))
                    except Exception:
                        continue

        except Exception as e:
            print(f"Deals refresh error: {e}")


# ── SEO Endpoints ─────────────────────────────────────────────────────────────

@app.route('/robots.txt')
def robots_txt():
    return Response(render_template('robots.txt'), mimetype='text/plain')

@app.route('/sitemap.xml')
def sitemap_xml():
    return Response(render_template('sitemap.xml'), mimetype='text/xml')

@app.route('/_ping')
def ping():
    """Health-check endpoint for uptime monitors (UptimeRobot, cron-job.org).
    Keeps the Render free tier instance warm by external ping every 5 min."""
    return Response('pong', mimetype='text/plain')


# ── Admin / Analytics Dashboard ───────────────────────────────────────────────

def check_admin_auth():
    if ADMIN_PASSWORD:
        auth = request.headers.get('Authorization')
        if not auth or not auth.startswith('Basic '):
            return False
        try:
            import base64
            decoded = base64.b64decode(auth[6:]).decode('utf-8')
            user, pw = decoded.split(':', 1)
            if pw != ADMIN_PASSWORD:
                return False
        except Exception:
            return False
    return True

def admin_unauthorized():
    return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Tawfeery Admin"'})

@app.route('/admin')
def admin_dashboard():
    if not check_admin_auth():
        return admin_unauthorized()
    stats = cache.get_analytics_summary()
    # Mask IPs for privacy
    if 'recent_searches' in stats:
        stats['recent_searches'] = stats['recent_searches'][:20]
    if 'recent_visits' in stats:
        for v in stats['recent_visits']:
            ip = v.get('ip', '')
            v['ip'] = mask_ip(ip)
        stats['recent_visits'] = stats['recent_visits'][:20]
    return render_template('admin.html', stats=stats)

@app.route('/api/admin/stats')
def admin_stats_api():
    if not check_admin_auth():
        return admin_unauthorized()
    stats = cache.get_analytics_summary()
    if 'recent_searches' in stats:
        stats['recent_searches'] = stats['recent_searches'][:20]
    if 'recent_visits' in stats:
        for v in stats['recent_visits']:
            ip = v.get('ip', '')
            v['ip'] = mask_ip(ip)
        stats['recent_visits'] = stats['recent_visits'][:20]
    return Response(json.dumps(stats, ensure_ascii=False), mimetype='application/json')

def mask_ip(ip):
    parts = ip.split('.')
    if len(parts) == 4:
        return f'{parts[0]}.{parts[1]}.*.*'
    return ip


# Pre-warm deals cache on startup
threading.Thread(target=_refresh_deals, daemon=True).start()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True, use_reloader=False)
