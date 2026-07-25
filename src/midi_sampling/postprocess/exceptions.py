from midi_sampling.exceptions import MidiSamplingError


class PostprocessError(MidiSamplingError):
    """
    Base class for all application errors raised by the postprocess package.
    """
    pass


class PostprocessDefinitionError(PostprocessError):
    """
    Raised when a postprocess session definition cannot be read, fails
    schema validation or violates a semantic constraint.
    """
    pass


class PostprocessSourceError(PostprocessError):
    """
    Raised when the sampling output used as input is missing, incomplete
    or inconsistent. (e.g. missing tone directory, manifest not
    completed, missing source WAV)
    """
    pass


class PostprocessDependencyError(PostprocessError):
    """
    Raised when an enabled stage needs an optional DSP package that is
    not installed.
    """
    pass


class PostprocessStageError(PostprocessError):
    """
    Raised when a stage fails to process one sample.
    """
    pass


class PostprocessExistingOutputError(PostprocessError):
    """
    Raised when a tone output directory already exists. Existing derived
    output is never overwritten, deleted or resumed automatically.
    """
    pass


class PostprocessExecutionError(PostprocessError):
    """
    Raised when postprocessing fails for a reason that is not attributable
    to a single stage.
    """
    pass


class PostprocessManifestReadError(PostprocessError):
    """
    Raised when an existing derived manifest cannot be read or fails
    validation.
    """
    pass


class PostprocessManifestWriteError(PostprocessError):
    """
    Raised when a derived manifest cannot be written atomically.
    """
    pass
