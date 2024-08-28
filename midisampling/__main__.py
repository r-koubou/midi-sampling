import os.path
import sys
import argparse
import datetime
from logging import getLogger

from midisampling.logging_management import init_logging_from_config

from midisampling.sampling import SamplingArguments, ISampling, DefaultSampling, DryRunSampling
from midisampling.appconfig.midi import MidiConfig, load as load_midi_config
from midisampling.appconfig.sampling import SamplingConfig, load as load_samplingconfig
from midisampling.appconfig.audioprocess import AudioProcessConfig
from midisampling.waveprocess.processing import validate_process_config

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
    parser.add_argument("--dry-run", help="Dry run the sampling process.", action="store_true", default=False)

    args = parser.parse_args()

    logfile_path = args.log_file
    if not logfile_path:
        timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logfile_dir  = os.path.dirname(os.path.abspath(args.midi_config_path))
        logfile_path = os.path.join(logfile_dir, f"midi-sampling-{timestamp}.log")

    init_logging_from_config(logfile_path=logfile_path, verbose=args.verbose)
    _log_system_info()

    samplig_args = SamplingArguments(
        sampling_config_path=args.sampling_config_path,
        midi_config_path=args.midi_config_path,
        postprocess_config_path=args.postprocess_config_path,
        overwrite_recorded=args.overwrite_recorded
    )

    sampling_config: SamplingConfig = load_samplingconfig(args.sampling_config_path)
    midi_config: MidiConfig = load_midi_config(args.midi_config_path)

    postprocess_config: AudioProcessConfig = None
    if args.postprocess_config_path:
        postprocess_config = AudioProcessConfig(args.postprocess_config_path)
        validate_process_config(postprocess_config)

    sampling: ISampling = None

    if args.dry_run:
        sampling = DryRunSampling(
            sampling_config=sampling_config,
            midi_config=midi_config,
            postprocess_config=postprocess_config,
            overwrite_recorded=args.overwrite_recorded
        )
    else:
        sampling = DefaultSampling(
            sampling_config=sampling_config,
            midi_config=midi_config,
            postprocess_config=postprocess_config,
            overwrite_recorded=args.overwrite_recorded)

    try:
        sampling.initialize()
        sampling.execute()
    except Exception as e:
        logger.error(e, exc_info=True)
    finally:
        try:
            sampling.dispose()
        except Exception as e:
            logger.error(e, exc_info=True)
        logger.debug("End")

    return

    if args.dry_run:
        from midisampling.dryrun import execute as dry_run
        try:
            dry_run(args=samplig_args)
        except Exception as e:
            logger.error(e, exc_info=True)
        finally:
            logger.debug("End")
        return

    from midisampling.sampling import main as sampling_main
    try:
        sampling_main(args=samplig_args)
    except Exception as e:
        logger.error(e, exc_info=True)
    finally:
        logger.debug("End")

if __name__ == '__main__':
    main()
