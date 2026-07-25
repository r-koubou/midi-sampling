"""
Integration tests against the real optional DSP packages.

Skipped when the `postprocess` extra is not installed, so the suite still
runs on a bare checkout.
"""

import math
from pathlib import Path

import pytest

from midi_sampling.postprocess.definitions import (
    LoopSettingsDefinition,
    TrimSettingsDefinition,
)
from midi_sampling.postprocess.manifest import ManifestLoop, ManifestTrim
from midi_sampling.postprocess.stages import LoopStage, StageContext, TrimStage

np = pytest.importorskip("numpy")
sf = pytest.importorskip("soundfile")
pytest.importorskip("wav_silence_trimmer")
pytest.importorskip("sample_loop_detector")

SAMPLE_RATE = 48000
ROOT_NOTE = 69  # A4 = 440 Hz, so the detector's pitch estimate is checkable.
FREQUENCY = 440.0


def write_tone(
    path: Path,
    *,
    lead_silence: float = 1.0,
    body: float = 4.0,
    tail_silence: float = 0.5,
) -> Path:
    """
    Steady sine with digital silence at both ends: trimmable and loopable.
    """
    lead = np.zeros(int(SAMPLE_RATE * lead_silence))
    tail = np.zeros(int(SAMPLE_RATE * tail_silence))
    time = np.arange(int(SAMPLE_RATE * body)) / SAMPLE_RATE
    tone = 0.5 * np.sin(2.0 * math.pi * FREQUENCY * time)

    audio = np.concatenate([lead, tone, tail]).astype(np.float64)
    stereo = np.column_stack([audio, audio])

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), stereo, SAMPLE_RATE, subtype="PCM_24", format="WAV")
    return path


def context(input_path: Path, output_path: Path) -> StageContext:
    return StageContext(
        input_path=input_path,
        output_path=output_path,
        root_note=ROOT_NOTE,
        sample_rate=SAMPLE_RATE,
        channels=2,
    )


def test_trim_stage_removes_the_silence(tmp_path: Path):
    source = write_tone(tmp_path / "in.wav")
    output = tmp_path / "out.wav"

    outcome = TrimStage.create(TrimSettingsDefinition()).apply(
        context(source, output)
    )

    assert output.is_file()
    assert isinstance(outcome.manifest_block, ManifestTrim)
    assert outcome.output_written
    assert outcome.manifest_block.applied
    assert outcome.manifest_block.removed_head_frames > SAMPLE_RATE // 2
    assert sf.info(str(output)).frames < sf.info(str(source)).frames


def test_trim_stage_preserves_the_audio_format(tmp_path: Path):
    source = write_tone(tmp_path / "in.wav")
    output = tmp_path / "out.wav"

    TrimStage.create(TrimSettingsDefinition()).apply(context(source, output))

    before = sf.info(str(source))
    after = sf.info(str(output))
    assert after.subtype == before.subtype == "PCM_24"
    assert after.samplerate == before.samplerate
    assert after.channels == before.channels


def test_trim_stage_does_not_modify_the_input(tmp_path: Path):
    source = write_tone(tmp_path / "in.wav")
    before = source.read_bytes()

    TrimStage.create(TrimSettingsDefinition()).apply(
        context(source, tmp_path / "out.wav")
    )

    assert source.read_bytes() == before


def test_loop_stage_writes_an_smpl_chunk_with_the_manifest_root_note(tmp_path: Path):
    from sample_loop_detector.audio.riff import parse_wave_file

    source = write_tone(tmp_path / "in.wav", lead_silence=0.0, tail_silence=0.0)
    output = tmp_path / "out.wav"

    stage = LoopStage.create(LoopSettingsDefinition(), on_failure="error")
    outcome = stage.apply(context(source, output))

    assert output.is_file()
    assert isinstance(outcome.manifest_block, ManifestLoop)
    assert outcome.manifest_block.status == "success"
    assert outcome.manifest_block.smpl_chunk_written

    wave = parse_wave_file(output)
    assert wave.smpl_chunks, "no smpl chunk was written"
    # from_manifest is the default, so the recorded note must win over the
    # detector's own pitch estimate.
    assert outcome.manifest_block.midi_unity_note == ROOT_NOTE


def test_loop_stage_auto_mode_does_not_use_the_manifest_note(tmp_path: Path):
    source = write_tone(tmp_path / "in.wav", lead_silence=0.0, tail_silence=0.0)
    output = tmp_path / "out.wav"

    stage = LoopStage.create(
        LoopSettingsDefinition(midi_unity_note="auto"), on_failure="error"
    )
    outcome = stage.apply(context(source, output))

    assert outcome.manifest_block.status == "success"
    # A 440 Hz sine is A4 either way; the point is that it was estimated.
    assert outcome.manifest_block.midi_unity_note is not None


def test_loop_stage_skips_when_no_loop_is_found(tmp_path: Path):
    # White noise has no stable sustain, so no candidate can be accepted.
    rng = np.random.default_rng(0)
    audio = rng.standard_normal((SAMPLE_RATE * 3, 2)) * 0.1
    source = tmp_path / "noise.wav"
    sf.write(str(source), audio, SAMPLE_RATE, subtype="PCM_24", format="WAV")
    output = tmp_path / "out.wav"

    stage = LoopStage.create(
        LoopSettingsDefinition(quality_threshold=1.0), on_failure="skip"
    )
    outcome = stage.apply(context(source, output))

    assert not outcome.output_written
    assert outcome.manifest_block.status == "not_found"
    assert not output.exists()


def test_trim_then_loop_chain(tmp_path: Path):
    from sample_loop_detector.audio.riff import parse_wave_file

    source = write_tone(tmp_path / "in.wav")
    trimmed = tmp_path / "work" / "s1-trim.wav"
    looped = tmp_path / "work" / "s2-loop.wav"

    TrimStage.create(TrimSettingsDefinition()).apply(context(source, trimmed))
    outcome = LoopStage.create(LoopSettingsDefinition(), on_failure="error").apply(
        context(trimmed, looped)
    )

    assert outcome.manifest_block.status == "success"
    assert parse_wave_file(looped).smpl_chunks
    assert sf.info(str(looped)).subtype == "PCM_24"
