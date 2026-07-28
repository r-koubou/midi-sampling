from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from midi_sampling.export.definitions.field_types import (
    NonNegativeSeconds,
    OptionalDecayDbPerSecond,
)
from midi_sampling.sampling.definitions.field_types import MidiByte

AudioFormat = Literal["wav", "flac"]

_FORBIDDEN_NAME_CHARACTERS = '\\/:*?"<>|'

DEFAULT_ENVELOPE_ATTACK = 0.0
DEFAULT_ENVELOPE_RELEASE = 0.3


class EnvelopeDefinition(BaseModel):
    """
    Patch-wide amplitude envelope defaults, in seconds (the unit every
    time value of this project uses). Writers map them onto the target
    format when it supports an envelope, converting the unit if needed.
    """
    model_config = ConfigDict(extra="forbid")

    attack: NonNegativeSeconds = DEFAULT_ENVELOPE_ATTACK
    release: NonNegativeSeconds = DEFAULT_ENVELOPE_RELEASE


class AudioSettingsDefinition(BaseModel):
    """
    Audio format of the exported samples. The default is a byte-exact
    WAV copy, which also preserves the `smpl` loop chunk.
    """
    model_config = ConfigDict(extra="forbid")

    format: AudioFormat = "wav"
    bit_depth: Literal[16, 24] | None = None

    @model_validator(mode="after")
    def _bit_depth_requires_flac(self) -> "AudioSettingsDefinition":
        if self.bit_depth is not None and self.format != "flac":
            raise ValueError("audio.bit_depth is only supported for format: flac")
        return self


class SourceReference(BaseModel):
    """
    One tone of the postprocess output. `manifest` is relative to the
    instrument definition file and must point at a postprocess manifest;
    sampling manifests under recorded/ are not accepted.
    """
    model_config = ConfigDict(extra="forbid")

    tone: StrictStr
    manifest: StrictStr


class ExclusiveGroupMember(BaseModel):
    """
    A member of a choke group. Omitting `root_note` selects every region
    of the tone.
    """
    model_config = ConfigDict(extra="forbid")

    tone: StrictStr
    root_note: MidiByte | None = None


class ExclusiveGroupDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    members: list[ExclusiveGroupMember] = Field(min_length=2)

    @model_validator(mode="after")
    def _reject_duplicate_members(self) -> "ExclusiveGroupDefinition":
        seen: set[tuple[str, int | None]] = set()
        for member in self.members:
            key = (member.tone, member.root_note)
            if key in seen:
                raise ValueError(
                    f"duplicate member in exclusive group {self.name!r}: "
                    f"tone {member.tone!r}, root_note {member.root_note!r}"
                )
            seen.add(key)
        return self


class ReleaseTriggerSide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: StrictStr


class ReleaseTriggerDefinition(BaseModel):
    """
    Every region of the `plays` tone becomes a release-triggered region.
    A tone referenced as `plays` is exported as release regions only.
    """
    model_config = ConfigDict(extra="forbid")

    trigger_of: ReleaseTriggerSide
    plays: ReleaseTriggerSide
    rt_decay: OptionalDecayDbPerSecond = None


class InstrumentDefinition(BaseModel):
    """
    Instrument definition file. (kind: instrument_definition)

    The hand-written third layer on top of the generated manifests: it
    declares which processed tones form one instrument and the
    relations between samples (choke groups, release triggers) that no
    single recording can express. It never modifies the manifests it
    references.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["instrument_definition"]

    name: StrictStr
    audio: AudioSettingsDefinition = Field(default_factory=AudioSettingsDefinition)
    envelope: EnvelopeDefinition = Field(default_factory=EnvelopeDefinition)
    sources: list[SourceReference] = Field(min_length=1)
    exclusive_groups: list[ExclusiveGroupDefinition] = Field(default_factory=list)
    release_triggers: list[ReleaseTriggerDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_name(self) -> "InstrumentDefinition":
        if self.name.strip() == "":
            raise ValueError("name must not be empty")
        forbidden = [c for c in _FORBIDDEN_NAME_CHARACTERS if c in self.name]
        if forbidden:
            raise ValueError(
                f"name is used as a file name and must not contain "
                f"{' '.join(repr(c) for c in forbidden)}: {self.name!r}"
            )
        return self

    @model_validator(mode="after")
    def _reject_duplicate_sources(self) -> "InstrumentDefinition":
        seen: set[str] = set()
        for source in self.sources:
            if source.tone in seen:
                raise ValueError(f"duplicate source tone: {source.tone!r}")
            seen.add(source.tone)
        return self

    @model_validator(mode="after")
    def _validate_exclusive_groups(self) -> "InstrumentDefinition":
        declared = self._declared_tones()
        seen_names: set[str] = set()
        for group in self.exclusive_groups:
            if group.name in seen_names:
                raise ValueError(f"duplicate exclusive group name: {group.name!r}")
            seen_names.add(group.name)
            for member in group.members:
                if member.tone not in declared:
                    raise ValueError(
                        f"exclusive group {group.name!r} references tone "
                        f"{member.tone!r} which is not declared in sources"
                    )
        return self

    @model_validator(mode="after")
    def _validate_release_triggers(self) -> "InstrumentDefinition":
        declared = self._declared_tones()
        plays_tones: set[str] = set()
        trigger_tones: set[str] = set()
        for trigger in self.release_triggers:
            for label, tone in (
                ("trigger_of", trigger.trigger_of.tone),
                ("plays", trigger.plays.tone),
            ):
                if tone not in declared:
                    raise ValueError(
                        f"release trigger {label} references tone {tone!r} "
                        f"which is not declared in sources"
                    )
            if trigger.trigger_of.tone == trigger.plays.tone:
                raise ValueError(
                    f"release trigger must connect two different tones, "
                    f"got {trigger.plays.tone!r} for both sides"
                )
            if trigger.plays.tone in plays_tones:
                raise ValueError(
                    f"tone {trigger.plays.tone!r} is referenced by plays "
                    f"more than once"
                )
            plays_tones.add(trigger.plays.tone)
            trigger_tones.add(trigger.trigger_of.tone)

        conflicted = plays_tones & trigger_tones
        if conflicted:
            raise ValueError(
                "tone(s) referenced as both trigger_of and plays: "
                + ", ".join(repr(tone) for tone in sorted(conflicted))
            )
        return self

    def _declared_tones(self) -> set[str]:
        return {source.tone for source in self.sources}
