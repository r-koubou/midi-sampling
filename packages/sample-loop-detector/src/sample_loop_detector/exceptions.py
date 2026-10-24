"""Application exception hierarchy.

CLI code translates these into process exit codes; analysis code never
calls ``sys.exit`` directly.
"""


class LoopDetectorError(Exception):
    """Base class for all application errors."""


class InvalidWaveError(LoopDetectorError):
    """The input file is not a valid or supported RIFF/WAVE file."""


class UnsupportedWaveFormatError(InvalidWaveError):
    """The WAV file is structurally valid but uses an unsupported format."""


class SustainNotFoundError(LoopDetectorError):
    """No sufficiently stable sustain region was found."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class LoopCandidateNotFoundError(LoopDetectorError):
    """No acceptable loop candidate was found."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class InvalidArgumentsError(LoopDetectorError):
    """Command-line arguments are inconsistent with the input file."""


class ExistingSmplChunkError(LoopDetectorError):
    """The input already contains an ``smpl`` chunk and replacement was not requested."""


class WaveWriteError(LoopDetectorError):
    """Writing the output WAV file failed."""
