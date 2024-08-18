import os.path
import sys
import json
from logging import getLogger, config as logging_config

THIS_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
logger = getLogger(__name__)

def _setup_logging_config():
    config_filepath = os.path.join(THIS_SCRIPT_DIR, "logging_config.json")
    if os.path.exists(config_filepath):
        with open(config_filepath, "r") as f:
            logging_config.dictConfig(json.load(f))

def _log_system_info():
    logger.debug(f"{"-"*120}")
    logger.debug(f"Operating system: {sys.platform}")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"{"-"*120}")

def main(args: list):
    _setup_logging_config()
    _log_system_info()

    if len(args) < 2:
            print(f"Usage: python -m {__package__} <path/to/sampling-config.json> <path/to/midi-config.json>")
            sys.exit(1)

    logger.debug("Start")

    from midisampling.sampling import main as sampling_main

    try:
        sampling_main(args)
    except Exception as e:
        logger.error(e, exc_info=True)
    finally:
        logger.debug("End")

if __name__ == '__main__':
    main(sys.argv[1:])
