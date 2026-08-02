from dataclasses import dataclass
from pathlib import Path

from midi_sampling.export.abstractions import InstrumentModel
from midi_sampling.export.definitions import AudioFormat

SAMPLES_DIRECTORY_NAME = "Samples"
INSTRUMENTS_DIRECTORY_NAME = "Instruments"

# One step from a patch file towards the output root. A patch lives in
# `<root>/<INSTRUMENTS_DIRECTORY_NAME>/<subdirectory…>/`, so a sample
# reference inside a patch repeats this once per level; the depth is the
# caller's to decide (see `ExportPlanBuilder._sample_reference_path`).
PATCH_TO_ROOT_STEP = ".."


@dataclass(frozen=True)
class AudioExportTask:
    """
    One audio file to write into the patch output directory.
    `relative_path` is POSIX-style, relative to the output root (the
    per-format directory that holds both `Samples/` and `Instruments/`).
    """
    source_path: Path
    relative_path: str
    data_format: str


@dataclass(frozen=True)
class ExportPlan:
    """
    A fully resolved export: the sampler-agnostic instrument model plus
    the audio files it references. No YAML structures are held here.

    `patch_subdirectory` is where the patch goes below `Instruments/`,
    already validated; empty means directly in `Instruments/`.
    """
    instrument: InstrumentModel
    audio_format: AudioFormat
    bit_depth: int | None
    audio_tasks: tuple[AudioExportTask, ...]
    patch_subdirectory: tuple[str, ...] = ()
