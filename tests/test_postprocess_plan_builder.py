from pathlib import Path

import pytest

from conftest import (
    DEFAULT_POSTPROCESS_SESSION_YAML,
    FakeStage,
    build_postprocess_plan,
    make_postprocess_session,
    make_recorded_output,
)
from midi_sampling.postprocess.exceptions import PostprocessSourceError
from midi_sampling.postprocess.planning import WORK_DIRECTORY_NAME
from midi_sampling.sampling.manifest import SampleManifestRepository


@pytest.fixture
def recorded(tmp_path: Path) -> Path:
    return make_recorded_output(tmp_path)


@pytest.fixture
def session_file(tmp_path: Path, recorded: Path) -> Path:
    return make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)


def test_targets_match_the_source_manifest(session_file: Path, recorded: Path):
    source = SampleManifestRepository().read(recorded / "tone-1" / "manifest.yaml")

    plan = build_postprocess_plan(session_file)

    tone = plan.tones[0]
    assert len(tone.targets) == len(source.samples)
    assert [target.file_name for target in tone.targets] == [
        sample.file for sample in source.samples
    ]
    assert [target.sample_index for target in tone.targets] == [
        sample.index for sample in source.samples
    ]


def test_output_file_names_are_one_to_one_with_the_source(session_file: Path):
    plan = build_postprocess_plan(session_file)

    for target in plan.tones[0].targets:
        assert target.output_path.name == target.source_path.name
        assert target.output_path.parent == plan.output_root / "tone-1"


def test_mapping_is_copied_from_the_manifest_not_the_file_name(
    session_file: Path, recorded: Path
):
    source = SampleManifestRepository().read(recorded / "tone-1" / "manifest.yaml")

    plan = build_postprocess_plan(session_file)

    for target, sample in zip(plan.tones[0].targets, source.samples, strict=True):
        assert target.mapping.root_note == sample.mapping.root_note
        assert target.mapping.key_low == sample.mapping.key_low
        assert target.mapping.key_high == sample.mapping.key_high
        assert target.mapping.velocity_low == sample.mapping.velocity_low
        assert target.mapping.velocity_high == sample.mapping.velocity_high


def test_carried_over_manifest_blocks(session_file: Path, recorded: Path):
    source = SampleManifestRepository().read(recorded / "tone-1" / "manifest.yaml")

    tone = build_postprocess_plan(session_file).tones[0]

    assert tone.midi == source.midi
    assert tone.audio == source.audio
    assert tone.naming == source.naming
    assert tone.resolved_definition == source.resolved_definition
    assert tone.resolved_definition_sha256 == (
        source.provenance.resolved_definition_sha256
    )


def test_work_paths_live_under_the_tone_directory_and_end_with_wav(
    session_file: Path,
):
    plan = build_postprocess_plan(session_file)

    tone = plan.tones[0]
    assert tone.work_directory == tone.directory / WORK_DIRECTORY_NAME

    for target in tone.targets:
        work_path = target.work_path(1, "trim")
        assert work_path.parent == tone.work_directory
        assert work_path.suffix == ".wav"
        assert work_path != target.output_path


def test_source_manifest_hash_changes_with_the_source(
    session_file: Path, recorded: Path
):
    before = build_postprocess_plan(session_file).tones[0].source_manifest_sha256

    manifest_path = recorded / "tone-1" / "manifest.yaml"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8") + "\n# a change\n", encoding="utf-8"
    )
    after = build_postprocess_plan(session_file).tones[0].source_manifest_sha256

    assert before != after


def test_settings_hash_changes_with_the_stage_settings(session_file: Path):
    first = build_postprocess_plan(session_file, stages=(FakeStage(marker="a"),))
    second = build_postprocess_plan(session_file, stages=(FakeStage(marker="b"),))
    same = build_postprocess_plan(session_file, stages=(FakeStage(marker="a"),))

    assert first.settings_sha256 != second.settings_sha256
    assert first.settings_sha256 == same.settings_sha256


def test_settings_hash_changes_with_the_stage_order(session_file: Path):
    forward = build_postprocess_plan(
        session_file, stages=(FakeStage("trim"), FakeStage("loop"))
    )
    reverse = build_postprocess_plan(
        session_file, stages=(FakeStage("loop"), FakeStage("trim"))
    )

    assert forward.settings_sha256 != reverse.settings_sha256


def test_settings_hash_ignores_directories_and_comments(
    tmp_path: Path, recorded: Path
):
    plain = make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)
    baseline = build_postprocess_plan(plain).settings_sha256

    commented = tmp_path / "commented.yaml"
    commented.write_text(
        "# a leading comment\n"
        + DEFAULT_POSTPROCESS_SESSION_YAML.replace(
            "directory: processed", "directory: elsewhere  # moved"
        ),
        encoding="utf-8",
    )

    assert build_postprocess_plan(commented).settings_sha256 == baseline


def test_source_file_without_wav_extension_is_rejected(
    session_file: Path, recorded: Path
):
    manifest_path = recorded / "tone-1" / "manifest.yaml"
    text = manifest_path.read_text(encoding="utf-8")
    first_wav = next(iter(sorted((recorded / "tone-1").glob("*.wav")))).name
    manifest_path.write_text(
        text.replace(first_wav, first_wav.replace(".wav", ".wav.part")), "utf-8"
    )
    (recorded / "tone-1" / first_wav).rename(
        recorded / "tone-1" / first_wav.replace(".wav", ".wav.part")
    )

    with pytest.raises(PostprocessSourceError, match="must end with"):
        build_postprocess_plan(session_file)
