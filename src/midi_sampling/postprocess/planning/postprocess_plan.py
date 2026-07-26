import os
from dataclasses import dataclass
from pathlib import Path

from midi_sampling.postprocess.planning.postprocess_target import PostprocessTarget
from midi_sampling.postprocess.stages import PostprocessStage
from midi_sampling.sampling.manifest.sample_manifest import (
    ManifestAudio,
    ManifestMidi,
    ManifestNaming,
    ManifestResolvedDefinition,
)

MANIFEST_FILENAME = "manifest.yaml"


@dataclass(frozen=True)
class TonePostprocessPlan:
    """
    Execution plan for a single tone. Targets are in source manifest
    order (sample index ascending).

    `midi`, `audio`, `naming` and `resolved_definition` are carried over
    from the source manifest so that the derived manifest is self
    contained for patch generation.
    """
    definition_id: str
    name: str | None
    source_directory: Path
    source_manifest_path: Path
    source_manifest_sha256: str
    resolved_definition_sha256: str
    midi: ManifestMidi
    audio: ManifestAudio
    naming: ManifestNaming
    resolved_definition: ManifestResolvedDefinition
    directory: Path
    manifest_path: Path
    work_directory: Path
    targets: tuple[PostprocessTarget, ...]

    def relative_source_directory(self) -> str:
        """
        Source location as a POSIX relative path from this tone's output
        directory, for the `source.directory` manifest field.
        """
        try:
            relative = os.path.relpath(self.source_directory, self.directory)
        except ValueError:
            # Different drives on Windows: fall back to the absolute path.
            return self.source_directory.as_posix()
        return Path(relative).as_posix()


@dataclass(frozen=True)
class PostprocessPlan:
    """
    A fully validated execution plan for one postprocess session. The
    executor consumes this model only; it never sees YAML files or
    unresolved references.
    """
    session_path: Path
    source_root: Path
    output_root: Path
    stages: tuple[PostprocessStage, ...]
    settings_sha256: str
    tones: tuple[TonePostprocessPlan, ...]

    @property
    def stage_kinds(self) -> tuple[str, ...]:
        return tuple(stage.kind for stage in self.stages)

    @property
    def total_sample_count(self) -> int:
        return sum(len(tone.targets) for tone in self.tones)
