"""Shared fixtures: synthetic WAV builders used across the test suite."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def build_wav_bytes(
    audio: FloatArray,
    sample_rate: int,
    bits_per_sample: int = 16,
    float_format: bool = False,
    extensible: bool = False,
    extra_chunks: list[tuple[bytes, bytes]] | None = None,
    smpl_chunk: bytes | None = None,
) -> bytes:
    """Serialize a float array (frames, channels) into WAV bytes."""
    if audio.ndim == 1:
        audio = audio[:, None]
    channels = audio.shape[1]
    clipped = np.clip(audio, -1.0, 1.0)

    if float_format:
        if bits_per_sample == 32:
            payload = clipped.astype("<f4").tobytes()
        else:
            payload = clipped.astype("<f8").tobytes()
        format_tag = 0x0003
    else:
        if bits_per_sample == 8:
            payload = ((clipped * 127.0) + 128.0).astype(np.uint8).tobytes()
        elif bits_per_sample == 16:
            payload = (clipped * 32767.0).astype("<i2").tobytes()
        elif bits_per_sample == 24:
            as_int = (clipped * ((1 << 23) - 1)).astype(np.int32)
            raw = np.zeros((as_int.size, 3), dtype=np.uint8)
            flat = as_int.ravel()
            raw[:, 0] = flat & 0xFF
            raw[:, 1] = (flat >> 8) & 0xFF
            raw[:, 2] = (flat >> 16) & 0xFF
            payload = raw.tobytes()
        elif bits_per_sample == 32:
            as_int32 = (clipped * ((1 << 31) - 1)).astype("<i4")
            payload = as_int32.tobytes()
        else:
            raise ValueError(bits_per_sample)
        format_tag = 0x0001

    block_align = channels * (bits_per_sample // 8)
    byte_rate = sample_rate * block_align

    if extensible:
        guid_tag = 0x0003 if float_format else 0x0001
        sub_format = struct.pack("<H", guid_tag) + bytes.fromhex("000000001000800000aa00389b71")
        fmt = (
            struct.pack(
                "<HHIIHHHHI",
                0xFFFE,
                channels,
                sample_rate,
                byte_rate,
                block_align,
                bits_per_sample,
                22,
                bits_per_sample,
                0x3,
            )
            + sub_format
        )
    else:
        fmt = struct.pack(
            "<HHIIHH",
            format_tag,
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
        )

    def chunk(chunk_id: bytes, data: bytes) -> bytes:
        padding = b"\x00" if len(data) % 2 else b""
        return chunk_id + struct.pack("<I", len(data)) + data + padding

    body = chunk(b"fmt ", fmt)
    for chunk_id, data in extra_chunks or []:
        body += chunk(chunk_id, data)
    if smpl_chunk is not None:
        body += chunk(b"smpl", smpl_chunk)
    body += chunk(b"data", payload)

    return b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body


def sustained_tone(
    sample_rate: int = 22050,
    seconds: float = 6.0,
    f0: float = 220.0,
    attack: float = 0.15,
    release: float = 0.3,
    harmonics: tuple[tuple[float, float], ...] = ((1.0, 0.6), (2.0, 0.25), (3.0, 0.12)),
    vibrato_hz: float = 0.0,
    vibrato_cents: float = 0.0,
    tremolo_hz: float = 0.0,
    tremolo_depth: float = 0.0,
    stereo: bool = False,
) -> FloatArray:
    """Deterministic sustained tone with optional vibrato/tremolo."""
    n = int(sample_rate * seconds)
    t = np.arange(n) / sample_rate

    if vibrato_hz > 0.0:
        depth = vibrato_cents / 1200.0
        ratio = 2.0 ** (depth * np.sin(2 * np.pi * vibrato_hz * t))
        phase = 2 * np.pi * f0 * np.cumsum(ratio) / sample_rate
    else:
        phase = 2 * np.pi * f0 * t

    signal = np.zeros(n)
    for multiple, amplitude in harmonics:
        signal += amplitude * np.sin(multiple * phase + multiple)

    envelope = np.ones(n)
    attack_n = int(attack * sample_rate)
    release_n = int(release * sample_rate)
    if attack_n:
        envelope[:attack_n] = np.linspace(0.0, 1.0, attack_n)
    if release_n:
        envelope[-release_n:] = np.linspace(1.0, 0.0, release_n)
    if tremolo_hz > 0.0:
        envelope *= 1.0 + tremolo_depth * np.sin(2 * np.pi * tremolo_hz * t)

    mono = signal * envelope * 0.5
    if not stereo:
        return mono
    right = np.zeros(n)
    delay = 12
    right[delay:] = mono[: n - delay]
    return np.stack([mono, 0.95 * right], axis=1)


def noise_pad(sample_rate: int = 22050, seconds: float = 6.0) -> FloatArray:
    """Deterministic band-limited noise texture without periodic pitch."""
    rng = np.random.default_rng(1234)
    n = int(sample_rate * seconds)
    noise = rng.standard_normal(n)
    kernel = np.hanning(255)
    kernel /= kernel.sum()
    smooth = np.convolve(noise, kernel, mode="same")
    envelope = np.ones(n)
    attack = int(0.2 * sample_rate)
    envelope[:attack] = np.linspace(0.0, 1.0, attack)
    release = int(0.3 * sample_rate)
    envelope[-release:] = np.linspace(1.0, 0.0, release)
    peak = np.max(np.abs(smooth))
    return smooth / peak * 0.4 * envelope


def percussive_hit(sample_rate: int = 22050, seconds: float = 2.0) -> FloatArray:
    """Sharply decaying strike: no loopable sustain."""
    n = int(sample_rate * seconds)
    t = np.arange(n) / sample_rate
    return (
        np.sin(2 * np.pi * 180.0 * t) * np.exp(-t * 12.0)
        + 0.3 * np.sin(2 * np.pi * 900.0 * t) * np.exp(-t * 30.0)
    ) * 0.8


@pytest.fixture()
def tone_wav(tmp_path: Path) -> Path:
    path = tmp_path / "tone.wav"
    path.write_bytes(build_wav_bytes(sustained_tone(), 22050))
    return path


@pytest.fixture()
def stereo_tone_wav(tmp_path: Path) -> Path:
    path = tmp_path / "stereo_tone.wav"
    path.write_bytes(build_wav_bytes(sustained_tone(stereo=True), 22050, bits_per_sample=24))
    return path
