import asyncio
import logging

import yaml

from cache import APICache
from checkpoint import Checkpoint
from compactor import Compactor
from index import SeedIndex
from session import create_session
from worker import process_person


class Orchestrator:
    def __init__(self, config_path="config.yaml"):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.cache = APICache(
            db_path=self.config["cache"]["db_path"],
            ttl_seconds=self.config["cache"]["ttl_seconds"],
            enabled=self.config["cache"]["enabled"],
            flush_interval=200,
        )
        self.checkpoint = Checkpoint()
        self.compactor = Compactor(
            output_dir=self.config["output"]["dir"],
            found_suffix=self.config["output"]["found_suffix"],
            not_found_suffix=self.config["output"]["not_found_suffix"],
            years=self.config["filters"]["years_to_check"],
        )
        self.seed_index = SeedIndex()

    async def run(self):
        logging.info("Starting context-engineered data processing")

        session = await create_session(limit=self.config["processing"]["max_workers"])

        try:
            for file_info in self.seed_index.get_files():
                self.checkpoint.set_current_file(file_info["filename"])
                logging.info(f"Processing: {file_info['filename']} ({file_info['row_count']} rows)")

                batch_size = self.config["processing"]["batch_size"]
                processed_count = 0

                for start in range(0, file_info["row_count"], batch_size):
                    batch = self.seed_index.load_batch(
                        file_info["filepath"], start=start, size=batch_size
                    )
                    tasks = []
                    for name, rfc in batch:
                        if self.checkpoint.is_processed(rfc):
                            continue
                        tasks.append(
                            process_person(name, rfc, self.config, self.cache, session)
                        )

                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            continue
                        self.checkpoint.mark_processed(result["RFC"], result)
                        processed_count += 1

                    self.checkpoint.save()
                    self.cache.flush()
                    logging.info(f"Batch complete: {processed_count} records processed")

                found, not_found = self.checkpoint.get_results()
                summary = self.compactor.compact(found, not_found, file_info["basename"])
                logging.info(
                    f"Completed {file_info['filename']}: "
                    f"{summary['found_count']} found, {summary['not_found_count']} not found"
                )
        finally:
            await session.close()
            self.cache.close()

        logging.info("All processing completed.")
