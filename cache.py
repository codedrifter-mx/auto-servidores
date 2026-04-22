import hashlib
import json
import os
import sqlite3
import time
import threading


class APICache:
    def __init__(self, db_path, ttl_seconds=3600, enabled=True, flush_interval=100, use_wal=True):
        self.ttl = ttl_seconds
        self.enabled = enabled
        self._mem = {}
        self._lock = threading.RLock()
        self._dirty = 0
        self._flush_interval = flush_interval
        if enabled:
            self.db_path = db_path
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            if use_wal:
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            self._conn.commit()
            self._load_db()

    def _load_db(self):
        rows = self._conn.execute("SELECT key, response, timestamp FROM cache").fetchall()
        for key, response, ts in rows:
            if (time.time() - ts) < self.ttl:
                self._mem[key] = (json.loads(response), ts)

    def _make_key(self, endpoint, params):
        raw = json.dumps({'endpoint': endpoint, 'params': params}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, endpoint, params):
        if not self.enabled:
            return None
        key = self._make_key(endpoint, params)
        with self._lock:
            entry = self._mem.get(key)
        if entry and (time.time() - entry[1]) < self.ttl:
            return entry[0]
        return None

    def set(self, endpoint, params, response):
        if not self.enabled:
            return
        key = self._make_key(endpoint, params)
        ts = time.time()
        with self._lock:
            self._mem[key] = (response, ts)
            self._dirty += 1
            if self._dirty >= self._flush_interval:
                self._flush()
                self._dirty = 0

    def _flush(self):
        if not self.enabled:
            return
        with self._lock:
            items = [(k, json.dumps(v[0]), v[1]) for k, v in self._mem.items()]
        self._conn.executemany(
            "INSERT OR REPLACE INTO cache (key, response, timestamp) VALUES (?, ?, ?)",
            items
        )
        self._conn.commit()

    def flush(self):
        self._flush()
        self._dirty = 0

    def close(self):
        if self.enabled:
            self._flush()
            self._conn.close()
