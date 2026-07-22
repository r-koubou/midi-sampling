import pytest

from midi_sampling.sampling.exceptions import (
    DuplicateOutputFilenameError,
    InvalidFilenameTemplateError,
)

from conftest import DEFAULT_SESSION_YAML, build_plan, make_session


class TestPlanGeneration:
    def test_sample_count_is_zones_times_layers(self, plan):
        tone = plan.tones[0]
        assert len(tone.zones) == 2
        assert len(tone.velocity_layers) == 2
        assert len(tone.targets) == 4

    def test_execution_order(self, plan):
        targets = plan.tones[0].targets
        order = [(t.root_note, t.velocity_low) for t in targets]
        assert order == [(38, 1), (38, 64), (43, 1), (43, 64)]
        assert [t.sample_index for t in targets] == [0, 1, 2, 3]

    def test_standard_filenames(self, plan):
        names = [t.file_name for t in plan.tones[0].targets]
        assert names == [
            "r038__k036-040__v001-063__s048.wav",
            "r038__k036-040__v064-127__s112.wav",
            "r043__k041-045__v001-063__s048.wav",
            "r043__k041-045__v064-127__s112.wav",
        ]

    def test_output_paths_under_tone_directory(self, plan):
        tone = plan.tones[0]
        assert tone.directory == plan.output_root / "tone-1"
        assert tone.manifest_path == tone.directory / "manifest.yaml"
        for target in tone.targets:
            assert target.output_path.parent == tone.directory

    def test_total_recording_seconds(self, plan):
        target = plan.tones[0].targets[0]
        assert plan.total_recording_seconds(target) == pytest.approx(
            1.0 + 4.0 + 3.0
        )

    def test_hash_is_stored_per_tone(self, plan):
        assert len(plan.tones[0].resolved_definition_sha256) == 64


class TestNamingTemplate:
    def test_custom_template_override(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace(
            "output:\n  directory: recorded",
            "output:\n  directory: recorded\n  naming:\n"
            "    sample_filename: >-\n"
            "      {definition_id}__r{root_note:03d}__v{send_velocity:03d}",
        )
        plan = build_plan(make_session(tmp_path, session_yaml=session_yaml))
        assert plan.tones[0].targets[0].file_name == "tone-1__r038__v048.wav"

    def test_duplicate_filenames_rejected(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace(
            "output:\n  directory: recorded",
            "output:\n  directory: recorded\n  naming:\n"
            "    sample_filename: >-\n"
            "      {definition_id}",
        )
        with pytest.raises(DuplicateOutputFilenameError):
            build_plan(make_session(tmp_path, session_yaml=session_yaml))

    def test_unknown_placeholder_rejected(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace(
            "output:\n  directory: recorded",
            "output:\n  directory: recorded\n  naming:\n"
            "    sample_filename: >-\n"
            "      {no_such_placeholder}",
        )
        with pytest.raises(InvalidFilenameTemplateError):
            build_plan(make_session(tmp_path, session_yaml=session_yaml))
