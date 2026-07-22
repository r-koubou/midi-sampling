import pytest
from typer.testing import CliRunner

from conftest import FakeAudioDevice, FakeMidiDevice, build_plan, make_session
from midi_sampling.sampling import SamplingExecutor

cli = pytest.importorskip("midi_sampling.cli")

runner = CliRunner()


class TestAuditCommand:
    def test_exit_1_when_resampling_required(self, tmp_path):
        session_path = make_session(tmp_path)
        result = runner.invoke(cli.app, ["audit", str(session_path)])
        assert result.exit_code == 1
        assert "[RESAMPLE] tone-1" in result.output
        assert "reason: missing" in result.output

    def test_exit_0_when_up_to_date(self, tmp_path):
        session_path = make_session(tmp_path)
        plan = build_plan(session_path)
        executor = SamplingExecutor(
            audio_device=FakeAudioDevice(),
            midi_device=FakeMidiDevice(),
            sleep=lambda seconds: None,
        )
        executor.execute(plan)

        result = runner.invoke(cli.app, ["audit", str(session_path)])
        assert result.exit_code == 0
        assert "[UP TO DATE] tone-1" in result.output
        assert "samples: 4" in result.output
        assert "up to date: 1" in result.output

    def test_exit_2_on_definition_error(self, tmp_path):
        result = runner.invoke(
            cli.app, ["audit", str(tmp_path / "does_not_exist.yaml")]
        )
        assert result.exit_code == 2

    def test_exit_2_on_invalid_session(self, tmp_path):
        session_path = make_session(tmp_path)
        session_path.write_text("schema_version: 1\nkind: wrong\n", encoding="utf-8")
        result = runner.invoke(cli.app, ["audit", str(session_path)])
        assert result.exit_code == 2
