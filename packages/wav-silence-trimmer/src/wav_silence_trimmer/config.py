"""Default parameter values and configuration validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import InvalidConfigurationError

if TYPE_CHECKING:
    from .models import TrimConfig

DEFAULT_FRAME_MS = 10.0
DEFAULT_HOP_MS = 2.0
DEFAULT_EDGE_NOISE_SECONDS = 1.0
DEFAULT_NOISE_PERCENTILE = 20.0
DEFAULT_MINIMUM_NOISE_FLOOR_DBFS = -120.0
DEFAULT_ON_MARGIN_DB = 15.0
DEFAULT_OFF_MARGIN_DB = 8.0
DEFAULT_MINIMUM_ON_MS = 10.0
DEFAULT_BRIDGE_GAP_MS = 80.0
DEFAULT_PRE_ROLL_MS = 8.0
DEFAULT_POST_ROLL_MS = 40.0
DEFAULT_FADE_IN_MS = 1.0
DEFAULT_FADE_OUT_MS = 5.0


def validate_config(config: "TrimConfig") -> None:
    """Validate a TrimConfig, raising InvalidConfigurationError on bad values.

    Args:
        config: The configuration to validate.

    Raises:
        InvalidConfigurationError: If any value is out of range or the
            hysteresis margins are inconsistent.
    """
    if config.edge_noise_seconds <= 0:
        raise InvalidConfigurationError("--edge-noise-seconds must be positive")
    if config.frame_ms <= 0:
        raise InvalidConfigurationError("--frame-ms must be positive")
    if config.hop_ms <= 0:
        raise InvalidConfigurationError("--hop-ms must be positive")
    if config.hop_ms > config.frame_ms:
        raise InvalidConfigurationError("--hop-ms must not exceed --frame-ms")
    if not 0.0 <= config.noise_percentile <= 100.0:
        raise InvalidConfigurationError(
            "--noise-percentile must be between 0 and 100"
        )
    if config.on_margin_db <= config.off_margin_db:
        raise InvalidConfigurationError(
            "--on-margin-db must be greater than --off-margin-db"
        )
    if config.off_margin_db < 0:
        raise InvalidConfigurationError("--off-margin-db must be non-negative")
    if config.minimum_on_ms < 0:
        raise InvalidConfigurationError("--minimum-on-ms must be non-negative")
    if config.bridge_gap_ms < 0:
        raise InvalidConfigurationError("--bridge-gap-ms must be non-negative")
    if config.pre_roll_ms < 0:
        raise InvalidConfigurationError("--pre-roll-ms must be non-negative")
    if config.post_roll_ms < 0:
        raise InvalidConfigurationError("--post-roll-ms must be non-negative")
    if config.fade_in_ms < 0:
        raise InvalidConfigurationError("--fade-in-ms must be non-negative")
    if config.fade_out_ms < 0:
        raise InvalidConfigurationError("--fade-out-ms must be non-negative")
