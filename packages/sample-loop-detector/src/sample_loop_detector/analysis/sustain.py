"""Attack estimation and sustain-region detection (section 11)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.ndimage import median_filter

from sample_loop_detector.analysis.features import FrameFeatures
from sample_loop_detector.config import (
    ATTACK_EXCLUSION_SECONDS,
    ATTACK_SEARCH_MAX_RATIO,
    ATTACK_SEARCH_MAX_SECONDS,
    PITCH_STABLE_VOICED_RATIO,
    RELEASE_GUARD_SECONDS,
    ROBUST_Z_CLIP,
    SHORT_GAP_MERGE_SECONDS,
    STABILITY_SCORE_THRESHOLD,
    STABILITY_WEIGHTS,
    FrameConfig,
)
from sample_loop_detector.exceptions import SustainNotFoundError
from sample_loop_detector.models import SustainRegion

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

_EPS = 1e-12


@dataclass(frozen=True)
class SustainAnalysis:
    """Selected sustain region plus intermediate detection state."""

    region: SustainRegion  # sample-frame units
    start_frame_index: int  # analysis-frame units
    end_frame_index: int
    attack_end_seconds: float
    stability: FloatArray  # per analysis frame, 0 = stable
    candidates: tuple[SustainRegion, ...]


def robust_z(values: FloatArray, reference: FloatArray | None = None) -> FloatArray:
    """Median/MAD z-score, clipped to +-ROBUST_Z_CLIP."""
    ref = values if reference is None else reference
    finite = ref[np.isfinite(ref)]
    if finite.size == 0:
        return np.zeros_like(values)
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    z = (values - median) / (1.4826 * mad + _EPS)
    z = np.where(np.isfinite(z), z, ROBUST_Z_CLIP)
    return np.asarray(np.clip(z, -ROBUST_Z_CLIP, ROBUST_Z_CLIP), dtype=np.float64)


def _rolling_median(values: FloatArray, window: int) -> FloatArray:
    finite = np.isfinite(values)
    filled = values.copy()
    if not finite.all():
        if not finite.any():
            return np.zeros_like(values)
        idx = np.arange(len(values), dtype=np.float64)
        filled[~finite] = np.interp(idx[~finite], idx[finite], values[finite])
    return np.asarray(median_filter(filled, size=window, mode="nearest"), dtype=np.float64)


def _rolling_std(values: FloatArray, window: int) -> FloatArray:
    kernel = np.ones(window) / window
    mean = np.convolve(values, kernel, mode="same")
    mean_sq = np.convolve(values**2, kernel, mode="same")
    return np.asarray(np.sqrt(np.maximum(mean_sq - mean**2, 0.0)), dtype=np.float64)


def estimate_attack_end_frame(features: FrameFeatures, config: FrameConfig) -> int:
    """Return the first analysis frame after the attack exclusion zone."""
    n = features.n_frames
    duration = n * config.hop_length / config.sample_rate
    search_seconds = min(ATTACK_SEARCH_MAX_SECONDS, duration * ATTACK_SEARCH_MAX_RATIO)
    search_frames = max(1, min(n, config.seconds_to_frames(search_seconds)))

    score = (
        robust_z(np.maximum(features.rms_db_diff, 0.0))
        + robust_z(features.mel_flux)
        + robust_z(features.onset_strength)
    )
    attack_frame = int(np.argmax(score[:search_frames]))
    exclusion = config.seconds_to_frames(ATTACK_EXCLUSION_SECONDS)
    return attack_frame + max(exclusion, 1)


def compute_stability(features: FrameFeatures, active_floor_db: float) -> FloatArray:
    """Per-frame stability score in 0..1 (0 = very stable)."""
    window = features.stability_window_frames
    active = features.rms_db > active_floor_db
    reference_mask = active if active.any() else np.ones(features.n_frames, dtype=bool)

    def cost(values: FloatArray) -> FloatArray:
        z = robust_z(np.abs(values), np.abs(values[reference_mask]))
        return np.asarray(np.clip(z, 0.0, ROBUST_Z_CLIP) / ROBUST_Z_CLIP, dtype=np.float64)

    energy_residual = cost(features.rms_residual)
    spectral_flux = cost(_rolling_median(features.mel_flux, window))
    spectral_variation = cost(_rolling_median(features.mel_frame_dist, window))
    centroid_variation = cost(
        _rolling_std(features.centroid, window)
        / (np.abs(_rolling_median(features.centroid, window)) + _EPS)
    )
    envelope_jump = cost(_rolling_std(features.rms_db_diff, window))

    weights = dict(STABILITY_WEIGHTS)
    voiced_ratio = float(features.voiced_flag.mean()) if features.n_frames else 0.0
    pitch_ok = voiced_ratio >= PITCH_STABLE_VOICED_RATIO
    if pitch_ok:
        cents_med = _rolling_median(features.cents, window)
        cents_mad = _rolling_median(np.abs(features.cents - cents_med), window)
        pitch_variation = cost(cents_mad)
    else:
        pitch_variation = np.zeros(features.n_frames)
        weights.pop("pitch_variation")

    total_weight = sum(weights.values())
    stability = (
        weights["energy_residual"] * energy_residual
        + weights["spectral_flux"] * spectral_flux
        + weights["spectral_variation"] * spectral_variation
        + weights["centroid_variation"] * centroid_variation
        + weights.get("pitch_variation", 0.0) * pitch_variation
        + weights["other_modulation"] * envelope_jump
    ) / total_weight
    return np.asarray(np.clip(stability, 0.0, 1.0), dtype=np.float64)


def _contiguous_runs(mask: BoolArray) -> list[tuple[int, int]]:
    """Return [start, end] index pairs (inclusive) of True runs."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def detect_sustain(
    features: FrameFeatures,
    config: FrameConfig,
    active_floor_db: float,
    min_sustain_seconds: float,
    search_start_seconds: float | None = None,
    search_end_seconds: float | None = None,
) -> SustainAnalysis:
    stability = compute_stability(features, active_floor_db)
    attack_end = estimate_attack_end_frame(features, config)
    attack_end_seconds = attack_end * config.hop_length / config.sample_rate

    active = features.rms_db > active_floor_db
    if not active.any():
        raise SustainNotFoundError(
            "no_active_signal", "No frames above the activity floor were found."
        )

    # Release guard: stay clear of the trailing inactive region.
    last_active = int(np.nonzero(active)[0][-1])
    release_guard = config.seconds_to_frames(RELEASE_GUARD_SECONDS)
    usable_end = max(0, last_active - release_guard)

    mask = active & (stability <= STABILITY_SCORE_THRESHOLD)
    mask[:attack_end] = False
    mask[usable_end + 1 :] = False

    if search_start_seconds is not None:
        start_frame = config.seconds_to_frames(search_start_seconds)
        mask[:start_frame] = False
    if search_end_seconds is not None:
        end_frame = config.seconds_to_frames(search_end_seconds)
        mask[end_frame + 1 :] = False

    # Bridge unstable gaps up to SHORT_GAP_MERGE_SECONDS between stable runs.
    max_gap = max(1, config.seconds_to_frames(SHORT_GAP_MERGE_SECONDS))
    runs = _contiguous_runs(mask)
    merged: list[tuple[int, int]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] - 1 <= max_gap:
            merged[-1] = (merged[-1][0], run[1])
        else:
            merged.append(run)

    min_frames = max(1, config.seconds_to_frames(min_sustain_seconds))
    candidates: list[SustainRegion] = []
    for start, end in merged:
        if end - start + 1 < min_frames:
            continue
        segment_stability = float(np.mean(stability[start : end + 1]))
        confidence = _region_confidence(segment_stability, (end - start + 1), min_frames)
        candidates.append(
            SustainRegion(
                start_frame=config.frame_to_sample(start),
                end_frame=config.frame_to_sample(end) + config.frame_length,
                stability_score=segment_stability,
                confidence=confidence,
            )
        )

    if not candidates:
        if not any(end - start + 1 >= min_frames for start, end in _contiguous_runs(active)):
            raise SustainNotFoundError(
                "sustain_region_too_short",
                "The active signal is shorter than the minimum sustain length.",
            )
        raise SustainNotFoundError(
            "no_stable_sustain_region",
            "A sufficiently stable sustain region was not found.",
        )

    # Selection (section 11.7): stability first, then length, level,
    # distance from the release.  Stability is bucketed so nearly equal
    # regions fall through to the later criteria.
    def sort_key(region: SustainRegion) -> tuple[float, float, float, float]:
        start_idx = config.sample_to_frame(region.start_frame)
        end_idx = config.sample_to_frame(region.end_frame - config.frame_length)
        length = region.end_frame - region.start_frame
        level = float(np.mean(features.rms_db[start_idx : end_idx + 1]))
        distance_from_release = usable_end - end_idx
        return (
            round(region.stability_score, 2),
            -length,
            -level,
            -distance_from_release,
        )

    best = min(candidates, key=sort_key)
    start_idx = config.sample_to_frame(best.start_frame)
    end_idx = config.sample_to_frame(best.end_frame - config.frame_length)
    return SustainAnalysis(
        region=best,
        start_frame_index=start_idx,
        end_frame_index=end_idx,
        attack_end_seconds=attack_end_seconds,
        stability=stability,
        candidates=tuple(candidates),
    )


def _region_confidence(mean_stability: float, length_frames: int, min_frames: int) -> float:
    base = 1.0 - mean_stability
    length_factor = min(1.0, length_frames / (2.0 * min_frames))
    return float(np.clip(base * (0.5 + 0.5 * length_factor), 0.0, 1.0))
