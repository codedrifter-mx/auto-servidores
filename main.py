import argparse
import asyncio
import logging
import sys


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def run_headless():
    setup_logging()
    from orchestrator import Orchestrator
    orchestrator = Orchestrator()
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        logging.info("Interrumpido por el usuario.")
        sys.exit(130)
    except Exception as e:
        logging.error(f"El procesamiento falló: {e}")
        sys.exit(1)


def run_gui():
    from gui import main as gui_main
    gui_main()


def main():
    parser = argparse.ArgumentParser(description="Auto Servidores")
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Ejecutar en modo headless sin iniciar la GUI"
    )
    args = parser.parse_args()

    if args.no_gui:
        run_headless()
    else:
        run_gui()


if __name__ == "__main__":
    main()