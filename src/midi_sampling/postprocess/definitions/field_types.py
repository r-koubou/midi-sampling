"""
Shared pydantic field types for postprocess definition models.

Follows the same rules as the sampling definitions:
- bool is never accepted as a number.
- Numeric values must be finite; NaN and +-inf are rejected.
- Values are normalized to float so that the settings hash has a single
  representation for `1` and `1.0`.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, Field, StrictInt


def _to_finite_float(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("bool is not accepted as a numeric value")
    if not isinstance(value, (int, float)):
        raise ValueError("value must be an integer or a floating point number")
    return float(value)


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("bool is not accepted as an integer value")
    return value


_FiniteFloat = Annotated[float, BeforeValidator(_to_finite_float)]

NonNegativeSeconds = Annotated[_FiniteFloat, Field(ge=0, allow_inf_nan=False)]
"""Non-negative finite time value in seconds."""

PositiveSeconds = Annotated[_FiniteFloat, Field(gt=0, allow_inf_nan=False)]
"""Positive finite time value in seconds."""

OptionalSeconds = Annotated[_FiniteFloat, Field(ge=0, allow_inf_nan=False)] | None
"""Optional non-negative time value in seconds."""

OptionalMilliseconds = Annotated[_FiniteFloat, Field(ge=0, allow_inf_nan=False)] | None
"""Optional non-negative time value in milliseconds."""

OptionalPositiveMilliseconds = (
    Annotated[_FiniteFloat, Field(gt=0, allow_inf_nan=False)] | None
)
"""Optional positive time value in milliseconds."""

OptionalDecibels = Annotated[_FiniteFloat, Field(allow_inf_nan=False)] | None
"""Optional finite decibel value. May be negative."""

OptionalPercentage = (
    Annotated[_FiniteFloat, Field(ge=0, le=100, allow_inf_nan=False)] | None
)
"""Optional percentage in the closed range 0-100."""

OptionalFrequencyHz = (
    Annotated[_FiniteFloat, Field(gt=0, allow_inf_nan=False)] | None
)
"""Optional positive frequency in Hz."""

OptionalUnitInterval = (
    Annotated[_FiniteFloat, Field(ge=0, le=1, allow_inf_nan=False)] | None
)
"""Optional score in the closed range 0.0-1.0."""

OptionalPositiveInt = (
    Annotated[StrictInt, BeforeValidator(_reject_bool), Field(gt=0)] | None
)
"""Optional positive integer. bool is rejected."""
