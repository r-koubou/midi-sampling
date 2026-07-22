from collections.abc import Sequence
from logging import getLogger

from midi_sampling.sampling.definitions import (
    VelocityLayerDefinition,
    ZoneDefinition,
)
from midi_sampling.sampling.exceptions import (
    InvalidVelocityProfileError,
    InvalidZoneLayoutError,
)

logger = getLogger(__name__)

VELOCITY_MIN = 1
VELOCITY_MAX = 127


class SemanticValidator:
    """
    Cross-element semantic validation and normalization for zone layouts
    and velocity profiles. The same input always produces the same
    normalized result, independent of YAML ordering.
    """

    def normalize_zones(
        self, zones: Sequence[ZoneDefinition], context: str
    ) -> tuple[ZoneDefinition, ...]:
        """
        Sort zones by (low, root, high) and reject overlapping zones.
        Gaps between zones are allowed.

        Args:
            zones:   Zones in YAML order.
            context: Label used in error messages (e.g. definition id).
        """
        if len(zones) == 0:
            raise InvalidZoneLayoutError(f"{context}: at least one zone is required")

        ordered = tuple(sorted(zones, key=lambda z: (z.low, z.root, z.high)))

        for previous, current in zip(ordered, ordered[1:]):
            if current.low <= previous.high:
                raise InvalidZoneLayoutError(
                    f"{context}: zones overlap: "
                    f"[{previous.low}-{previous.high}] and "
                    f"[{current.low}-{current.high}]"
                )

        return ordered

    def normalize_velocity_layers(
        self, layers: Sequence[VelocityLayerDefinition], context: str
    ) -> tuple[VelocityLayerDefinition, ...]:
        """
        Sort layers by (low, high, send) and require a gapless,
        non-overlapping, complete coverage of velocities 1-127.

        Args:
            layers:  Layers in YAML order.
            context: Label used in error messages (e.g. definition id).
        """
        if len(layers) == 0:
            raise InvalidVelocityProfileError(
                f"{context}: at least one velocity layer is required"
            )

        ordered = tuple(sorted(layers, key=lambda v: (v.low, v.high, v.send)))

        if ordered[0].low != VELOCITY_MIN:
            raise InvalidVelocityProfileError(
                f"{context}: velocity layers must start at {VELOCITY_MIN}, "
                f"got {ordered[0].low}"
            )

        for previous, current in zip(ordered, ordered[1:]):
            if current.low <= previous.high:
                raise InvalidVelocityProfileError(
                    f"{context}: velocity layers overlap: "
                    f"[{previous.low}-{previous.high}] and "
                    f"[{current.low}-{current.high}]"
                )
            if current.low != previous.high + 1:
                raise InvalidVelocityProfileError(
                    f"{context}: velocity layers must not have gaps: "
                    f"[{previous.low}-{previous.high}] and "
                    f"[{current.low}-{current.high}]"
                )

        if ordered[-1].high != VELOCITY_MAX:
            raise InvalidVelocityProfileError(
                f"{context}: velocity layers must end at {VELOCITY_MAX}, "
                f"got {ordered[-1].high}"
            )

        return ordered
