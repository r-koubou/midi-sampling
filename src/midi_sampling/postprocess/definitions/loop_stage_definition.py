"""
Loop detection stage settings.

Every field mirrors one field of `sample_loop_detector.config.DetectionSettings`
explicitly, except for the input/output paths which this package owns.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from midi_sampling.postprocess.definitions.field_types import (
    OptionalFrequencyHz,
    OptionalPositiveInt,
    OptionalSeconds,
    OptionalUnitInterval,
)
from midi_sampling.sampling.definitions.field_types import MidiByte

FROM_MANIFEST = "from_manifest"
AUTO = "auto"

MidiUnityNoteSetting = Literal["from_manifest", "auto"] | MidiByte
"""
How to choose the `smpl` chunk unity note.

- `from_manifest`: use `mapping.root_note` of the source manifest. This is
  the whole point of running loop detection inside midi-sampling: the note
  that was actually recorded is known exactly, so pitch estimation cannot
  pick the wrong octave.
- `auto`: let the detector estimate it from the audio.
- 0-127: use a fixed note.
"""

LoopFailureMode = Literal["skip", "error"]
"""
What to do when no acceptable loop is found. Defaults to `skip` because
"no loop" is a legitimate result for percussive or fully decaying tones.
"""

LOOP_SETTING_NAMES = (
    "search_start",
    "search_end",
    "min_sustain",
    "min_loop",
    "max_loop",
    "fmin",
    "fmax",
    "crossfade_lengths_ms",
    "top_k",
    "quality_threshold",
    "midi_unity_note",
    "replace_existing_loop",
)


class LoopSettingsDefinition(BaseModel):
    """
    Optional overrides for loop detection. `None` means "use the
    sample-loop-detector default".
    """
    model_config = ConfigDict(extra="forbid")

    search_start: OptionalSeconds = None
    search_end: OptionalSeconds = None
    min_sustain: OptionalSeconds = None
    min_loop: OptionalSeconds = None
    max_loop: OptionalSeconds = None
    fmin: OptionalFrequencyHz = None
    fmax: OptionalFrequencyHz = None
    crossfade_lengths_ms: list[float] | None = Field(default=None, min_length=1)
    top_k: OptionalPositiveInt = None
    quality_threshold: OptionalUnitInterval = None
    midi_unity_note: MidiUnityNoteSetting = FROM_MANIFEST
    replace_existing_loop: StrictBool | None = None


class LoopStageDefinition(BaseModel):
    """
    `kind: loop` entry of a postprocess session `stages` list.
    """
    model_config = ConfigDict(extra="forbid")

    kind: Literal["loop"]
    on_failure: LoopFailureMode = "skip"
    settings: LoopSettingsDefinition = LoopSettingsDefinition()
