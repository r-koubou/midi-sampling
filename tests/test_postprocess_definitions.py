import pytest
from pydantic import ValidationError

from midi_sampling.postprocess.definitions import PostprocessSessionDefinition

BASE = {
    "schema_version": 1,
    "kind": "postprocess_session",
    "source": {"directory": "recorded"},
    "output": {"directory": "processed"},
    "stages": [{"kind": "trim"}],
}


def make(**overrides) -> dict:
    return {**BASE, **overrides}


def test_minimal_session_is_valid():
    session = PostprocessSessionDefinition.model_validate(BASE)

    assert session.stages[0].kind == "trim"
    assert session.tones is None


def test_loop_stage_defaults():
    session = PostprocessSessionDefinition.model_validate(
        make(stages=[{"kind": "loop"}])
    )

    stage = session.stages[0]
    assert stage.on_failure == "skip"
    assert stage.settings.midi_unity_note == "from_manifest"
    assert stage.settings.min_loop is None


def test_unknown_top_level_field_is_rejected():
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(make(unknown=1))


def test_unknown_stage_setting_is_rejected():
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(
            make(stages=[{"kind": "trim", "settings": {"nope": 1.0}}])
        )


def test_unknown_stage_kind_is_rejected():
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(
            make(stages=[{"kind": "normalize"}])
        )


def test_empty_stages_is_rejected():
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(make(stages=[]))


def test_duplicate_stage_kind_is_rejected():
    with pytest.raises(ValidationError, match="duplicate stage kind"):
        PostprocessSessionDefinition.model_validate(
            make(stages=[{"kind": "trim"}, {"kind": "trim"}])
        )


def test_duplicate_tone_id_is_rejected():
    with pytest.raises(ValidationError, match="duplicate tone id"):
        PostprocessSessionDefinition.model_validate(make(tones=["a", "a"]))


def test_empty_tone_list_is_rejected():
    with pytest.raises(ValidationError, match="must not be an empty list"):
        PostprocessSessionDefinition.model_validate(make(tones=[]))


@pytest.mark.parametrize("value", [-1, 128, "middle_c"])
def test_invalid_midi_unity_note_is_rejected(value):
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(
            make(stages=[{"kind": "loop", "settings": {"midi_unity_note": value}}])
        )


@pytest.mark.parametrize("value", ["from_manifest", "auto", 0, 60, 127])
def test_valid_midi_unity_note(value):
    session = PostprocessSessionDefinition.model_validate(
        make(stages=[{"kind": "loop", "settings": {"midi_unity_note": value}}])
    )

    assert session.stages[0].settings.midi_unity_note == value


def test_bool_is_not_accepted_as_a_number():
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(
            make(stages=[{"kind": "trim", "settings": {"fade_in_ms": True}}])
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_numbers_are_rejected(value):
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(
            make(stages=[{"kind": "trim", "settings": {"fade_in_ms": value}}])
        )


def test_out_of_range_percentage_is_rejected():
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(
            make(stages=[{"kind": "trim", "settings": {"noise_percentile": 101.0}}])
        )


def test_wrong_kind_is_rejected():
    with pytest.raises(ValidationError):
        PostprocessSessionDefinition.model_validate(make(kind="sampling_session"))
