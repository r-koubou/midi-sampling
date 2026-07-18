"""Custom exception hierarchy for wav-silence-trimmer."""


class WavTrimmerError(Exception):
    """Base class for all wav-silence-trimmer errors."""


class InvalidInputError(WavTrimmerError):
    """The input file or directory is invalid or unreadable."""


class UnsupportedFormatError(WavTrimmerError):
    """The input file is not a supported WAV file."""


class NoSignalDetectedError(WavTrimmerError):
    """No valid signal region was detected in the input audio."""


class OutputExistsError(WavTrimmerError):
    """The output file already exists and overwriting is not allowed."""


class InvalidConfigurationError(WavTrimmerError):
    """The detection or fade configuration values are invalid."""
