import pytest

from session import create_headers, RateLimitGate


class TestSession:
    def test_create_headers_returns_dict(self):
        headers = create_headers()
        assert isinstance(headers, dict)

    def test_headers_content_type(self):
        headers = create_headers()
        assert headers["Content-Type"] == "application/json"

    def test_headers_user_agent(self):
        headers = create_headers()
        assert "Chrome" in headers["User-Agent"]

    def test_headers_accept(self):
        headers = create_headers()
        assert headers["Accept"] == "application/json, text/plain, */*"

    def test_headers_origin(self):
        headers = create_headers()
        assert "buengobierno.gob.mx" in headers["Origin"]

    def test_headers_referer(self):
        headers = create_headers()
        assert "buengobierno.gob.mx" in headers["Referer"]


class TestRateLimitGate:
    @pytest.mark.asyncio
    async def test_acquire_release_cycle(self):
        gate = RateLimitGate(max_concurrent=2, min_interval=0.0)
        await gate.acquire()
        await gate.acquire()
        gate.release()
        gate.release()

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        gate = RateLimitGate(max_concurrent=1, min_interval=0.0)
        await gate.acquire()
        acquired = False

        async def try_acquire():
            nonlocal acquired
            await gate.acquire()
            acquired = True
            gate.release()

        import asyncio
        task = asyncio.create_task(try_acquire())
        await asyncio.sleep(0.05)
        assert not acquired
        gate.release()
        await task
        assert acquired

    @pytest.mark.asyncio
    async def test_report_429_sets_cooldown(self):
        gate = RateLimitGate(max_concurrent=2, min_interval=0.0, cooldown_base=5.0, cooldown_max=60.0)
        cooldown = await gate.report_429()
        assert cooldown == 5.0
        cooldown = await gate.report_429()
        assert cooldown == 10.0

    @pytest.mark.asyncio
    async def test_report_success_resets_429_counter(self):
        gate = RateLimitGate(max_concurrent=2, min_interval=0.0, cooldown_base=5.0)
        await gate.report_429()
        await gate.report_success()
        cooldown = await gate.report_429()
        assert cooldown == 5.0

    @pytest.mark.asyncio
    async def test_cooldown_max_cap(self):
        gate = RateLimitGate(max_concurrent=2, min_interval=0.0, cooldown_base=5.0, cooldown_max=10.0)
        await gate.report_429()
        cooldown = await gate.report_429()
        assert cooldown == 10.0

    @pytest.mark.asyncio
    async def test_min_interval_sleep_releases_lock(self):
        import asyncio
        import time
        from unittest.mock import patch

        gate = RateLimitGate(max_concurrent=2, min_interval=0.1)
        sleep_count = [0]

        original_sleep = asyncio.sleep

        async def tracked_sleep(duration):
            sleep_count[0] += 1
            await original_sleep(duration)

        async def task():
            await gate.acquire()
            gate.release()

        with patch('asyncio.sleep', tracked_sleep):
            start = time.monotonic()
            await asyncio.gather(task(), task())
            elapsed = time.monotonic() - start

        # With the fix, _last_request reserves a future slot so only the first task sleeps.
        # With the bug, the second task blocks on the lock and also sleeps, taking ~0.2s total.
        assert sleep_count[0] == 1
        assert elapsed < 0.15