import asyncio
import logging

import yaml

from cache import APICache
from compactor import Compactor
from index import SeedIndex
from session import RateLimitGate, create_session
from worker import process_person


class Orchestrator:
    def __init__(self, config_path="config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        rate_cfg = self.config.get("rate_limit", {})
        self.rate_gate = RateLimitGate(
            max_concurrent=rate_cfg.get("max_concurrent", 10),
            min_interval=rate_cfg.get("min_interval", 0.15),
            cooldown_base=rate_cfg.get("cooldown_base", 5.0),
            cooldown_max=rate_cfg.get("cooldown_max", 60.0),
        )

        self.cache = APICache(
            db_path=self.config["cache"]["db_path"],
            ttl_seconds=self.config["cache"]["ttl_seconds"],
            enabled=self.config["cache"]["enabled"],
            flush_interval=200,
        )
        self.compactor = Compactor(
            output_dir=self.config["output"]["dir"],
            found_suffix=self.config["output"]["found_suffix"],
            not_found_suffix=self.config["output"]["not_found_suffix"],
            years=self.config["filters"]["years_to_check"],
        )
        self.seed_index = SeedIndex()

    async def run(self, on_progress=None, on_log=None):
        if on_log:
            on_log("Iniciando procesamiento de datos")
        else:
            logging.info("Iniciando procesamiento de datos")

        max_workers = self.config["processing"]["max_workers"]
        rl_cfg = self.config.get("rate_limit", {})
        max_concurrent = rl_cfg.get("max_concurrent", max_workers)
        session, self.rate_gate = await create_session(limit=max_concurrent, rate_gate=self.rate_gate)

        try:
            files = self.seed_index.get_files()
            total_rows = sum(f["row_count"] for f in files)
            processed_overall = 0

            for file_info in files:
                found = []
                not_found = []
                msg = f"Procesando: {file_info['filename']} ({file_info['row_count']} filas)"
                if on_log: on_log(msg)
                else: logging.info(msg)

                batch_size = self.config["processing"]["batch_size"]
                processed_in_file = 0
                for start in range(0, file_info["row_count"], batch_size):
                    batch = self.seed_index.load_batch(
                        file_info["filepath"], start=start, size=batch_size
                    )
                    tasks = [
                        process_person(name, rfc, self.config, self.cache, session, self.rate_gate)
                        for name, rfc in batch
                    ]

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            processed_overall += 1
                            continue
                        if result.get("Status") == "Found":
                            found.append(result)
                        else:
                            not_found.append(result)
                        processed_in_file += 1
                        processed_overall += 1

                    self.cache.flush()

                    if on_progress:
                        on_progress(processed_overall, total_rows)

                    msg = f"Lote completado: {processed_in_file}/{file_info['row_count']} registros"
                    if on_log: on_log(msg)
                    else: logging.info(msg)

                    inter_batch = self.config.get("rate_limit", {}).get("inter_batch_delay", 1.5)
                    await asyncio.sleep(inter_batch)

                summary = self.compactor.compact(found, not_found, file_info["basename"])
                msg = f"Completado {file_info['filename']}: {summary['found_count']} encontrados, {summary['not_found_count']} no encontrados"
                if on_log: on_log(msg)
                else: logging.info(msg)
        finally:
            await session.close()
            self.cache.close()

        msg = "Procesamiento completado."
        if on_log: on_log(msg)
        else: logging.info(msg)