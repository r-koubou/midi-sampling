from importlib import metadata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from midi_sampling.sampling.planning import SamplingPlan, TonePlan

ToneStatus = Literal["pending", "in_progress", "completed", "failed"]
SampleStatus = Literal["pending", "completed", "failed"]


def application_version() -> str:
    try:
        return metadata.version("midi-sampling")
    except metadata.PackageNotFoundError:
        return "0.0.0"


class ManifestDefinitionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str | None = None


class ManifestProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_version: str
    resolved_definition_sha256: str


class ManifestMidi(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: int = Field(ge=0, le=15)
    bank_msb: int = Field(ge=0, le=127)
    bank_lsb: int = Field(ge=0, le=127)
    program: int = Field(ge=0, le=127)


class ManifestAudio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    data_format: str


class ManifestTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program_change_settle: float = Field(ge=0)
    pre_roll: float = Field(ge=0)
    note_on: float = Field(ge=0)
    release_capture: float = Field(ge=0)
    inter_sample_wait: float = Field(ge=0)


class ManifestNaming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_filename: str


class ManifestZone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: int = Field(ge=0, le=127)
    root: int = Field(ge=0, le=127)
    high: int = Field(ge=0, le=127)


class ManifestVelocityLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: int = Field(ge=1, le=127)
    high: int = Field(ge=1, le=127)
    send: int = Field(ge=1, le=127)


class ManifestResolvedDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: list[ManifestZone]
    velocity_layers: list[ManifestVelocityLayer]


class ManifestSampleMapping(BaseModel):
    """
    Mapping information intended for the sampler that will consume the
    generated samples.
    """
    model_config = ConfigDict(extra="forbid")

    root_note: int = Field(ge=0, le=127)
    key_low: int = Field(ge=0, le=127)
    key_high: int = Field(ge=0, le=127)
    velocity_low: int = Field(ge=1, le=127)
    velocity_high: int = Field(ge=1, le=127)


class ManifestSampleCaptured(BaseModel):
    """
    What was actually sent to the MIDI sound module during recording.
    """
    model_config = ConfigDict(extra="forbid")

    note: int = Field(ge=0, le=127)
    velocity: int = Field(ge=1, le=127)
    note_on: float = Field(ge=0)
    release_capture: float = Field(ge=0)


class ManifestSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    file: str
    status: SampleStatus
    mapping: ManifestSampleMapping
    captured: ManifestSampleCaptured


class ManifestError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str


class SampleManifest(BaseModel):
    """
    Per-tone manifest. Generated and updated by the sampling program.
    Later tools must be able to rebuild the full mapping from this file
    alone, without parsing WAV filenames.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["sample_manifest"]

    status: ToneStatus

    definition: ManifestDefinitionInfo
    provenance: ManifestProvenance
    midi: ManifestMidi
    audio: ManifestAudio
    timing: ManifestTiming
    naming: ManifestNaming
    resolved_definition: ManifestResolvedDefinition
    samples: list[ManifestSample]
    error: ManifestError | None = None


def create_initial_manifest(plan: SamplingPlan, tone: TonePlan) -> SampleManifest:
    """
    Build the initial (all pending) manifest for one tone of a plan.
    """
    return SampleManifest(
        schema_version=1,
        kind="sample_manifest",
        status="pending",
        definition=ManifestDefinitionInfo(id=tone.definition_id, name=tone.name),
        provenance=ManifestProvenance(
            application_version=application_version(),
            resolved_definition_sha256=tone.resolved_definition_sha256,
        ),
        midi=ManifestMidi(
            channel=plan.channel,
            bank_msb=tone.bank_msb,
            bank_lsb=tone.bank_lsb,
            program=tone.program,
        ),
        audio=ManifestAudio(
            sample_rate=plan.audio_format.sample_rate,
            channels=plan.audio_format.channels,
            data_format=plan.audio_format.data_format,
        ),
        timing=ManifestTiming(
            program_change_settle=plan.program_change_settle,
            pre_roll=plan.pre_roll,
            note_on=tone.note_on,
            release_capture=tone.release_capture,
            inter_sample_wait=plan.inter_sample_wait,
        ),
        naming=ManifestNaming(sample_filename=plan.sample_filename_template),
        resolved_definition=ManifestResolvedDefinition(
            zones=[
                ManifestZone(low=zone.low, root=zone.root, high=zone.high)
                for zone in tone.zones
            ],
            velocity_layers=[
                ManifestVelocityLayer(
                    low=layer.low, high=layer.high, send=layer.send
                )
                for layer in tone.velocity_layers
            ],
        ),
        samples=[
            ManifestSample(
                index=target.sample_index,
                file=target.file_name,
                status="pending",
                mapping=ManifestSampleMapping(
                    root_note=target.root_note,
                    key_low=target.key_low,
                    key_high=target.key_high,
                    velocity_low=target.velocity_low,
                    velocity_high=target.velocity_high,
                ),
                captured=ManifestSampleCaptured(
                    note=target.root_note,
                    velocity=target.send_velocity,
                    note_on=target.note_on,
                    release_capture=target.release_capture,
                ),
            )
            for target in tone.targets
        ],
    )
