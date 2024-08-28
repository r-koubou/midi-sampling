import os.path
import sys
import argparse
import datetime
from logging import getLogger

from midisampling.logging_management import init_logging_from_config

from midisampling.sampling import SamplingArguments

THIS_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
logger = getLogger(__name__)

def _log_system_info():
    logger.debug(f"{"-"*120}")
    logger.debug(f"Operating system: {sys.platform}")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Args: {" ".join(sys.argv[1:])}")
    logger.debug(f"{"-"*120}")

def main():

    parser = argparse.ArgumentParser(prog=f"python -m {__package__}")
    parser.add_argument("-v", "--verbose", help="Enable verbose logging.", action="store_true")
    parser.add_argument("sampling_config_path", help="Path to the sampling configuration file.")
    parser.add_argument("midi_config_path", help="Path to the MIDI configuration file.")
    parser.add_argument("postprocess_config_path", help="Path to the process configuration file for post processing.", default=None, nargs="?")
    parser.add_argument("-l", "--log-file", help="Path to save the log file.")
    parser.add_argument("-rw", "--overwrite-recorded", help="Overwrite recorded file if it exists.", action="store_true", default=False)

    args = parser.parse_args()

    logfile_path = args.log_file
    if not logfile_path:
        timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logfile_dir  = os.path.dirname(os.path.abspath(args.midi_config_path))
        logfile_path = os.path.join(logfile_dir, f"midi-sampling-{timestamp}.log")

    init_logging_from_config(logfile_path=logfile_path, verbose=args.verbose)
    _log_system_info()

    from midisampling.sampling import main as sampling_main
    try:
        sampling_main(args=samplig_args)
    except Exception as e:
        logger.error(e, exc_info=True)
    finally:
        logger.debug("End")

if __name__ == '__main__':
    main()
