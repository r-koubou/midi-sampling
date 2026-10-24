"""RIFF ``smpl`` chunk construction (section 19)."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

from sample_loop_detector.audio.riff import RiffChunk
from sample_loop_detector.config import DEFAULT_MIDI_UNITY_NOTE

SMPL_PAYLOAD_SIZE = 36 + 24  # header + one loop structure


@dataclass(frozen=True)
class MidiUnityNote:
    note: int
    pitch_fraction: int


def estimate_midi_unity_note(f0_hz: float | None) -> MidiUnityNote:
    """Derive the smpl unity note and pitch fraction from a detected F0."""
    if f0_hz is None or f0_hz <= 0.0:
        return MidiUnityNote(note=DEFAULT_MIDI_UNITY_NOTE, pitch_fraction=0)
    midi_float = 69.0 + 12.0 * math.log2(f0_hz / 440.0)
    midi_note = math.floor(midi_float)
    fraction = midi_float - midi_note
    pitch_fraction = round(fraction * 2**32)
    if pitch_fraction >= 2**32:
        midi_note += 1
        pitch_fraction = 0
    midi_note = max(0, min(127, midi_note))
    return MidiUnityNote(note=midi_note, pitch_fraction=pitch_fraction)


def build_smpl_chunk(
    sample_rate: int,
    loop_start_frame: int,
    loop_end_frame: int,
    unity_note: MidiUnityNote,
) -> RiffChunk:
    """Build a single forward, infinite loop smpl chunk.

    ``loop_end_frame`` is inclusive, matching the smpl specification.
    """
    if loop_start_frame < 0 or loop_end_frame < loop_start_frame:
        raise ValueError("invalid loop frame range")

    sample_period = round(1_000_000_000 / sample_rate)
    payload = struct.pack(
        "<9I",
        0,  # Manufacturer
        0,  # Product
        sample_period,  # Sample Period (ns)
        unity_note.note,  # MIDI Unity Note
        unity_note.pitch_fraction,  # MIDI Pitch Fraction
        0,  # SMPTE Format
        0,  # SMPTE Offset
        1,  # Number of Sample Loops
        0,  # Sampler Data
    )
    payload += struct.pack(
        "<6I",
        0,  # Cue Point ID
        0,  # Type: forward loop
        loop_start_frame,  # Start (sample frame, inclusive)
        loop_end_frame,  # End (sample frame, inclusive)
        0,  # Fraction
        0,  # Play Count: infinite
    )
    assert len(payload) == SMPL_PAYLOAD_SIZE
    return RiffChunk(chunk_id=b"smpl", data=payload)


@dataclass(frozen=True)
class ParsedSmpl:
    """Decoded smpl values, used by tests and existing-chunk inspection."""

    sample_period: int
    midi_unity_note: int
    midi_pitch_fraction: int
    loop_count: int
    loop_type: int
    loop_start: int
    loop_end: int
    play_count: int


def parse_smpl_chunk(chunk: RiffChunk) -> ParsedSmpl:
    if chunk.chunk_id != b"smpl" or len(chunk.data) < SMPL_PAYLOAD_SIZE:
        raise ValueError("not a valid smpl chunk")
    header = struct.unpack_from("<9I", chunk.data, 0)
    loop = struct.unpack_from("<6I", chunk.data, 36)
    return ParsedSmpl(
        sample_period=header[2],
        midi_unity_note=header[3],
        midi_pitch_fraction=header[4],
        loop_count=header[7],
        loop_type=loop[1],
        loop_start=loop[2],
        loop_end=loop[3],
        play_count=loop[5],
    )
