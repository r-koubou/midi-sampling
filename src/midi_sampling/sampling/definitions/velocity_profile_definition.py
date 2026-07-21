from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from midi_sampling.sampling.definitions.field_types import MidiVelocity


class VelocityLayerDefinition(BaseModel):
    """
    A single velocity layer. All values are MIDI velocities (1-127).
    Velocity 0 means Note Off and is not allowed.
    """
    model_config = ConfigDict(extra="forbid")

    low: MidiVelocity
    high: MidiVelocity
    send: MidiVelocity

    @model_validator(mode="after")
    def _validate_order(self) -> "VelocityLayerDefinition":
        if not (self.low <= self.send <= self.high):
            raise ValueError(
                f"velocity layer must satisfy low <= send <= high, "
                f"got low={self.low}, send={self.send}, high={self.high}"
            )
        return self


class VelocityProfileDefinition(BaseModel):
    """
    External velocity profile preset file. (kind: velocity_profile)
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["velocity_profile"]
    layers: list[VelocityLayerDefinition] = Field(min_length=1)
