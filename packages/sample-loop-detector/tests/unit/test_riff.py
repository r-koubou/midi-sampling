"""RIFF parser tests (section 29.1)."""

from __future__ import annotations

import struct

import numpy as np
import pytest

from sample_loop_detector.audio.riff import (
    WAVE_FORMAT_EXTENSIBLE,
    WAVE_FORMAT_IEEE_FLOAT,
    WAVE_FORMAT_PCM,
    RiffChunk,
    build_wave_bytes,
    insert_smpl_chunk,
    parse_wave_bytes,
)
from sample_loop_detector.exceptions import (
    InvalidWaveError,
    UnsupportedWaveFormatError,
    WaveWriteError,
)
from tests.conftest import build_wav_bytes, sustained_tone


def _short_tone() -> np.ndarray:
    return sustained_tone(seconds=2.0)


def test_parse_riff_header_and_fmt() -> None:
    wave = parse_wave_bytes(build_wav_bytes(_short_tone(), 22050))
    assert wave.fmt.format_tag == WAVE_FORMAT_PCM
    assert wave.fmt.channels == 1
    assert wave.fmt.sample_rate == 22050
    assert wave.fmt.bits_per_sample == 16
    assert wave.frame_count == 44100


def test_data_chunk_detection() -> None:
    wave = parse_wave_bytes(build_wav_bytes(_short_tone(), 22050))
    assert wave.data_chunk.chunk_id == b"data"
    assert len(wave.data_chunk.data) == 44100 * 2


def test_unknown_chunks_preserved() -> None:
    raw = build_wav_bytes(
        _short_tone(), 22050, extra_chunks=[(b"JUNK", b"hello world"), (b"iXML", b"<x/>")]
    )
    wave = parse_wave_bytes(raw)
    ids = [chunk.chunk_id for chunk in wave.chunks]
    assert b"JUNK" in ids and b"iXML" in ids
    junk = next(c for c in wave.chunks if c.chunk_id == b"JUNK")
    assert junk.data == b"hello world"


def test_odd_sized_chunk_padding_roundtrip() -> None:
    raw = build_wav_bytes(_short_tone(), 22050, extra_chunks=[(b"JUNK", b"odd")])
    wave = parse_wave_bytes(raw)
    rebuilt = build_wave_bytes(list(wave.chunks))
    assert rebuilt == raw
    # Odd payloads are padded in the byte stream.
    junk_offset = rebuilt.find(b"JUNK")
    (size,) = struct.unpack_from("<I", rebuilt, junk_offset + 4)
    assert size == 3
    assert rebuilt[junk_offset + 8 + 3] == 0


def test_riff_size_updated_after_insert() -> None:
    raw = build_wav_bytes(_short_tone(), 22050)
    wave = parse_wave_bytes(raw)
    smpl = RiffChunk(chunk_id=b"smpl", data=b"\x00" * 60)
    output = insert_smpl_chunk(wave, smpl, replace_existing=False)
    (riff_size,) = struct.unpack_from("<I", output, 4)
    assert riff_size == len(output) - 8


def test_corrupt_chunk_size_rejected() -> None:
    raw = bytearray(build_wav_bytes(_short_tone(), 22050))
    data_offset = raw.find(b"data")
    struct.pack_into("<I", raw, data_offset + 4, 0xFFFFFFF0)
    with pytest.raises(InvalidWaveError):
        parse_wave_bytes(bytes(raw))


def test_rf64_rejected() -> None:
    raw = bytearray(build_wav_bytes(_short_tone(), 22050))
    raw[0:4] = b"RF64"
    with pytest.raises(UnsupportedWaveFormatError):
        parse_wave_bytes(bytes(raw))


def test_not_riff_rejected() -> None:
    with pytest.raises(InvalidWaveError):
        parse_wave_bytes(b"OggS" + b"\x00" * 100)


def test_missing_fmt_rejected() -> None:
    body = b"data" + struct.pack("<I", 4) + b"\x00" * 4
    raw = b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body
    with pytest.raises(InvalidWaveError):
        parse_wave_bytes(raw)


def test_missing_data_rejected() -> None:
    fmt = struct.pack("<HHIIHH", 1, 1, 22050, 44100, 2, 16)
    body = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    raw = b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body
    wave_error = InvalidWaveError
    with pytest.raises(wave_error):
        parse_wave_bytes(raw)


def test_extensible_pcm_identified() -> None:
    raw = build_wav_bytes(_short_tone(), 22050, bits_per_sample=16, extensible=True)
    wave = parse_wave_bytes(raw)
    assert wave.fmt.format_tag == WAVE_FORMAT_EXTENSIBLE
    assert wave.fmt.resolved_format_tag == WAVE_FORMAT_PCM


def test_extensible_float_identified() -> None:
    raw = build_wav_bytes(
        _short_tone(), 22050, bits_per_sample=32, float_format=True, extensible=True
    )
    wave = parse_wave_bytes(raw)
    assert wave.fmt.resolved_format_tag == WAVE_FORMAT_IEEE_FLOAT
    assert wave.fmt.is_float


def test_compressed_format_rejected() -> None:
    raw = bytearray(build_wav_bytes(_short_tone(), 22050))
    fmt_offset = raw.find(b"fmt ")
    struct.pack_into("<H", raw, fmt_offset + 8, 0x0055)  # MP3
    with pytest.raises(UnsupportedWaveFormatError):
        parse_wave_bytes(bytes(raw))


def test_unsupported_channel_count_rejected() -> None:
    audio = np.zeros((1000, 3))
    audio[:, :] = 0.1
    raw = build_wav_bytes(audio, 22050)
    with pytest.raises(UnsupportedWaveFormatError):
        parse_wave_bytes(raw)


def test_existing_smpl_blocks_insert() -> None:
    raw = build_wav_bytes(_short_tone(), 22050, smpl_chunk=b"\x00" * 60)
    wave = parse_wave_bytes(raw)
    replacement = RiffChunk(chunk_id=b"smpl", data=b"\x01" * 60)
    with pytest.raises(WaveWriteError):
        insert_smpl_chunk(wave, replacement, replace_existing=False)


def test_replace_existing_smpl_keeps_single_chunk() -> None:
    raw = build_wav_bytes(_short_tone(), 22050, smpl_chunk=b"\x00" * 60)
    wave = parse_wave_bytes(raw)
    replacement = RiffChunk(chunk_id=b"smpl", data=b"\x01" * 60)
    output = insert_smpl_chunk(wave, replacement, replace_existing=True)
    reparsed = parse_wave_bytes(output)
    assert len(reparsed.smpl_chunks) == 1
    assert reparsed.smpl_chunks[0].data == b"\x01" * 60
