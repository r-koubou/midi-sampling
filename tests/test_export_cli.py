from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import (
    make_instrument_definition,
    make_processed_output,
    replace_with_real_wavs,
)
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

    def test_exports_sfz_patch_into_shared_format_root(
        self, tmp_path: Path, instrument_file: Path
    ):
        result = runner.invoke(cli.app, ["export", str(instrument_file)])

        assert result.exit_code == 0, result.output
        format_root = tmp_path / "patches" / "sfz"
        patch_path = format_root / "Instruments" / "test-instrument.sfz"
        assert patch_path.is_file()
        assert len(list((format_root / "Samples" / "tone-1").glob("*.wav"))) == 4

        content = patch_path.read_text(encoding="utf-8")
        assert content.count("<region>") == 4
        # The patch sits one level below the samples root.
        assert "sample=../Samples/tone-1/" in content
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
        # The <format>/{Samples,Instruments} layout applies below the
        # explicit root too.
        assert (output / "sfz" / "Instruments" / "test-instrument.sfz").is_file()
        assert (output / "sfz" / "Samples" / "tone-1").is_dir()

    def test_re_exporting_overwrites_existing_output(
        self, tmp_path: Path, instrument_file: Path
    ):
        first = runner.invoke(cli.app, ["export", str(instrument_file)])
        assert first.exit_code == 0, first.output

        second = runner.invoke(cli.app, ["export", str(instrument_file)])
        assert second.exit_code == 0, second.output
        assert (
            tmp_path / "patches" / "sfz" / "Instruments" / "test-instrument.sfz"
        ).is_file()

    def test_instruments_share_one_format_root(
        self, tmp_path: Path, instrument_file: Path
    ):
        second_file = tmp_path / "second.yaml"
        second_file.write_text(
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: second-instrument\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n",
            encoding="utf-8",
        )

        for definition in (instrument_file, second_file):
            result = runner.invoke(cli.app, ["export", str(definition)])
            assert result.exit_code == 0, result.output

        format_root = tmp_path / "patches" / "sfz"
        assert sorted(
            path.name for path in (format_root / "Instruments").iterdir()
        ) == ["second-instrument.sfz", "test-instrument.sfz"]
        # Both patches reference the same shared Samples tree.
        assert [path.name for path in (format_root / "Samples").iterdir()] == [
            "tone-1"
        ]

    def test_unknown_format_exits_with_definition_error(
        self, tmp_path: Path, instrument_file: Path
    ):
        result = runner.invoke(
            cli.app, ["export", str(instrument_file), "--format", "uvip"]
        )
        assert result.exit_code == 2
        assert "unknown patch format" in result.output

    def test_missing_definition_exits_with_definition_error(self, tmp_path: Path):
        result = runner.invoke(cli.app, ["export", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 2
        assert "Error:" in result.output


class TestNkiExportCli:
    @pytest.fixture
    def instrument_file(self, tmp_path: Path) -> Path:
        make_processed_output(tmp_path)
        # The fake devices write unparseable WAV bytes; the NKI writer
        # reads the exported samples, so they must be real files.
        replace_with_real_wavs(tmp_path / "processed")
        return make_instrument_definition(tmp_path)

    def test_exports_nki_patch_into_shared_format_root(
        self, tmp_path: Path, instrument_file: Path
    ):
        result = runner.invoke(
            cli.app, ["export", str(instrument_file), "--format", "nki"]
        )

        assert result.exit_code == 0, result.output
        format_root = tmp_path / "patches" / "nki"
        patch_path = format_root / "Instruments" / "test-instrument.nki"
        assert patch_path.is_file()
        assert len(list((format_root / "Samples" / "tone-1").glob("*.wav"))) == 4

        import zlib

        raw = patch_path.read_bytes()
        assert raw[:4] == b"\x5e\xe5\x6e\xb3"
        xml_text = zlib.decompress(raw[0x24:]).decode("utf-8")
        assert 'name="test-instrument"' in xml_text
        assert xml_text.count("<NiSS_Zone ") == 4

    def test_flac_definition_falls_back_to_wav(
        self, tmp_path: Path, instrument_file: Path
    ):
        instrument_file = make_instrument_definition(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "audio: { format: flac }\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n",
        )

        result = runner.invoke(
            cli.app, ["export", str(instrument_file), "--format", "nki"]
        )

        assert result.exit_code == 0, result.output
        samples = tmp_path / "patches" / "nki" / "Samples"
        assert len(list(samples.rglob("*.wav"))) == 4
        assert list(samples.rglob("*.flac")) == []
