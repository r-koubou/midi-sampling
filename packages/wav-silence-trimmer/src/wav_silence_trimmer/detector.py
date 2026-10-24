"""Signal region detection based on edge-noise-floor-relative hysteresis thresholds."""

from __future__ import annotations

import logging
import math

import numpy as np
from scipy import ndimage

from .errors import NoSignalDetectedError
from .models import DetectionResult, TrimConfig

logger = logging.getLogger(__name__)

_EPSILON = 1e-12

# High-precision boundary re-search parameters (spec section 8.11).
_REFINE_START_RANGE_MS = 50.0
_REFINE_END_RANGE_MS = 100.0
_REFINE_WINDOW_MS = 1.0
_REFINE_HOP_MS = 0.25


def remove_dc_offset(audio: np.ndarray) -> np.ndarray:
    """Return an analysis copy with per-channel median subtracted.

    The median is used instead of the mean so that large amplitudes in the
    sounding region do not bias the offset estimate.

    Args:
        audio: Audio array shaped (samples, channels).

    Returns:
        A float64 copy with DC offset removed per channel.
    """
    analysis = audio.astype(np.float64, copy=True)
    analysis -= np.median(analysis, axis=0, keepdims=True)
    return analysis


def compute_frame_rms(
    analysis: np.ndarray,
    frame_length: int,
    hop_length: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute the per-frame representative RMS using cumulative sums.

    The representative value of each frame is the maximum of the per-channel
    RMS values, which protects material that is panned to one side or has a
    longer release in a single channel.

    Args:
        analysis: DC-removed audio shaped (samples, channels).
        frame_length: Frame length in samples.
        hop_length: Hop length in samples.

    Returns:
        Tuple of (frame_rms, frame_starts, frame_ends) where frame_rms is the
        per-frame maximum channel RMS and the start/end arrays are sample
        positions. Trailing frames may be shorter than frame_length.
    """
    total = analysis.shape[0]
    if total == 0:
        empty = np.empty(0)
        return empty, empty.astype(np.int64), empty.astype(np.int64)
    squared = analysis * analysis
    cumulative = np.vstack(
        [np.zeros((1, analysis.shape[1])), np.cumsum(squared, axis=0)]
    )
    starts = np.arange(0, total, hop_length, dtype=np.int64)
    ends = np.minimum(starts + frame_length, total)
    sums = cumulative[ends] - cumulative[starts]
    lengths = (ends - starts).astype(np.float64)[:, None]
    channel_rms = np.sqrt(np.maximum(sums / lengths, 0.0))
    frame_rms = channel_rms.max(axis=1)
    return frame_rms, starts, ends


def to_dbfs(rms: np.ndarray) -> np.ndarray:
    """Convert linear RMS values to dBFS with an epsilon floor."""
    return 20.0 * np.log10(np.maximum(rms, _EPSILON))


def estimate_noise_floor(
    frame_db: np.ndarray,
    frame_starts: np.ndarray,
    frame_ends: np.ndarray,
    total_samples: int,
    sample_rate: int,
    config: TrimConfig,
) -> float:
    """Estimate the noise floor from the head and tail edge regions.

    A percentile of the edge level distribution is used instead of a plain
    mean, so short reverb tails or impulse noise inside the margins do not
    inflate the estimate.

    Args:
        frame_db: Median-filtered per-frame dBFS levels.
        frame_starts: Frame start sample positions.
        frame_ends: Frame end sample positions.
        total_samples: Total number of samples in the input.
        sample_rate: Sample rate in Hz.
        config: Detection configuration.

    Returns:
        Estimated noise floor in dBFS, clamped to the configured minimum.
    """
    edge_samples = int(round(config.edge_noise_seconds * sample_rate))
    if edge_samples >= total_samples:
        logger.warning(
            "edge noise region (%.3f s) covers the whole input; "
            "using all frames for noise estimation",
            config.edge_noise_seconds,
        )
        edge_levels = frame_db
    else:
        if edge_samples * 2 > total_samples:
            logger.warning(
                "head and tail noise regions overlap significantly; "
                "noise floor estimate may include signal"
            )
        head = frame_db[frame_starts < edge_samples]
        tail = frame_db[frame_ends > total_samples - edge_samples]
        edge_levels = np.concatenate([head, tail])
    if edge_levels.size == 0:
        return config.minimum_noise_floor_dbfs
    estimated = float(np.percentile(edge_levels, config.noise_percentile))
    return max(estimated, config.minimum_noise_floor_dbfs)


def _runs_of(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return [start, stop) index pairs of consecutive True runs in mask."""
    if not mask.any():
        return []
    labels, count = ndimage.label(mask)
    slices = ndimage.find_objects(labels)
    return [(s[0].start, s[0].stop) for s in slices]


def _build_seed_mask(strong_mask: np.ndarray, min_on_frames: int) -> np.ndarray:
    """Keep only runs of strong frames long enough to count as onsets."""
    seed = np.zeros_like(strong_mask)
    for start, stop in _runs_of(strong_mask):
        if stop - start >= min_on_frames:
            seed[start:stop] = True
    return seed


def _bridge_gaps(weak_mask: np.ndarray, bridge_frames: int) -> np.ndarray:
    """Close short gaps in the weak mask via morphological closing.

    The result is OR-ed with the original mask so border effects of the
    closing can never remove genuine active frames.
    """
    if bridge_frames <= 1 or not weak_mask.any():
        return weak_mask.copy()
    structure = np.ones(bridge_frames, dtype=bool)
    closed = ndimage.binary_closing(weak_mask, structure=structure)
    return closed | weak_mask


def _sliding_rms_max(
    segment: np.ndarray, window: int, hop: int
) -> tuple[np.ndarray, np.ndarray]:
    """Short-window max-channel RMS over a segment, for boundary refinement."""
    total = segment.shape[0]
    if total == 0:
        empty = np.empty(0)
        return empty, empty.astype(np.int64)
    squared = segment * segment
    cumulative = np.vstack(
        [np.zeros((1, segment.shape[1])), np.cumsum(squared, axis=0)]
    )
    starts = np.arange(0, total, hop, dtype=np.int64)
    ends = np.minimum(starts + window, total)
    sums = cumulative[ends] - cumulative[starts]
    lengths = (ends - starts).astype(np.float64)[:, None]
    rms = np.sqrt(np.maximum(sums / lengths, 0.0)).max(axis=1)
    return rms, starts


def _refine_boundaries(
    analysis: np.ndarray,
    sample_rate: int,
    threshold_off_dbfs: float,
    coarse_start: int,
    coarse_end: int,
) -> tuple[int, int]:
    """Re-search boundaries around the coarse positions with short windows."""
    total = analysis.shape[0]
    window = max(1, round(sample_rate * _REFINE_WINDOW_MS / 1000.0))
    hop = max(1, round(sample_rate * _REFINE_HOP_MS / 1000.0))
    threshold_linear = 10.0 ** (threshold_off_dbfs / 20.0)

    start_range = round(sample_rate * _REFINE_START_RANGE_MS / 1000.0)
    lo = max(0, coarse_start - start_range)
    hi = min(total, coarse_start + start_range)
    refined_start = coarse_start
    if hi > lo:
        rms, starts = _sliding_rms_max(analysis[lo:hi], window, hop)
        above = np.flatnonzero(rms >= threshold_linear)
        if above.size:
            refined_start = lo + int(starts[above[0]])

    end_range = round(sample_rate * _REFINE_END_RANGE_MS / 1000.0)
    lo = max(0, coarse_end - end_range)
    hi = min(total, coarse_end + end_range)
    refined_end = coarse_end
    if hi > lo:
        rms, starts = _sliding_rms_max(analysis[lo:hi], window, hop)
        above = np.flatnonzero(rms >= threshold_linear)
        if above.size:
            refined_end = min(total, lo + int(starts[above[-1]]) + window)

    if refined_end <= refined_start:
        return coarse_start, coarse_end
    return refined_start, refined_end


def detect_trim_region(
    audio: np.ndarray,
    sample_rate: int,
    config: TrimConfig,
) -> DetectionResult:
    """Detect the active signal region of an audio array.

    Implements the full pipeline of spec section 8: DC removal, frame RMS,
    edge noise floor estimation, hysteresis thresholding, gap bridging,
    seed-gated component selection, boundary refinement, and pre/post roll.

    Args:
        audio: Audio shaped (samples, channels).
        sample_rate: Sample rate in Hz.
        config: Detection configuration.

    Returns:
        DetectionResult with final and intermediate boundary positions.

    Raises:
        NoSignalDetectedError: If no strong onset region is found.
    """
    total = audio.shape[0]
    if total == 0:
        raise NoSignalDetectedError("Input audio is empty.")

    analysis = remove_dc_offset(audio)

    frame_length = max(1, round(sample_rate * config.frame_ms / 1000.0))
    hop_length = max(1, round(sample_rate * config.hop_ms / 1000.0))

    frame_rms, frame_starts, frame_ends = compute_frame_rms(
        analysis, frame_length, hop_length
    )
    frame_db = to_dbfs(frame_rms)
    filtered_db = ndimage.median_filter(frame_db, size=3, mode="nearest")

    noise_floor = estimate_noise_floor(
        filtered_db, frame_starts, frame_ends, total, sample_rate, config
    )
    threshold_on = noise_floor + config.on_margin_db
    threshold_off = noise_floor + config.off_margin_db

    logger.debug(
        "frames=%d frame_length=%d hop_length=%d noise_floor=%.1f dBFS "
        "threshold_on=%.1f threshold_off=%.1f",
        filtered_db.size, frame_length, hop_length,
        noise_floor, threshold_on, threshold_off,
    )

    min_on_frames = max(1, math.ceil(config.minimum_on_ms / config.hop_ms))
    strong_mask = filtered_db >= threshold_on
    seed_mask = _build_seed_mask(strong_mask, min_on_frames)
    if not seed_mask.any():
        raise NoSignalDetectedError("No valid signal region was detected.")

    weak_mask = filtered_db >= threshold_off
    bridge_frames = max(1, round(config.bridge_gap_ms / config.hop_ms))
    connected_mask = _bridge_gaps(weak_mask, bridge_frames)

    accepted = [
        (start, stop)
        for start, stop in _runs_of(connected_mask)
        if seed_mask[start:stop].any()
    ]
    if not accepted:
        raise NoSignalDetectedError("No valid signal region was detected.")

    # Keep everything from the first accepted component to the last one:
    # rests in the middle of a sample must never be removed.
    first_frame = accepted[0][0]
    last_frame = accepted[-1][1] - 1
    coarse_start = int(frame_starts[first_frame])
    coarse_end = int(frame_ends[last_frame])

    refined_start, refined_end = _refine_boundaries(
        analysis, sample_rate, threshold_off, coarse_start, coarse_end
    )
    logger.debug(
        "coarse=[%d, %d) refined=[%d, %d)",
        coarse_start, coarse_end, refined_start, refined_end,
    )

    pre_roll = round(sample_rate * config.pre_roll_ms / 1000.0)
    post_roll = round(sample_rate * config.post_roll_ms / 1000.0)
    start = max(0, refined_start - pre_roll)
    end = min(total, refined_end + post_roll)
    if end <= start:
        raise NoSignalDetectedError("Detected region is empty after clamping.")

    return DetectionResult(
        start_sample=start,
        end_sample_exclusive=end,
        noise_floor_dbfs=noise_floor,
        threshold_on_dbfs=threshold_on,
        threshold_off_dbfs=threshold_off,
        coarse_start=coarse_start,
        coarse_end=coarse_end,
        refined_start=refined_start,
        refined_end=refined_end,
    )
