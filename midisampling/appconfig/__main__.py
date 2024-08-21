import sys
import traceback
import argparse

from midisampling.appconfig import midi as midi_conf
from midisampling.appconfig import sampling as sampling_conf


def main() -> None:

    parser = argparse.ArgumentParser(prog=f"python -m {__package__}")
    parser.add_argument("-v", "--verbose", help="Enable verbose logging.", action="store_true")

    # Command per processing
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Validate validate-sampling
    validate_sampling_parser = subparsers.add_parser("validate-sampling", help="Test validation and deserialization of setting file.")
    validate_sampling_parser.add_argument("input", help="Path to the input setting file.")

    # Validate midi-config
    validate_midi_parser = subparsers.add_parser("validate-midi", help="Test validation and deserialization of setting file.")
    validate_midi_parser.add_argument("input", help="Path to the input setting file.")

    args = parser.parse_args()

    # Process
    try:
        if args.command == "validate-sampling":
            sampling_conf.validate(args.input)
            print("Validation OK")
            sampling_conf.SamplingConfig(args.input)
            print("Deserialization OK")

        elif args.command == "validate-midi":
            midi_conf.validate(args.input)
            print("Validation OK")
            midi_conf.MidiConfig(args.input)
            print("Deserialization OK")

    except Exception as e:
        print(e)
        if args.verbose:
            (_, _, trace) = sys.exc_info()
            traceback.print_tb(trace)


if __name__ == '__main__':
    main()