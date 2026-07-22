from pathlib import Path

import pytest

from midi_sampling.sampling.exceptions import InvalidOutputPathError
from midi_sampling.sampling.validation import OutputPathValidator
from midi_sampling.sampling.validation.output_path_validator import (
    MAX_FULL_PATH_LENGTH,
)

validator = OutputPathValidator()


class TestComponentValidation:
    @pytest.mark.parametrize(
        "name",
        ["CON", "con", "NUL", "com1", "LPT9", "CON.wav", "com1.sample.wav"],
    )
    def test_windows_reserved_names_rejected(self, name):
        with pytest.raises(InvalidOutputPathError):
            validator.validate_component(name, "test")

    @pytest.mark.parametrize(
        "name",
        ["a/b.wav", "a\\b.wav", "a\x00b.wav", "a:b.wav", "a?.wav", "a*.wav", "a<b>.wav"],
    )
    def test_invalid_characters_rejected(self, name):
        with pytest.raises(InvalidOutputPathError):
            validator.validate_component(name, "test")

    def test_empty_name_rejected(self):
        with pytest.raises(InvalidOutputPathError):
            validator.validate_component("", "test")

    @pytest.mark.parametrize("name", ["sample.wav ", "sample.wav.", "trailing."])
    def test_trailing_space_or_period_rejected(self, name):
        with pytest.raises(InvalidOutputPathError):
            validator.validate_component(name, "test")

    def test_too_long_component_rejected(self):
        with pytest.raises(InvalidOutputPathError):
            validator.validate_component("a" * 256, "test")

    def test_normal_names_accepted(self):
        validator.validate_component("r038__k036-040__v001-063__s048.wav", "test")
        validator.validate_component("tone-1", "test")
        validator.validate_component("console.wav", "test")  # not a reserved name


class TestFullPathValidation:
    def test_too_long_path_rejected(self):
        path = Path("C:/") / ("a" * MAX_FULL_PATH_LENGTH)
        with pytest.raises(InvalidOutputPathError):
            validator.validate_full_path(path, "test")

    def test_normal_path_accepted(self, tmp_path):
        validator.validate_full_path(tmp_path / "recorded" / "sample.wav", "test")


class TestOutputRoot:
    def test_creatable_under_existing_directory(self, tmp_path):
        validator.validate_output_root_creatable(tmp_path / "new" / "nested")

    def test_file_in_the_way_rejected(self, tmp_path):
        blocking_file = tmp_path / "recorded"
        blocking_file.write_text("", encoding="utf-8")
        with pytest.raises(InvalidOutputPathError):
            validator.validate_output_root_creatable(blocking_file / "tone")
