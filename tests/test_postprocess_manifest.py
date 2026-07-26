import sys
from pathlib import Path

import pytest
import yaml

from conftest import (
    DEFAULT_POSTPROCESS_SESSION_YAML,
    FakeStage,
    build_postprocess_plan,
    make_postprocess_session,
    make_recorded_output,
)
from midi_sampling.postprocess import PostprocessExecutor
from midi_sampling.postprocess.exceptions import (
    PostprocessDependencyError,
    PostprocessManifestReadError,
)
from midi_sampling.postprocess.manifest import (
    PostprocessManifestRepository,
    create_initial_manifest,
)


@pytest.fixture
def session_file(tmp_path: Path) -> Path:
    make_recorded_output(tmp_path)
    return make_postprocess_session(tmp_path, DEFAULT_POSTPROCESS_SESSION_YAML)


def test_initial_manifest_is_all_pending(session_file: Path):
    plan = build_postprocess_plan(session_file)

    manifest = create_initial_manifest(plan, plan.tones[0])

    assert manifest.status == "pending"
    assert all(sample.status == "pending" for sample in manifest.samples)
    assert all(sample.trim is None and sample.loop is None for sample in manifest.samples)
    assert all(
        sample.file == sample.source_file for sample in manifest.samples
    )


def test_manifest_round_trips_through_yaml(session_file: Path, tmp_path: Path):
    plan = build_postprocess_plan(session_file)
    manifest = create_initial_manifest(plan, plan.tones[0])
    repository = PostprocessManifestRepository()
    path = tmp_path / "manifest.yaml"

    repository.write(path, manifest)

    assert repository.read(path) == manifest


def test_written_manifest_declares_its_kind(session_file: Path, tmp_path: Path):
    plan = build_postprocess_plan(session_file)
    path = tmp_path / "manifest.yaml"

    PostprocessManifestRepository().write(
        path, create_initial_manifest(plan, plan.tones[0])
    )

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["kind"] == "postprocess_manifest"
    assert data["schema_version"] == 1


def test_write_is_atomic_and_leaves_no_temporary_file(
    session_file: Path, tmp_path: Path
):
    plan = build_postprocess_plan(session_file)
    path = tmp_path / "manifest.yaml"

    PostprocessManifestRepository().write(
        path, create_initial_manifest(plan, plan.tones[0])
    )

    assert path.is_file()
    assert not (tmp_path / "manifest.yaml.tmp").exists()


def test_reading_an_invalid_manifest_is_rejected(tmp_path: Path):
    path = tmp_path / "manifest.yaml"
    path.write_text("kind: something_else\n", encoding="utf-8")

    with pytest.raises(PostprocessManifestReadError):
        PostprocessManifestRepository().read(path)


def test_reading_a_sample_manifest_as_derived_is_rejected(tmp_path: Path):
    recorded = make_recorded_output(tmp_path)

    with pytest.raises(PostprocessManifestReadError):
        PostprocessManifestRepository().read(recorded / "tone-1" / "manifest.yaml")


def test_completed_manifest_is_self_contained_for_patch_generation(
    session_file: Path,
):
    plan = build_postprocess_plan(
        session_file, stages=(FakeStage("trim"), FakeStage("loop"))
    )
    PostprocessExecutor().execute(plan)

    manifest = PostprocessManifestRepository().read(plan.tones[0].manifest_path)

    # Everything a patch generator needs, without touching the source.
    assert manifest.resolved_definition.zones
    assert manifest.resolved_definition.velocity_layers
    assert manifest.audio.sample_rate > 0
    for sample in manifest.samples:
        assert (plan.tones[0].directory / sample.file).is_file()
        assert sample.mapping.key_low <= sample.mapping.root_note
        assert sample.mapping.root_note <= sample.mapping.key_high
        assert sample.loop is not None
        assert sample.loop.midi_unity_note == sample.mapping.root_note


class TestOptionalDependency:
    def _hide(self, monkeypatch, name: str) -> None:
        for module in list(sys.modules):
            if module == name or module.startswith(f"{name}."):
                monkeypatch.delitem(sys.modules, module, raising=False)
        monkeypatch.setitem(sys.modules, name, None)

    def test_trim_stage_reports_a_missing_package(self, monkeypatch):
        from midi_sampling.postprocess.definitions import TrimSettingsDefinition
        from midi_sampling.postprocess.stages import TrimStage

        self._hide(monkeypatch, "wav_silence_trimmer")

        with pytest.raises(PostprocessDependencyError, match="midi-sampling\\[postprocess\\]"):
            TrimStage.create(TrimSettingsDefinition())

    def test_loop_stage_reports_a_missing_package(self, monkeypatch):
        from midi_sampling.postprocess.definitions import LoopSettingsDefinition
        from midi_sampling.postprocess.stages import LoopStage

        self._hide(monkeypatch, "sample_loop_detector")

        with pytest.raises(PostprocessDependencyError, match="midi-sampling\\[postprocess\\]"):
            LoopStage.create(LoopSettingsDefinition(), on_failure="skip")
