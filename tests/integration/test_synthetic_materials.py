"""Pipeline tests on modulated and stereo synthetic material (section 29.4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.config import DetectionSettings
from sample_loop_detector.pipeline import DetectionOutput, run_detection
from tests.conftest import build_wav_bytes, noise_pad, sustained_tone

SR = 22050


def _detect(
    tmp_path: Path, name: str, audio: NDArray[np.float64], bits: int = 16
) -> DetectionOutput:
    path = tmp_path / name
    path.write_bytes(build_wav_bytes(audio, SR, bits_per_sample=bits))
    settings = DetectionSettings(
        input_path=path,
        output_path=tmp_path / f"{name}.looped.wav",
        dry_run=True,
    )
    return run_detection(settings)


def test_vibrato_tone_loops_full_modulation_cycles(tmp_path: Path) -> None:
    audio = sustained_tone(sample_rate=SR, seconds=6.0, vibrato_hz=5.5, vibrato_cents=35.0)
    output = _detect(tmp_path, "vibrato.wav", audio)
    assert output.succeeded, output.failure_reason
    assert output.result is not None
    # Loops shorter than one vibrato cycle cannot be phase-consistent.
    assert output.result.selected.length_frames / SR > 1.0 / 5.5


def test_tremolo_tone_detected(tmp_path: Path) -> None:
    audio = sustained_tone(sample_rate=SR, seconds=6.0, tremolo_hz=4.0, tremolo_depth=0.15)
    output = _detect(tmp_path, "tremolo.wav", audio)
    assert output.succeeded, output.failure_reason


def test_stereo_tone_detected_with_stereo_scores(tmp_path: Path) -> None:
    audio = sustained_tone(sample_rate=SR, seconds=6.0, stereo=True)
    output = _detect(tmp_path, "stereo.wav", audio, bits=24)
    assert output.succeeded, output.failure_reason
    assert output.result is not None
    # Stereo continuity must have been evaluated, not skipped.
    assert output.result.score.stereo is not None


def test_noise_pad_detected_without_pitch(tmp_path: Path) -> None:
    output = _detect(tmp_path, "noise.wav", noise_pad(sample_rate=SR, seconds=6.0))
    assert output.pitch is not None
    assert output.pitch.f0_hz is None
    if output.succeeded:
        assert output.result is not None
        assert output.result.score.pitch is None


def test_pipeline_determinism(tmp_path: Path) -> None:
    audio = sustained_tone(sample_rate=SR, seconds=6.0)
    first = _detect(tmp_path, "det_a.wav", audio)
    second = _detect(tmp_path, "det_b.wav", audio)
    assert first.succeeded and second.succeeded
    assert first.result is not None and second.result is not None
    assert first.result.selected == second.result.selected
    assert first.result.score == second.result.score
