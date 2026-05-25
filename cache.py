import sqlite3
import json
import time
import threading
import os

DB_PATH = os.environ.get('CACHE_DB_PATH', '/tmp/tawfeery_cache.db')

_local = threading.local()

def _get_conn():
    if not hasattr(_local, 'conn') or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, timeout=10)
        _local.conn.execute('PRAGMA journal_mode=WAL')
        _local.conn.execute('PRAGMA synchronous=NORMAL')
    return _local.conn

def init_db():
    conn = _get_conn()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS search_cache (
            query TEXT NOT NULL,
            store TEXT NOT NULL,
            results TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (query, store)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS deals_cache (
            key TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            ip TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            window_start REAL NOT NULL,
            PRIMARY KEY (ip, endpoint, window_start)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS analytics_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            user_agent TEXT DEFAULT '',
            page TEXT NOT NULL,
            query TEXT DEFAULT '',
            referrer TEXT DEFAULT '',
            created_at REAL NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS analytics_daily (
            date TEXT PRIMARY KEY,
            visits INTEGER DEFAULT 0,
            unique_ips INTEGER DEFAULT 0,
            searches INTEGER DEFAULT 0
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_visits_created ON analytics_visits(created_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_visits_page ON analytics_visits(page)')
    conn.commit()

# Search cache
def get_search_cache(query, store, max_age=300):
    """Get cached search results. Returns list or None if stale/missing."""
    conn = _get_conn()
    cur = conn.execute(
        'SELECT results, created_at FROM search_cache WHERE query=? AND store=?',
        (query.lower().strip(), store)
    )
    row = cur.fetchone()
    if row:
        data, ts = row
        if time.time() - ts < max_age:
            return json.loads(data)
    return None

def set_search_cache(query, store, results):
    conn = _get_conn()
    conn.execute(
        'INSERT OR REPLACE INTO search_cache (query, store, results, created_at) VALUES (?, ?, ?, ?)',
        (query.lower().strip(), store, json.dumps(results, ensure_ascii=False), time.time())
    )
    conn.commit()

# Deals cache (shared across all workers)
def get_deals_cache(max_age=3600):
    conn = _get_conn()
    cur = conn.execute('SELECT data, updated_at FROM deals_cache WHERE key=?', ('deals',))
    row = cur.fetchone()
    if row:
        data, ts = row
        if time.time() - ts < max_age:
            return json.loads(data), ts
    return None, 0

def set_deals_cache(data):
    conn = _get_conn()
    conn.execute(
        'INSERT OR REPLACE INTO deals_cache (key, data, updated_at) VALUES (?, ?, ?)',
        ('deals', json.dumps(data, ensure_ascii=False), time.time())
    )
    conn.commit()

# Rate limiting (simple sliding window per IP + endpoint)
def check_rate_limit(ip, endpoint, max_requests=30, window=60):
    """Returns True if allowed, False if rate limited."""
    now = time.time()
    window_start = int(now / window) * window
    conn = _get_conn()
    try:
        cur = conn.execute(
            'SELECT count FROM rate_limits WHERE ip=? AND endpoint=? AND window_start=?',
            (ip, endpoint, window_start)
        )
        row = cur.fetchone()
        if row:
            count = row[0] + 1
            if count > max_requests:
                return False
            conn.execute(
                'UPDATE rate_limits SET count=? WHERE ip=? AND endpoint=? AND window_start=?',
                (count, ip, endpoint, window_start)
            )
        else:
            conn.execute(
                'INSERT INTO rate_limits (ip, endpoint, count, window_start) VALUES (?, ?, 1, ?)',
                (ip, endpoint, window_start)
            )
        conn.commit()
        # Cleanup old entries
        conn.execute('DELETE FROM rate_limits WHERE window_start < ?', (int(now / window) * window - 2 * window,))
        conn.commit()
        return True
    except Exception:
        return True

# ── Analytics ──────────────────────────────────────────────────────────────────

def track_visit(ip, page, query='', user_agent='', referrer=''):
    try:
        conn = _get_conn()
        now = time.time()
        conn.execute(
            'INSERT INTO analytics_visits (ip, user_agent, page, query, referrer, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (ip, (user_agent or '')[:200], page, query, (referrer or '')[:200], now)
        )
        # Update daily aggregate
        date = time.strftime('%Y-%m-%d', time.localtime(now))
        conn.execute(
            'INSERT INTO analytics_daily (date, visits, unique_ips, searches) VALUES (?, 1, 0, 0) '
            'ON CONFLICT(date) DO UPDATE SET visits = visits + 1',
            (date,)
        )
        if query:
            conn.execute(
                'UPDATE analytics_daily SET searches = searches + 1 WHERE date = ?',
                (date,)
            )
        conn.commit()
    except Exception:
        pass

def get_analytics_summary():
    """Returns dict with today/lifetime stats."""
    conn = _get_conn()
    today = time.strftime('%Y-%m-%d')
    result = {}
    try:
        # Today's stats
        cur = conn.execute(
            'SELECT visits, searches FROM analytics_daily WHERE date=?', (today,)
        )
        row = cur.fetchone()
        result['today_visits'] = row[0] if row else 0
        result['today_searches'] = row[1] if row else 0

        # Today unique IPs
        today_start = time.mktime(time.strptime(today, '%Y-%m-%d'))
        cur = conn.execute(
            'SELECT COUNT(DISTINCT ip) FROM analytics_visits WHERE created_at >= ?', (today_start,)
        )
        result['today_ips'] = cur.fetchone()[0] or 0

        # Lifetime
        cur = conn.execute('SELECT COUNT(*) FROM analytics_visits')
        result['total_visits'] = cur.fetchone()[0] or 0
        cur = conn.execute('SELECT COUNT(DISTINCT ip) FROM analytics_visits')
        result['total_ips'] = cur.fetchone()[0] or 0
        cur = conn.execute('SELECT SUM(searches) FROM analytics_daily')
        result['total_searches'] = cur.fetchone()[0] or 0

        # Recent searches
        cur = conn.execute(
            'SELECT query, created_at, ip FROM analytics_visits WHERE query != "" AND page = "search" ORDER BY created_at DESC LIMIT 20'
        )
        result['recent_searches'] = [{'query': r[0], 'time': r[1], 'ip': r[2]} for r in cur.fetchall()]

        # Top queries today
        cur = conn.execute(
            'SELECT query, COUNT(*) as cnt FROM analytics_visits WHERE query != "" AND created_at >= ? GROUP BY query ORDER BY cnt DESC LIMIT 20',
            (today_start,)
        )
        result['top_queries'] = [{'query': r[0], 'count': r[1]} for r in cur.fetchall()]

        # Visits last 7 days
        week_ago = today_start - 7 * 86400
        cur = conn.execute(
            'SELECT date, visits, unique_ips, searches FROM analytics_daily WHERE date >= ? ORDER BY date DESC',
            (time.strftime('%Y-%m-%d', time.localtime(week_ago)),)
        )
        result['daily'] = [{'date': r[0], 'visits': r[1], 'searches': r[3]} for r in cur.fetchall()]

        # Latest visits
        cur = conn.execute(
            'SELECT ip, page, query, user_agent, created_at FROM analytics_visits ORDER BY created_at DESC LIMIT 10'
        )
        result['recent_visits'] = [{'ip': r[0], 'page': r[1], 'query': r[2], 'ua': (r[3] or '')[:60], 'time': r[4]} for r in cur.fetchall()]
    except Exception:
        pass
    return result


# Initialize on import
init_db()
