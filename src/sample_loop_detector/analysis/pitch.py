"""Fundamental period estimation over the sustain region (section 12)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.analysis.features import FrameFeatures
from sample_loop_detector.analysis.sustain import SustainAnalysis
from sample_loop_detector.config import (
    PITCH_STABLE_MAX_MAD_CENTS,
    PITCH_STABLE_MEDIAN_PROB,
    PITCH_STABLE_VOICED_RATIO,
    FrameConfig,
)
from sample_loop_detector.models import PitchEstimate

FloatArray = NDArray[np.float64]


def weighted_median(values: FloatArray, weights: FloatArray) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    cutoff = cumulative[-1] / 2.0
    index = int(np.searchsorted(cumulative, cutoff))
    return float(sorted_values[min(index, len(sorted_values) - 1)])


def estimate_pitch(
    features: FrameFeatures,
    sustain: SustainAnalysis,
    config: FrameConfig,
) -> PitchEstimate:
    lo = sustain.start_frame_index
    hi = sustain.end_frame_index + 1
    f0 = features.f0[lo:hi]
    voiced = features.voiced_flag[lo:hi]
    prob = features.voiced_prob[lo:hi]

    total = len(f0)
    if total == 0:
        return PitchEstimate(f0_hz=None, confidence=0.0, voiced_ratio=0.0, period_samples=None)

    finite = np.isfinite(f0)
    voiced_ratio = float((voiced & finite).mean())
    valid = finite & (prob > 0.0)
    if not valid.any():
        return PitchEstimate(
            f0_hz=None, confidence=0.0, voiced_ratio=voiced_ratio, period_samples=None
        )

    median_prob = float(np.median(prob[valid]))
    f0_median = weighted_median(f0[valid], prob[valid])
    cents = 1200.0 * np.log2(f0[valid] / f0_median)
    cents_mad = float(np.median(np.abs(cents - np.median(cents))))

    stable = (
        voiced_ratio >= PITCH_STABLE_VOICED_RATIO
        and median_prob >= PITCH_STABLE_MEDIAN_PROB
        and cents_mad <= PITCH_STABLE_MAX_MAD_CENTS
    )

    # Confidence blends the three stability inputs so callers can also use
    # it as a soft weight.
    ratio_term = min(1.0, voiced_ratio / PITCH_STABLE_VOICED_RATIO)
    prob_term = min(1.0, median_prob / PITCH_STABLE_MEDIAN_PROB)
    mad_term = float(np.clip(1.0 - cents_mad / (2 * PITCH_STABLE_MAX_MAD_CENTS), 0.0, 1.0))
    confidence = ratio_term * prob_term * (0.5 + 0.5 * mad_term)

    if not stable:
        return PitchEstimate(
            f0_hz=None,
            confidence=confidence,
            voiced_ratio=voiced_ratio,
            period_samples=None,
        )

    return PitchEstimate(
        f0_hz=f0_median,
        confidence=confidence,
        voiced_ratio=voiced_ratio,
        period_samples=config.sample_rate / f0_median,
    )
