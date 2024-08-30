import os.path
import sys
import argparse
import datetime
from logging import getLogger

from midisampling.logging_management import init_logging_from_config, OutputMode

from midisampling.sampling import ISampling, DefaultSampling, DryRunSampling
from midisampling.appconfig.midi import MidiConfig, load as load_midi_config
from midisampling.appconfig.sampling import SamplingConfig, load as load_samplingconfig
from midisampling.appconfig.audioprocess import AudioProcessConfig
from midisampling.waveprocess.processing import validate_effect_config

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
    parser.add_argument("sampling_config_path", help="Path to the sampling configuration file.")
    parser.add_argument("midi_config_path", help="Path to the MIDI configuration file.")
    parser.add_argument("postprocess_config_path", help="Path to the process configuration file for post processing.", default=None, nargs="?")
    parser.add_argument("-l", "--log-file", help="Path to save the log file.")
    parser.add_argument("--overwrite-recorded", help="Overwrite recorded file if it exists.", action="store_true", default=False)
    parser.add_argument("--dry-run", help="Dry run the sampling process.", action="store_true", default=False)

    log_level_group = parser.add_mutually_exclusive_group()
    log_level_group.add_argument("-v", "--verbose", help="Enable verbose logging.", action="store_true")
    log_level_group.add_argument("-q", "--quiet", help="Quiet mode. Only error messages are output.", action="store_true")

    args = parser.parse_args()

    #----------------------------------------------------------------
    # Initialize logging
    #----------------------------------------------------------------
    logfile_path = args.log_file
    if not logfile_path:
        timestamp    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logfile_dir  = os.path.dirname(os.path.abspath(args.midi_config_path))
        logfile_path = os.path.join(logfile_dir, f"midi-sampling-{timestamp}.log")

    output_mode = OutputMode.Default
    if args.verbose:
        output_mode = OutputMode.Verbose
    elif args.quiet:
        output_mode = OutputMode.Quiet

    init_logging_from_config(logfile_path=logfile_path, output_mode=output_mode)
    _log_system_info()

    #----------------------------------------------------------------
    # Load config
    #----------------------------------------------------------------

    # Sampling config
    try:
        logger.info(f"Load sampling config: {args.sampling_config_path}")
        sampling_config: SamplingConfig = load_samplingconfig(args.sampling_config_path)

    except Exception as e:
        logger.error(f"Failed to load sampling config: {args.sampling_config_path}")
        logger.error(e, exc_info=True)
        sys.exit(1)

    # MIDI config
    try:
        logger.info(f"Load MIDI config: {args.midi_config_path}")
        midi_config: MidiConfig = load_midi_config(args.midi_config_path)

    except Exception as e:
        logger.faerrortal(f"Failed to load MIDI config: {args.midi_config_path}")
        logger.error(e, exc_info=True)
        sys.exit(1)

    # Postprocess config
    try:
        postprocess_config: AudioProcessConfig = None
        if args.postprocess_config_path:
            logger.info(f"Load postprocess config: {args.postprocess_config_path}")
            postprocess_config = AudioProcessConfig(args.postprocess_config_path)
            validate_effect_config(postprocess_config)
        else:
            logger.info("Postprocess config is not specified. Postprocess will not be performed.")

    except Exception as e:
        logger.error(f"Failed to load postprocess config: {args.postprocess_config_path}")
        logger.error(e, exc_info=True)
        sys.exit(1)

    #----------------------------------------------------------------
    # Sampling
    #----------------------------------------------------------------
    try:
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

        sampling.initialize()
        sampling.execute()

    except Exception as e:
        logger.error(e, exc_info=True)
        sys.exit(1)

    finally:
        try:
            sampling.dispose()
        except Exception as e:
            logger.error(e, exc_info=True)
        logger.debug("End")

    return

if __name__ == '__main__':
    main()
