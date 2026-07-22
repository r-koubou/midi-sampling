from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator
from typing import Literal

from midi_sampling.sampling.definitions.field_types import MidiByte, Seconds
from midi_sampling.sampling.definitions.zone_layout_definition import ZoneDefinition
from midi_sampling.sampling.definitions.velocity_profile_definition import (
    VelocityLayerDefinition,
)

DEFINITION_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class MidiProgramDefinition(BaseModel):
    """
    Bank Select MSB / LSB and Program Change. All fields are required;
    implicit zero-filling of Bank Select is not allowed.
    """
    model_config = ConfigDict(extra="forbid")

    bank_msb: MidiByte
    bank_lsb: MidiByte
    program: MidiByte


class ZoneLayoutReference(BaseModel):
    """
    Zone layout given either as an external file reference or inline.
    Exactly one of `file` / `zones` must be present.
    """
    model_config = ConfigDict(extra="forbid")

    file: StrictStr | None = None
    zones: list[ZoneDefinition] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_exclusive(self) -> "ZoneLayoutReference":
        if (self.file is None) == (self.zones is None):
            raise ValueError("zone_layout requires exactly one of 'file' or 'zones'")
        return self


class VelocityProfileReference(BaseModel):
    """
    Velocity profile given either as an external file reference or inline.
    Exactly one of `file` / `layers` must be present.
    """
    model_config = ConfigDict(extra="forbid")

    file: StrictStr | None = None
    layers: list[VelocityLayerDefinition] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_exclusive(self) -> "VelocityProfileReference":
        if (self.file is None) == (self.layers is None):
            raise ValueError(
                "velocity_profile requires exactly one of 'file' or 'layers'"
            )
        return self


class ToneTimingDefinition(BaseModel):
    """
    Tone specific timing in seconds.

    - note_on:         seconds between Note On and Note Off.
    - release_capture: seconds to keep recording after Note Off.
    """
    model_config = ConfigDict(extra="forbid")

    note_on: Seconds
    release_capture: Seconds


class SamplingDefinition(BaseModel):
    """
    A single tone sampling definition file. (kind: sampling_definition)
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["sampling_definition"]

    id: StrictStr = Field(pattern=DEFINITION_ID_PATTERN)
    name: StrictStr | None = None

    midi_program: MidiProgramDefinition
    zone_layout: ZoneLayoutReference
    velocity_profile: VelocityProfileReference
    timing: ToneTimingDefinition
