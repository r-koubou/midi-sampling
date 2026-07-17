"""Sustain detection tests on synthetic material (sections 11, 29.4)."""

from __future__ import annotations

import numpy as np
import pytest

from sample_loop_detector.analysis.features import FrameFeatures, extract_features
from sample_loop_detector.analysis.preprocessing import (
    compute_floors,
    prepare_analysis_audio,
)
from sample_loop_detector.analysis.sustain import detect_sustain
from sample_loop_detector.config import make_frame_config
from sample_loop_detector.exceptions import InvalidWaveError, SustainNotFoundError
from tests.conftest import noise_pad, percussive_hit, sustained_tone

SR = 22050


def _features(audio: np.ndarray) -> tuple[FrameFeatures, float]:
    if audio.ndim == 1:
        audio = audio[:, None]
    config = make_frame_config(SR)
    analysis = prepare_analysis_audio(audio)
    features = extract_features(analysis, config, 40.0, 4000.0)
    floors = compute_floors(features.rms_db)
    return features, floors.active_floor_db


@pytest.fixture(scope="module")
def tone_features() -> tuple[FrameFeatures, float]:
    return _features(sustained_tone(sample_rate=SR, seconds=6.0))


def test_sustain_excludes_attack_and_release(
    tone_features: tuple[FrameFeatures, float],
) -> None:
    features, floor = tone_features
    config = make_frame_config(SR)
    sustain = detect_sustain(features, config, floor, 0.75)
    start_seconds = sustain.region.start_frame / SR
    end_seconds = sustain.region.end_frame / SR
    # Attack is 0.15 s plus a 200 ms exclusion zone.
    assert start_seconds >= 0.2
    # Release starts at 5.7 s.
    assert end_seconds <= 5.9
    assert end_seconds - start_seconds >= 0.75


def test_sustain_stability_is_low_for_steady_tone(
    tone_features: tuple[FrameFeatures, float],
) -> None:
    features, floor = tone_features
    config = make_frame_config(SR)
    sustain = detect_sustain(features, config, floor, 0.75)
    assert sustain.region.stability_score < 0.3
    assert sustain.region.confidence > 0.5


def test_sustain_respects_user_search_range(
    tone_features: tuple[FrameFeatures, float],
) -> None:
    features, floor = tone_features
    config = make_frame_config(SR)
    sustain = detect_sustain(features, config, floor, 0.75, 2.0, 5.0)
    assert sustain.region.start_frame / SR >= 1.8
    assert sustain.region.end_frame / SR <= 5.4


def test_noise_pad_has_sustain() -> None:
    features, floor = _features(noise_pad(sample_rate=SR, seconds=6.0))
    config = make_frame_config(SR)
    sustain = detect_sustain(features, config, floor, 0.75)
    assert sustain.region.end_frame > sustain.region.start_frame


def test_percussive_hit_has_no_sustain() -> None:
    features, floor = _features(percussive_hit(sample_rate=SR, seconds=2.0))
    config = make_frame_config(SR)
    with pytest.raises(SustainNotFoundError):
        detect_sustain(features, config, floor, 0.75)


def test_silence_rejected() -> None:
    with pytest.raises(InvalidWaveError):
        _features(np.zeros((SR * 2, 1)))


def test_detection_is_deterministic() -> None:
    audio = sustained_tone(sample_rate=SR, seconds=6.0)
    features_a, floor_a = _features(audio)
    features_b, floor_b = _features(audio)
    config = make_frame_config(SR)
    sustain_a = detect_sustain(features_a, config, floor_a, 0.75)
    sustain_b = detect_sustain(features_b, config, floor_b, 0.75)
    assert sustain_a.region == sustain_b.region
