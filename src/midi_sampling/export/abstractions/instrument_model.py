from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TriggerMode = Literal["attack", "release"]


@dataclass(frozen=True)
class RegionLoop:
    """
    Sustain loop in frames of the exported audio file. `end_frame` is
    inclusive, the same convention as the `smpl` chunk the loop stage
    wrote and as the SFZ `loop_end` opcode.
    """
    start_frame: int
    end_frame: int


@dataclass(frozen=True)
class InstrumentRegion:
    """
    One key/velocity region of the instrument, fully resolved and
    sampler-agnostic. `sample_path` is the POSIX-style path of the audio
    file relative to the patch file inside the output directory.
    """
    tone_id: str
    source_path: Path
    sample_path: str
    root_note: int
    key_low: int
    key_high: int
    velocity_low: int
    velocity_high: int
    loop: RegionLoop | None
    exclusive_group: int | None
    trigger: TriggerMode
    rt_decay: float | None


@dataclass(frozen=True)
class InstrumentExclusiveGroup:
    """
    A choke group. `number` is the sampler-agnostic integer id shared by
    every member region; writers map it onto their native concept
    (SFZ group/off_by, Falcon mute group, KONTAKT voice group).
    """
    number: int
    name: str


@dataclass(frozen=True)
class InstrumentEnvelope:
    """
    Patch-wide amplitude envelope in seconds. Writers whose format
    supports an envelope apply it globally, converting the unit when the
    format is not second-based.
    """
    attack: float
    release: float


@dataclass(frozen=True)
class InstrumentModel:
    """
    Sampler-independent description of one instrument patch. Writers
    consume this model only and never read YAML or manifests themselves.
    """
    name: str
    envelope: InstrumentEnvelope
    regions: tuple[InstrumentRegion, ...]
    exclusive_groups: tuple[InstrumentExclusiveGroup, ...]
