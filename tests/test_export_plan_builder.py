from pathlib import Path

import pytest

from conftest import (
    DEFAULT_SESSION_YAML,
    DEFAULT_TONE_YAML,
    make_instrument_definition,
    make_processed_output,
)
from midi_sampling.export.exceptions import ExportDefinitionError
from midi_sampling.export.planning import ExportPlanBuilder
from midi_sampling.export.resolving import ExportResolver
from midi_sampling.postprocess.manifest import (
    ManifestLoop,
    PostprocessManifestRepository,
)

TWO_TONE_SESSION_YAML = DEFAULT_SESSION_YAML + "  - file: tones/tone2.yaml\n"

TONE2_YAML = DEFAULT_TONE_YAML.replace("id: tone-1", "id: tone-2").replace(
    "name: Tone 1", "name: Tone 2"
)


@pytest.fixture
def processed(tmp_path: Path) -> Path:
    return make_processed_output(tmp_path)


def build(tmp_path: Path, instrument_yaml: str):
    path = make_instrument_definition(tmp_path, instrument_yaml)
    resolved = ExportResolver().resolve(path)
    return ExportPlanBuilder().build(resolved)


class TestExportPlanBuilder:
    def test_one_region_and_task_per_sample(self, tmp_path: Path, processed: Path):
        plan = build(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n",
        )

        assert len(plan.instrument.regions) == 4
        assert len(plan.audio_tasks) == 4
        assert plan.audio_format == "wav"
        assert plan.instrument.envelope.attack == 0.0
        assert plan.instrument.envelope.release == 0.3

        region = plan.instrument.regions[0]
        assert region.sample_path.startswith("Samples/tone-1/")
        assert region.sample_path.endswith(".wav")
        assert region.trigger == "attack"
        assert region.exclusive_group is None
        assert region.source_path.is_file()

        # Mapping comes from the manifest, never from file names.
        mappings = {
            (r.key_low, r.root_note, r.key_high, r.velocity_low, r.velocity_high)
            for r in plan.instrument.regions
        }
        assert mappings == {
            (36, 38, 40, 1, 63),
            (36, 38, 40, 64, 127),
            (41, 43, 45, 1, 63),
            (41, 43, 45, 64, 127),
        }

    def test_flac_format_changes_sample_extension(
        self, tmp_path: Path, processed: Path
    ):
        plan = build(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "audio: { format: flac }\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n",
        )

        assert all(
            region.sample_path.endswith(".flac")
            for region in plan.instrument.regions
        )
        # Sources stay WAV; only the exported copy changes format.
        assert all(
            task.source_path.suffix == ".wav" for task in plan.audio_tasks
        )

    def test_loop_from_manifest_is_carried_into_region(
        self, tmp_path: Path, processed: Path
    ):
        repository = PostprocessManifestRepository()
        manifest_path = processed / "tone-1" / "manifest.yaml"
        manifest = repository.read(manifest_path)
        manifest.samples[0].loop = ManifestLoop(
            applied=True,
            status="success",
            start_frame=1000,
            end_frame=2000,
            smpl_chunk_written=True,
        )
        repository.write(manifest_path, manifest)

        plan = build(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n",
        )

        loops = [region.loop for region in plan.instrument.regions]
        assert loops[0] is not None
        assert (loops[0].start_frame, loops[0].end_frame) == (1000, 2000)
        assert loops[1:] == [None, None, None]


class TestExclusiveGroupAssignment:
    def test_root_note_member_selects_matching_regions_only(
        self, tmp_path: Path, processed: Path
    ):
        plan = build(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n"
            "exclusive_groups:\n"
            "  - name: pair\n"
            "    members:\n"
            "      - { tone: tone-1, root_note: 38 }\n"
            "      - { tone: tone-1, root_note: 43 }\n",
        )

        assert plan.instrument.exclusive_groups[0].number == 1
        assert plan.instrument.exclusive_groups[0].name == "pair"
        assert all(
            region.exclusive_group == 1 for region in plan.instrument.regions
        )

    def test_region_in_two_groups_is_rejected(self, tmp_path: Path, processed: Path):
        with pytest.raises(ExportDefinitionError, match="more than one"):
            build(
                tmp_path,
                "schema_version: 1\n"
                "kind: instrument_definition\n"
                "name: test-instrument\n"
                "sources:\n"
                "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n"
                "exclusive_groups:\n"
                "  - name: first\n"
                "    members:\n"
                "      - { tone: tone-1, root_note: 38 }\n"
                "      - { tone: tone-1, root_note: 43 }\n"
                "  - name: second\n"
                "    members:\n"
                "      - { tone: tone-1 }\n"
                "      - { tone: tone-1, root_note: 43 }\n",
            )


class TestReleaseTriggerAssignment:
    def test_plays_tone_becomes_release_regions(self, tmp_path: Path):
        make_processed_output(
            tmp_path,
            session_yaml=TWO_TONE_SESSION_YAML,
            extra_files={"tones/tone2.yaml": TONE2_YAML},
        )
        plan = build(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n"
            "  - { tone: tone-2, manifest: processed/tone-2/manifest.yaml }\n"
            "release_triggers:\n"
            "  - trigger_of: { tone: tone-1 }\n"
            "    plays: { tone: tone-2 }\n"
            "    rt_decay: 6.0\n",
        )

        by_tone = {}
        for region in plan.instrument.regions:
            by_tone.setdefault(region.tone_id, []).append(region)

        assert all(r.trigger == "attack" for r in by_tone["tone-1"])
        assert all(r.rt_decay is None for r in by_tone["tone-1"])
        assert all(r.trigger == "release" for r in by_tone["tone-2"])
        assert all(r.rt_decay == 6.0 for r in by_tone["tone-2"])
