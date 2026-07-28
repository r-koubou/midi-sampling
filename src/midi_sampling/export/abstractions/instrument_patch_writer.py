import abc
from dataclasses import dataclass
from pathlib import Path

from midi_sampling.export.abstractions.instrument_model import InstrumentModel


@dataclass(frozen=True)
class PatchWriteContext:
    """
    Everything a writer needs to emit one patch file. The audio files
    referenced by the regions have already been written below
    `output_directory` when a writer runs.
    """
    instrument: InstrumentModel
    output_directory: Path


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
        `<output root>/<directory_name>/<patch name>/`. Defaults to
        `format_id`; a format may override it when its conventional
        directory name differs from the CLI identifier.
        """
        return self.format_id

    @abc.abstractmethod
    def write(self, context: PatchWriteContext) -> PatchWriteOutcome:
        ...
