"""CLI integration tests: failure paths and exit codes (sections 6, 29.5)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from sample_loop_detector.cli import app
from tests.conftest import build_wav_bytes, percussive_hit, sustained_tone

runner = CliRunner()
SR = 22050


def _write_tone(tmp_path: Path) -> Path:
    path = tmp_path / "tone.wav"
    path.write_bytes(build_wav_bytes(sustained_tone(sample_rate=SR), SR))
    return path


def test_percussive_input_returns_exit_2(tmp_path: Path) -> None:
    input_path = tmp_path / "hit.wav"
    input_path.write_bytes(build_wav_bytes(percussive_hit(sample_rate=SR), SR))
    output_path = tmp_path / "out.wav"
    report_path = tmp_path / "report.json"

    result = runner.invoke(
        app,
        [
            "detect",
            str(input_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ],
    )
    assert result.exit_code == 2
    assert not output_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "no_acceptable_loop"
    assert report["failure"]["reason"] in (
        "no_stable_sustain_region",
        "sustain_region_too_short",
        "no_loop_candidates",
        "all_candidates_above_threshold",
        "hard_seam_above_threshold",
        "no_active_signal",
    )


def test_invalid_search_range_returns_exit_3(tmp_path: Path) -> None:
    input_path = _write_tone(tmp_path)
    result = runner.invoke(
        app,
        ["detect", str(input_path), "--search-start", "5.0", "--search-end", "2.0"],
    )
    assert result.exit_code == 3


def test_search_range_beyond_duration_returns_exit_3(tmp_path: Path) -> None:
    input_path = _write_tone(tmp_path)
    result = runner.invoke(
        app,
        ["detect", str(input_path), "--search-start", "1.0", "--search-end", "100.0"],
    )
    assert result.exit_code == 3


def test_invalid_loop_bounds_returns_exit_3(tmp_path: Path) -> None:
    input_path = _write_tone(tmp_path)
    result = runner.invoke(
        app, ["detect", str(input_path), "--min-loop", "5.0", "--max-loop", "2.0"]
    )
    assert result.exit_code == 3


def test_invalid_quality_threshold_returns_exit_3(tmp_path: Path) -> None:
    input_path = _write_tone(tmp_path)
    result = runner.invoke(app, ["detect", str(input_path), "--quality-threshold", "1.5"])
    assert result.exit_code == 3


def test_non_wave_input_returns_exit_3(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.wav"
    bogus.write_bytes(b"this is not a wave file at all" * 10)
    result = runner.invoke(app, ["detect", str(bogus)])
    assert result.exit_code == 3


def test_too_short_input_returns_exit_3(tmp_path: Path) -> None:
    short = tmp_path / "short.wav"
    short.write_bytes(build_wav_bytes(sustained_tone(sample_rate=SR, seconds=1.0), SR))
    result = runner.invoke(app, ["detect", str(short)])
    assert result.exit_code == 3


def test_missing_input_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["detect", str(tmp_path / "missing.wav")])
    assert result.exit_code != 0
