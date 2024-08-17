import sys
from midisampling.sampling import main

if len(sys.argv) < 3:
        print(f"Usage: python -m {__package__} <path/to/sampling-config.json> <path/to/midi-config.json>")
        sys.exit(1)

main(sys.argv[1:])
