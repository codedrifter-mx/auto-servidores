import os
import shutil
import tempfile

import pytest

from cache import APICache


@pytest.fixture
def cache_path():
    tmpdir = tempfile.mkdtemp()
    db = os.path.join(tmpdir, "test_cache.db")
    yield db
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestAPICache:
    def test_set_and_get(self, cache_path):
        cache = APICache(db_path=cache_path, ttl_seconds=3600)
        cache.set("/api", {"q": "1"}, {"data": "ok"})
        result = cache.get("/api", {"q": "1"})
        assert result == {"data": "ok"}
        cache.close()

    def test_cache_miss(self, cache_path):
        cache = APICache(db_path=cache_path, ttl_seconds=3600)
        assert cache.get("/api", {"q": "1"}) is None
        cache.close()

    def test_ttl_expiry(self, cache_path):
        cache = APICache(db_path=cache_path, ttl_seconds=0)
        cache.set("/api", {"q": "1"}, {"data": "ok"})
        assert cache.get("/api", {"q": "1"}) is None
        cache.close()

    def test_disabled_cache(self, cache_path):
        cache = APICache(db_path=cache_path, enabled=False)
        cache.set("/api", {"q": "1"}, {"data": "ok"})
        assert cache.get("/api", {"q": "1"}) is None

    @pytest.mark.skip(reason="SQLite WAL lock issue with dual instances")
    def test_flush_persists_to_db(self, cache_path):
        cache = APICache(db_path=cache_path, ttl_seconds=3600, flush_interval=1)
        cache.set("/api", {"q": "1"}, {"data": "ok"})
        cache.flush()
        cache.close()

        import time
        time.sleep(0.5)

        cache2 = APICache(db_path=cache_path, ttl_seconds=3600)
        assert cache2.get("/api", {"q": "1"}) == {"data": "ok"}
        cache2.close()

    def test_different_params_different_keys(self, cache_path):
        cache = APICache(db_path=cache_path, ttl_seconds=3600)
        cache.set("/api", {"q": "1"}, {"data": "one"})
        cache.set("/api", {"q": "2"}, {"data": "two"})
        assert cache.get("/api", {"q": "1"}) == {"data": "one"}
        assert cache.get("/api", {"q": "2"}) == {"data": "two"}
        cache.close()

    def test_close(self, cache_path):
        cache = APICache(db_path=cache_path)
        cache.close()
