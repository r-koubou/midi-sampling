"""CLI integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from wav_silence_trimmer import cli

from conftest import SAMPLE_RATE, make_noise, make_standard_sample


def write_sample_wav(path: Path, subtype: str = "PCM_16") -> None:
    audio, _, _ = make_standard_sample()
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, SAMPLE_RATE, subtype=subtype, format="WAV")


def write_silence_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(
        str(path),
        np.zeros((SAMPLE_RATE * 3, 1)),
        SAMPLE_RATE,
        subtype="PCM_16",
        format="WAV",
    )


def test_single_file_success(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    write_sample_wav(src)
    assert cli.main([str(src), "--output", str(dst)]) == 0
    assert dst.exists()
    info = sf.info(str(dst))
    assert info.samplerate == SAMPLE_RATE
    assert info.subtype == "PCM_16"
    assert info.frames < SAMPLE_RATE * 4


def test_single_file_missing_output_option(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    write_sample_wav(src)
    assert cli.main([str(src)]) == 2


def test_missing_input(tmp_path: Path) -> None:
    assert cli.main([str(tmp_path / "none.wav"), "--output", str(tmp_path / "o.wav")]) == 3


def test_non_wav_input(tmp_path: Path) -> None:
    src = tmp_path / "data.txt"
    src.write_text("hello")
    assert cli.main([str(src), "--output", str(tmp_path / "o.wav")]) == 3


def test_output_exists_without_overwrite(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    write_sample_wav(src)
    dst.write_bytes(b"existing")
    assert cli.main([str(src), "--output", str(dst)]) == 5
    assert dst.read_bytes() == b"existing"


def test_output_exists_with_overwrite(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    write_sample_wav(src)
    write_sample_wav(dst)
    assert cli.main([str(src), "--output", str(dst), "--overwrite"]) == 0
    assert sf.info(str(dst)).frames < SAMPLE_RATE * 4


def test_same_input_output_requires_overwrite(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    write_sample_wav(src)
    assert cli.main([str(src), "--output", str(src)]) == 5


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    write_sample_wav(src)
    assert cli.main([str(src), "--output", str(dst), "--dry-run"]) == 0
    assert not dst.exists()


def test_report_json(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    dst = tmp_path / "out.wav"
    report = tmp_path / "report.json"
    write_sample_wav(src)
    assert cli.main(
        [str(src), "--output", str(dst), "--report-json", str(report)]
    ) == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["version"] == 1
    entry = data["files"][0]
    assert entry["status"] == "success"
    assert entry["sample_rate"] == SAMPLE_RATE
    assert entry["start_sample"] > 0
    assert entry["end_sample_exclusive"] > entry["start_sample"]


def test_silence_file_skipped_by_default(tmp_path: Path) -> None:
    src = tmp_path / "silent.wav"
    dst = tmp_path / "out.wav"
    write_silence_wav(src)
    assert cli.main([str(src), "--output", str(dst)]) == 0
    assert not dst.exists()


def test_silence_file_fails_with_flag(tmp_path: Path) -> None:
    src = tmp_path / "silent.wav"
    dst = tmp_path / "out.wav"
    write_silence_wav(src)
    assert cli.main(
        [str(src), "--output", str(dst), "--fail-on-no-signal"]
    ) == 4


def test_silence_error_in_report(tmp_path: Path) -> None:
    src = tmp_path / "silent.wav"
    report = tmp_path / "report.json"
    write_silence_wav(src)
    cli.main(
        [str(src), "--output", str(tmp_path / "o.wav"), "--report-json", str(report)]
    )
    entry = json.loads(report.read_text(encoding="utf-8"))["files"][0]
    assert entry["status"] == "error"
    assert entry["error_type"] == "NoSignalDetectedError"


def test_invalid_margins(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    write_sample_wav(src)
    code = cli.main(
        [
            str(src),
            "--output",
            str(tmp_path / "o.wav"),
            "--on-margin-db",
            "5",
            "--off-margin-db",
            "8",
        ]
    )
    assert code == 2


def test_directory_batch(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    write_sample_wav(src_dir / "a.wav")
    write_sample_wav(src_dir / "b.wav")
    assert cli.main([str(src_dir), "--output-dir", str(out_dir)]) == 0
    assert (out_dir / "a.wav").exists()
    assert (out_dir / "b.wav").exists()


def test_directory_requires_output_dir(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    write_sample_wav(src_dir / "a.wav")
    assert cli.main([str(src_dir), "--output", str(tmp_path / "o.wav")]) == 2


def test_directory_uppercase_extension(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    write_sample_wav(src_dir / "LOUD.WAV")
    assert cli.main([str(src_dir), "--output-dir", str(out_dir)]) == 0
    assert (out_dir / "LOUD.WAV").exists()


def test_directory_not_recursive_by_default(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    write_sample_wav(src_dir / "top.wav")
    write_sample_wav(src_dir / "nested" / "deep.wav")
    assert cli.main([str(src_dir), "--output-dir", str(out_dir)]) == 0
    assert (out_dir / "top.wav").exists()
    assert not (out_dir / "nested" / "deep.wav").exists()


def test_directory_recursive_preserves_structure(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    write_sample_wav(src_dir / "top.wav")
    write_sample_wav(src_dir / "nested" / "deep.wav")
    assert cli.main(
        [str(src_dir), "--output-dir", str(out_dir), "--recursive"]
    ) == 0
    assert (out_dir / "top.wav").exists()
    assert (out_dir / "nested" / "deep.wav").exists()


def test_directory_empty(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    assert cli.main([str(src_dir), "--output-dir", str(tmp_path / "out")]) == 3


def test_directory_continues_after_failure(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    bad = src_dir / "bad.wav"
    write_sample_wav(src_dir / "good.wav")
    src_dir.mkdir(exist_ok=True)
    bad.write_text("not a wav")
    assert cli.main([str(src_dir), "--output-dir", str(out_dir)]) == 1
    assert (out_dir / "good.wav").exists()


def test_no_fade_preserves_samples(tmp_path: Path) -> None:
    src = tmp_path / "in.wav"
    dst_fade = tmp_path / "fade.wav"
    dst_nofade = tmp_path / "nofade.wav"
    write_sample_wav(src, subtype="FLOAT")
    assert cli.main([str(src), "--output", str(dst_fade)]) == 0
    assert cli.main([str(src), "--output", str(dst_nofade), "--no-fade"]) == 0
    faded, _ = sf.read(str(dst_fade), always_2d=True)
    plain, _ = sf.read(str(dst_nofade), always_2d=True)
    assert faded.shape == plain.shape
    # Fade-out must attenuate the very end relative to the unfaded output.
    assert np.abs(faded[-1]).max() <= np.abs(plain[-8:]).max() + 1e-9


def test_version(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
    assert "wav-trim" in capsys.readouterr().out
