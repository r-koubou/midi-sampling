"""Shared synthesis helpers for tests."""

from __future__ import annotations

import numpy as np
import pytest

SAMPLE_RATE = 44100
NOISE_AMP = 1e-4  # about -80 dBFS RMS


def make_noise(seconds: float, channels: int = 1, seed: int = 0) -> np.ndarray:
    """Gaussian noise at roughly -80 dBFS RMS, shaped (samples, channels)."""
    rng = np.random.default_rng(seed)
    n = round(seconds * SAMPLE_RATE)
    return rng.normal(0.0, NOISE_AMP, size=(n, channels))


def make_tone(
    seconds: float,
    amplitude: float = 0.3,
    frequency: float = 440.0,
    channels: int = 1,
) -> np.ndarray:
    """Sine tone shaped (samples, channels)."""
    n = round(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    tone = amplitude * np.sin(2.0 * np.pi * frequency * t)
    return np.tile(tone[:, None], (1, channels))


def make_standard_sample(
    channels: int = 1,
    head_noise: float = 1.0,
    tone_seconds: float = 2.0,
    tail_noise: float = 1.0,
    amplitude: float = 0.3,
) -> tuple[np.ndarray, int, int]:
    """Noise + tone + noise; returns (audio, true_start, true_end)."""
    head = make_noise(head_noise, channels, seed=1)
    tone = make_tone(tone_seconds, amplitude, channels=channels)
    tail = make_noise(tail_noise, channels, seed=2)
    audio = np.vstack([head, tone, tail])
    return audio, head.shape[0], head.shape[0] + tone.shape[0]


@pytest.fixture
def sample_rate() -> int:
    return SAMPLE_RATE
