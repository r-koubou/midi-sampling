from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import make_instrument_definition, make_processed_output
from midi_sampling import cli

runner = CliRunner()


@pytest.fixture
def instrument_file(tmp_path: Path) -> Path:
    make_processed_output(tmp_path)
    return make_instrument_definition(tmp_path)


def snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path: path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()
    }


class TestExportCli:
    def test_export_is_listed_in_help(self):
        result = runner.invoke(cli.app, ["--help"])
        assert result.exit_code == 0
        assert "export" in result.output

    def test_exports_self_contained_sfz_patch(self, tmp_path: Path, instrument_file: Path):
        result = runner.invoke(cli.app, ["export", str(instrument_file)])

        assert result.exit_code == 0, result.output
        patch_dir = tmp_path / "patches" / "sfz" / "test-instrument"
        patch_path = patch_dir / "test-instrument.sfz"
        assert patch_path.is_file()
        assert len(list((patch_dir / "Samples" / "tone-1").glob("*.wav"))) == 4

        content = patch_path.read_text(encoding="utf-8")
        assert content.count("<region>") == 4
        assert "sample=Samples/tone-1/" in content
        assert "<global>" in content
        assert "ampeg_attack=0" in content
        assert "ampeg_release=0.3" in content

    def test_sources_are_never_modified(self, tmp_path: Path, instrument_file: Path):
        before_recorded = snapshot(tmp_path / "recorded")
        before_processed = snapshot(tmp_path / "processed")

        result = runner.invoke(cli.app, ["export", str(instrument_file)])

        assert result.exit_code == 0, result.output
        assert snapshot(tmp_path / "recorded") == before_recorded
        assert snapshot(tmp_path / "processed") == before_processed

    def test_output_option_overrides_default_root(
        self, tmp_path: Path, instrument_file: Path
    ):
        output = tmp_path / "elsewhere"
        result = runner.invoke(
            cli.app, ["export", str(instrument_file), "--output", str(output)]
        )

        assert result.exit_code == 0, result.output
        # The <format>/<name> layout applies below the explicit root too.
        assert (output / "sfz" / "test-instrument" / "test-instrument.sfz").is_file()

    def test_existing_output_is_refused(self, tmp_path: Path, instrument_file: Path):
        first = runner.invoke(cli.app, ["export", str(instrument_file)])
        assert first.exit_code == 0, first.output

        second = runner.invoke(cli.app, ["export", str(instrument_file)])
        assert second.exit_code == 1
        assert "never overwritten" in second.output

    def test_unknown_format_exits_with_definition_error(
        self, tmp_path: Path, instrument_file: Path
    ):
        result = runner.invoke(
            cli.app, ["export", str(instrument_file), "--format", "nki"]
        )
        assert result.exit_code == 2
        assert "unknown patch format" in result.output

    def test_missing_definition_exits_with_definition_error(self, tmp_path: Path):
        result = runner.invoke(cli.app, ["export", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 2
        assert "Error:" in result.output
