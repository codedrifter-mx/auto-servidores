import aiohttp


def create_headers():
    return {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
        'Origin': 'https://servicios.dkla8prod.buengobierno.gob.mx',
        'Referer': 'https://servicios.dkla8prod.buengobierno.gob.mx/declaranet/consulta-servidores-publicos/buscarsp',
    }


async def create_session(limit=200):
    connector = aiohttp.TCPConnector(limit=limit, limit_per_host=limit, ttl_dns_cache=300, use_dns_cache=True)
    timeout = aiohttp.ClientTimeout(total=30)
    session = aiohttp.ClientSession(connector=connector, timeout=timeout, headers=create_headers())
    return session
