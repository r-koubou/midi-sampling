"""Seam rendering and evaluation tests (sections 15, 16, 29.4)."""

from __future__ import annotations

import numpy as np
import pytest

from sample_loop_detector.analysis.features import FrameFeatures, extract_features
from sample_loop_detector.analysis.modulation import ModulationFeatures, extract_modulation
from sample_loop_detector.analysis.pitch import estimate_pitch
from sample_loop_detector.analysis.preprocessing import (
    compute_floors,
    prepare_analysis_audio,
)
from sample_loop_detector.analysis.refinement import refine_candidate
from sample_loop_detector.analysis.render import (
    allowed_crossfade_samples,
    crossfade_curves,
    evaluate_crossfade,
    evaluate_hard_seam,
    render_crossfaded_repeats,
)
from sample_loop_detector.analysis.sustain import SustainAnalysis, detect_sustain
from sample_loop_detector.config import make_frame_config
from sample_loop_detector.models import LoopCandidate, PitchEstimate
from tests.conftest import sustained_tone

SR = 22050
F0 = 220.0


@pytest.fixture(scope="module")
def tone_context() -> tuple[
    np.ndarray, FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures
]:
    audio = sustained_tone(sample_rate=SR, seconds=6.0, f0=F0)[:, None]
    config = make_frame_config(SR)
    analysis = prepare_analysis_audio(audio)
    features = extract_features(analysis, config, 40.0, 4000.0)
    floors = compute_floors(features.rms_db)
    sustain = detect_sustain(features, config, floors.active_floor_db, 0.75)
    pitch = estimate_pitch(features, sustain, config)
    modulation = extract_modulation(features, config)
    return analysis, features, sustain, pitch, modulation


def test_crossfade_curves_are_complementary() -> None:
    fade_in, fade_out = crossfade_curves(256)
    assert np.allclose(fade_in + fade_out, 1.0)
    assert fade_in[0] == pytest.approx(0.0)
    assert fade_in[-1] == pytest.approx(1.0)


def test_allowed_crossfade_constraints() -> None:
    # 20% cap: with a 0.5 s loop at 22050 Hz only short fades survive.
    allowed = allowed_crossfade_samples((20.0, 50.0, 100.0, 200.0, 600.0), 11025, SR)
    assert all(cf <= 11025 * 0.2 for cf in allowed)
    assert all(cf >= 8 for cf in allowed)
    assert round(0.6 * SR) not in allowed


def test_render_crossfaded_repeats_length() -> None:
    loop = np.ones((1000, 1))
    crossfade = 100
    rendered, seams = render_crossfaded_repeats(loop, crossfade, repeats=4)
    assert rendered.shape[0] == 4 * 1000 - 3 * crossfade
    assert len(seams) == 3
    # Constant signal stays constant through complementary fades.
    assert np.allclose(rendered, 1.0)


def test_hard_seam_prefers_period_aligned_loop(
    tone_context: tuple[
        np.ndarray, FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures
    ],
) -> None:
    analysis, features, sustain, pitch, modulation = tone_context
    config = make_frame_config(SR)
    period = SR / F0
    start = sustain.region.start_frame + 4000
    aligned_end = start + round(200 * period)
    misaligned_end = aligned_end + round(period / 2)

    good = evaluate_hard_seam(analysis, features, config, start, aligned_end, pitch, modulation)
    bad = evaluate_hard_seam(analysis, features, config, start, misaligned_end, pitch, modulation)
    assert good.waveform < bad.waveform
    assert good.amplitude <= bad.amplitude + 1e-9


def test_refinement_improves_correlation(
    tone_context: tuple[
        np.ndarray, FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures
    ],
) -> None:
    analysis, _features, sustain, pitch, _modulation = tone_context
    period = SR / F0
    start = sustain.region.start_frame + 4000
    # Start half a period off; refinement should pull it near a multiple.
    rough_end = start + round(200 * period + period / 2)
    candidate = LoopCandidate(
        start_frame=start, end_frame=rough_end, crossfade_frames=0, coarse_score=0.0
    )
    refined = refine_candidate(
        analysis, candidate, SR, pitch, sustain.region.start_frame, sustain.region.end_frame
    )
    count = (refined.end_frame - refined.start_frame) / period
    assert abs(count - round(count)) < 0.15


def test_crossfade_evaluation_scores_smooth_loop(
    tone_context: tuple[
        np.ndarray, FrameFeatures, SustainAnalysis, PitchEstimate, ModulationFeatures
    ],
) -> None:
    analysis, _features, sustain, _pitch, _modulation = tone_context
    period = SR / F0
    start = sustain.region.start_frame + 4000
    end = start + round(200 * period)
    loop = analysis[start : end + 1]
    cost = evaluate_crossfade(loop, round(0.02 * SR), SR)
    assert 0.0 <= cost < 0.5
