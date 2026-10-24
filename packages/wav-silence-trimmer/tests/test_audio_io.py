"""Unit tests for WAV reading and writing."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from wav_silence_trimmer.audio_io import read_wav, write_wav
from wav_silence_trimmer.errors import (
    InvalidInputError,
    OutputExistsError,
    UnsupportedFormatError,
)


def _write_test_wav(path: Path, channels: int = 2, subtype: str = "PCM_16") -> None:
    audio = 0.1 * np.sin(
        2 * np.pi * 440 * np.arange(44100)[:, None] / 44100
    ) * np.ones((1, channels))
    sf.write(str(path), audio, 44100, subtype=subtype, format="WAV")


def test_read_returns_2d_and_metadata(tmp_path: Path) -> None:
    wav = tmp_path / "in.wav"
    _write_test_wav(wav, channels=2)
    audio, metadata = read_wav(wav)
    assert audio.ndim == 2
    assert audio.shape[1] == 2
    assert metadata.sample_rate == 44100
    assert metadata.channels == 2
    assert metadata.frames == 44100
    assert metadata.subtype == "PCM_16"
    assert metadata.format == "WAV"


def test_read_mono_is_2d(tmp_path: Path) -> None:
    wav = tmp_path / "mono.wav"
    _write_test_wav(wav, channels=1)
    audio, metadata = read_wav(wav)
    assert audio.shape[1] == 1


def test_read_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError):
        read_wav(tmp_path / "missing.wav")


def test_read_non_audio_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_text("not a wav file")
    with pytest.raises(UnsupportedFormatError):
        read_wav(bad)


def test_read_non_wav_format(tmp_path: Path) -> None:
    flac = tmp_path / "audio.wav"
    audio = np.zeros((1000, 1))
    sf.write(str(flac), audio, 44100, format="FLAC")
    with pytest.raises(UnsupportedFormatError):
        read_wav(flac)


def test_read_wavex(tmp_path: Path) -> None:
    wav = tmp_path / "ex.wav"
    audio = 0.1 * np.ones((1000, 2))
    sf.write(str(wav), audio, 44100, subtype="PCM_16", format="WAVEX")
    read_audio, metadata = read_wav(wav)
    assert metadata.format == "WAVEX"
    assert read_audio.shape == (1000, 2)


def test_write_preserves_wavex_format(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    write_wav(out, 0.1 * np.ones((1000, 2)), 44100, "PCM_16", format="WAVEX")
    info = sf.info(str(out))
    assert info.format == "WAVEX"
    assert info.subtype == "PCM_16"


def test_write_roundtrip_preserves_subtype(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "out.wav"
    audio = 0.25 * np.ones((1000, 2))
    write_wav(out, audio, 48000, "PCM_24")
    info = sf.info(str(out))
    assert info.samplerate == 48000
    assert info.channels == 2
    assert info.subtype == "PCM_24"
    assert info.frames == 1000


def test_write_refuses_existing_without_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    audio = np.zeros((100, 1))
    write_wav(out, audio, 44100, "PCM_16")
    with pytest.raises(OutputExistsError):
        write_wav(out, audio, 44100, "PCM_16")


def test_write_overwrite_replaces(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    write_wav(out, np.zeros((100, 1)), 44100, "PCM_16")
    write_wav(out, np.zeros((200, 1)), 44100, "PCM_16", overwrite=True)
    assert sf.info(str(out)).frames == 200


def test_write_leaves_no_temp_files(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    write_wav(out, np.zeros((100, 1)), 44100, "PCM_16")
    leftovers = [p for p in tmp_path.iterdir() if p.name != "out.wav"]
    assert leftovers == []


def test_failed_write_leaves_no_partial_file(tmp_path: Path) -> None:
    out = tmp_path / "out.wav"
    with pytest.raises(Exception):
        write_wav(out, np.zeros((100, 1)), 44100, "BOGUS_SUBTYPE")
    assert not out.exists()
    assert list(tmp_path.iterdir()) == []
