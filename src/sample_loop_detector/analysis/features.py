"""Frame-level feature extraction (section 10).

All frame-based features use center=False so that frame ``i`` covers
samples ``[i * hop, i * hop + frame_length)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.analysis.framing import frame_count, rolling_regression
from sample_loop_detector.config import (
    STABILITY_WINDOW_SECONDS,
    FrameConfig,
)

FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

_EPS = 1e-12


@dataclass(frozen=True)
class FrameFeatures:
    """Per-frame features, channel-averaged unless noted otherwise."""

    config: FrameConfig
    n_frames: int
    # Level
    rms: FloatArray
    rms_db: FloatArray
    rms_db_diff: FloatArray
    rms_slope: FloatArray  # dB per frame, local regression
    rms_residual: FloatArray  # dB, residual RMS from local regression
    # Spectral
    log_mel: FloatArray  # (n_frames, n_mels)
    mel_flux: FloatArray  # positive log-mel difference
    mel_frame_dist: FloatArray  # adjacent-frame log-mel distance
    centroid: FloatArray  # Hz
    centroid_slope: FloatArray
    flatness: FloatArray
    onset_strength: FloatArray
    # Pitch
    f0: FloatArray  # Hz, NaN when unvoiced
    voiced_flag: BoolArray
    voiced_prob: FloatArray
    cents: FloatArray  # relative to the voiced median F0, NaN when unvoiced
    pitch_channel: int
    # Stereo (empty arrays for mono input)
    channel_rms_db: FloatArray  # (n_frames, channels)
    side_rms_db: FloatArray
    lr_corr: FloatArray

    @property
    def stability_window_frames(self) -> int:
        return max(3, self.config.seconds_to_frames(STABILITY_WINDOW_SECONDS))


def extract_features(
    audio: FloatArray,
    config: FrameConfig,
    fmin: float,
    fmax: float,
) -> FrameFeatures:
    """Extract all frame features from a DC-free ``(frames, channels)`` signal."""
    sr = config.sample_rate
    n_fft = config.frame_length
    hop = config.hop_length
    channels = audio.shape[1]
    n_frames = frame_count(config, audio.shape[0])
    if n_frames < 4:
        raise ValueError("audio is too short for frame analysis")

    mel_sum: FloatArray | None = None
    mag_sum: FloatArray | None = None
    rms_channels: list[FloatArray] = []
    for ch in range(channels):
        y = np.ascontiguousarray(audio[:, ch])
        power = librosa.feature.melspectrogram(
            y=y,
            sr=sr,
            n_fft=n_fft,
            hop_length=hop,
            center=False,
            power=2.0,
            n_mels=config.mel_bands,
        ).astype(np.float64)[:, :n_frames]
        mag = np.abs(
            librosa.stft(y=y, n_fft=n_fft, hop_length=hop, center=False, window="hann")
        ).astype(np.float64)[:, :n_frames]
        rms = (
            librosa.feature.rms(y=y, frame_length=n_fft, hop_length=hop, center=False)
            .astype(np.float64)
            .ravel()[:n_frames]
        )
        rms_channels.append(rms)
        mel_sum = power if mel_sum is None else mel_sum + power
        mag_sum = mag if mag_sum is None else mag_sum + mag

    assert mel_sum is not None and mag_sum is not None
    mel_power = mel_sum / channels
    mag = mag_sum / channels

    log_mel = librosa.power_to_db(mel_power, ref=1.0, top_db=None).astype(np.float64).T
    rms_matrix = np.stack(rms_channels, axis=1)
    rms = np.sqrt(np.mean(rms_matrix**2, axis=1))
    rms_db = 20.0 * np.log10(np.maximum(rms, _EPS))
    channel_rms_db = 20.0 * np.log10(np.maximum(rms_matrix, _EPS))
    rms_db_diff = np.diff(rms_db, prepend=rms_db[0])

    window_frames = max(3, config.seconds_to_frames(STABILITY_WINDOW_SECONDS))
    rms_slope, rms_residual = rolling_regression(rms_db, window_frames)

    mel_diff = np.diff(log_mel, axis=0)
    mel_flux = np.concatenate(([0.0], np.mean(np.maximum(mel_diff, 0.0), axis=1)))
    mel_frame_dist = np.concatenate(
        ([0.0], np.linalg.norm(mel_diff, axis=1) / np.sqrt(log_mel.shape[1]))
    )

    centroid = (
        librosa.feature.spectral_centroid(S=mag, sr=sr, n_fft=n_fft)
        .astype(np.float64)
        .ravel()[:n_frames]
    )
    centroid_slope, _ = rolling_regression(centroid, window_frames)
    flatness = librosa.feature.spectral_flatness(S=mag).astype(np.float64).ravel()[:n_frames]
    onset = librosa.onset.onset_strength(
        S=librosa.power_to_db(mel_power, ref=np.max), sr=sr, hop_length=hop
    ).astype(np.float64)[:n_frames]
    if len(onset) < n_frames:
        onset = np.pad(onset, (0, n_frames - len(onset)))

    # Pitch: analyze the louder channel (section 8.3).
    pitch_channel = int(np.argmax([float(np.mean(r**2)) for r in rms_channels]))
    fmax_effective = min(fmax, sr / 4)
    # pyin needs at least two fmin periods per frame.
    fmin_effective = max(fmin, 2.0 * sr / n_fft * 1.01)
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y=np.ascontiguousarray(audio[:, pitch_channel]),
        fmin=fmin_effective,
        fmax=max(fmax_effective, fmin_effective * 1.1),
        sr=sr,
        frame_length=n_fft,
        hop_length=hop,
        center=False,
        fill_na=np.nan,
    )
    f0 = np.asarray(f0, dtype=np.float64)[:n_frames]
    voiced_flag = np.asarray(voiced_flag, dtype=np.bool_)[:n_frames]
    voiced_prob = np.asarray(voiced_prob, dtype=np.float64)[:n_frames]
    if len(f0) < n_frames:
        pad = n_frames - len(f0)
        f0 = np.pad(f0, (0, pad), constant_values=np.nan)
        voiced_flag = np.pad(voiced_flag, (0, pad), constant_values=False)
        voiced_prob = np.pad(voiced_prob, (0, pad))

    voiced_f0 = f0[np.isfinite(f0)]
    reference_f0 = float(np.median(voiced_f0)) if voiced_f0.size else 440.0
    with np.errstate(invalid="ignore", divide="ignore"):
        cents = 1200.0 * np.log2(f0 / reference_f0)

    # Stereo descriptors.
    if channels == 2:
        side = (audio[:, 0] - audio[:, 1]) / 2.0
        side_rms = (
            librosa.feature.rms(
                y=np.ascontiguousarray(side),
                frame_length=n_fft,
                hop_length=hop,
                center=False,
            )
            .astype(np.float64)
            .ravel()[:n_frames]
        )
        side_rms_db = 20.0 * np.log10(np.maximum(side_rms, _EPS))
        lr_corr = _framewise_correlation(audio[:, 0], audio[:, 1], n_fft, hop, n_frames)
    else:
        side_rms_db = np.zeros(0)
        lr_corr = np.zeros(0)

    return FrameFeatures(
        config=config,
        n_frames=n_frames,
        rms=rms,
        rms_db=rms_db,
        rms_db_diff=rms_db_diff,
        rms_slope=rms_slope,
        rms_residual=rms_residual,
        log_mel=np.ascontiguousarray(log_mel),
        mel_flux=mel_flux,
        mel_frame_dist=mel_frame_dist,
        centroid=centroid,
        centroid_slope=centroid_slope,
        flatness=flatness,
        onset_strength=onset,
        f0=f0,
        voiced_flag=voiced_flag,
        voiced_prob=voiced_prob,
        cents=np.asarray(cents, dtype=np.float64),
        pitch_channel=pitch_channel,
        channel_rms_db=channel_rms_db,
        side_rms_db=side_rms_db,
        lr_corr=lr_corr,
    )


def _framewise_correlation(
    left: FloatArray, right: FloatArray, frame_length: int, hop: int, n_frames: int
) -> FloatArray:
    """Per-frame Pearson correlation between the two channels."""
    frames_l = librosa.util.frame(left, frame_length=frame_length, hop_length=hop)
    frames_r = librosa.util.frame(right, frame_length=frame_length, hop_length=hop)
    frames_l = frames_l[:, :n_frames]
    frames_r = frames_r[:, :n_frames]
    ml = frames_l - frames_l.mean(axis=0, keepdims=True)
    mr = frames_r - frames_r.mean(axis=0, keepdims=True)
    denom = np.sqrt(np.sum(ml**2, axis=0) * np.sum(mr**2, axis=0))
    corr = np.sum(ml * mr, axis=0) / np.maximum(denom, _EPS)
    return np.asarray(np.clip(corr, -1.0, 1.0), dtype=np.float64)
