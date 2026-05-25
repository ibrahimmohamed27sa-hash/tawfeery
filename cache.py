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

# Initialize on import
init_db()
