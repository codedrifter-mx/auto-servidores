import asyncio
import logging

from orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

if __name__ == "__main__":
    logging.info("Starting data processing")
    orchestrator = Orchestrator()
    asyncio.run(orchestrator.run())
