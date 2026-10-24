"""CLI integration tests: successful detection paths (section 29.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sample_loop_detector.audio.riff import parse_wave_bytes
from sample_loop_detector.audio.smpl import parse_smpl_chunk
from sample_loop_detector.cli import app
from tests.conftest import build_wav_bytes, sustained_tone

runner = CliRunner()
SR = 22050


@pytest.fixture(scope="module")
def detected(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Run one full detection shared by the assertions in this module."""
    tmp_path = tmp_path_factory.mktemp("cli")
    input_path = tmp_path / "tone.wav"
    input_path.write_bytes(build_wav_bytes(sustained_tone(sample_rate=SR), SR))
    output_path = tmp_path / "out.wav"
    report_path = tmp_path / "report.json"
    preview_path = tmp_path / "preview.wav"

    result = runner.invoke(
        app,
        [
            "detect",
            str(input_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
            "--preview-output",
            str(preview_path),
        ],
    )
    assert result.exit_code == 0, result.output
    return {
        "input": input_path,
        "output": output_path,
        "report": report_path,
        "preview": preview_path,
    }


def test_detect_writes_output(detected: dict[str, Path]) -> None:
    assert detected["output"].exists()


def test_smpl_chunk_matches_report(detected: dict[str, Path]) -> None:
    report = json.loads(detected["report"].read_text(encoding="utf-8"))
    assert report["status"] == "success"
    wave = parse_wave_bytes(detected["output"].read_bytes())
    assert len(wave.smpl_chunks) == 1
    smpl = parse_smpl_chunk(wave.smpl_chunks[0])
    assert smpl.loop_start == report["selected_loop"]["start_frame"]
    assert smpl.loop_end == report["selected_loop"]["end_frame"]
    assert smpl.loop_count == 1


def test_output_data_chunk_preserved(detected: dict[str, Path]) -> None:
    original = parse_wave_bytes(detected["input"].read_bytes())
    written = parse_wave_bytes(detected["output"].read_bytes())
    assert written.data_chunk.data == original.data_chunk.data


def test_loop_is_inside_sustain(detected: dict[str, Path]) -> None:
    report = json.loads(detected["report"].read_text(encoding="utf-8"))
    loop = report["selected_loop"]
    analysis = report["analysis"]
    assert analysis["sustain_start_seconds"] <= loop["start_seconds"]
    assert loop["end_seconds"] <= analysis["sustain_end_seconds"] + 0.1
    assert loop["length_seconds"] >= 0.5
    assert loop["score"]["total"] <= 0.35


def test_preview_written(detected: dict[str, Path]) -> None:
    assert detected["preview"].exists()
    preview = detected["preview"].read_bytes()
    assert preview[:4] == b"RIFF"


def test_output_conflict_without_force(detected: dict[str, Path]) -> None:
    result = runner.invoke(
        app,
        ["detect", str(detected["input"]), "--output", str(detected["output"])],
    )
    assert result.exit_code == 4


def test_force_overwrites(detected: dict[str, Path]) -> None:
    result = runner.invoke(
        app,
        ["detect", str(detected["input"]), "--output", str(detected["output"]), "--force"],
    )
    assert result.exit_code == 0


def test_dry_run_writes_nothing(tmp_path: Path, detected: dict[str, Path]) -> None:
    output_path = tmp_path / "never.wav"
    result = runner.invoke(
        app,
        ["detect", str(detected["input"]), "--output", str(output_path), "--dry-run"],
    )
    assert result.exit_code == 0
    assert not output_path.exists()


def test_detection_is_deterministic(tmp_path: Path, detected: dict[str, Path]) -> None:
    reports = []
    for name in ("a.json", "b.json"):
        report_path = tmp_path / name
        result = runner.invoke(
            app,
            [
                "detect",
                str(detected["input"]),
                "--dry-run",
                "--report",
                str(report_path),
            ],
        )
        assert result.exit_code == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["input"]["path"] = "normalized"
        reports.append(report)
    assert reports[0] == reports[1]


def test_replace_existing_smpl(tmp_path: Path, detected: dict[str, Path]) -> None:
    looped = detected["output"].read_bytes()
    source = tmp_path / "already_looped.wav"
    source.write_bytes(looped)

    denied = runner.invoke(app, ["detect", str(source), "--dry-run"])
    assert denied.exit_code == 4

    replaced_path = tmp_path / "replaced.wav"
    replaced = runner.invoke(
        app,
        [
            "detect",
            str(source),
            "--output",
            str(replaced_path),
            "--replace-existing-loop",
        ],
    )
    assert replaced.exit_code == 0
    wave = parse_wave_bytes(replaced_path.read_bytes())
    assert len(wave.smpl_chunks) == 1


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "sample-loop-detector" in result.output
