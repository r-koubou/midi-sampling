from midi_sampling.exceptions import MidiSamplingError


class SamplingError(MidiSamplingError):
    """
    Base class for all application errors raised by the sampling package.
    """
    pass


class DefinitionLoadError(SamplingError):
    """
    Raised when a YAML definition file cannot be read or parsed.
    """
    pass


class DefinitionValidationError(SamplingError):
    """
    Raised when a YAML definition violates the schema or value constraints.
    """
    pass


class DefinitionReferenceError(SamplingError):
    """
    Raised when an external file reference is invalid.
    (e.g. missing file, wrong kind, absolute path, URL, glob etc.)
    """
    pass


class InvalidZoneLayoutError(SamplingError):
    """
    Raised when a zone layout violates semantic constraints.
    (e.g. low <= root <= high, overlapping zones)
    """
    pass


class InvalidVelocityProfileError(SamplingError):
    """
    Raised when a velocity profile violates semantic constraints.
    (e.g. gaps, overlaps, incomplete coverage of 1-127)
    """
    pass


class DuplicateDefinitionIdError(SamplingError):
    """
    Raised when two sampling definitions in a session share the same id.
    """
    pass


class InvalidFilenameTemplateError(SamplingError):
    """
    Raised when a sample filename template is malformed or uses
    unknown placeholders.
    """
    pass


class DuplicateOutputFilenameError(SamplingError):
    """
    Raised when two sampling targets resolve to the same output filename
    within one tone directory.
    """
    pass


class InvalidOutputPathError(SamplingError):
    """
    Raised when a generated output path is unusable on the current OS.
    (e.g. reserved device names, forbidden characters, too long)
    """
    pass


class ExistingOutputError(SamplingError):
    """
    Raised when the output directory, manifest or a target WAV already
    exists. The initial implementation never overwrites silently.
    """
    pass


class ManifestReadError(SamplingError):
    """
    Raised when an existing manifest cannot be read or fails validation.
    """
    pass


class ManifestWriteError(SamplingError):
    """
    Raised when a manifest cannot be written atomically.
    """
    pass


class DefinitionHashMismatchError(SamplingError):
    """
    Raised when the stored resolved definition hash differs from the
    current one in a context where this is fatal.
    """
    pass


class SamplingExecutionError(SamplingError):
    """
    Raised when MIDI control or audio recording fails during execution.
    """
    pass
