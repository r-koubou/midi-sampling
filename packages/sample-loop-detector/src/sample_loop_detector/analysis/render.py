"""Hard-seam and crossfade-seam rendering and evaluation (sections 15, 16)."""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.analysis.features import FrameFeatures
from sample_loop_detector.analysis.modulation import ModulationFeatures, phase_difference_cost
from sample_loop_detector.analysis.refinement import waveform_correlation
from sample_loop_detector.config import (
    AMPLITUDE_JUMP_SCALE,
    CROSSFADE_MAX_RATIO,
    CROSSFADE_MAX_SECONDS,
    CROSSFADE_MIN_SAMPLES,
    DERIVATIVE_JUMP_SCALE,
    LEVEL_DB_SCALE,
    LEVEL_SLOPE_SCALE,
    PITCH_CENTS_SCALE,
    RENDER_REPEAT_COUNT,
    SEAM_WINDOW_SECONDS,
    SPECTRAL_RELATIVE_SCALE,
    STEREO_CORR_SCALE,
    STEREO_SIDE_DB_SCALE,
    FrameConfig,
)
from sample_loop_detector.models import PitchEstimate

FloatArray = NDArray[np.float64]

_EPS = 1e-12


@dataclass(frozen=True)
class SeamMetrics:
    """Individual 0..1 seam costs; None marks disabled features."""

    waveform: float
    amplitude: float
    derivative: float
    spectral: float
    level: float
    pitch: float | None
    modulation: float | None
    stereo: float | None


def _clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def _local_rms(mono: FloatArray, position: int, window: int) -> float:
    lo = max(0, position - window)
    hi = min(len(mono), position + window)
    if hi <= lo:
        return 0.0
    return float(np.sqrt(np.mean(mono[lo:hi] ** 2)))


def _frame_at_sample(config: FrameConfig, position: int, n_frames: int) -> int:
    frame = (position - config.frame_length // 2) // config.hop_length
    return int(np.clip(frame, 0, n_frames - 1))


def _segment_mel_distance(mono_segment: FloatArray, boundary: int, sample_rate: int) -> float:
    """log-Mel distance between the frames straddling ``boundary``."""
    n_fft = 1024
    hop = 256
    if len(mono_segment) < 2 * n_fft:
        return 0.0
    mel = librosa.feature.melspectrogram(
        y=np.ascontiguousarray(mono_segment),
        sr=sample_rate,
        n_fft=n_fft,
        hop_length=hop,
        center=False,
        power=2.0,
        n_mels=40,
    ).astype(np.float64)
    log_mel = librosa.power_to_db(mel, ref=1.0, top_db=None).T
    if log_mel.shape[0] < 2:
        return 0.0
    # Frame index whose window covers the boundary sample.
    boundary_frame = int(np.clip((boundary - n_fft // 2) // hop, 0, log_mel.shape[0] - 2))
    diff = log_mel[boundary_frame + 1] - log_mel[boundary_frame]
    return float(np.linalg.norm(diff) / np.sqrt(log_mel.shape[1]))


def evaluate_hard_seam(
    audio: FloatArray,
    features: FrameFeatures,
    config: FrameConfig,
    start: int,
    end: int,
    pitch: PitchEstimate,
    modulation: ModulationFeatures,
) -> SeamMetrics:
    """Evaluate the direct end→start jump of a candidate."""
    mono = audio.mean(axis=1)
    sr = config.sample_rate
    window = max(64, round(SEAM_WINDOW_SECONDS * sr))
    local_rms = max(_local_rms(mono, end, window), _local_rms(mono, start, window), _EPS)

    # 15.1 amplitude difference, normalized by local RMS.
    amplitude_jump = abs(float(mono[end] - mono[start])) / local_rms
    amplitude = _clip01(amplitude_jump / AMPLITUDE_JUMP_SCALE)

    # 15.2 first-derivative difference.
    end_slope = float(mono[end] - mono[end - 1])
    start_slope = float(mono[start + 1] - mono[start])
    derivative_rms = float(np.sqrt(np.mean(np.diff(mono[start : end + 1]) ** 2))) + _EPS
    derivative = _clip01(abs(end_slope - start_slope) / derivative_rms / DERIVATIVE_JUMP_SCALE)

    # 15.3 waveform correlation: average and worst channel.
    per_channel = [
        waveform_correlation(audio[:, ch : ch + 1], start, end, window)
        for ch in range(audio.shape[1])
    ]
    costs = [(1.0 - corr) / 2.0 for corr in per_channel]
    waveform = _clip01(0.5 * float(np.mean(costs)) + 0.5 * float(np.max(costs)))

    # 15.4 spectral seam relative to internal adjacent-frame variation.
    ctx = max(2048, round(0.1 * sr))
    seg_lo = max(0, end - ctx + 1)
    seg_hi = min(len(mono), start + ctx)
    segment = np.concatenate([mono[seg_lo : end + 1], mono[start:seg_hi]])
    boundary_distance = _segment_mel_distance(segment, end + 1 - seg_lo, sr)
    frame_lo = _frame_at_sample(config, start, features.n_frames)
    frame_hi = _frame_at_sample(config, end, features.n_frames)
    internal = features.mel_frame_dist[frame_lo : frame_hi + 1]
    internal_median = float(np.median(internal)) if internal.size else 0.0
    relative = boundary_distance / (internal_median + _EPS)
    spectral = _clip01(max(0.0, relative - 1.0) / SPECTRAL_RELATIVE_SCALE)

    # 15.5 level continuity: dB step, slope step, per-repeat ramp.
    end_frames = slice(max(frame_lo, frame_hi - 2), frame_hi + 1)
    start_frames = slice(frame_lo, min(frame_hi + 1, frame_lo + 3))
    db_step = abs(
        float(np.mean(features.rms_db[end_frames]) - np.mean(features.rms_db[start_frames]))
    )
    slope_step = abs(
        float(np.mean(features.rms_slope[end_frames]) - np.mean(features.rms_slope[start_frames]))
    )
    level = _clip01(0.6 * db_step / LEVEL_DB_SCALE + 0.4 * slope_step * LEVEL_SLOPE_SCALE)

    # 15.6 pitch continuity.
    pitch_cost: float | None = None
    if pitch.f0_hz is not None:
        cents_start = features.cents[start_frames]
        cents_end = features.cents[end_frames]
        finite_start = cents_start[np.isfinite(cents_start)]
        finite_end = cents_end[np.isfinite(cents_end)]
        if finite_start.size and finite_end.size:
            cents_step = abs(float(np.mean(finite_end) - np.mean(finite_start)))
            pitch_cost = _clip01(cents_step / PITCH_CENTS_SCALE)

    # Modulation phase continuity (vibrato / tremolo / timbre).
    phase_costs: list[float] = []
    for track in (modulation.vibrato, modulation.tremolo, modulation.timbre):
        cost = phase_difference_cost(track, frame_lo, frame_hi)
        if cost is not None:
            phase_costs.append(cost * track.strength)
    modulation_cost = _clip01(float(np.mean(phase_costs))) if phase_costs else None

    # 15.7 stereo continuity.
    stereo_cost: float | None = None
    if features.side_rms_db.size:
        side_step = abs(
            float(
                np.mean(features.side_rms_db[end_frames])
                - np.mean(features.side_rms_db[start_frames])
            )
        )
        corr_step = abs(
            float(np.mean(features.lr_corr[end_frames]) - np.mean(features.lr_corr[start_frames]))
        )
        mid_side_step = abs(
            float(
                np.mean(features.side_rms_db[end_frames] - features.rms_db[end_frames])
                - np.mean(features.side_rms_db[start_frames] - features.rms_db[start_frames])
            )
        )
        stereo_cost = _clip01(
            0.4 * side_step / STEREO_SIDE_DB_SCALE
            + 0.3 * corr_step / STEREO_CORR_SCALE
            + 0.3 * mid_side_step / STEREO_SIDE_DB_SCALE
        )

    return SeamMetrics(
        waveform=waveform,
        amplitude=amplitude,
        derivative=derivative,
        spectral=spectral,
        level=level,
        pitch=pitch_cost,
        modulation=modulation_cost,
        stereo=stereo_cost,
    )


def allowed_crossfade_samples(
    crossfade_lengths_ms: tuple[float, ...], loop_length: int, sample_rate: int
) -> tuple[int, ...]:
    """Apply the section 16.2 constraints to the requested crossfade lengths."""
    result = []
    for ms in crossfade_lengths_ms:
        samples = round(ms / 1000.0 * sample_rate)
        if samples < CROSSFADE_MIN_SAMPLES:
            continue
        if samples > loop_length * CROSSFADE_MAX_RATIO:
            continue
        if samples > CROSSFADE_MAX_SECONDS * sample_rate:
            continue
        result.append(samples)
    return tuple(result)


def crossfade_curves(crossfade_frames: int) -> tuple[FloatArray, FloatArray]:
    """Complementary cosine fade-in / fade-out curves (section 16.3)."""
    phase = np.linspace(0.0, np.pi, crossfade_frames)
    fade_in = 0.5 - 0.5 * np.cos(phase)
    fade_out = 1.0 - fade_in
    return fade_in, fade_out


def render_crossfaded_repeats(
    loop: FloatArray, crossfade: int, repeats: int = RENDER_REPEAT_COUNT
) -> tuple[FloatArray, list[int]]:
    """Overlap-add ``repeats`` copies of the loop; return signal and seam centers."""
    fade_in, fade_out = crossfade_curves(crossfade)
    fade_in = fade_in[:, None]
    fade_out = fade_out[:, None]
    length = loop.shape[0]

    pieces: list[FloatArray] = [loop[: length - crossfade]]
    seam_centers: list[int] = []
    position = length - crossfade
    for _ in range(repeats - 1):
        overlap = loop[length - crossfade :] * fade_out + loop[:crossfade] * fade_in
        pieces.append(overlap)
        seam_centers.append(position + crossfade // 2)
        pieces.append(loop[crossfade : length - crossfade])
        position += length - crossfade
    pieces.append(loop[length - crossfade :])
    return np.concatenate(pieces, axis=0), seam_centers


def evaluate_crossfade(
    loop: FloatArray,
    crossfade: int,
    sample_rate: int,
) -> float:
    """0..1 cost of the crossfaded seam (section 16.4)."""
    rendered, seam_centers = render_crossfaded_repeats(loop, crossfade)
    mono = rendered.mean(axis=1)
    window = max(64, round(SEAM_WINDOW_SECONDS * sample_rate))

    seam_costs: list[float] = []
    for center in seam_centers:
        # Amplitude / cancellation dip inside the fade region.
        region = mono[max(0, center - crossfade) : center + crossfade]
        outside_lo = mono[max(0, center - 4 * crossfade) : max(0, center - crossfade)]
        outside_hi = mono[center + crossfade : center + 4 * crossfade]
        outside = np.concatenate([outside_lo, outside_hi])
        if region.size and outside.size:
            hop = max(32, crossfade // 8)
            region_rms = np.sqrt(np.convolve(region**2, np.ones(hop) / hop, mode="valid"))
            outside_rms = float(np.sqrt(np.mean(outside**2))) + _EPS
            dip = float(np.min(region_rms)) / outside_rms
            rise = float(np.max(region_rms)) / outside_rms
            cancellation = max(0.0, 1.0 - dip) + max(0.0, rise - 1.2)
        else:
            cancellation = 1.0

        # Spectral discontinuity across the fade region.
        seg_lo = max(0, center - 6 * window)
        seg_hi = min(len(mono), center + 6 * window)
        distance = _segment_mel_distance(mono[seg_lo:seg_hi], center - seg_lo, sample_rate)
        interior = mono[: loop.shape[0] - crossfade]
        interior_dist = _segment_mel_distance(interior, len(interior) // 2, sample_rate)
        relative = distance / (interior_dist + 0.5)
        spectral = max(0.0, relative - 1.0) / SPECTRAL_RELATIVE_SCALE

        seam_costs.append(0.6 * min(1.0, cancellation) + 0.4 * min(1.0, spectral))

    # Periodic pumping across the repeats.
    repeat_rms = []
    step = loop.shape[0] - crossfade
    for k in range(len(seam_centers) + 1):
        chunk = mono[k * step : (k + 1) * step]
        if chunk.size:
            repeat_rms.append(20.0 * np.log10(float(np.sqrt(np.mean(chunk**2))) + _EPS))
    pumping = float(np.std(repeat_rms)) / LEVEL_DB_SCALE if len(repeat_rms) > 1 else 0.0

    seam_mean = float(np.mean(seam_costs)) if seam_costs else 1.0
    return _clip01(0.8 * seam_mean + 0.2 * min(1.0, pumping))
