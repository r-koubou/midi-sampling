"""Low-frequency modulation (vibrato / tremolo / timbre) phase extraction.

Envelope-rate series (frame rate = 1 / hop seconds) are band-passed to the
modulation band and converted to instantaneous phase via the analytic
signal.  Phases are compared between loop endpoints during seam scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.signal import butter, hilbert, sosfiltfilt

from sample_loop_detector.analysis.features import FrameFeatures
from sample_loop_detector.config import (
    MODULATION_FMAX_HZ,
    MODULATION_FMIN_HZ,
    FrameConfig,
)

FloatArray = NDArray[np.float64]

# A band signal must carry at least this share of its source's variance to
# count as meaningful modulation.
_MIN_RELATIVE_STRENGTH = 0.05


@dataclass(frozen=True)
class ModulationTrack:
    """Band-limited modulation of one envelope series."""

    phase: FloatArray  # radians, per frame
    frequency_hz: float  # dominant modulation frequency
    strength: float  # 0..1 relative variance in the modulation band
    valid: bool


@dataclass(frozen=True)
class ModulationFeatures:
    tremolo: ModulationTrack  # from RMS envelope
    vibrato: ModulationTrack  # from F0 track
    timbre: ModulationTrack  # from spectral centroid

    @property
    def any_valid(self) -> bool:
        return self.tremolo.valid or self.vibrato.valid or self.timbre.valid


def _analyze_series(series: FloatArray, frame_rate: float) -> ModulationTrack:
    n = len(series)
    empty = ModulationTrack(phase=np.zeros(n), frequency_hz=0.0, strength=0.0, valid=False)
    if n < 32:
        return empty

    finite = np.isfinite(series)
    if finite.mean() < 0.5:
        return empty
    filled = series.copy()
    if not finite.all():
        indices = np.arange(n, dtype=np.float64)
        filled[~finite] = np.interp(indices[~finite], indices[finite], series[finite])
    filled = filled - float(np.mean(filled))

    total_var = float(np.var(filled))
    if total_var < 1e-12:
        return empty

    nyquist = frame_rate / 2.0
    high = min(MODULATION_FMAX_HZ, nyquist * 0.9)
    low = MODULATION_FMIN_HZ
    if low >= high:
        return empty
    sos = butter(2, [low / nyquist, high / nyquist], btype="bandpass", output="sos")
    band = np.asarray(sosfiltfilt(sos, filled), dtype=np.float64)

    band_var = float(np.var(band))
    strength = band_var / total_var
    if strength < _MIN_RELATIVE_STRENGTH:
        return ModulationTrack(phase=np.zeros(n), frequency_hz=0.0, strength=strength, valid=False)

    analytic = hilbert(band)
    phase = np.asarray(np.angle(analytic), dtype=np.float64)

    spectrum = np.abs(np.fft.rfft(band))
    freqs = np.fft.rfftfreq(n, d=1.0 / frame_rate)
    in_band = (freqs >= low) & (freqs <= high)
    if not in_band.any():
        return empty
    dominant = float(freqs[in_band][int(np.argmax(spectrum[in_band]))])

    return ModulationTrack(
        phase=phase,
        frequency_hz=dominant,
        strength=min(1.0, strength),
        valid=dominant > 0.0,
    )


def extract_modulation(features: FrameFeatures, config: FrameConfig) -> ModulationFeatures:
    frame_rate = config.sample_rate / config.hop_length
    return ModulationFeatures(
        tremolo=_analyze_series(features.rms_db, frame_rate),
        vibrato=_analyze_series(features.cents, frame_rate),
        timbre=_analyze_series(features.centroid, frame_rate),
    )


def phase_difference_cost(track: ModulationTrack, frame_a: int, frame_b: int) -> float | None:
    """Return 0..1 cost for the modulation phase mismatch between two frames."""
    if not track.valid:
        return None
    n = len(track.phase)
    if not (0 <= frame_a < n and 0 <= frame_b < n):
        return None
    delta = track.phase[frame_a] - track.phase[frame_b]
    wrapped = float(np.abs(np.angle(np.exp(1j * delta))))
    return wrapped / np.pi
