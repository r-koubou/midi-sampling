import abc
from dataclasses import dataclass
from pathlib import Path

from midi_sampling.export.abstractions.instrument_model import InstrumentModel


@dataclass(frozen=True)
class PatchWriteContext:
    """
    Everything a writer needs to emit one patch file. The patch goes
    into `patch_directory`; the audio files have already been written
    when a writer runs and are reachable by joining `patch_directory`
    with each region's `sample_path`.
    """
    instrument: InstrumentModel
    patch_directory: Path


@dataclass(frozen=True)
class PatchWriteOutcome:
    patch_path: Path


class InstrumentPatchWriter(metaclass=abc.ABCMeta):
    """
    One sampler patch format. Implementations translate the
    sampler-agnostic InstrumentModel into their native file format and
    must not modify anything outside the output directory.

    An abstract base class (not a Protocol) on purpose: implementing a
    format must be visible as explicit inheritance, so that a class
    that merely happens to have a `write` method is never mistaken for
    a patch writer.
    """

    @property
    @abc.abstractmethod
    def format_id(self) -> str:
        """
        Identifier of the patch format, as accepted by the CLI
        `--format` option and `create_patch_writer`.
        """
        ...

    @property
    def directory_name(self) -> str:
        """
        Name of the per-format subdirectory in the output layout
        `<output root>/<directory_name>/{Samples,Instruments}/`. Defaults
        to `format_id`; a format may override it when its conventional
        directory name differs from the CLI identifier.
        """
        return self.format_id

    @property
    def supported_audio_formats(self) -> tuple[str, ...] | None:
        """
        Audio formats the target sampler can load, or None when the
        format has no restriction. When the instrument definition asks
        for an unsupported format, the export plan falls back to the
        first entry with a warning instead of failing.
        """
        return None

    @abc.abstractmethod
    def write(self, context: PatchWriteContext) -> PatchWriteOutcome:
        ...
