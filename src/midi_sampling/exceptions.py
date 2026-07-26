class MidiSamplingError(Exception):
    """
    Base class for every application error raised by this package.

    The CLI catches this single type so that a new stage can add its own
    error hierarchy without touching the command implementations.
    """
    pass
