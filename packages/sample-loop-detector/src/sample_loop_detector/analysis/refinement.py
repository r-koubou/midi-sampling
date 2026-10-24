"""Sample-accurate candidate refinement (section 14).

The end position is shifted within a bounded range to maximize the
normalized cross-correlation between the waveform windows around the loop
start and end.  Zero crossings are only used afterwards for a tiny
correlation-neutral nudge.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.config import (
    REFINE_MAX_RANGE_SECONDS,
    REFINE_PERIOD_FACTOR,
    REFINE_UNPITCHED_RANGE_SECONDS,
    REFINE_WINDOW_SECONDS,
    ZERO_CROSS_ADJUST_SECONDS,
)
from sample_loop_detector.models import LoopCandidate, PitchEstimate

FloatArray = NDArray[np.float64]

_EPS = 1e-12


def _normalize(window: FloatArray) -> FloatArray:
    centered = window - window.mean()
    norm = float(np.sqrt(np.sum(centered**2)))
    return np.asarray(centered / (norm + _EPS), dtype=np.float64)


def waveform_correlation(audio: FloatArray, position_a: int, position_b: int, window: int) -> float:
    """Mean per-channel normalized correlation of windows centered on two frames."""
    half = window // 2
    frames = audio.shape[0]
    if (
        position_a - half < 0
        or position_b - half < 0
        or position_a + half > frames
        or position_b + half > frames
    ):
        return -1.0
    total = 0.0
    channels = audio.shape[1]
    for ch in range(channels):
        a = _normalize(audio[position_a - half : position_a + half, ch])
        b = _normalize(audio[position_b - half : position_b + half, ch])
        total += float(np.dot(a, b))
    return float(total / channels)


def refine_candidate(
    audio: FloatArray,
    candidate: LoopCandidate,
    sample_rate: int,
    pitch: PitchEstimate,
    sustain_start: int,
    sustain_end: int,
) -> LoopCandidate:
    """Return the candidate with its end shifted to the best correlation."""
    if pitch.period_samples is not None:
        search = round(pitch.period_samples * REFINE_PERIOD_FACTOR)
    else:
        search = round(REFINE_UNPITCHED_RANGE_SECONDS * sample_rate)
    search = min(search, round(REFINE_MAX_RANGE_SECONDS * sample_rate))
    search = max(search, 1)

    window = max(32, round(REFINE_WINDOW_SECONDS * sample_rate))
    start = candidate.start_frame
    end = candidate.end_frame

    reference_half = window // 2
    lo = max(end - search, start + 1, sustain_start + reference_half)
    hi = min(end + search, sustain_end - reference_half, audio.shape[0] - reference_half - 2)
    if hi <= lo:
        return candidate

    offsets = np.arange(lo, hi + 1, dtype=np.int64)
    scores = np.array([waveform_correlation(audio, start, int(pos), window) for pos in offsets])
    best_index = int(np.argmax(scores))
    best_end = int(offsets[best_index])
    best_score = float(scores[best_index])

    # Zero-cross nudge: within +-2 ms, move the end toward a smaller hard
    # seam amplitude jump without hurting the correlation meaningfully.
    nudge = round(ZERO_CROSS_ADJUST_SECONDS * sample_rate)
    nudge_lo = max(best_end - nudge, lo)
    nudge_hi = min(best_end + nudge, hi)
    mono = audio.mean(axis=1)
    best_jump = abs(mono[best_end] - mono[start])
    tolerance = 0.002
    for pos in range(nudge_lo, nudge_hi + 1):
        jump = abs(mono[pos] - mono[start])
        idx = int(pos - lo)
        if jump < best_jump and scores[idx] >= best_score - tolerance:
            best_end = pos
            best_jump = jump

    return LoopCandidate(
        start_frame=start,
        end_frame=best_end,
        crossfade_frames=candidate.crossfade_frames,
        coarse_score=candidate.coarse_score,
    )
