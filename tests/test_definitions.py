from pathlib import Path

import pytest

from midi_sampling.sampling.definitions import (
    SamplingDefinition,
    SamplingSessionDefinition,
    VelocityProfileDefinition,
    ZoneLayoutDefinition,
)
from midi_sampling.sampling.exceptions import (
    DefinitionLoadError,
    DefinitionValidationError,
)
from midi_sampling.sampling.loading import YamlDefinitionLoader

from conftest import (
    DEFAULT_SESSION_YAML,
    DEFAULT_TONE_YAML,
    DEFAULT_VELOCITIES_YAML,
    DEFAULT_ZONES_YAML,
)


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "definition.yaml"
    path.write_text(text, encoding="utf-8")
    return path


loader = YamlDefinitionLoader()


class TestValidDefinitions:
    def test_zone_layout(self, tmp_path):
        model = loader.load(_write(tmp_path, DEFAULT_ZONES_YAML), ZoneLayoutDefinition)
        assert len(model.zones) == 2
        assert model.zones[0].low == 36
        assert model.zones[0].root == 38
        assert model.zones[0].high == 40

    def test_velocity_profile(self, tmp_path):
        model = loader.load(
            _write(tmp_path, DEFAULT_VELOCITIES_YAML), VelocityProfileDefinition
        )
        assert len(model.layers) == 2
        assert model.layers[1].send == 112

    def test_sampling_definition(self, tmp_path):
        model = loader.load(_write(tmp_path, DEFAULT_TONE_YAML), SamplingDefinition)
        assert model.id == "tone-1"
        assert model.midi_program.program == 41
        assert model.timing.note_on == 4.0
        assert model.timing.release_capture == 3.0

    def test_sampling_session(self, tmp_path):
        model = loader.load(
            _write(tmp_path, DEFAULT_SESSION_YAML), SamplingSessionDefinition
        )
        assert model.midi.channel == 0
        assert model.timing.pre_roll == 1.0
        assert model.output.directory == "recorded"

    def test_inline_zone_and_velocity(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace(
            "zone_layout:\n  file: ../presets/zones.yaml",
            "zone_layout:\n  zones:\n    - low: 36\n      root: 38\n      high: 40",
        ).replace(
            "velocity_profile:\n  file: ../presets/velocities.yaml",
            "velocity_profile:\n  layers:\n    - low: 1\n      high: 127\n      send: 100",
        )
        model = loader.load(_write(tmp_path, text), SamplingDefinition)
        assert model.zone_layout.zones[0].root == 38
        assert model.velocity_profile.layers[0].send == 100

    def test_integer_time_values_become_float(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace("note_on: 4.0", "note_on: 4")
        model = loader.load(_write(tmp_path, text), SamplingDefinition)
        assert model.timing.note_on == 4.0
        assert isinstance(model.timing.note_on, float)


class TestRejectedDefinitions:
    def test_unknown_field(self, tmp_path):
        text = DEFAULT_ZONES_YAML + "\nunknown_field: 1\n"
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), ZoneLayoutDefinition)

    def test_bool_is_not_an_integer(self, tmp_path):
        text = DEFAULT_ZONES_YAML.replace("root: 38", "root: true")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), ZoneLayoutDefinition)

    def test_string_is_not_an_integer(self, tmp_path):
        text = DEFAULT_ZONES_YAML.replace("root: 38", 'root: "38"')
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), ZoneLayoutDefinition)

    def test_out_of_range_midi_value(self, tmp_path):
        text = DEFAULT_ZONES_YAML.replace("high: 40", "high: 128")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), ZoneLayoutDefinition)

    def test_velocity_zero_rejected(self, tmp_path):
        text = DEFAULT_VELOCITIES_YAML.replace("low: 1", "low: 0", 1)
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), VelocityProfileDefinition)

    def test_nan_time_rejected(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace("note_on: 4.0", "note_on: .nan")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), SamplingDefinition)

    def test_infinite_time_rejected(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace("note_on: 4.0", "note_on: .inf")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), SamplingDefinition)

    def test_negative_time_rejected(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace("note_on: 4.0", "note_on: -1.0")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), SamplingDefinition)

    def test_wrong_kind_rejected(self, tmp_path):
        text = DEFAULT_ZONES_YAML.replace("kind: zone_layout", "kind: velocity_profile")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), ZoneLayoutDefinition)

    def test_file_and_inline_zones_together_rejected(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace(
            "zone_layout:\n  file: ../presets/zones.yaml",
            "zone_layout:\n  file: ../presets/zones.yaml\n"
            "  zones:\n    - low: 36\n      root: 38\n      high: 40",
        )
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), SamplingDefinition)

    def test_neither_file_nor_inline_rejected(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace(
            "zone_layout:\n  file: ../presets/zones.yaml",
            "zone_layout: {}",
        )
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), SamplingDefinition)

    def test_invalid_definition_id_rejected(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace("id: tone-1", "id: Tone One")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), SamplingDefinition)

    def test_missing_bank_select_rejected(self, tmp_path):
        text = DEFAULT_TONE_YAML.replace("  bank_msb: 0\n", "")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), SamplingDefinition)

    def test_zone_root_outside_range_rejected(self, tmp_path):
        text = DEFAULT_ZONES_YAML.replace("root: 38", "root: 41")
        with pytest.raises(DefinitionValidationError):
            loader.load(_write(tmp_path, text), ZoneLayoutDefinition)


class TestYamlSyntax:
    def test_syntax_error_reports_position(self, tmp_path):
        path = _write(tmp_path, "zones:\n  - low: 36\n high: [")
        with pytest.raises(DefinitionLoadError) as excinfo:
            loader.load(path, ZoneLayoutDefinition)
        assert str(path) in str(excinfo.value)

    def test_non_mapping_root_rejected(self, tmp_path):
        path = _write(tmp_path, "- 1\n- 2\n")
        with pytest.raises(DefinitionLoadError):
            loader.load(path, ZoneLayoutDefinition)

    def test_custom_yaml_tag_rejected(self, tmp_path):
        path = _write(
            tmp_path,
            "schema_version: 1\nkind: zone_layout\nzones: !!python/object:os.system []\n",
        )
        with pytest.raises(DefinitionLoadError):
            loader.load(path, ZoneLayoutDefinition)
