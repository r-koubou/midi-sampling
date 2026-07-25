"""
Trim stage settings.

Every field mirrors one field of `wav_silence_trimmer.models.TrimConfig`
explicitly. The settings mapping is never passed through as a raw dict:
an unknown key must fail loudly instead of being silently ignored.

Omitted fields fall back to the DSP package default, which is resolved
before hashing so that the recorded settings hash always describes the
effective configuration.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool

from midi_sampling.postprocess.definitions.field_types import (
    NonNegativeSeconds,
    OptionalDecibels,
    OptionalMilliseconds,
    OptionalPercentage,
    OptionalPositiveMilliseconds,
)

TRIM_SETTING_NAMES = (
    "edge_noise_seconds",
    "frame_ms",
    "hop_ms",
    "noise_percentile",
    "on_margin_db",
    "off_margin_db",
    "minimum_noise_floor_dbfs",
    "minimum_on_ms",
    "bridge_gap_ms",
    "pre_roll_ms",
    "post_roll_ms",
    "fade_in_ms",
    "fade_out_ms",
    "no_fade",
)


class TrimSettingsDefinition(BaseModel):
    """
    Optional overrides for the trimming pipeline. `None` means "use the
    wav-silence-trimmer default".
    """
    model_config = ConfigDict(extra="forbid")

    edge_noise_seconds: NonNegativeSeconds | None = None
    frame_ms: OptionalPositiveMilliseconds = None
    hop_ms: OptionalPositiveMilliseconds = None
    noise_percentile: OptionalPercentage = None
    on_margin_db: OptionalDecibels = None
    off_margin_db: OptionalDecibels = None
    minimum_noise_floor_dbfs: OptionalDecibels = None
    minimum_on_ms: OptionalMilliseconds = None
    bridge_gap_ms: OptionalMilliseconds = None
    pre_roll_ms: OptionalMilliseconds = None
    post_roll_ms: OptionalMilliseconds = None
    fade_in_ms: OptionalMilliseconds = None
    fade_out_ms: OptionalMilliseconds = None
    no_fade: StrictBool | None = None


class TrimStageDefinition(BaseModel):
    """
    `kind: trim` entry of a postprocess session `stages` list.
    """
    model_config = ConfigDict(extra="forbid")

    kind: Literal["trim"]
    settings: TrimSettingsDefinition = TrimSettingsDefinition()
