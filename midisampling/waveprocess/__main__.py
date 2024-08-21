import sys
import traceback
import argparse

from midisampling.waveprocess import normalize
from midisampling.waveprocess import trim

from midisampling.logging_management import init_logging_as_stdout

def main() -> None:
    parser = argparse.ArgumentParser(prog=f"python -m {__package__}")
    parser.add_argument("-v", "--verbose", help="Enable verbose logging.", action="store_true")

    # Command per processing
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Normalize
    normalize_parser = subparsers.add_parser("normalize")
    normalize_parser.add_argument("input_directory", help="Path to the input directory with audio files (*.wav).")
    normalize_parser.add_argument("output_directory", help="Path to the output directory to save the normalized audio files.")
    normalize_parser.add_argument("target_db", type=float, help="Target decibel level for normalization.")

    # Trim
    trim_parser = subparsers.add_parser("trim")
    trim_parser.add_argument("input_directory", help="Path to the input directory with audio files (*.wav).")
    trim_parser.add_argument("output_directory", help="Path to the output directory to save the trimmed audio files.")
    trim_parser.add_argument("threshold", type=float, help="Threshold for trimming silence. (db)")
    trim_parser.add_argument("min_silence", type=int, help="Minimum silence duration to be trimmed. (msec)")


    args = parser.parse_args()

    try:
        init_logging_as_stdout(verbose=args.verbose)

        # Process

        if args.command == "normalize":
            normalize.normalize_across_mitiple(
                input_directory=args.input_directory,
                output_directory=args.output_directory,
                target_peak_dBFS=args.target_db
            )
        elif args.command == "trim":
            trim.batch_trim(
                input_directory=args.input_directory,
                output_directory=args.output_directory,
                threshold_dBFS=args.threshold,
                min_silence_ms=args.min_silence
            )
    except Exception as e:
        print(e)
        if args.verbose:
            (_, _, trace) = sys.exc_info()
            traceback.print_tb(trace)

if __name__ == '__main__':
    main()
