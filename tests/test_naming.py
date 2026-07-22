import pytest

from midi_sampling.sampling.exceptions import InvalidFilenameTemplateError
from midi_sampling.sampling.naming import SampleFilenameFormatter

VALUES = {
    "definition_id": "tone-1",
    "bank_msb": 0,
    "bank_lsb": 0,
    "program": 41,
    "root_note": 38,
    "key_low": 36,
    "key_high": 40,
    "velocity_low": 1,
    "velocity_high": 63,
    "send_velocity": 48,
    "sample_index": 0,
}


class TestSampleFilenameFormatter:
    def test_standard_template(self):
        formatter = SampleFilenameFormatter(
            "r{root_note:03d}__k{key_low:03d}-{key_high:03d}"
            "__v{velocity_low:03d}-{velocity_high:03d}__s{send_velocity:03d}"
        )
        assert formatter.format(VALUES) == "r038__k036-040__v001-063__s048"

    def test_all_placeholders_available(self):
        formatter = SampleFilenameFormatter(
            "{definition_id}_{bank_msb}_{bank_lsb}_{program}_{sample_index}"
        )
        assert formatter.format(VALUES) == "tone-1_0_0_41_0"

    def test_empty_template_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("")

    def test_unknown_placeholder_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("{unknown_name}")

    def test_positional_placeholder_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("{}")

    def test_attribute_access_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("{definition_id.__class__}")

    def test_index_access_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("{definition_id[0]}")

    def test_conversion_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("{definition_id!r}")

    def test_nested_placeholder_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("{root_note:{program}d}")

    def test_malformed_template_rejected(self):
        with pytest.raises(InvalidFilenameTemplateError):
            SampleFilenameFormatter("{root_note")
