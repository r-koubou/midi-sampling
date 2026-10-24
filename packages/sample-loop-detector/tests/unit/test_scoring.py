"""Score aggregation and selection tests (sections 17, 18)."""

from __future__ import annotations

import pytest

from sample_loop_detector.analysis.render import SeamMetrics
from sample_loop_detector.analysis.scoring import (
    check_acceptance,
    combine_scores,
    compute_confidence,
    hard_seam_score,
    select_best,
)
from sample_loop_detector.models import (
    LoopCandidate,
    LoopScore,
    PitchEstimate,
    SustainRegion,
)


def _metrics(**overrides: float | None) -> SeamMetrics:
    values: dict[str, float | None] = {
        "waveform": 0.1,
        "amplitude": 0.1,
        "derivative": 0.1,
        "spectral": 0.1,
        "level": 0.1,
        "pitch": 0.1,
        "modulation": 0.1,
        "stereo": 0.1,
    }
    values.update(overrides)
    return SeamMetrics(**values)  # type: ignore[arg-type]


def _score(total: float = 0.2, hard: float = 0.2) -> LoopScore:
    return LoopScore(
        total=total,
        hard_seam=hard,
        crossfade_seam=0.1,
        waveform=0.1,
        spectral=0.1,
        level=0.1,
        pitch=None,
        modulation=None,
        stereo=None,
        sustain=0.1,
        length_penalty=0.0,
    )


_SUSTAIN = SustainRegion(start_frame=0, end_frame=200000, stability_score=0.1, confidence=0.9)


def test_hard_seam_score_uniform() -> None:
    assert hard_seam_score(_metrics()) == pytest.approx(0.1)


def test_hard_seam_score_renormalizes_missing_features() -> None:
    # Disabled features must not dilute the score.
    with_missing = hard_seam_score(_metrics(pitch=None, modulation=None, stereo=None))
    assert with_missing == pytest.approx(0.1)


def test_combine_scores_weights() -> None:
    candidate = LoopCandidate(start_frame=0, end_frame=66150, crossfade_frames=0, coarse_score=0.0)
    score = combine_scores(candidate, _metrics(), 0.2, _SUSTAIN, 22050)
    # 3-second loop: no length penalty.
    assert score.length_penalty == 0.0
    expected = 0.55 * 0.1 + 0.30 * 0.2 + 0.10 * 0.1 + 0.05 * 0.0
    assert score.total == pytest.approx(expected)


def test_acceptance_thresholds() -> None:
    good = check_acceptance(_score(total=0.2, hard=0.3), 0.8, 0.35, 0.5, 3.0)
    assert good.accepted

    bad_total = check_acceptance(_score(total=0.5, hard=0.3), 0.8, 0.35, 0.5, 3.0)
    assert not bad_total.accepted
    assert bad_total.reason == "all_candidates_above_threshold"

    bad_hard = check_acceptance(_score(total=0.2, hard=0.6), 0.8, 0.35, 0.5, 3.0)
    assert not bad_hard.accepted
    assert bad_hard.reason == "hard_seam_above_threshold"

    bad_sustain = check_acceptance(_score(), 0.2, 0.35, 0.5, 3.0)
    assert not bad_sustain.accepted
    assert bad_sustain.reason == "no_stable_sustain_region"


def test_tie_break_prefers_longer_loop() -> None:
    short = LoopCandidate(start_frame=1000, end_frame=45100, crossfade_frames=0, coarse_score=0.0)
    long = LoopCandidate(start_frame=1000, end_frame=89200, crossfade_frames=0, coarse_score=0.0)
    entries = [
        (short, _score(total=0.200), 0.0),
        (long, _score(total=0.210), 0.0),  # within the 0.02 tie window
    ]
    assert select_best(entries, _SUSTAIN) == 1


def test_clear_winner_not_tie_broken() -> None:
    short = LoopCandidate(start_frame=1000, end_frame=45100, crossfade_frames=0, coarse_score=0.0)
    long = LoopCandidate(start_frame=1000, end_frame=89200, crossfade_frames=0, coarse_score=0.0)
    entries = [
        (short, _score(total=0.10), 0.0),
        (long, _score(total=0.30), 0.0),
    ]
    assert select_best(entries, _SUSTAIN) == 0


def test_confidence_labels() -> None:
    pitch = PitchEstimate(f0_hz=220.0, confidence=0.9, voiced_ratio=0.9, period_samples=100.0)
    high_value, high_label = compute_confidence(_score(total=0.05), 0.4, 20, 0.95, pitch, 1.0, 0.0)
    assert high_label == "high"
    assert high_value > 0.75

    weak_pitch = PitchEstimate(f0_hz=None, confidence=0.0, voiced_ratio=0.0, period_samples=None)
    low_value, low_label = compute_confidence(
        _score(total=0.34, hard=0.44), 0.341, 1, 0.5, weak_pitch, 0.0, 0.5
    )
    assert low_label in ("low", "medium")
    assert low_value < high_value
