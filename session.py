import asyncio
import time

import aiohttp


class RateLimitGate:
    def __init__(self, max_concurrent=10, min_interval=0.15, cooldown_base=5.0, cooldown_max=60.0):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._min_interval = min_interval
        self._last_request = 0.0
        self._cooldown_until = 0.0
        self._cooldown_base = cooldown_base
        self._cooldown_max = cooldown_max
        self._consecutive_429s = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self._semaphore.acquire()
        try:
            await self._wait_if_cooled_down()
            await self._enforce_min_interval()
        except Exception:
            self._semaphore.release()
            raise

    def release(self):
        self._semaphore.release()

    async def report_429(self):
        async with self._lock:
            self._consecutive_429s += 1
            cooldown = min(
                self._cooldown_base * (2 ** (self._consecutive_429s - 1)),
                self._cooldown_max,
            )
            self._cooldown_until = time.monotonic() + cooldown
            return cooldown

    async def report_success(self):
        async with self._lock:
            self._consecutive_429s = 0

    async def _wait_if_cooled_down(self):
        while True:
            async with self._lock:
                remaining = self._cooldown_until - time.monotonic()
            if remaining <= 0:
                break
            await asyncio.sleep(remaining)

    async def _enforce_min_interval(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_request)
            self._last_request = now + max(wait, 0)
        if wait > 0:
            await asyncio.sleep(wait)


def create_headers():
    return {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        'Origin': 'https://servicios.dkla8prod.buengobierno.gob.mx',
        'Referer': 'https://servicios.dkla8prod.buengobierno.gob.mx/declaranet/consulta-servidores-publicos/buscarsp',
    }


async def create_session(limit=10, rate_gate=None):
    connector = aiohttp.TCPConnector(limit=limit, limit_per_host=limit, ttl_dns_cache=300, use_dns_cache=True)
    timeout = aiohttp.ClientTimeout(total=60)
    session = aiohttp.ClientSession(connector=connector, timeout=timeout, headers=create_headers())
    if rate_gate is None:
        rate_gate = RateLimitGate(max_concurrent=limit)
    return session, rate_gate