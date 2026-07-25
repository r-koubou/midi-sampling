from pathlib import Path

import pytest

from conftest import (
    DEFAULT_POSTPROCESS_SESSION_YAML,
    FakeStage,
    build_postprocess_plan,
    make_postprocess_session,
    make_recorded_output,
)
from midi_sampling.postprocess import PostprocessExecutor
from midi_sampling.postprocess.exceptions import (
    PostprocessExistingOutputError,
    PostprocessStageError,
)
from midi_sampling.postprocess.manifest import PostprocessManifestRepository
from midi_sampling.postprocess.planning import WORK_DIRECTORY_NAME
from midi_sampling.sampling.manifest import SampleManifestRepository


@pytest.fixture
def recorded(tmp_path: Path) -> Path:
    return make_recorded_output(tmp_path)


@pytest.fixture
def session_file(tmp_path: Path, recorded: Path) -> Path:
    return make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)


def snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path: path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()
    }


def read_manifest(plan) -> object:
    return PostprocessManifestRepository().read(plan.tones[0].manifest_path)


def test_produces_one_output_per_source_sample(session_file: Path):
    plan = build_postprocess_plan(session_file)

    PostprocessExecutor().execute(plan)

    tone = plan.tones[0]
    produced = sorted(path.name for path in tone.directory.glob("*.wav"))
    assert produced == sorted(target.file_name for target in tone.targets)


def test_source_is_never_modified(session_file: Path, recorded: Path):
    before = snapshot(recorded)
    plan = build_postprocess_plan(session_file)

    PostprocessExecutor().execute(plan)

    assert snapshot(recorded) == before


def test_stages_are_applied_in_order_and_chained(session_file: Path):
    trim = FakeStage("trim")
    loop = FakeStage("loop")
    plan = build_postprocess_plan(session_file, stages=(trim, loop))

    PostprocessExecutor().execute(plan)

    first_target = plan.tones[0].targets[0]
    trim_input, trim_output, _ = trim.calls[0]
    loop_input, loop_output, _ = loop.calls[0]

    assert trim_input == first_target.source_path
    assert loop_input == trim_output
    assert loop_output != first_target.output_path
    assert first_target.output_path.is_file()


def test_every_path_handed_to_a_stage_ends_with_wav(session_file: Path):
    trim = FakeStage("trim")
    loop = FakeStage("loop")
    plan = build_postprocess_plan(session_file, stages=(trim, loop))

    PostprocessExecutor().execute(plan)

    for stage in (trim, loop):
        assert stage.calls
        for input_path, output_path, _ in stage.calls:
            assert input_path.suffix == ".wav", input_path
            assert output_path.suffix == ".wav", output_path


def test_root_note_is_passed_from_the_manifest(session_file: Path, recorded: Path):
    source = SampleManifestRepository().read(recorded / "tone-1" / "manifest.yaml")
    stage = FakeStage("loop")
    plan = build_postprocess_plan(session_file, stages=(stage,))

    PostprocessExecutor().execute(plan)

    assert [call[2] for call in stage.calls] == [
        sample.mapping.root_note for sample in source.samples
    ]


def test_work_directory_is_removed_on_success(session_file: Path):
    plan = build_postprocess_plan(session_file)

    PostprocessExecutor().execute(plan)

    assert not (plan.tones[0].directory / WORK_DIRECTORY_NAME).exists()


def test_manifest_is_completed_and_carries_the_mapping(
    session_file: Path, recorded: Path
):
    source = SampleManifestRepository().read(recorded / "tone-1" / "manifest.yaml")
    plan = build_postprocess_plan(session_file)

    PostprocessExecutor().execute(plan)

    manifest = read_manifest(plan)
    assert manifest.kind == "postprocess_manifest"
    assert manifest.status == "completed"
    assert all(sample.status == "completed" for sample in manifest.samples)
    assert [sample.mapping.model_dump() for sample in manifest.samples] == [
        sample.mapping.model_dump() for sample in source.samples
    ]
    assert manifest.midi == source.midi
    assert manifest.naming == source.naming
    assert manifest.resolved_definition == source.resolved_definition


def test_manifest_records_all_three_hashes(session_file: Path):
    plan = build_postprocess_plan(session_file)

    PostprocessExecutor().execute(plan)

    provenance = read_manifest(plan).provenance
    tone = plan.tones[0]
    assert provenance.source_manifest_sha256 == tone.source_manifest_sha256
    assert provenance.resolved_definition_sha256 == tone.resolved_definition_sha256
    assert provenance.postprocess_settings_sha256 == plan.settings_sha256
    assert provenance.stages == ["trim"]


def test_manifest_source_points_back_at_the_recording(session_file: Path):
    plan = build_postprocess_plan(session_file)

    PostprocessExecutor().execute(plan)

    manifest = read_manifest(plan)
    tone = plan.tones[0]
    resolved = (tone.directory / manifest.source.directory).resolve()
    assert resolved == tone.source_directory
    assert (resolved / manifest.source.manifest).is_file()


def test_stage_blocks_are_recorded(session_file: Path):
    plan = build_postprocess_plan(
        session_file, stages=(FakeStage("trim"), FakeStage("loop"))
    )

    PostprocessExecutor().execute(plan)

    for sample in read_manifest(plan).samples:
        assert sample.trim is not None and sample.trim.applied
        assert sample.loop is not None and sample.loop.status == "success"


def test_stage_that_writes_nothing_still_produces_an_output(session_file: Path):
    plan = build_postprocess_plan(
        session_file, stages=(FakeStage("loop", output_written=False),)
    )

    PostprocessExecutor().execute(plan)

    tone = plan.tones[0]
    for target in tone.targets:
        assert target.output_path.is_file()
        assert target.output_path.read_bytes() == target.source_path.read_bytes()

    manifest = read_manifest(plan)
    assert all(sample.loop.status == "not_found" for sample in manifest.samples)


def test_stops_on_the_first_failure(session_file: Path):
    stage = FakeStage("trim", fail_on_sample_index=1)
    plan = build_postprocess_plan(session_file, stages=(stage,))

    with pytest.raises(PostprocessStageError):
        PostprocessExecutor().execute(plan)

    tone = plan.tones[0]
    assert len(stage.calls) == 2
    assert tone.targets[0].output_path.is_file()
    assert not tone.targets[1].output_path.exists()
    assert not tone.targets[2].output_path.exists()


def test_failure_marks_the_manifest(session_file: Path):
    plan = build_postprocess_plan(
        session_file, stages=(FakeStage("trim", fail_on_sample_index=1),)
    )

    with pytest.raises(PostprocessStageError):
        PostprocessExecutor().execute(plan)

    manifest = read_manifest(plan)
    assert manifest.status == "failed"
    assert manifest.error is not None
    assert manifest.samples[0].status == "completed"
    assert manifest.samples[1].status == "failed"
    assert manifest.samples[2].status == "pending"


def test_failure_keeps_the_work_directory_for_inspection(session_file: Path):
    plan = build_postprocess_plan(
        session_file, stages=(FakeStage("trim", fail_on_sample_index=1),)
    )

    with pytest.raises(PostprocessStageError):
        PostprocessExecutor().execute(plan)

    assert (plan.tones[0].directory / WORK_DIRECTORY_NAME).is_dir()


def test_failure_does_not_touch_the_source(session_file: Path, recorded: Path):
    before = snapshot(recorded)
    plan = build_postprocess_plan(
        session_file, stages=(FakeStage("trim", fail_on_sample_index=0),)
    )

    with pytest.raises(PostprocessStageError):
        PostprocessExecutor().execute(plan)

    assert snapshot(recorded) == before


def test_existing_output_directory_is_refused(session_file: Path):
    plan = build_postprocess_plan(session_file)
    PostprocessExecutor().execute(plan)

    again = build_postprocess_plan(session_file)
    with pytest.raises(PostprocessExistingOutputError, match="already exists"):
        PostprocessExecutor().execute(again)


def test_existing_output_error_reports_all_three_hashes(session_file: Path):
    PostprocessExecutor().execute(build_postprocess_plan(session_file))

    changed = build_postprocess_plan(session_file, stages=(FakeStage(marker="other"),))
    with pytest.raises(PostprocessExistingOutputError) as error:
        PostprocessExecutor().execute(changed)

    message = str(error.value)
    assert "source manifest hash" in message
    assert "definition hash" in message
    assert "settings hash" in message
    assert "different" in message


def test_manifest_is_written_before_processing_starts(session_file: Path):
    plan = build_postprocess_plan(
        session_file, stages=(FakeStage("trim", fail_on_sample_index=0),)
    )

    with pytest.raises(PostprocessStageError):
        PostprocessExecutor().execute(plan)

    # Even though no sample completed, the manifest exists and lists them all.
    manifest = read_manifest(plan)
    assert len(manifest.samples) == len(plan.tones[0].targets)
