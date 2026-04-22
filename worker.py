async def process_person(name, rfc, config, cache, session):
    try:
        base_url = config["api"]["base_url"]
        coll_name = config["api"]["default_coll_name"]
        years = config["filters"]["years_to_check"]
        common = config["filters"]["common_filters"]

        search_endpoint = config["api"]["endpoints"]["search"]
        search_params = {"busqueda": rfc, "collName": coll_name}
        search_url = f"{base_url}{search_endpoint}?busqueda={rfc}&collName={coll_name}"

        cached = cache.get(search_endpoint, search_params)
        if cached:
            person_result = cached
        else:
            async with session.post(search_url) as resp:
                if resp.status != 200:
                    return {"Name": name, "RFC": rfc, "Status": "Error"}
                person_result = await resp.json()
            cache.set(search_endpoint, search_params, person_result)

        if not (person_result.get("estatus") and person_result.get("datos")):
            return {"Name": name, "RFC": rfc, "Status": "Not found"}

        person_data = person_result["datos"][0]
        history_endpoint = config["api"]["endpoints"]["history"]
        history_params = {"idUsrDecnet": person_data["idUsrDecnet"], "collName": coll_name}
        history_url = f"{base_url}{history_endpoint}?idUsrDecnet={person_data['idUsrDecnet']}&collName={coll_name}"

        cached_hist = cache.get(history_endpoint, history_params)
        if cached_hist:
            declaration_result = cached_hist
        else:
            async with session.post(history_url) as resp:
                if resp.status != 200:
                    return {"Name": name, "RFC": rfc, "Status": "Error"}
                declaration_result = await resp.json()
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
        return {"Name": name, "RFC": rfc, "Status": "Error"}
