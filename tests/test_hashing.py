from pathlib import Path

from midi_sampling.sampling.planning import SamplingPlanBuilder
from midi_sampling.sampling.resolving import DefinitionResolver

from conftest import (
    DEFAULT_SESSION_YAML,
    DEFAULT_TONE_YAML,
    DEFAULT_ZONES_YAML,
    FakeAudioInformationLoader,
    build_plan,
    make_session,
)


def hash_of(session_path: Path) -> str:
    return build_plan(session_path).tones[0].resolved_definition_sha256


def default_hash(tmp_path: Path) -> str:
    return hash_of(make_session(tmp_path / "base"))


class TestHashStability:
    def test_comment_changes_do_not_change_hash(self, tmp_path):
        commented = "# a comment\n" + DEFAULT_ZONES_YAML.replace(
            "zones:", "zones:  # key zones"
        )
        changed = hash_of(make_session(tmp_path / "changed", zones_yaml=commented))
        assert changed == default_hash(tmp_path)

    def test_key_order_does_not_change_hash(self, tmp_path):
        reordered = DEFAULT_ZONES_YAML.replace(
            "  - low: 36\n    root: 38\n    high: 40",
            "  - high: 40\n    low: 36\n    root: 38",
        )
        changed = hash_of(make_session(tmp_path / "changed", zones_yaml=reordered))
        assert changed == default_hash(tmp_path)

    def test_zone_order_does_not_change_hash(self, tmp_path):
        reordered = """\
schema_version: 1
kind: zone_layout

zones:
  - low: 41
    root: 43
    high: 45

  - low: 36
    root: 38
    high: 40
"""
        changed = hash_of(make_session(tmp_path / "changed", zones_yaml=reordered))
        assert changed == default_hash(tmp_path)

    def test_preset_location_does_not_change_hash(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace(
            "../presets/zones.yaml", "../elsewhere/keyzones.yaml"
        )
        changed = hash_of(
            make_session(
                tmp_path / "changed",
                tone_yaml=tone_yaml,
                extra_files={"elsewhere/keyzones.yaml": DEFAULT_ZONES_YAML},
            )
        )
        assert changed == default_hash(tmp_path)

    def test_display_name_does_not_change_hash(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace("name: Tone 1", "name: Renamed")
        changed = hash_of(make_session(tmp_path / "changed", tone_yaml=tone_yaml))
        assert changed == default_hash(tmp_path)


class TestHashSensitivity:
    def test_zone_value_changes_hash(self, tmp_path):
        changed_yaml = DEFAULT_ZONES_YAML.replace("high: 40", "high: 39")
        changed = hash_of(make_session(tmp_path / "changed", zones_yaml=changed_yaml))
        assert changed != default_hash(tmp_path)

    def test_velocity_value_changes_hash(self, tmp_path):
        changed_yaml = make_session(
            tmp_path / "changed",
            velocities_yaml="""\
schema_version: 1
kind: velocity_profile

layers:
  - low: 1
    high: 63
    send: 40

  - low: 64
    high: 127
    send: 112
""",
        )
        assert hash_of(changed_yaml) != default_hash(tmp_path)

    def test_midi_program_changes_hash(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace("program: 41", "program: 42")
        changed = hash_of(make_session(tmp_path / "changed", tone_yaml=tone_yaml))
        assert changed != default_hash(tmp_path)

    def test_timing_changes_hash(self, tmp_path):
        tone_yaml = DEFAULT_TONE_YAML.replace("note_on: 4.0", "note_on: 5.0")
        changed = hash_of(make_session(tmp_path / "changed", tone_yaml=tone_yaml))
        assert changed != default_hash(tmp_path)

    def test_session_timing_changes_hash(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace("pre_roll: 1.0", "pre_roll: 2.0")
        changed = hash_of(make_session(tmp_path / "changed", session_yaml=session_yaml))
        assert changed != default_hash(tmp_path)

    def test_naming_template_changes_hash(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace(
            "output:\n  directory: recorded",
            "output:\n  directory: recorded\n  naming:\n"
            "    sample_filename: >-\n"
            "      {definition_id}__{sample_index:03d}",
        )
        changed = hash_of(make_session(tmp_path / "changed", session_yaml=session_yaml))
        assert changed != default_hash(tmp_path)

    def test_audio_format_changes_hash(self, tmp_path):
        session_path = make_session(tmp_path / "changed")
        resolver = DefinitionResolver(FakeAudioInformationLoader(sample_rate=44100))
        plan = SamplingPlanBuilder().build(resolver.resolve(session_path))
        assert plan.tones[0].resolved_definition_sha256 != default_hash(tmp_path)

    def test_midi_channel_changes_hash(self, tmp_path):
        session_yaml = DEFAULT_SESSION_YAML.replace("channel: 0", "channel: 1")
        changed = hash_of(make_session(tmp_path / "changed", session_yaml=session_yaml))
        assert changed != default_hash(tmp_path)
