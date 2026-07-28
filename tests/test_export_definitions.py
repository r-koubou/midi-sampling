import pytest
from pydantic import ValidationError

from midi_sampling.export.definitions import InstrumentDefinition


def base_definition() -> dict:
    return {
        "schema_version": 1,
        "kind": "instrument_definition",
        "name": "test-instrument",
        "sources": [
            {"tone": "tone-1", "manifest": "processed/tone-1/manifest.yaml"},
            {"tone": "tone-2", "manifest": "processed/tone-2/manifest.yaml"},
        ],
    }


class TestInstrumentDefinition:
    def test_minimal_definition_defaults_to_wav(self):
        definition = InstrumentDefinition.model_validate(base_definition())

        assert definition.audio.format == "wav"
        assert definition.audio.bit_depth is None
        assert definition.exclusive_groups == []
        assert definition.release_triggers == []

    def test_envelope_defaults(self):
        definition = InstrumentDefinition.model_validate(base_definition())

        assert definition.envelope.attack == 0.0
        assert definition.envelope.release == 0.3

    def test_envelope_accepts_seconds(self):
        data = base_definition() | {"envelope": {"attack": 0.01, "release": 1}}
        definition = InstrumentDefinition.model_validate(data)

        assert definition.envelope.attack == 0.01
        assert definition.envelope.release == 1.0

    def test_negative_envelope_is_rejected(self):
        data = base_definition() | {"envelope": {"release": -0.1}}
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)

    def test_wrong_kind_is_rejected(self):
        data = base_definition() | {"kind": "postprocess_session"}
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)

    def test_unknown_key_is_rejected(self):
        data = base_definition() | {"unknown": 1}
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)

    def test_empty_sources_is_rejected(self):
        data = base_definition() | {"sources": []}
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)

    def test_duplicate_source_tone_is_rejected(self):
        data = base_definition()
        data["sources"][1]["tone"] = "tone-1"
        with pytest.raises(ValidationError, match="duplicate source tone"):
            InstrumentDefinition.model_validate(data)

    def test_name_with_path_separator_is_rejected(self):
        data = base_definition() | {"name": "patches/evil"}
        with pytest.raises(ValidationError, match="file name"):
            InstrumentDefinition.model_validate(data)

    def test_empty_name_is_rejected(self):
        data = base_definition() | {"name": "  "}
        with pytest.raises(ValidationError, match="empty"):
            InstrumentDefinition.model_validate(data)


class TestAudioSettings:
    def test_flac_with_bit_depth_is_accepted(self):
        data = base_definition() | {"audio": {"format": "flac", "bit_depth": 24}}
        definition = InstrumentDefinition.model_validate(data)
        assert definition.audio.bit_depth == 24

    def test_bit_depth_without_flac_is_rejected(self):
        data = base_definition() | {"audio": {"format": "wav", "bit_depth": 16}}
        with pytest.raises(ValidationError, match="format: flac"):
            InstrumentDefinition.model_validate(data)

    def test_unsupported_bit_depth_is_rejected(self):
        data = base_definition() | {"audio": {"format": "flac", "bit_depth": 32}}
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)

    def test_unknown_format_is_rejected(self):
        data = base_definition() | {"audio": {"format": "ogg"}}
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)


class TestExclusiveGroups:
    def test_valid_group_is_accepted(self):
        data = base_definition() | {
            "exclusive_groups": [
                {
                    "name": "hihat",
                    "members": [
                        {"tone": "tone-1", "root_note": 42},
                        {"tone": "tone-1", "root_note": 46},
                    ],
                }
            ]
        }
        definition = InstrumentDefinition.model_validate(data)
        assert definition.exclusive_groups[0].members[0].root_note == 42

    def test_single_member_group_is_rejected(self):
        data = base_definition() | {
            "exclusive_groups": [
                {"name": "hihat", "members": [{"tone": "tone-1"}]}
            ]
        }
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)

    def test_undeclared_tone_is_rejected(self):
        data = base_definition() | {
            "exclusive_groups": [
                {
                    "name": "hihat",
                    "members": [{"tone": "tone-1"}, {"tone": "ghost"}],
                }
            ]
        }
        with pytest.raises(ValidationError, match="not declared in sources"):
            InstrumentDefinition.model_validate(data)

    def test_duplicate_group_name_is_rejected(self):
        group = {
            "name": "hihat",
            "members": [{"tone": "tone-1"}, {"tone": "tone-2"}],
        }
        data = base_definition() | {"exclusive_groups": [group, group]}
        with pytest.raises(ValidationError, match="duplicate exclusive group"):
            InstrumentDefinition.model_validate(data)

    def test_duplicate_member_is_rejected(self):
        data = base_definition() | {
            "exclusive_groups": [
                {
                    "name": "hihat",
                    "members": [
                        {"tone": "tone-1", "root_note": 42},
                        {"tone": "tone-1", "root_note": 42},
                    ],
                }
            ]
        }
        with pytest.raises(ValidationError, match="duplicate member"):
            InstrumentDefinition.model_validate(data)


class TestReleaseTriggers:
    def test_valid_trigger_is_accepted(self):
        data = base_definition() | {
            "release_triggers": [
                {
                    "trigger_of": {"tone": "tone-1"},
                    "plays": {"tone": "tone-2"},
                    "rt_decay": 6.0,
                }
            ]
        }
        definition = InstrumentDefinition.model_validate(data)
        assert definition.release_triggers[0].rt_decay == 6.0

    def test_same_tone_on_both_sides_is_rejected(self):
        data = base_definition() | {
            "release_triggers": [
                {"trigger_of": {"tone": "tone-1"}, "plays": {"tone": "tone-1"}}
            ]
        }
        with pytest.raises(ValidationError, match="two different tones"):
            InstrumentDefinition.model_validate(data)

    def test_undeclared_tone_is_rejected(self):
        data = base_definition() | {
            "release_triggers": [
                {"trigger_of": {"tone": "tone-1"}, "plays": {"tone": "ghost"}}
            ]
        }
        with pytest.raises(ValidationError, match="not declared in sources"):
            InstrumentDefinition.model_validate(data)

    def test_tone_played_by_two_triggers_is_rejected(self):
        trigger = {"trigger_of": {"tone": "tone-1"}, "plays": {"tone": "tone-2"}}
        data = base_definition() | {"release_triggers": [trigger, trigger]}
        with pytest.raises(ValidationError, match="more than once"):
            InstrumentDefinition.model_validate(data)

    def test_tone_as_both_plays_and_trigger_is_rejected(self):
        data = base_definition()
        data["sources"].append(
            {"tone": "tone-3", "manifest": "processed/tone-3/manifest.yaml"}
        )
        data["release_triggers"] = [
            {"trigger_of": {"tone": "tone-1"}, "plays": {"tone": "tone-2"}},
            {"trigger_of": {"tone": "tone-2"}, "plays": {"tone": "tone-3"}},
        ]
        with pytest.raises(ValidationError, match="both trigger_of and plays"):
            InstrumentDefinition.model_validate(data)

    def test_negative_rt_decay_is_rejected(self):
        data = base_definition() | {
            "release_triggers": [
                {
                    "trigger_of": {"tone": "tone-1"},
                    "plays": {"tone": "tone-2"},
                    "rt_decay": -1.0,
                }
            ]
        }
        with pytest.raises(ValidationError):
            InstrumentDefinition.model_validate(data)
