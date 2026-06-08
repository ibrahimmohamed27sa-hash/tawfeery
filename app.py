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

_nahdi_scraper = None
_nahdi_scraper_lock = threading.Lock()

def get_nahdi_scraper():
    global _nahdi_scraper
    if _nahdi_scraper is None:
        with _nahdi_scraper_lock:
            if _nahdi_scraper is None:
                _nahdi_scraper = cloudscraper.create_scraper()
    return _nahdi_scraper

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
    q = re.sub(r'[^\w\s\+\-\أ-يإآةؤئىء]+', '', q)
    return q.strip()

# Rate limiting: max 20 search requests per minute per IP, 10 deals fetches per minute
def check_rate(ip, endpoint, limit, window=60):
    allowed = cache.check_rate_limit(ip, endpoint, limit, window)
    if not allowed:
        return False
    return True

def client_ip():
    raw = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if raw and re.match(r'^\d{1,3}(\.\d{1,3}){3}$', raw):
        return raw
    return request.remote_addr or '127.0.0.1'


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
        # NOTE: Do NOT include dosage/volume units (ML, Mg, G, KG) here — those are
        # dosage values (e.g. 500mg), not item counts.
        r'(\d+)\s*(Tablets?|Capsules?|Pills?|Diapers?|Pieces?|Count|Pack|Tabs?|Caps?|Pcs)',
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
        return None

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
            m = re.search(r'(\d+)', str(raw_qty))
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
                        brand = h.get('brand', '')
                        name_en = h.get('name_locally_en', '')
                        item = {
                            'store': 'United Pharmacy',
                            'name': name,
                            'price': float(price_val),
                            'image': img_url,
                            'link': link,
                            'offer': offer_text,
                            'sku': sku,
                            'brand': brand,
                            'name_en': name_en,
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
    Nahdi uses Magento REST API at ecombe.nahdionline.com.
    Their Algolia search SSR ignores queries, so we hit the Magento API directly.
    Product names are in English, so Arabic queries get transliterated first.
    """
    results = []

    # Arabic-to-English transliteration for common pharmacy terms
    translit = {
        'بنادول': 'panadol', 'بروفين': 'brufen', 'سولبادين': 'solpadeine',
        'كلاريتين': 'claritin', 'جافيسكون': 'gaviscon', 'سنتروم': 'centrum',
        'فيفادول': 'vivadol', 'ميتفورمين': 'metformin', 'ريني': 'rennie',
        'كانستين': 'canesten', 'لا روشيه': 'la roche', 'سيتريزين': 'cetirizine',
        'امبولا': 'ampoule', 'زنك': 'zinc', 'فيتامين سي': 'vitamin c',
        'فيتامين د': 'vitamin d', 'اوميغا 3': 'omega 3', 'كالسيوم': 'calcium',
        'حفاضات': 'diapers', 'كحة': 'cough', 'دوف': 'dove', 'نيورون': 'neurone',
        'بيبي جوي كلوت': 'baby joy culotte', 'بيبي جوي': 'baby joy',
        'حفاضة': 'diaper', 'كلوت': 'culotte', 'شامبو': 'shampoo',
        'مسكن': 'analgesic', 'مضاد': 'antibiotic', 'قطرة': 'drops',
        'شراب': 'syrup', 'كبسولة': 'capsule', 'قرص': 'tablet',
        'حبة': 'tablet', 'مرطب': 'moisturizer', 'واقي شمس': 'sunscreen',
        'معقم': 'sanitizer', 'مناديل': 'wipes', 'شاش': 'gauze',
        'لاصق': 'tape', 'ضمادة': 'bandage', 'قطن': 'cotton',
        'مسواك': 'miswak', 'فرشاة': 'brush', 'معجون': 'paste',
        'بيبي': 'baby', 'جوي': 'joy', 'كبوت': 'culotte', 'كوت': 'culotte',
        'بنادول': 'panadol', 'فيتامين': 'vitamin', 'كالسيوم': 'calcium',
        'حفاض': 'diaper', 'كبسول': 'capsule', 'أقراص': 'tablets',
        'مقاس': 'size', 'كبير': 'large', 'صغير': 'small', 'وسط': 'medium',
    }

    def transliterate_query(q):
        q_lower = q.lower().strip()
        # Normalize Arabic text (remove tashkeel, normalize alef, etc.)
        q_norm = re.sub(r'[ًٌٍَُِّْ]', '', q_lower)  # Remove tashkeel
        q_norm = q_norm.replace('إ', 'ا').replace('آ', 'ا').replace('أ', 'ا')  # Normalize alef
        q_norm = q_norm.replace('ة', 'ه').replace('ى', 'ي')  # Normalize ta-marbuta and alef-maksura

        # Try full phrase match first (normalized)
        for ar, en in translit.items():
            ar_norm = re.sub(r'[ًٌٍَُِّْ]', '', ar.lower())
            ar_norm = ar_norm.replace('إ', 'ا').replace('آ', 'ا').replace('أ', 'ا')
            ar_norm = ar_norm.replace('ة', 'ه').replace('ى', 'ي')
            if q_norm == ar_norm:
                return en

        # Try word-by-word transliteration
        words = q_norm.split()
        en_words = []
        for w in words:
            found = False
            for ar, en in translit.items():
                ar_norm_w = re.sub(r'[ًٌٍَُِّْ]', '', ar.lower())
                ar_norm_w = ar_norm_w.replace('إ', 'ا').replace('آ', 'ا').replace('أ', 'ا')
                ar_norm_w = ar_norm_w.replace('ة', 'ه').replace('ى', 'ي')
                if w == ar_norm_w:
                    en_words.append(en)
                    found = True
                    break
            if not found:
                en_words.append(w)

        result = ' '.join(en_words)
        return result

    # Build search queries: original + transliterated + individual terms
    queries_to_try = [query]
    en_query = transliterate_query(query)
    if en_query.lower() != query.lower():
        queries_to_try.append(en_query)
    # Also try shorter sub-queries for multi-word queries (Magento LIKE is strict)
    en_words = en_query.split()
    if len(en_words) > 2:
        for i in range(len(en_words)):
            for j in range(i + 2, len(en_words) + 1):
                sub = ' '.join(en_words[i:j])
                if sub not in queries_to_try and len(sub) > 2:
                    queries_to_try.append(sub)

    scraper = get_nahdi_scraper()
    seen_skus = set()

    for q in queries_to_try:
        try:
            url = 'https://ecombe.nahdionline.com/rest/V1/products'
            params = {
                'searchCriteria[filterGroups][0][filters][0][field]': 'name',
                'searchCriteria[filterGroups][0][filters][0][value]': f'%{q}%',
                'searchCriteria[filterGroups][0][filters][0][conditionType]': 'like',
                'searchCriteria[pageSize]': '30',
            }
            res = scraper.get(url, params=params, timeout=15, headers={'Accept': 'application/json'})
            if res.status_code != 200:
                continue

            data = res.json()
            for item in data.get('items', []):
                sku = item.get('sku', '')
                if sku in seen_skus:
                    continue
                seen_skus.add(sku)

                name = item.get('name', '')
                price = float(item.get('price', 0))
                if not name or price <= 0:
                    continue

                img_path = ''
                qty = None
                for attr in item.get('custom_attributes', []):
                    code = attr.get('attribute_code', '')
                    val = attr.get('value', '')
                    if code == 'image':
                        img_path = val
                    elif code == 'quantity_and_unit_description':
                        m = re.search(r'(\d+)', val)
                        if m:
                            qty = int(m.group(1))
                    elif code == 'size':
                        m = re.search(r'(\d+)', str(val))
                        if m:
                            qty = int(m.group(1))

                image_url = f"https://ecombe.nahdionline.com/media/catalog/product{img_path}" if img_path else ''
                link = f"https://www.nahdionline.com/ar-sa/search?query={urllib.parse.quote(name)}"

                item_result = {
                    'store': 'Nahdi Online',
                    'name': name,
                    'price': price,
                    'image': image_url,
                    'link': link,
                    'offer': '',
                    'sku': sku,
                    'name_en': name,
                    'brand': '',
                    'manufacturer': '',
                    'gtin': '',
                    'quantity': qty,
                    'unit_price': round(price / qty, 4) if qty else None,
                }
                enrich_item(item_result)
                results.append(item_result)
        except Exception as e:
            print(f"Nahdi Magento error [{q}]: {e}")

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
                brand = ''
                brand_data = p.get('brand')
                if isinstance(brand_data, dict):
                    brand = brand_data.get('name', '') or ''
                name_en = p.get('urlProductName', '') or ''
                item = {
                    'store': 'Al-Dawaa',
                    'name': name,
                    'price': float(price_val),
                    'image': img_url,
                    'link': link,
                    'offer': offer_text,
                    'sku': sku,
                    'brand': brand,
                    'name_en': name_en,
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
            'Access-Control-Allow-Origin': request.headers.get('Origin', '*')
        }
    )


# ── Best Deals / Featured Endpoint ────────────────────────────────────────────

POPULAR_QUERIES = [
    'Panadol', 'بنادول', 'بروفين', 'سولبادين',
    'كلاريتين', 'جافيسكون', 'حفاضات', 'سنتروم',
    'اوميغا 3', 'فيتامين سي', 'فيتامين د', 'كالسيوم',
    'فيفادول', 'ميتفورمين', 'ريني', 'كانستين',
    'لا روشيه', 'سيتريزين', 'امبولا', 'زنك',
    'حليب اطفال', 'كحة', 'دوف', 'نيورون',
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
        data, ts = cache.get_deals_cache(max_age=3600)
        if data and time.time() - ts < 120:
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
                offer_items.sort(key=lambda i: (i.get('unit_price') if i.get('unit_price') is not None else 999999))
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
                    except Exception:
                        continue
            cache.set_deals_cache(rebuild_cache(all_items))

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
    if not ADMIN_PASSWORD:
        return False
    auth = request.headers.get('Authorization')
    if not auth or not auth.startswith('Basic '):
        return False
    try:
        import base64
        decoded = base64.b64decode(auth[6:]).decode('utf-8')
        user, pw = decoded.split(':', 1)
        if not secrets.compare_digest(pw, ADMIN_PASSWORD):
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
        for s in stats['recent_searches']:
            s['ip'] = mask_ip(s.get('ip', ''))
        stats['recent_searches'] = stats['recent_searches'][:20]
    if 'recent_visits' in stats:
        for v in stats['recent_visits']:
            v['ip'] = mask_ip(v.get('ip', ''))
        stats['recent_visits'] = stats['recent_visits'][:20]
    return render_template('admin.html', stats=stats)

@app.route('/api/admin/stats')
def admin_stats_api():
    if not check_admin_auth():
        return admin_unauthorized()
    stats = cache.get_analytics_summary()
    if 'recent_searches' in stats:
        for s in stats['recent_searches']:
            s['ip'] = mask_ip(s.get('ip', ''))
        stats['recent_searches'] = stats['recent_searches'][:20]
    if 'recent_visits' in stats:
        for v in stats['recent_visits']:
            v['ip'] = mask_ip(v.get('ip', ''))
        stats['recent_visits'] = stats['recent_visits'][:20]
    return Response(json.dumps(stats, ensure_ascii=False), mimetype='application/json')

def mask_ip(ip):
    if not ip:
        return '*.*.*.*'
    parts = ip.split('.')
    if len(parts) == 4:
        return f'{parts[0]}.{parts[1]}.*.*'
    if ':' in ip:
        groups = ip.split(':')
        if len(groups) > 2:
            return ':'.join(groups[:2]) + ':****'
    return '*.*.*.*'


# Pre-warm deals cache on startup
threading.Thread(target=_refresh_deals, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True, use_reloader=False)
