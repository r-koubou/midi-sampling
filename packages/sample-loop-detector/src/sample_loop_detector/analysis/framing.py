"""Frame layout helpers (center=False throughout).

Frame ``i`` covers samples ``[i * hop, i * hop + frame_length)``; its
nominal position is the window center.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.config import FrameConfig


def frame_count(config: FrameConfig, sample_count: int) -> int:
    if sample_count < config.frame_length:
        return 0
    return 1 + (sample_count - config.frame_length) // config.hop_length


def frame_center_samples(config: FrameConfig, n_frames: int) -> NDArray[np.int64]:
    starts = np.arange(n_frames, dtype=np.int64) * config.hop_length
    return starts + config.frame_length // 2


def frame_center_seconds(config: FrameConfig, n_frames: int) -> NDArray[np.float64]:
    return frame_center_samples(config, n_frames).astype(np.float64) / config.sample_rate


def rolling_regression(
    values: NDArray[np.float64], window: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Rolling linear regression: per-position slope and RMS residual.

    Uses centered windows of ``window`` frames (clamped at the edges) and
    closed-form least squares over cumulative sums so the cost stays O(N).
    """
    n = len(values)
    if n == 0:
        return np.zeros(0), np.zeros(0)
    window = max(3, min(window, n))
    half = window // 2

    x = np.arange(n, dtype=np.float64)
    ones = np.ones(n, dtype=np.float64)

    def windowed_sum(series: NDArray[np.float64]) -> NDArray[np.float64]:
        csum = np.concatenate(([0.0], np.cumsum(series)))
        lo = np.clip(np.arange(n) - half, 0, n)
        hi = np.clip(np.arange(n) + half + 1, 0, n)
        return csum[hi] - csum[lo]

    s1 = windowed_sum(ones)
    sx = windowed_sum(x)
    sy = windowed_sum(values)
    sxx = windowed_sum(x * x)
    sxy = windowed_sum(x * values)
    syy = windowed_sum(values * values)

    denom = s1 * sxx - sx * sx
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    slope = (s1 * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / s1

    # Residual sum of squares from the closed form:
    # SSE = Syy - a*Sy - b*Sxy where y ~ a + b*x
    sse = syy - intercept * sy - slope * sxy
    sse = np.maximum(sse, 0.0)
    residual_rms = np.sqrt(sse / s1)
    return slope, residual_rms
