from pathlib import Path

import pytest

from conftest import (
    DEFAULT_POSTPROCESS_SESSION_YAML,
    make_postprocess_session,
    make_recorded_output,
)
from midi_sampling.postprocess.exceptions import (
    PostprocessDefinitionError,
    PostprocessSourceError,
)
from midi_sampling.postprocess.resolving import PostprocessResolver


def session_yaml(**overrides) -> str:
    source = overrides.get("source", "recorded")
    output = overrides.get("output", "processed")
    tones = overrides.get("tones")
    text = (
        "schema_version: 1\n"
        "kind: postprocess_session\n"
        "\n"
        f"source:\n  directory: {source}\n"
        "\n"
        f"output:\n  directory: {output}\n"
        "\n"
        "stages:\n  - kind: trim\n"
    )
    if tones is not None:
        text += "\ntones:\n" + "".join(f"  - {tone}\n" for tone in tones)
    return text


@pytest.fixture
def recorded(tmp_path: Path) -> Path:
    return make_recorded_output(tmp_path)


def test_resolves_all_tones_by_default(tmp_path: Path, recorded: Path):
    path = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)

    session = PostprocessResolver().resolve(path)

    assert [tone.definition_id for tone in session.tones] == ["tone-1"]
    assert session.source_root == recorded
    assert session.output_root == tmp_path / "processed"
    assert len(session.tones[0].manifest.samples) == 4


def test_explicit_tone_selection(tmp_path: Path, recorded: Path):
    path = make_postprocess_session(tmp_path, session_yaml(tones=["tone-1"]))

    session = PostprocessResolver().resolve(path)

    assert [tone.definition_id for tone in session.tones] == ["tone-1"]


def test_unknown_tone_is_rejected(tmp_path: Path, recorded: Path):
    path = make_postprocess_session(tmp_path, session_yaml(tones=["missing-tone"]))

    with pytest.raises(PostprocessSourceError, match="not found"):
        PostprocessResolver().resolve(path)


def test_missing_source_directory_is_rejected(tmp_path: Path):
    path = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)

    with pytest.raises(PostprocessSourceError, match="source directory not found"):
        PostprocessResolver().resolve(path)


def test_source_equal_to_output_is_rejected(tmp_path: Path, recorded: Path):
    path = make_postprocess_session(
        tmp_path, session_yaml(source="recorded", output="recorded")
    )

    with pytest.raises(PostprocessDefinitionError, match="must differ"):
        PostprocessResolver().resolve(path)


def test_incomplete_source_manifest_is_rejected(tmp_path: Path, recorded: Path):
    manifest_path = recorded / "tone-1" / "manifest.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "status: completed", "status: in_progress", 1
        ),
        encoding="utf-8",
    )
    path = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)

    with pytest.raises(PostprocessSourceError, match="status is 'in_progress'"):
        PostprocessResolver().resolve(path)


def test_missing_source_wav_is_rejected(tmp_path: Path, recorded: Path):
    wavs = sorted((recorded / "tone-1").glob("*.wav"))
    wavs[0].unlink()
    path = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)

    with pytest.raises(PostprocessSourceError, match="missing"):
        PostprocessResolver().resolve(path)


def test_invalid_source_manifest_is_rejected(tmp_path: Path, recorded: Path):
    (recorded / "tone-1" / "manifest.yaml").write_text("not: a manifest\n", "utf-8")
    path = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)

    with pytest.raises(PostprocessSourceError):
        PostprocessResolver().resolve(path)


def test_empty_source_directory_is_rejected(tmp_path: Path):
    (tmp_path / "recorded").mkdir()
    path = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)

    with pytest.raises(PostprocessSourceError, match="no tone directory"):
        PostprocessResolver().resolve(path)


@pytest.mark.parametrize(
    "directory",
    ["/absolute/path", "C:/absolute", "~/home", "http://example.com/x", "rec*"],
)
def test_unsupported_source_references_are_rejected(tmp_path: Path, directory: str):
    path = make_postprocess_session(tmp_path, session_yaml(source=directory))

    with pytest.raises(PostprocessDefinitionError):
        PostprocessResolver().resolve(path)


def test_missing_session_file_is_rejected(tmp_path: Path):
    with pytest.raises(PostprocessDefinitionError, match="not found"):
        PostprocessResolver().resolve(tmp_path / "nope.yaml")


def test_resolver_does_not_modify_the_source(tmp_path: Path, recorded: Path):
    before = {
        path: path.read_bytes()
        for path in sorted(recorded.rglob("*"))
        if path.is_file()
    }
    path = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)

    PostprocessResolver().resolve(path)

    after = {
        path: path.read_bytes()
        for path in sorted(recorded.rglob("*"))
        if path.is_file()
    }
    assert after == before
