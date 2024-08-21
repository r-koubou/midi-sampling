import os
import json

from logging import getLogger, config as logging_config

THIS_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_LOGGING_CONFIG_FILE = os.path.join(THIS_SCRIPT_DIR, "logging_config.json")

__initialized = False

def init_logging_from_config(logconfig_file_path: str = None, logfile_path: str = None, verbose: bool = False):
    """
    Initialize the logging configuration.
    This function should be called before any logging is done and only once in startup.

    Parameters
    ----------
    logconfig_file_path : str, optional
        Path to the logging configuration file (default: None).

    verbose : bool, optional
        Enable verbose logging (default: False).
    """
    global __initialized

    if __initialized:
        return

    if not logconfig_file_path:
        logconfig_file_path = DEFAULT_LOGGING_CONFIG_FILE

    with open(logconfig_file_path, "r") as f:
        config_json = json.load(f)

    if verbose:
        for handler in config_json["handlers"].values():
            handler["level"] = "DEBUG"

    logging_config.dictConfig(config_json)
    __initialized = True


DEFAULT_MESSAGE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def init_logging_as_stdout(verbose: bool = False, message_format: str = DEFAULT_MESSAGE_FORMAT):
    """
    Initialize the logging configuration to output to stdout.
    This function should be called before any logging is done and only once in startup.

    Parameters
    ----------
    verbose : bool, optional
        Enable verbose logging (default: False).
    message_format : str, optional
        Log message format (default: "%(asctime)s [%(levelname)s] %(name)s: %(message)s").
    """
    global __initialized

    if __initialized:
        return

    config_json = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": f"{message_format}"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG" if verbose else "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout"
            }
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": "DEBUG" if verbose else "INFO",
            }
        }
    }

    logging_config.dictConfig(config_json)
    __initialized = True