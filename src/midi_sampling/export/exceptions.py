from midi_sampling.exceptions import MidiSamplingError


class ExportError(MidiSamplingError):
    """
    Base class for all application errors raised by the export package.
    """
    pass


class ExportDefinitionError(ExportError):
    """
    Raised when an instrument definition cannot be read, fails schema
    validation or violates a semantic constraint.
    """
    pass


class ExportSourceError(ExportError):
    """
    Raised when the postprocess output used as input is missing,
    incomplete or inconsistent. (e.g. missing manifest, manifest not
    completed, missing audio file)
    """
    pass


class ExportAudioError(ExportError):
    """
    Raised when a sample cannot be copied or encoded into the patch
    output directory.
    """
    pass


class ExportWriteError(ExportError):
    """
    Raised when the patch file cannot be written.
    """
    pass


class ExportExistingOutputError(ExportError):
    """
    Raised when the patch output directory already contains files.
    Existing export output is never overwritten or deleted automatically.
    """
    pass
