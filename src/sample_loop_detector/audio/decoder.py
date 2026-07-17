"""Decode WAV ``data`` chunk bytes into float64 analysis arrays.

Decoding operates on the already-parsed data chunk so the analysis signal
is guaranteed to correspond exactly to the bytes preserved in the output.
The decoded array is used for analysis only and is never written back.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.audio.riff import WaveFile
from sample_loop_detector.config import MAX_INVALID_SAMPLE_RATIO, MIN_DURATION_SECONDS
from sample_loop_detector.exceptions import InvalidWaveError, UnsupportedWaveFormatError
from sample_loop_detector.models import AudioMetadata

FloatArray = NDArray[np.float64]


def decode_wave(wave: WaveFile) -> tuple[FloatArray, AudioMetadata]:
    """Return ``(audio, metadata)`` with audio shaped ``(frames, channels)``."""
    fmt = wave.fmt
    raw = wave.data_chunk.data
    channels = fmt.channels

    if fmt.is_float:
        if fmt.bits_per_sample == 32:
            flat = np.frombuffer(raw, dtype="<f4").astype(np.float64)
        else:
            flat = np.frombuffer(raw, dtype="<f8").astype(np.float64)
    elif fmt.bits_per_sample == 8:
        flat = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif fmt.bits_per_sample == 16:
        flat = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif fmt.bits_per_sample == 24:
        as_bytes = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        as_int = (
            as_bytes[:, 0].astype(np.int32)
            | (as_bytes[:, 1].astype(np.int32) << 8)
            | (as_bytes[:, 2].astype(np.int32) << 16)
        )
        as_int = np.where(as_int >= 1 << 23, as_int - (1 << 24), as_int)
        flat = as_int.astype(np.float64) / float(1 << 23)
    elif fmt.bits_per_sample == 32:
        flat = np.frombuffer(raw, dtype="<i4").astype(np.float64) / float(1 << 31)
    else:  # pragma: no cover - already rejected by the fmt parser
        raise UnsupportedWaveFormatError(f"unsupported bit depth: {fmt.bits_per_sample}")

    audio = flat.reshape(-1, channels)
    frame_count = audio.shape[0]
    duration = frame_count / fmt.sample_rate

    invalid = ~np.isfinite(audio)
    if invalid.any():
        if invalid.mean() > MAX_INVALID_SAMPLE_RATIO:
            raise InvalidWaveError("audio contains too many NaN or Infinity samples")
        audio = np.where(invalid, 0.0, audio)

    if duration < MIN_DURATION_SECONDS:
        raise InvalidWaveError(f"file is too short: {duration:.3f} s < {MIN_DURATION_SECONDS} s")

    metadata = AudioMetadata(
        sample_rate=fmt.sample_rate,
        channels=channels,
        frame_count=frame_count,
        duration_seconds=duration,
        format_tag=fmt.format_tag,
        bits_per_sample=fmt.bits_per_sample,
        subtype=fmt.subtype_name,
    )
    return np.ascontiguousarray(audio), metadata
