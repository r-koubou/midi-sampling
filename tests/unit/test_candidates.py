"""Loop-candidate generation tests (sections 13, 29.4)."""

from __future__ import annotations

import numpy as np
import pytest

from sample_loop_detector.analysis.candidates import (
    generate_candidates,
    loop_length_penalty,
    period_error_penalty,
)
from sample_loop_detector.analysis.features import FrameFeatures, extract_features
from sample_loop_detector.analysis.modulation import ModulationFeatures, extract_modulation
from sample_loop_detector.analysis.pitch import estimate_pitch
from sample_loop_detector.analysis.preprocessing import (
    compute_floors,
    prepare_analysis_audio,
)
from sample_loop_detector.analysis.sustain import SustainAnalysis, detect_sustain
from sample_loop_detector.config import MAX_COARSE_CANDIDATES, make_frame_config
from sample_loop_detector.models import PitchEstimate
from tests.conftest import sustained_tone

SR = 22050


@pytest.fixture(scope="module")
def tone_analysis() -> tuple[FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures]:
    audio = sustained_tone(sample_rate=SR, seconds=6.0)[:, None]
    config = make_frame_config(SR)
    analysis = prepare_analysis_audio(audio)
    features = extract_features(analysis, config, 40.0, 4000.0)
    floors = compute_floors(features.rms_db)
    sustain = detect_sustain(features, config, floors.active_floor_db, 0.75)
    pitch = estimate_pitch(features, sustain, config)
    modulation = extract_modulation(features, config)
    return features, sustain, pitch, modulation


def test_length_penalty_bands() -> None:
    assert loop_length_penalty(0.4) is None
    strong = loop_length_penalty(0.55)
    light = loop_length_penalty(1.5)
    free = loop_length_penalty(2.5)
    assert strong is not None and light is not None and free is not None
    assert strong > light > free == 0.0


def test_period_error_penalty() -> None:
    assert period_error_penalty(1000, None) == 0.0
    assert period_error_penalty(1000, 100.0) == pytest.approx(0.0)
    assert period_error_penalty(1050, 100.0) == pytest.approx(1.0)


def test_candidates_respect_constraints(
    tone_analysis: tuple[FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures],
) -> None:
    features, sustain, pitch, modulation = tone_analysis
    config = make_frame_config(SR)
    candidates = generate_candidates(features, sustain, config, pitch, modulation, 0.5, 8.0, 0.2)
    assert 0 < len(candidates) <= MAX_COARSE_CANDIDATES
    for candidate in candidates:
        assert sustain.region.start_frame <= candidate.start_frame
        assert candidate.end_frame <= sustain.region.end_frame
        length_seconds = candidate.length_frames / SR
        assert 0.5 <= length_seconds <= 8.0


def test_candidates_prefer_period_multiples(
    tone_analysis: tuple[FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures],
) -> None:
    features, sustain, pitch, modulation = tone_analysis
    config = make_frame_config(SR)
    candidates = generate_candidates(features, sustain, config, pitch, modulation, 0.5, 8.0, 0.2)
    assert pitch.period_samples is not None
    errors = []
    for candidate in candidates[:10]:
        count = candidate.length_frames / pitch.period_samples
        errors.append(abs(count - round(count)))
    # The bulk of the top candidates should sit near period multiples.
    assert np.median(errors) < 0.25


def test_candidates_are_deterministic(
    tone_analysis: tuple[FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures],
) -> None:
    features, sustain, pitch, modulation = tone_analysis
    config = make_frame_config(SR)
    first = generate_candidates(features, sustain, config, pitch, modulation, 0.5, 8.0, 0.2)
    second = generate_candidates(features, sustain, config, pitch, modulation, 0.5, 8.0, 0.2)
    assert first == second
