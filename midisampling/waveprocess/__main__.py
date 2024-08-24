from typing import List
import sys
import traceback
import argparse

from midisampling.waveprocess import normalize
from midisampling.waveprocess import trim

from midisampling.exportpath import RecordedAudioPath
from midisampling.appconfig.audioprocess import AudioProcessConfig
from midisampling.waveprocess.processing import process
from midisampling.waveprocess.processing import validate_process_config

from midisampling.logging_management import init_logging_as_stdout

def main() -> None:

    parser = argparse.ArgumentParser(prog=f"python -m {__package__}")
    parser.add_argument("-v", "--verbose", help="Enable verbose logging.", action="store_true")
    parser.add_argument("processing_config_path", help="Path to the processing configuration file.")
    parser.add_argument("input_directory", help="Path to the input directory with audio files (*.wav).")
    parser.add_argument("output_directory", help="Path to the output directory to save the processed audio files.")

    args = parser.parse_args()

    init_logging_as_stdout(args.verbose)

    try:
        process_config = AudioProcessConfig(args.processing_config_path)
        validate_process_config(process_config)

        sources: List[RecordedAudioPath] = RecordedAudioPath.from_directory(args.input_directory)

        for i in sources:
            print(i)

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
