from dataclasses import dataclass
from pathlib import Path

from midi_sampling.export.abstractions import InstrumentModel
from midi_sampling.export.definitions import AudioFormat

SAMPLES_DIRECTORY_NAME = "Samples"


@dataclass(frozen=True)
class AudioExportTask:
    """
    One audio file to write into the patch output directory.
    `relative_path` is POSIX-style, relative to the output directory.
    """
    source_path: Path
    relative_path: str
    data_format: str


@dataclass(frozen=True)
class ExportPlan:
    """
    A fully resolved export: the sampler-agnostic instrument model plus
    the audio files it references. No YAML structures are held here.
    """
    instrument: InstrumentModel
    audio_format: AudioFormat
    bit_depth: int | None
    audio_tasks: tuple[AudioExportTask, ...]
