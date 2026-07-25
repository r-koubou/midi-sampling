from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from midi_sampling.sampling.manifest.sample_manifest import (
    ManifestAudio,
    ManifestDefinitionInfo,
    ManifestError,
    ManifestMidi,
    ManifestNaming,
    ManifestResolvedDefinition,
    application_version,
)

if TYPE_CHECKING:
    from midi_sampling.postprocess.planning import PostprocessPlan, TonePostprocessPlan

ToneStatus = Literal["pending", "in_progress", "completed", "failed"]
SampleStatus = Literal["pending", "completed", "failed"]
LoopStatus = Literal["success", "not_found", "skipped"]

KIND = "postprocess_manifest"
SCHEMA_VERSION = 1


class ManifestProvenance(BaseModel):
    """
    Three independent hashes so that a future audit can tell apart
    "the recording changed", "the tone definition changed" and
    "the postprocess settings changed".
    """
    model_config = ConfigDict(extra="forbid")

    application_version: str
    source_manifest_sha256: str
    resolved_definition_sha256: str
    postprocess_settings_sha256: str
    stages: list[str]


class ManifestSource(BaseModel):
    """
    Where the input came from, relative to this manifest.
    """
    model_config = ConfigDict(extra="forbid")

    directory: str
    manifest: str


class ManifestSampleMapping(BaseModel):
    """
    Mapping information intended for the sampler. Copied verbatim from
    the source manifest so that a patch generator needs this file only.
    """
    model_config = ConfigDict(extra="forbid")

    root_note: int = Field(ge=0, le=127)
    key_low: int = Field(ge=0, le=127)
    key_high: int = Field(ge=0, le=127)
    velocity_low: int = Field(ge=1, le=127)
    velocity_high: int = Field(ge=1, le=127)


class ManifestSampleAudio(BaseModel):
    """
    Measured properties of the processed WAV.
    """
    model_config = ConfigDict(extra="forbid")

    frame_count: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)


class ManifestTrim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applied: bool
    start_sample: int | None = None
    end_sample_exclusive: int | None = None
    removed_head_frames: int | None = None
    removed_tail_frames: int | None = None
    removed_head_seconds: float | None = None
    removed_tail_seconds: float | None = None
    noise_floor_dbfs: float | None = None
    fade_in_frames: int | None = None
    fade_out_frames: int | None = None


class ManifestLoop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applied: bool
    status: LoopStatus
    start_frame: int | None = None
    end_frame: int | None = None
    crossfade_ms: float | None = None
    midi_unity_note: int | None = Field(default=None, ge=0, le=127)
    confidence: float | None = None
    confidence_label: str | None = None
    smpl_chunk_written: bool = False
    detail: str | None = None


class ManifestSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    file: str
    source_file: str
    status: SampleStatus
    mapping: ManifestSampleMapping
    audio: ManifestSampleAudio | None = None
    trim: ManifestTrim | None = None
    loop: ManifestLoop | None = None


class PostprocessManifest(BaseModel):
    """
    Per-tone derived manifest. Generated and updated by the postprocess
    program; never written by hand.

    Later tools must be able to rebuild the full mapping from this file
    alone, without parsing WAV filenames and without reading the source
    manifest.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["postprocess_manifest"]

    status: ToneStatus

    definition: ManifestDefinitionInfo
    provenance: ManifestProvenance
    source: ManifestSource
    midi: ManifestMidi
    audio: ManifestAudio
    naming: ManifestNaming
    resolved_definition: ManifestResolvedDefinition
    samples: list[ManifestSample]
    error: ManifestError | None = None


def create_initial_manifest(
    plan: "PostprocessPlan", tone: "TonePostprocessPlan"
) -> PostprocessManifest:
    """
    Build the initial (all pending) derived manifest for one tone.

    `definition`, `midi`, `audio`, `naming`, `resolved_definition` and
    every `mapping` are copied from the source manifest so that a patch
    generator only ever needs this one file.
    """
    return PostprocessManifest(
        schema_version=SCHEMA_VERSION,
        kind=KIND,
        status="pending",
        definition=ManifestDefinitionInfo(
            id=tone.definition_id, name=tone.name
        ),
        provenance=ManifestProvenance(
            application_version=application_version(),
            source_manifest_sha256=tone.source_manifest_sha256,
            resolved_definition_sha256=tone.resolved_definition_sha256,
            postprocess_settings_sha256=plan.settings_sha256,
            stages=list(plan.stage_kinds),
        ),
        source=ManifestSource(
            directory=tone.relative_source_directory(),
            manifest=tone.source_manifest_path.name,
        ),
        midi=tone.midi,
        audio=tone.audio,
        naming=tone.naming,
        resolved_definition=tone.resolved_definition,
        samples=[
            ManifestSample(
                index=target.sample_index,
                file=target.file_name,
                source_file=target.file_name,
                status="pending",
                mapping=target.mapping,
            )
            for target in tone.targets
        ],
    )


__all__ = [
    "KIND",
    "SCHEMA_VERSION",
    "LoopStatus",
    "ManifestLoop",
    "ManifestProvenance",
    "ManifestSample",
    "ManifestSampleAudio",
    "ManifestSampleMapping",
    "ManifestSource",
    "ManifestTrim",
    "PostprocessManifest",
    "SampleStatus",
    "ToneStatus",
    "application_version",
    "create_initial_manifest",
]
