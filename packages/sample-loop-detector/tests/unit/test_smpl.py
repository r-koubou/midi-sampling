"""smpl chunk tests (section 29.2)."""

from __future__ import annotations

import struct

import pytest

from sample_loop_detector.audio.riff import parse_wave_bytes
from sample_loop_detector.audio.smpl import (
    SMPL_PAYLOAD_SIZE,
    MidiUnityNote,
    build_smpl_chunk,
    estimate_midi_unity_note,
    parse_smpl_chunk,
)
from tests.conftest import build_wav_bytes, sustained_tone


def test_payload_size_is_60_bytes() -> None:
    chunk = build_smpl_chunk(44100, 1000, 2000, MidiUnityNote(60, 0))
    assert len(chunk.data) == SMPL_PAYLOAD_SIZE == 60


def test_little_endian_layout() -> None:
    chunk = build_smpl_chunk(44100, 0x01020304, 0x0A0B0C0D, MidiUnityNote(60, 0))
    # Start field is at offset 36 + 8 within the payload.
    assert chunk.data[44:48] == struct.pack("<I", 0x01020304)
    assert chunk.data[48:52] == struct.pack("<I", 0x0A0B0C0D)


def test_header_fields() -> None:
    chunk = build_smpl_chunk(48000, 100, 200, MidiUnityNote(69, 12345))
    parsed = parse_smpl_chunk(chunk)
    assert parsed.sample_period == round(1_000_000_000 / 48000)
    assert parsed.midi_unity_note == 69
    assert parsed.midi_pitch_fraction == 12345
    assert parsed.loop_count == 1
    assert parsed.loop_type == 0
    assert parsed.play_count == 0


def test_start_end_inclusive() -> None:
    chunk = build_smpl_chunk(44100, 1000, 2000, MidiUnityNote(60, 0))
    parsed = parse_smpl_chunk(chunk)
    assert parsed.loop_start == 1000
    assert parsed.loop_end == 2000
    # Inclusive end: loop length is end - start + 1.
    assert parsed.loop_end - parsed.loop_start + 1 == 1001


def test_invalid_range_rejected() -> None:
    with pytest.raises(ValueError):
        build_smpl_chunk(44100, 2000, 1000, MidiUnityNote(60, 0))


def test_stereo_positions_are_sample_frames() -> None:
    audio = sustained_tone(seconds=2.0, stereo=True)
    raw = build_wav_bytes(audio, 22050)
    wave = parse_wave_bytes(raw)
    # 2 seconds at 22050 Hz: frame count is time-based, not interleaved count.
    assert wave.frame_count == 44100
    chunk = build_smpl_chunk(22050, 0, wave.frame_count - 1, MidiUnityNote(60, 0))
    parsed = parse_smpl_chunk(chunk)
    assert parsed.loop_end == 44099


def test_midi_unity_note_from_a440() -> None:
    unity = estimate_midi_unity_note(440.0)
    assert unity.note == 69
    assert unity.pitch_fraction == 0


def test_midi_unity_note_fraction() -> None:
    # A quarter tone above A4: 50 cents -> fraction ~0.5.
    f0 = 440.0 * 2 ** (50 / 1200)
    unity = estimate_midi_unity_note(f0)
    assert unity.note == 69
    assert abs(unity.pitch_fraction / 2**32 - 0.5) < 0.01


def test_midi_unity_note_fraction_rounding_overflow() -> None:
    # Just below the next semitone: fraction rounds up to 2**32 and carries.
    f0 = 440.0 * 2 ** ((1 - 2**-34) / 12)
    unity = estimate_midi_unity_note(f0)
    assert unity.note == 70
    assert unity.pitch_fraction == 0


def test_midi_unity_note_default_when_no_pitch() -> None:
    unity = estimate_midi_unity_note(None)
    assert unity.note == 60
    assert unity.pitch_fraction == 0
