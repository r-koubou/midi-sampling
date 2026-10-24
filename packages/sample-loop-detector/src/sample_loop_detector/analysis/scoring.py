"""Score aggregation, acceptance, tie-breaks and confidence (sections 17, 18)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from sample_loop_detector.analysis.candidates import loop_length_penalty
from sample_loop_detector.analysis.render import SeamMetrics
from sample_loop_detector.config import (
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    HARD_SEAM_MAX_SCORE,
    HARD_SEAM_WEIGHTS,
    SUSTAIN_MIN_CONFIDENCE,
    TIE_BREAK_SCORE_DELTA,
    TOTAL_WEIGHTS,
)
from sample_loop_detector.models import LoopCandidate, LoopScore, PitchEstimate, SustainRegion


def hard_seam_score(metrics: SeamMetrics) -> float:
    """Weighted hard-seam score with unavailable features renormalized out."""
    contributions: dict[str, float | None] = {
        "waveform_correlation": metrics.waveform,
        "amplitude_jump": metrics.amplitude,
        "derivative_jump": metrics.derivative,
        "spectral_continuity": metrics.spectral,
        "level_continuity": metrics.level,
        "pitch_continuity": metrics.pitch,
        "modulation_continuity": metrics.modulation,
        "stereo_continuity": metrics.stereo,
    }
    total_weight = 0.0
    total = 0.0
    for name, value in contributions.items():
        if value is None:
            continue
        weight = HARD_SEAM_WEIGHTS[name]
        total += weight * value
        total_weight += weight
    if total_weight <= 0.0:
        return 1.0
    return float(np.clip(total / total_weight, 0.0, 1.0))


def combine_scores(
    candidate: LoopCandidate,
    metrics: SeamMetrics,
    crossfade_seam: float,
    sustain: SustainRegion,
    sample_rate: int,
) -> LoopScore:
    hard = hard_seam_score(metrics)
    sustain_cost = float(np.clip(sustain.stability_score, 0.0, 1.0))
    length_seconds = candidate.length_frames / sample_rate
    penalty = loop_length_penalty(length_seconds)
    length_cost = 1.0 if penalty is None else float(np.clip(penalty, 0.0, 1.0))

    total = (
        TOTAL_WEIGHTS["hard_seam"] * hard
        + TOTAL_WEIGHTS["crossfade_seam"] * crossfade_seam
        + TOTAL_WEIGHTS["sustain_quality"] * sustain_cost
        + TOTAL_WEIGHTS["loop_length_penalty"] * length_cost
    )
    return LoopScore(
        total=float(np.clip(total, 0.0, 1.0)),
        hard_seam=hard,
        crossfade_seam=float(np.clip(crossfade_seam, 0.0, 1.0)),
        waveform=metrics.waveform,
        spectral=metrics.spectral,
        level=metrics.level,
        pitch=metrics.pitch,
        modulation=metrics.modulation,
        stereo=metrics.stereo,
        sustain=sustain_cost,
        length_penalty=length_cost,
    )


@dataclass(frozen=True)
class AcceptanceDecision:
    accepted: bool
    reason: str | None  # failure reason code when rejected


def check_acceptance(
    score: LoopScore,
    sustain_confidence: float,
    quality_threshold: float,
    min_loop_seconds: float,
    length_seconds: float,
) -> AcceptanceDecision:
    if length_seconds < min_loop_seconds:
        return AcceptanceDecision(False, "all_candidates_above_threshold")
    if score.hard_seam > HARD_SEAM_MAX_SCORE:
        return AcceptanceDecision(False, "hard_seam_above_threshold")
    if score.total > quality_threshold:
        return AcceptanceDecision(False, "all_candidates_above_threshold")
    if sustain_confidence < SUSTAIN_MIN_CONFIDENCE:
        return AcceptanceDecision(False, "no_stable_sustain_region")
    return AcceptanceDecision(True, None)


def tie_break_key(
    candidate: LoopCandidate,
    score: LoopScore,
    sustain: SustainRegion,
    mono_abs_at_start: float,
) -> tuple[float, float, float, float]:
    """Ordering for candidates within TIE_BREAK_SCORE_DELTA (section 17.5)."""
    sustain_center = (sustain.start_frame + sustain.end_frame) / 2.0
    loop_center = (candidate.start_frame + candidate.end_frame) / 2.0
    center_distance = abs(loop_center - sustain_center) / max(
        1.0, (sustain.end_frame - sustain.start_frame) / 2.0
    )
    return (
        -candidate.length_frames,  # 1. longer loop
        score.hard_seam,  # 2. lower hard-seam score
        center_distance,  # 3. closer to the sustain center
        mono_abs_at_start,  # 4. nearer a zero crossing
    )


def select_best(
    entries: list[tuple[LoopCandidate, LoopScore, float]],
    sustain: SustainRegion,
) -> int:
    """Index of the winner among (candidate, score, |mono[start]|) entries."""
    best_total = min(entry[1].total for entry in entries)
    contenders = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry[1].total <= best_total + TIE_BREAK_SCORE_DELTA
    ]
    winner = min(
        contenders,
        key=lambda item: tie_break_key(item[1][0], item[1][1], sustain, item[1][2]),
    )
    return winner[0]


def compute_confidence(
    best_score: LoopScore,
    second_total: float | None,
    candidate_count: int,
    sustain_confidence: float,
    pitch: PitchEstimate,
    crossfade_consistency: float,
    refinement_shift_ratio: float,
) -> tuple[float, str]:
    """Blend the section 18 inputs into one 0..1 confidence value."""
    quality = 1.0 - best_score.total
    margin = (
        0.5
        if second_total is None
        else float(np.clip((second_total - best_score.total) * 10.0, 0.0, 1.0))
    )
    count_term = float(np.clip(candidate_count / 8.0, 0.0, 1.0))
    pitch_term = 0.5 + 0.5 * pitch.confidence
    stability_term = float(np.clip(sustain_confidence, 0.0, 1.0))
    shift_term = float(np.clip(1.0 - refinement_shift_ratio, 0.0, 1.0))

    value = (
        0.35 * quality
        + 0.15 * margin
        + 0.10 * count_term
        + 0.15 * stability_term
        + 0.10 * pitch_term
        + 0.10 * crossfade_consistency
        + 0.05 * shift_term
    )
    value = float(np.clip(value, 0.0, 1.0))
    if value >= CONFIDENCE_HIGH_THRESHOLD:
        label = "high"
    elif value >= CONFIDENCE_MEDIUM_THRESHOLD:
        label = "medium"
    else:
        label = "low"
    return value, label
