"""
Shared pydantic field types for export definition models.

Follows the same rules as the sampling and postprocess definitions:
- bool is never accepted as a number.
- Numeric values must be finite; NaN and +-inf are rejected.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator, Field


def _to_finite_float(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("bool is not accepted as a numeric value")
    if not isinstance(value, (int, float)):
        raise ValueError("value must be an integer or a floating point number")
    return float(value)


_FiniteFloat = Annotated[float, BeforeValidator(_to_finite_float)]

NonNegativeSeconds = Annotated[_FiniteFloat, Field(ge=0, allow_inf_nan=False)]
"""Non-negative finite time value in seconds."""

OptionalDecayDbPerSecond = (
    Annotated[_FiniteFloat, Field(ge=0, allow_inf_nan=False)] | None
)
"""Optional non-negative decay rate in dB per second."""
