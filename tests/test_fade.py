"""Unit tests for fade application."""

from __future__ import annotations

import numpy as np

from wav_silence_trimmer.fade import apply_fades

SAMPLE_RATE = 44100


def test_fade_in_starts_near_zero() -> None:
    audio = np.ones((SAMPLE_RATE, 2))
    faded, n_in, _ = apply_fades(audio, SAMPLE_RATE, 5.0, 0.0)
    assert n_in == round(SAMPLE_RATE * 0.005)
    assert abs(faded[0, 0]) < 1e-9
    assert np.isclose(faded[n_in, 0], 1.0)


def test_fade_in_end_near_one() -> None:
    audio = np.ones((SAMPLE_RATE, 1))
    faded, n_in, _ = apply_fades(audio, SAMPLE_RATE, 5.0, 0.0)
    assert faded[n_in - 1, 0] > 0.99


def test_fade_out_ends_near_zero() -> None:
    audio = np.ones((SAMPLE_RATE, 1))
    faded, _, n_out = apply_fades(audio, SAMPLE_RATE, 0.0, 5.0)
    assert n_out == round(SAMPLE_RATE * 0.005)
    assert abs(faded[-1, 0]) < 1e-2
    assert np.isclose(faded[-n_out - 1, 0], 1.0)


def test_same_gain_on_all_channels() -> None:
    audio = np.ones((SAMPLE_RATE, 4))
    faded, _, _ = apply_fades(audio, SAMPLE_RATE, 2.0, 3.0)
    for ch in range(1, 4):
        assert np.array_equal(faded[:, 0], faded[:, ch])


def test_very_short_audio_no_exception() -> None:
    audio = np.ones((3, 2))
    faded, n_in, n_out = apply_fades(audio, SAMPLE_RATE, 10.0, 10.0)
    assert faded.shape == audio.shape
    assert n_in <= 3
    assert n_out <= 3


def test_zero_length_audio() -> None:
    audio = np.ones((0, 2))
    faded, n_in, n_out = apply_fades(audio, SAMPLE_RATE, 1.0, 5.0)
    assert faded.shape == audio.shape
    assert n_in == 0
    assert n_out == 0


def test_disabled_fades_leave_audio_unchanged() -> None:
    audio = np.ones((SAMPLE_RATE, 2))
    faded, n_in, n_out = apply_fades(
        audio, SAMPLE_RATE, 5.0, 5.0, apply_fade_in=False, apply_fade_out=False
    )
    assert np.array_equal(faded, audio)
    assert n_in == 0
    assert n_out == 0


def test_original_not_mutated() -> None:
    audio = np.ones((SAMPLE_RATE, 1))
    apply_fades(audio, SAMPLE_RATE, 5.0, 5.0)
    assert np.all(audio == 1.0)
