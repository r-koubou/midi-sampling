from dataclasses import dataclass
from pathlib import Path

from midi_sampling.postprocess.manifest.postprocess_manifest import (
    ManifestSampleMapping,
)

WAV_SUFFIX = ".wav"
WORK_DIRECTORY_NAME = ".work"


@dataclass(frozen=True)
class PostprocessTarget:
    """
    One WAV to process. Fully resolved: no YAML structures and no
    external references are held here.

    `mapping` is copied from the source manifest, never derived from the
    file name.
    """
    definition_id: str
    sample_index: int
    file_name: str
    source_path: Path
    output_path: Path
    work_directory: Path
    mapping: ManifestSampleMapping

    @property
    def stem(self) -> str:
        return self.file_name[: -len(WAV_SUFFIX)]

    def work_path(self, position: int, stage_kind: str) -> Path:
        """
        Intermediate file for the stage at 1-based `position`.

        The `.wav` suffix is mandatory: libsndfile infers the output
        format from the extension when writing, and handing it anything
        else has already broken this project once (see the sampling
        implementation notes on `*.wav.part`).
        """
        return self.work_directory / f"{self.stem}.s{position}-{stage_kind}{WAV_SUFFIX}"
