"""
Shared pydantic field types for sampling definition models.

- MIDI values are validated as strict integers. bool is rejected.
- Time values accept int or float from YAML, are normalized to float,
  and must be finite (NaN / +-inf are rejected).
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, Field, StrictInt


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("bool is not accepted as an integer value")
    return value


def _to_finite_float(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("bool is not accepted as a time value")
    if not isinstance(value, (int, float)):
        raise ValueError("time value must be an integer or a floating point number")
    return float(value)


MidiByte = Annotated[StrictInt, BeforeValidator(_reject_bool), Field(ge=0, le=127)]
"""MIDI data byte: 0-127."""

MidiVelocity = Annotated[StrictInt, BeforeValidator(_reject_bool), Field(ge=1, le=127)]
"""Sampling velocity: 1-127. Velocity 0 means Note Off and is not allowed."""

MidiChannel = Annotated[StrictInt, BeforeValidator(_reject_bool), Field(ge=0, le=15)]
"""MIDI channel: 0-15."""

Seconds = Annotated[
    float,
    BeforeValidator(_to_finite_float),
    Field(ge=0, allow_inf_nan=False),
]
"""Non-negative finite time value in seconds."""
