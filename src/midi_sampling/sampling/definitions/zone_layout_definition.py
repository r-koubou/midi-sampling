from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from midi_sampling.sampling.definitions.field_types import MidiByte


class ZoneDefinition(BaseModel):
    """
    A single key zone. All values are MIDI note numbers (0-127).
    """
    model_config = ConfigDict(extra="forbid")

    low: MidiByte
    root: MidiByte
    high: MidiByte

    @model_validator(mode="after")
    def _validate_order(self) -> "ZoneDefinition":
        if not (self.low <= self.root <= self.high):
            raise ValueError(
                f"zone must satisfy low <= root <= high, "
                f"got low={self.low}, root={self.root}, high={self.high}"
            )
        return self


class ZoneLayoutDefinition(BaseModel):
    """
    External zone layout preset file. (kind: zone_layout)
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["zone_layout"]
    zones: list[ZoneDefinition] = Field(min_length=1)
