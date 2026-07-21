import pytest
from pydantic import ValidationError

from midi_sampling.sampling.definitions import (
    VelocityLayerDefinition,
    ZoneDefinition,
)
from midi_sampling.sampling.exceptions import (
    InvalidVelocityProfileError,
    InvalidZoneLayoutError,
)
from midi_sampling.sampling.validation import SemanticValidator


def zone(low: int, root: int, high: int) -> ZoneDefinition:
    return ZoneDefinition(low=low, root=root, high=high)


def layer(low: int, high: int, send: int) -> VelocityLayerDefinition:
    return VelocityLayerDefinition(low=low, high=high, send=send)


validator = SemanticValidator()


class TestZones:
    def test_low_root_high_order_enforced_by_model(self):
        with pytest.raises(ValidationError):
            zone(40, 38, 42)
        with pytest.raises(ValidationError):
            zone(36, 45, 40)

    def test_overlap_detected(self):
        with pytest.raises(InvalidZoneLayoutError):
            validator.normalize_zones([zone(36, 38, 40), zone(40, 42, 44)], "test")

    def test_identical_range_detected(self):
        with pytest.raises(InvalidZoneLayoutError):
            validator.normalize_zones([zone(36, 38, 40), zone(36, 38, 40)], "test")

    def test_gap_allowed(self):
        result = validator.normalize_zones(
            [zone(50, 52, 54), zone(36, 38, 40)], "test"
        )
        assert len(result) == 2

    def test_sorted_deterministically(self):
        forward = validator.normalize_zones(
            [zone(36, 38, 40), zone(41, 43, 45), zone(50, 52, 54)], "test"
        )
        backward = validator.normalize_zones(
            [zone(50, 52, 54), zone(41, 43, 45), zone(36, 38, 40)], "test"
        )
        assert forward == backward
        assert [z.low for z in forward] == [36, 41, 50]

    def test_empty_rejected(self):
        with pytest.raises(InvalidZoneLayoutError):
            validator.normalize_zones([], "test")


class TestVelocityLayers:
    def test_full_coverage_required_at_start(self):
        with pytest.raises(InvalidVelocityProfileError):
            validator.normalize_velocity_layers([layer(2, 127, 64)], "test")

    def test_full_coverage_required_at_end(self):
        with pytest.raises(InvalidVelocityProfileError):
            validator.normalize_velocity_layers([layer(1, 126, 64)], "test")

    def test_overlap_detected(self):
        with pytest.raises(InvalidVelocityProfileError):
            validator.normalize_velocity_layers(
                [layer(1, 64, 32), layer(64, 127, 100)], "test"
            )

    def test_gap_detected(self):
        with pytest.raises(InvalidVelocityProfileError):
            validator.normalize_velocity_layers(
                [layer(1, 62, 32), layer(64, 127, 100)], "test"
            )

    def test_send_must_be_inside_range(self):
        with pytest.raises(ValidationError):
            layer(1, 63, 100)

    def test_single_full_layer_accepted(self):
        result = validator.normalize_velocity_layers([layer(1, 127, 100)], "test")
        assert len(result) == 1

    def test_sorted_deterministically(self):
        forward = validator.normalize_velocity_layers(
            [layer(1, 63, 48), layer(64, 127, 112)], "test"
        )
        backward = validator.normalize_velocity_layers(
            [layer(64, 127, 112), layer(1, 63, 48)], "test"
        )
        assert forward == backward
        assert [v.low for v in forward] == [1, 64]

    def test_empty_rejected(self):
        with pytest.raises(InvalidVelocityProfileError):
            validator.normalize_velocity_layers([], "test")
