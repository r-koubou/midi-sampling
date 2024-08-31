from typing import List
import os.path
import sys
import traceback
import argparse
import datetime
from logging import getLogger

from midisampling.waveprocess import normalize
from midisampling.waveprocess import trim

from midisampling.exportpath import RecordedAudioPath
from midisampling.appconfig.audioprocess import AudioProcessConfig
from midisampling.waveprocess.processing import process
from midisampling.waveprocess.processing import validate_effect_config

from midisampling.logging_management import init_logging_from_config, OutputMode

logger = getLogger(__name__)

def main() -> None:

    parser = argparse.ArgumentParser(prog=f"python -m {__package__}")
    parser.add_argument("processing_config_path", help="Path to the processing configuration file.")
    parser.add_argument("input_directory", help="Path to the input directory with audio files (*.wav).")
    parser.add_argument("output_directory", help="Path to the output directory to save the processed audio files.")
    parser.add_argument("-l", "--log-file", help="Path to save the log file.")

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
        logfile_dir  = os.path.dirname(os.path.abspath(args.processing_config_path))
        logfile_path = os.path.join(logfile_dir, f"wave-process-{timestamp}.log")

    output_mode = OutputMode.Default
    if args.verbose:
        output_mode = OutputMode.Verbose
    elif args.quiet:
        output_mode = OutputMode.Quiet

    init_logging_from_config(logfile_path=logfile_path, output_mode=output_mode)

    try:
        process_config = AudioProcessConfig(args.processing_config_path)
        validate_effect_config(process_config)

        sources: List[RecordedAudioPath] = RecordedAudioPath.from_directory(args.input_directory)

        process(
            config=process_config,
            recorded_files=sources,
            output_dir=args.output_directory
        )
    except Exception as e:
        print(e)
        if args.verbose:
            (_, _, trace) = sys.exc_info()
            traceback.print_tb(trace)

    return

if __name__ == '__main__':
    main()
