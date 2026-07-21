from dataclasses import dataclass
from pathlib import Path

from midi_sampling.sampling.planning.sampling_target import SamplingTarget

MANIFEST_FILENAME = "manifest.yaml"
WAV_SUFFIX = ".wav"
PARTIAL_SUFFIX = ".part"


@dataclass(frozen=True)
class ZoneSpec:
    low: int
    root: int
    high: int


@dataclass(frozen=True)
class VelocityLayerSpec:
    low: int
    high: int
    send: int


@dataclass(frozen=True)
class AudioFormatSpec:
    sample_rate: int
    channels: int
    data_format: str


@dataclass(frozen=True)
class TonePlan:
    """
    Execution plan for a single tone. Targets are in the fixed execution
    order (root_note asc, then velocity_low asc).
    """
    definition_id: str
    name: str | None
    bank_msb: int
    bank_lsb: int
    program: int
    note_on: float
    release_capture: float
    zones: tuple[ZoneSpec, ...]
    velocity_layers: tuple[VelocityLayerSpec, ...]
    resolved_definition_sha256: str
    directory: Path
    manifest_path: Path
    targets: tuple[SamplingTarget, ...]


@dataclass(frozen=True)
class SamplingPlan:
    """
    A fully validated execution plan for one session. The executor and
    the audit service consume this model only; neither of them ever sees
    YAML files or unresolved references.
    """
    channel: int
    initialization_files: tuple[Path, ...]
    program_change_settle: float
    pre_roll: float
    inter_sample_wait: float
    audio_format: AudioFormatSpec
    sample_filename_template: str
    output_root: Path
    tones: tuple[TonePlan, ...]

    def total_recording_seconds(self, target: SamplingTarget) -> float:
        """
        Total recording duration for one target:
        pre_roll + note_on + release_capture
        """
        return self.pre_roll + target.note_on + target.release_capture
