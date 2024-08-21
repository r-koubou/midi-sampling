import os.path
import sys
import json
import argparse
from logging import getLogger
from midisampling.logging_management import init_logging_from_config

THIS_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
logger = getLogger(__name__)

def _log_system_info():
    logger.debug(f"{"-"*120}")
    logger.debug(f"Operating system: {sys.platform}")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Args: {" ".join(sys.argv)}")
    logger.debug(f"{"-"*120}")

def main():

    parser = argparse.ArgumentParser(prog=f"python -m {__package__}")
    parser.add_argument("--verbose", help="Enable verbose logging.", action="store_true")
    parser.add_argument("sampling_config_path", help="Path to the sampling configuration file.")
    parser.add_argument("midi_config_path", help="Path to the MIDI configuration file.")
    parser.add_argument("-l", "--log-file", help="Path to save the log file.")

    args = parser.parse_args()

    init_logging_from_config(logfile_path=args.log_file, verbose=args.verbose)
    _log_system_info()

    from midisampling.sampling import main as sampling_main
    try:
        sampling_main(args.sampling_config_path, args.midi_config_path)
    except Exception as e:
        logger.error(e, exc_info=True)
    finally:
        logger.debug("End")

if __name__ == '__main__':
    main()
