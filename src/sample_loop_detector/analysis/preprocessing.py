"""Analysis-signal construction: DC removal, silence and noise-floor checks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.config import (
    NOISE_FLOOR_MARGIN_DB,
    PEAK_RMS_FLOOR_DB,
    SILENCE_PEAK_THRESHOLD,
)
from sample_loop_detector.exceptions import InvalidWaveError

FloatArray = NDArray[np.float64]

_EPS = 1e-12


def prepare_analysis_audio(audio: FloatArray) -> FloatArray:
    """Return the DC-free analysis copy of the decoded audio.

    The original array (and the data chunk it came from) is never modified.
    """
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak < SILENCE_PEAK_THRESHOLD:
        raise InvalidWaveError("no analyzable signal: file peak is near silence")
    return np.ascontiguousarray(audio - np.mean(audio, axis=0, keepdims=True))


@dataclass(frozen=True)
class Floors:
    noise_floor_db: float
    active_floor_db: float


def compute_floors(rms_db_frames: FloatArray) -> Floors:
    """Derive the activity floor from the frame RMS series (section 8.4)."""
    if rms_db_frames.size == 0:
        raise InvalidWaveError("no analyzable signal: file shorter than one frame")
    noise_floor_db = float(np.percentile(rms_db_frames, 5))
    peak_rms_db = float(np.max(rms_db_frames))
    active_floor_db = max(
        noise_floor_db + NOISE_FLOOR_MARGIN_DB,
        peak_rms_db - PEAK_RMS_FLOOR_DB,
    )
    # A file with little or no silence pushes the percentile estimate close
    # to the sustain level; keep the floor usable in that case.
    active_floor_db = min(active_floor_db, peak_rms_db - 6.0)
    return Floors(noise_floor_db=noise_floor_db, active_floor_db=active_floor_db)


def validate_activity(
    rms_db_frames: FloatArray, active_floor_db: float, min_active_frames: int
) -> None:
    """Reject signals with no usable region above the activity floor."""
    active = rms_db_frames > active_floor_db
    if int(active.sum()) < max(1, min_active_frames):
        raise InvalidWaveError("no analyzable signal above the noise floor")
