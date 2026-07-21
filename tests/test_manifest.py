import pytest
import yaml

from midi_sampling.sampling.exceptions import ManifestReadError, ManifestWriteError
from midi_sampling.sampling.manifest import (
    SampleManifestRepository,
    create_initial_manifest,
)

repository = SampleManifestRepository()


class TestInitialManifest:
    def test_initial_state(self, plan):
        manifest = create_initial_manifest(plan, plan.tones[0])
        assert manifest.status == "pending"
        assert manifest.kind == "sample_manifest"
        assert manifest.definition.id == "tone-1"
        assert manifest.definition.name == "Tone 1"
        assert manifest.midi.program == 41
        assert manifest.audio.sample_rate == 48000
        assert manifest.audio.data_format == "int24"
        assert len(manifest.samples) == 4
        assert all(sample.status == "pending" for sample in manifest.samples)

    def test_mapping_and_captured_are_separated(self, plan):
        manifest = create_initial_manifest(plan, plan.tones[0])
        sample = manifest.samples[0]
        assert sample.mapping.root_note == 38
        assert sample.mapping.key_low == 36
        assert sample.mapping.key_high == 40
        assert sample.captured.note == 38
        assert sample.captured.velocity == 48
        assert sample.captured.note_on == 4.0
        assert sample.captured.release_capture == 3.0

    def test_hash_recorded_in_provenance(self, plan):
        manifest = create_initial_manifest(plan, plan.tones[0])
        assert (
            manifest.provenance.resolved_definition_sha256
            == plan.tones[0].resolved_definition_sha256
        )


class TestRepository:
    def test_write_read_roundtrip(self, plan, tmp_path):
        manifest = create_initial_manifest(plan, plan.tones[0])
        manifest_path = tmp_path / "manifest.yaml"
        repository.write(manifest_path, manifest)

        loaded = repository.read(manifest_path)
        assert loaded == manifest
        # No leftover temporary file after a successful write
        assert not manifest_path.with_name("manifest.yaml.tmp").exists()

    def test_update_replaces_atomically(self, plan, tmp_path):
        manifest = create_initial_manifest(plan, plan.tones[0])
        manifest_path = tmp_path / "manifest.yaml"
        repository.write(manifest_path, manifest)

        manifest.status = "in_progress"
        manifest.samples[0].status = "completed"
        repository.write(manifest_path, manifest)

        loaded = repository.read(manifest_path)
        assert loaded.status == "in_progress"
        assert loaded.samples[0].status == "completed"

    def test_failed_write_keeps_old_manifest(self, plan, tmp_path, monkeypatch):
        manifest = create_initial_manifest(plan, plan.tones[0])
        manifest_path = tmp_path / "manifest.yaml"
        repository.write(manifest_path, manifest)

        def broken_dump(*args, **kwargs):
            raise yaml.YAMLError("simulated failure")

        monkeypatch.setattr(yaml, "safe_dump", broken_dump)
        with pytest.raises(ManifestWriteError):
            repository.write(manifest_path, manifest)
        monkeypatch.undo()

        loaded = repository.read(manifest_path)
        assert loaded.status == "pending"

    def test_read_missing_file(self, tmp_path):
        with pytest.raises(ManifestReadError):
            repository.read(tmp_path / "does_not_exist.yaml")

    def test_read_invalid_yaml(self, tmp_path):
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("status: [unclosed", encoding="utf-8")
        with pytest.raises(ManifestReadError):
            repository.read(manifest_path)

    def test_read_schema_violation(self, tmp_path):
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("schema_version: 1\nkind: wrong_kind\n", encoding="utf-8")
        with pytest.raises(ManifestReadError):
            repository.read(manifest_path)

    def test_read_non_mapping(self, tmp_path):
        manifest_path = tmp_path / "manifest.yaml"
        manifest_path.write_text("- just\n- a list\n", encoding="utf-8")
        with pytest.raises(ManifestReadError):
            repository.read(manifest_path)
