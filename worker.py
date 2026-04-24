import asyncio
import logging
import random
from urllib.parse import urlencode


async def _post_with_retry(session, url, rate_gate, max_retries=5, base_delay=2.0):
    last_status = None
    for attempt in range(max_retries + 1):
        await rate_gate.acquire()
        try:
            async with session.post(url) as resp:
                last_status = resp.status
                if resp.status == 200:
                    await rate_gate.report_success()
                    return await resp.json()
                logging.warning(f"HTTP {resp.status} on {url[:80]}...")
                if resp.status in (429, 502, 503, 504):
                    cooldown = await rate_gate.report_429()
                    logging.info(f"Cooldown solicitado: {cooldown:.1f}s por 429 (intento {attempt + 1}/{max_retries})")
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt) * (1 + random.random() * 0.5)
                        logging.info(f"Reintentando en {delay:.1f}s (intento {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                break
        except Exception as exc:
            logging.warning(f"Error de red en intento {attempt + 1}: {exc}")
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt) * (1 + random.random() * 0.5)
                await asyncio.sleep(delay)
                continue
            break
        finally:
            rate_gate.release()
    return {"_http_error": True, "status": last_status}


async def process_person(name, rfc, config, cache, session, rate_gate):
    try:
        base_url = config["api"]["base_url"]
        coll_name = config["api"]["default_coll_name"]
        years = config["filters"]["years_to_check"]
        common = config["filters"]["common_filters"]
        max_retries = config["api"].get("max_retries", 5)
        retry_base_delay = config["api"].get("retry_base_delay", 2.0)

        search_endpoint = config["api"]["endpoints"]["search"]
        search_params = {"busqueda": rfc, "collName": coll_name}
        search_url = f"{base_url}{search_endpoint}?{urlencode(search_params)}"

        cached = cache.get(search_endpoint, search_params)
        if cached:
            person_result = cached
        else:
            person_result = await _post_with_retry(session, search_url, rate_gate, max_retries=max_retries, base_delay=retry_base_delay)
            if person_result.get("_http_error"):
                return {"Name": name, "RFC": rfc, "Status": "Error"}
            cache.set(search_endpoint, search_params, person_result)

        if not (person_result.get("estatus") and person_result.get("datos")):
            return {"Name": name, "RFC": rfc, "Status": "Not found"}

        person_data = person_result["datos"][0]
        history_endpoint = config["api"]["endpoints"]["history"]
        history_params = {"idUsrDecnet": person_data["idUsrDecnet"], "collName": coll_name}
        history_url = f"{base_url}{history_endpoint}?{urlencode(history_params)}"

        cached_hist = cache.get(history_endpoint, history_params)
        if cached_hist:
            declaration_result = cached_hist
        else:
            declaration_result = await _post_with_retry(session, history_url, rate_gate, max_retries=max_retries, base_delay=retry_base_delay)
            if declaration_result.get("_http_error"):
                return {"Name": name, "RFC": rfc, "Status": "Error"}
            cache.set(history_endpoint, history_params, declaration_result)

        result = {"Name": name, "RFC": rfc, "Status": "Not found"}
        for year in years:
            result[f"noComprobante_{year}"] = ""

        for declaration in declaration_result.get("datos", []):
            year = declaration.get("anio")
            if year not in years:
                continue
            matches_common = all(
                declaration.get(key) == value for key, value in common.items()
            )
            if matches_common:
                result[f"noComprobante_{year}"] = declaration["noComprobante"]
                result["Status"] = "Found"

        return result
    except Exception:
        logging.exception("Error processing person %s", name)
        return {"Name": name, "RFC": rfc, "Status": "Error"}