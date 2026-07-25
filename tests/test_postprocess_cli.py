import pytest
from typer.testing import CliRunner

from conftest import (
    DEFAULT_POSTPROCESS_SESSION_YAML,
    make_postprocess_session,
    make_recorded_output,
)

cli = pytest.importorskip("midi_sampling.cli")
pytest.importorskip("wav_silence_trimmer")

runner = CliRunner()


class TestPostprocessCommand:
    def test_exit_2_when_the_session_file_is_missing(self, tmp_path):
        result = runner.invoke(
            cli.app, ["postprocess", str(tmp_path / "does_not_exist.yaml")]
        )
        assert result.exit_code == 2

    def test_exit_2_on_invalid_session(self, tmp_path):
        make_recorded_output(tmp_path)
        session_file = make_postprocess_session(
            tmp_path, "schema_version: 1\nkind: wrong\n"
        )
        result = runner.invoke(cli.app, ["postprocess", str(session_file)])
        assert result.exit_code == 2

    def test_exit_2_when_the_source_is_missing(self, tmp_path):
        session_file = make_postprocess_session(
            tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML
        )
        result = runner.invoke(cli.app, ["postprocess", str(session_file)])
        assert result.exit_code == 2
        assert "source directory not found" in result.output

    def test_exit_1_when_the_output_already_exists(self, tmp_path):
        make_recorded_output(tmp_path)
        session_file = make_postprocess_session(
            tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML
        )
        (tmp_path / "processed" / "tone-1").mkdir(parents=True)

        result = runner.invoke(cli.app, ["postprocess", str(session_file)])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_help_lists_the_command(self):
        result = runner.invoke(cli.app, ["--help"])
        assert result.exit_code == 0
        assert "postprocess" in result.output
