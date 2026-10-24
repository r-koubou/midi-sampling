"""Coarse loop-candidate generation (section 13).

Start frames are decimated to a bounded set; end frames are compared with
vectorized descriptor distances, so the search never degenerates into an
unbounded O(N^2) scan.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.analysis.features import FrameFeatures
from sample_loop_detector.analysis.modulation import ModulationFeatures, phase_difference_cost
from sample_loop_detector.analysis.sustain import SustainAnalysis
from sample_loop_detector.config import (
    ENDPOINT_DESCRIPTOR_SECONDS,
    LENGTH_LIGHT_PENALTY,
    LENGTH_LIGHT_PENALTY_BELOW_SECONDS,
    LENGTH_REJECT_BELOW_SECONDS,
    LENGTH_STRONG_PENALTY,
    LENGTH_STRONG_PENALTY_BELOW_SECONDS,
    MAX_COARSE_CANDIDATES,
    MAX_START_CANDIDATES,
    PERIOD_ERROR_WEIGHT,
    TOP_ENDS_PER_START,
    FrameConfig,
)
from sample_loop_detector.exceptions import LoopCandidateNotFoundError
from sample_loop_detector.models import LoopCandidate, PitchEstimate

FloatArray = NDArray[np.float64]

_EPS = 1e-12


def loop_length_penalty(length_seconds: float) -> float | None:
    """Return the short-loop penalty, or None when the loop is too short.

    The penalty bands of section 13.6 are interpolated linearly so that
    nearby lengths do not produce score cliffs.
    """
    if length_seconds < LENGTH_REJECT_BELOW_SECONDS:
        return None
    if length_seconds < LENGTH_STRONG_PENALTY_BELOW_SECONDS:
        span = LENGTH_STRONG_PENALTY_BELOW_SECONDS - LENGTH_REJECT_BELOW_SECONDS
        t = (length_seconds - LENGTH_REJECT_BELOW_SECONDS) / span
        return LENGTH_STRONG_PENALTY + t * (LENGTH_LIGHT_PENALTY - LENGTH_STRONG_PENALTY)
    if length_seconds < LENGTH_LIGHT_PENALTY_BELOW_SECONDS:
        span = LENGTH_LIGHT_PENALTY_BELOW_SECONDS - LENGTH_STRONG_PENALTY_BELOW_SECONDS
        t = (length_seconds - LENGTH_STRONG_PENALTY_BELOW_SECONDS) / span
        return LENGTH_LIGHT_PENALTY * (1.0 - t)
    return 0.0


def period_error_penalty(length_samples: int, period_samples: float | None) -> float:
    """0..1 penalty for loop lengths away from integer period multiples."""
    if period_samples is None or period_samples <= 0:
        return 0.0
    period_count = length_samples / period_samples
    if period_count < 0.5:
        return 1.0
    period_error = abs(period_count - round(period_count))
    return 2.0 * period_error  # error is at most 0.5 periods


@dataclass(frozen=True)
class EndpointDescriptors:
    """Per-frame endpoint descriptors over the sustain region."""

    frame_indices: NDArray[np.int64]  # analysis-frame index of each row
    mel_mean: FloatArray  # (rows, n_mels)
    scalars: FloatArray  # (rows, k) scaled scalar features
    has_pitch: bool


def build_descriptors(
    features: FrameFeatures,
    sustain: SustainAnalysis,
    config: FrameConfig,
    pitch: PitchEstimate,
) -> EndpointDescriptors:
    lo, hi = sustain.start_frame_index, sustain.end_frame_index
    indices = np.arange(lo, hi + 1, dtype=np.int64)
    half = max(1, config.seconds_to_frames(ENDPOINT_DESCRIPTOR_SECONDS) // 2)

    n = features.n_frames
    window_lo = np.clip(indices - half, 0, n - 1)
    window_hi = np.clip(indices + half, 0, n - 1)

    # Windowed log-mel statistics via cumulative sums along time.
    mel = features.log_mel
    csum = np.concatenate([np.zeros((1, mel.shape[1])), np.cumsum(mel, axis=0)])
    counts = (window_hi - window_lo + 1).astype(np.float64)[:, None]
    mel_mean = (csum[window_hi + 1] - csum[window_lo]) / counts
    csum_sq = np.concatenate([np.zeros((1, mel.shape[1])), np.cumsum(mel**2, axis=0)])
    mel_var = (csum_sq[window_hi + 1] - csum_sq[window_lo]) / counts - mel_mean**2
    mel_std_mean = np.sqrt(np.maximum(mel_var, 0.0)).mean(axis=1)

    diff = np.abs(np.diff(mel, axis=0)).mean(axis=1)
    diff = np.concatenate(([0.0], diff))
    dsum = np.concatenate(([0.0], np.cumsum(diff)))
    mel_diff_mean = (dsum[window_hi + 1] - dsum[window_lo]) / counts.ravel()

    has_pitch = pitch.f0_hz is not None
    columns: list[FloatArray] = [
        features.rms_db[indices] / 6.0,
        features.rms_slope[indices] * 20.0,
        np.log2(np.maximum(features.centroid[indices], 1.0)),
        features.centroid_slope[indices] / 50.0,
        mel_std_mean / 6.0,
        mel_diff_mean / 3.0,
    ]
    if has_pitch:
        cents = np.nan_to_num(features.cents[indices], nan=0.0)
        cents_slope = np.diff(cents, prepend=cents[0])
        columns.append(cents / 25.0)
        columns.append(cents_slope / 10.0)
        columns.append(features.voiced_prob[indices])
    if features.side_rms_db.size:
        columns.append(features.side_rms_db[indices] / 6.0)
        columns.append(features.lr_corr[indices] * 2.0)

    return EndpointDescriptors(
        frame_indices=indices,
        mel_mean=np.ascontiguousarray(mel_mean),
        scalars=np.ascontiguousarray(np.stack(columns, axis=1)),
        has_pitch=has_pitch,
    )


def _descriptor_distance(
    descriptors: EndpointDescriptors, start_row: int, end_rows: NDArray[np.int64]
) -> FloatArray:
    """Cosine log-mel distance plus scaled scalar differences, vectorized."""
    a = descriptors.mel_mean[start_row]
    b = descriptors.mel_mean[end_rows]
    denom = np.linalg.norm(a) * np.linalg.norm(b, axis=1) + _EPS
    cosine = 1.0 - (b @ a) / denom
    scalar_diff = np.abs(descriptors.scalars[end_rows] - descriptors.scalars[start_row]).mean(
        axis=1
    )
    return np.asarray(cosine * 2.0 + scalar_diff, dtype=np.float64)


def generate_candidates(
    features: FrameFeatures,
    sustain: SustainAnalysis,
    config: FrameConfig,
    pitch: PitchEstimate,
    modulation: ModulationFeatures,
    min_loop_seconds: float,
    max_loop_seconds: float,
    max_crossfade_seconds: float,
) -> tuple[LoopCandidate, ...]:
    descriptors = build_descriptors(features, sustain, config, pitch)
    rows = len(descriptors.frame_indices)
    if rows < 4:
        raise LoopCandidateNotFoundError(
            "no_loop_candidates", "The sustain region is too short for loop candidates."
        )

    hop = config.hop_length
    center_offset = config.frame_length // 2
    sample_positions = descriptors.frame_indices * hop + center_offset

    sustain_start_sample = sustain.region.start_frame
    sustain_end_sample = sustain.region.end_frame
    margin = round(max_crossfade_seconds * config.sample_rate)

    min_len = round(min_loop_seconds * config.sample_rate)
    max_len = round(max_loop_seconds * config.sample_rate)

    stride = max(1, rows // MAX_START_CANDIDATES)
    start_rows = np.arange(0, rows, stride, dtype=np.int64)[:MAX_START_CANDIDATES]

    scored: list[tuple[float, int, int]] = []
    for start_row in start_rows:
        start_sample = int(sample_positions[start_row])
        if start_sample - margin < sustain_start_sample:
            continue
        lengths = sample_positions - start_sample
        valid = (
            (lengths >= min_len)
            & (lengths <= max_len)
            & (sample_positions + margin <= sustain_end_sample)
        )
        end_rows = np.nonzero(valid)[0]
        if end_rows.size == 0:
            continue

        distance = _descriptor_distance(descriptors, int(start_row), end_rows)
        length_seconds = lengths[end_rows].astype(np.float64) / config.sample_rate

        penalties = np.zeros_like(distance)
        keep = np.ones(len(end_rows), dtype=bool)
        for i, (row, secs) in enumerate(zip(end_rows, length_seconds, strict=True)):
            lp = loop_length_penalty(float(secs))
            if lp is None:
                keep[i] = False
                continue
            penalties[i] += lp * 0.5
            penalties[i] += PERIOD_ERROR_WEIGHT * period_error_penalty(
                int(lengths[row]), pitch.period_samples
            )
            for track in (modulation.vibrato, modulation.tremolo):
                phase_cost = phase_difference_cost(
                    track,
                    int(descriptors.frame_indices[start_row]),
                    int(descriptors.frame_indices[row]),
                )
                if phase_cost is not None:
                    penalties[i] += 0.15 * track.strength * phase_cost

        end_rows = end_rows[keep]
        if end_rows.size == 0:
            continue
        total = distance[keep] + penalties[keep]
        order = np.argsort(total)[:TOP_ENDS_PER_START]
        for pick in order:
            end_row = int(end_rows[pick])
            scored.append((float(total[pick]), start_sample, int(sample_positions[end_row])))

    if not scored:
        raise LoopCandidateNotFoundError(
            "no_loop_candidates",
            "No loop candidates satisfied the length and sustain constraints.",
        )

    scored.sort(key=lambda item: (item[0], -(item[2] - item[1]), item[1]))
    seen: set[tuple[int, int]] = set()
    result: list[LoopCandidate] = []
    for score, start_sample, end_sample in scored:
        key = (start_sample, end_sample)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            LoopCandidate(
                start_frame=start_sample,
                end_frame=end_sample,
                crossfade_frames=0,
                coarse_score=score,
            )
        )
        if len(result) >= MAX_COARSE_CANDIDATES:
            break
    return tuple(result)
