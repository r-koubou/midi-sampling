"""Non-destructive write tests (sections 20, 29.3)."""

from __future__ import annotations

import numpy as np
import pytest

from sample_loop_detector.audio.riff import insert_smpl_chunk, parse_wave_bytes
from sample_loop_detector.audio.smpl import MidiUnityNote, build_smpl_chunk
from tests.conftest import build_wav_bytes, sustained_tone

SR = 22050


def _tone(stereo: bool = False) -> np.ndarray:
    return sustained_tone(sample_rate=SR, seconds=2.0, stereo=stereo)


@pytest.mark.parametrize(
    ("audio", "kwargs"),
    [
        (_tone(), {"bits_per_sample": 16}),
        (_tone(stereo=True), {"bits_per_sample": 24}),
        (_tone(), {"bits_per_sample": 32}),
        (_tone(), {"bits_per_sample": 32, "float_format": True}),
        (_tone(), {"bits_per_sample": 16, "extensible": True}),
        (
            _tone(),
            {
                "bits_per_sample": 16,
                "extra_chunks": [(b"LIST", b"INFOIART" + b"\x08\x00\x00\x00" + b"someone\x00")],
            },
        ),
        (_tone(), {"bits_per_sample": 16, "extra_chunks": [(b"JUNK", b"odd")]}),
    ],
    ids=[
        "pcm16-mono",
        "pcm24-stereo",
        "pcm32-mono",
        "float32-mono",
        "extensible-pcm16",
        "list-info",
        "odd-junk",
    ],
)
def test_data_and_chunks_preserved(audio: np.ndarray, kwargs: dict) -> None:  # type: ignore[type-arg]
    raw = build_wav_bytes(audio, SR, **kwargs)
    wave = parse_wave_bytes(raw)
    smpl = build_smpl_chunk(SR, 1000, 30000, MidiUnityNote(60, 0))
    output_bytes = insert_smpl_chunk(wave, smpl, replace_existing=False)
    output = parse_wave_bytes(output_bytes)

    # data and fmt chunks are byte-identical.
    assert output.data_chunk.data == wave.data_chunk.data
    input_fmt = next(c for c in wave.chunks if c.chunk_id == b"fmt ")
    output_fmt = next(c for c in output.chunks if c.chunk_id == b"fmt ")
    assert output_fmt.data == input_fmt.data

    # Every original chunk survives, in order, with identical content.
    original_ids = [c.chunk_id for c in wave.chunks]
    output_non_smpl = [c for c in output.chunks if c.chunk_id != b"smpl"]
    assert [c.chunk_id for c in output_non_smpl] == original_ids
    for original, copied in zip(wave.chunks, output_non_smpl, strict=True):
        assert copied.data == original.data

    # smpl sits directly before data.
    ids = [c.chunk_id for c in output.chunks]
    assert ids.index(b"smpl") == ids.index(b"data") - 1


def test_insert_is_not_a_reencode() -> None:
    """The output must contain the original data chunk bytes verbatim."""
    raw = build_wav_bytes(_tone(), SR, bits_per_sample=24)
    wave = parse_wave_bytes(raw)
    smpl = build_smpl_chunk(SR, 0, 1000, MidiUnityNote(60, 0))
    output_bytes = insert_smpl_chunk(wave, smpl, replace_existing=False)
    assert wave.data_chunk.data in output_bytes
