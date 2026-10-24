"""Pitch estimation tests (sections 12, 29.4)."""

from __future__ import annotations

import numpy as np
import pytest

from sample_loop_detector.analysis.features import FrameFeatures, extract_features
from sample_loop_detector.analysis.pitch import estimate_pitch, weighted_median
from sample_loop_detector.analysis.preprocessing import (
    compute_floors,
    prepare_analysis_audio,
)
from sample_loop_detector.analysis.sustain import SustainAnalysis, detect_sustain
from sample_loop_detector.config import make_frame_config
from tests.conftest import noise_pad, sustained_tone

SR = 22050


def _analyze(audio: np.ndarray) -> tuple[FrameFeatures, SustainAnalysis]:
    if audio.ndim == 1:
        audio = audio[:, None]
    config = make_frame_config(SR)
    analysis = prepare_analysis_audio(audio)
    features = extract_features(analysis, config, 40.0, 4000.0)
    floors = compute_floors(features.rms_db)
    sustain = detect_sustain(features, config, floors.active_floor_db, 0.75)
    return features, sustain


def test_weighted_median_basic() -> None:
    values = np.array([1.0, 2.0, 100.0])
    weights = np.array([1.0, 1.0, 0.01])
    assert weighted_median(values, weights) == 2.0


def test_pitch_detected_for_tone() -> None:
    features, sustain = _analyze(sustained_tone(sample_rate=SR, seconds=6.0, f0=220.0))
    config = make_frame_config(SR)
    pitch = estimate_pitch(features, sustain, config)
    assert pitch.f0_hz is not None
    assert pitch.f0_hz == pytest.approx(220.0, rel=0.02)
    assert pitch.period_samples == pytest.approx(SR / 220.0, rel=0.02)
    assert pitch.voiced_ratio > 0.8


def test_pitch_disabled_for_noise() -> None:
    features, sustain = _analyze(noise_pad(sample_rate=SR, seconds=6.0))
    config = make_frame_config(SR)
    pitch = estimate_pitch(features, sustain, config)
    assert pitch.f0_hz is None
    assert pitch.period_samples is None
