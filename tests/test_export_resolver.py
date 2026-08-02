from pathlib import Path

import pytest

from conftest import make_instrument_definition, make_processed_output
from midi_sampling.export.exceptions import (
    ExportDefinitionError,
    ExportSourceError,
)
from midi_sampling.export.resolving import ExportResolver
from midi_sampling.postprocess.manifest import PostprocessManifestRepository


@pytest.fixture
def processed(tmp_path: Path) -> Path:
    return make_processed_output(tmp_path)


@pytest.fixture
def instrument_file(tmp_path: Path, processed: Path) -> Path:
    return make_instrument_definition(tmp_path)


def rewrite_manifest(processed: Path, mutate) -> None:
    repository = PostprocessManifestRepository()
    manifest_path = processed / "tone-1" / "manifest.yaml"
    manifest = repository.read(manifest_path)
    mutate(manifest)
    repository.write(manifest_path, manifest)


class TestExportResolver:
    def test_resolves_completed_tone(self, instrument_file: Path):
        resolved = ExportResolver().resolve(instrument_file)

        assert [tone.tone_id for tone in resolved.tones] == ["tone-1"]
        assert len(resolved.tones[0].manifest.samples) == 4
        assert resolved.tones[0].directory.name == "tone-1"

    def test_definition_file_not_found(self, tmp_path: Path):
        with pytest.raises(ExportDefinitionError, match="not found"):
            ExportResolver().resolve(tmp_path / "missing.yaml")

    def test_invalid_definition_is_rejected(self, tmp_path: Path):
        path = make_instrument_definition(tmp_path, "kind: something\n")
        with pytest.raises(ExportDefinitionError):
            ExportResolver().resolve(path)

    def test_missing_manifest_is_rejected(self, tmp_path: Path):
        path = make_instrument_definition(tmp_path)
        with pytest.raises(ExportSourceError, match="manifest not found"):
            ExportResolver().resolve(path)

    def test_absolute_manifest_path_is_rejected(self, tmp_path: Path, processed: Path):
        absolute = (processed / "tone-1" / "manifest.yaml").as_posix()
        path = make_instrument_definition(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "sources:\n"
            f"  - {{ tone: tone-1, manifest: \"{absolute}\" }}\n",
        )
        with pytest.raises(ExportDefinitionError, match="absolute paths"):
            ExportResolver().resolve(path)

    def test_tone_id_mismatch_is_rejected(self, tmp_path: Path, processed: Path):
        path = make_instrument_definition(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "sources:\n"
            "  - { tone: other-tone, manifest: processed/tone-1/manifest.yaml }\n",
        )
        with pytest.raises(ExportSourceError, match="does not match"):
            ExportResolver().resolve(path)

    def test_incomplete_manifest_is_rejected(
        self, instrument_file: Path, processed: Path
    ):
        def mutate(manifest):
            manifest.status = "in_progress"

        rewrite_manifest(processed, mutate)
        with pytest.raises(ExportSourceError, match="'completed'"):
            ExportResolver().resolve(instrument_file)

    def test_missing_audio_file_is_rejected(
        self, instrument_file: Path, processed: Path
    ):
        manifest = PostprocessManifestRepository().read(
            processed / "tone-1" / "manifest.yaml"
        )
        (processed / "tone-1" / manifest.samples[0].file).unlink()

        with pytest.raises(ExportSourceError, match="missing"):
            ExportResolver().resolve(instrument_file)

    def test_sample_manifest_is_rejected_as_source(self, tmp_path: Path, processed: Path):
        """
        recorded/ manifests (kind: sample_manifest) are not accepted:
        the third layer references postprocess output only.
        """
        path = make_instrument_definition(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: recorded/tone-1/manifest.yaml }\n",
        )
        with pytest.raises(ExportSourceError, match="schema validation failed"):
            ExportResolver().resolve(path)


class TestExclusiveGroupValidation:
    def test_known_root_note_is_accepted(self, tmp_path: Path, processed: Path):
        path = make_instrument_definition(
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
        resolved = ExportResolver().resolve(path)
        assert resolved.definition.exclusive_groups[0].name == "pair"

    def test_unknown_root_note_is_rejected(self, tmp_path: Path, processed: Path):
        path = make_instrument_definition(
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
            "      - { tone: tone-1, root_note: 100 }\n",
        )
        with pytest.raises(ExportDefinitionError, match="root_note"):
            ExportResolver().resolve(path)


class TestFlacValidation:
    FLAC_INSTRUMENT_YAML = (
        "schema_version: 1\n"
        "kind: instrument_definition\n"
        "name: test-instrument\n"
        "audio:\n"
        "  format: flac\n"
        "sources:\n"
        "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n"
    )

    def test_int24_source_needs_no_bit_depth(self, tmp_path: Path, processed: Path):
        path = make_instrument_definition(tmp_path, self.FLAC_INSTRUMENT_YAML)
        resolved = ExportResolver().resolve(path)
        assert resolved.definition.audio.format == "flac"

    def test_float32_source_requires_bit_depth(self, tmp_path: Path, processed: Path):
        def mutate(manifest):
            manifest.audio.data_format = "float32"

        rewrite_manifest(processed, mutate)
        path = make_instrument_definition(tmp_path, self.FLAC_INSTRUMENT_YAML)

        with pytest.raises(ExportDefinitionError, match="bit_depth"):
            ExportResolver().resolve(path)

    def test_float32_source_with_bit_depth_is_accepted(
        self, tmp_path: Path, processed: Path
    ):
        def mutate(manifest):
            manifest.audio.data_format = "float32"

        rewrite_manifest(processed, mutate)
        path = make_instrument_definition(
            tmp_path,
            self.FLAC_INSTRUMENT_YAML.replace(
                "  format: flac\n", "  format: flac\n  bit_depth: 24\n"
            ),
        )
        resolved = ExportResolver().resolve(path)
        assert resolved.definition.audio.bit_depth == 24


class TestPatchSubdirectory:
    def instrument_with(self, tmp_path: Path, subdirectory: str) -> Path:
        # Single-quoted YAML: backslashes stay literal, so a Windows-style
        # separator reaches the validator instead of tripping the parser.
        return make_instrument_definition(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "output:\n"
            f"  subdirectory: '{subdirectory}'\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n",
        )

    def test_absent_output_resolves_to_no_subdirectory(
        self, instrument_file: Path
    ):
        resolved = ExportResolver().resolve(instrument_file)

        assert resolved.patch_subdirectory == ()

    def test_subdirectory_is_split_into_components(
        self, tmp_path: Path, processed: Path
    ):
        path = self.instrument_with(tmp_path, "8850/Piano")
        resolved = ExportResolver().resolve(path)

        assert resolved.patch_subdirectory == ("8850", "Piano")

    def test_single_component_is_accepted(self, tmp_path: Path, processed: Path):
        path = self.instrument_with(tmp_path, "8850")
        resolved = ExportResolver().resolve(path)

        assert resolved.patch_subdirectory == ("8850",)

    def test_unquoted_number_is_rejected_as_not_a_string(
        self, tmp_path: Path, processed: Path
    ):
        """
        `subdirectory: 8850` is a YAML integer, and every string field of
        this project is StrictStr. An all-digit component must be quoted.
        """
        path = make_instrument_definition(
            tmp_path,
            "schema_version: 1\n"
            "kind: instrument_definition\n"
            "name: test-instrument\n"
            "output:\n"
            "  subdirectory: 8850\n"
            "sources:\n"
            "  - { tone: tone-1, manifest: processed/tone-1/manifest.yaml }\n",
        )
        with pytest.raises(ExportDefinitionError, match="valid string"):
            ExportResolver().resolve(path)

    @pytest.mark.parametrize(
        "subdirectory, message",
        [
            ("../escape", "period"),
            ("8850/../escape", "period"),
            (".", "period"),
            ("/8850", "absolute paths"),
            ("C:/8850", "absolute paths"),
            ("8850\\Piano", "invalid character"),
            ("~/8850", "'~' expansion"),
            ("8850/*", "glob patterns"),
            ("https://example.com/x", "URL"),
            ("", "must not be empty"),
            ("8850/", "must not be empty"),
            ("8850//Piano", "must not be empty"),
            ("CON", "reserved device name"),
            ("8850/nul", "reserved device name"),
            ("8850 /Piano", "space or a period"),
        ],
    )
    def test_unsafe_subdirectory_is_rejected(
        self, tmp_path: Path, processed: Path, subdirectory: str, message: str
    ):
        path = self.instrument_with(tmp_path, subdirectory)
        with pytest.raises(ExportDefinitionError, match=message):
            ExportResolver().resolve(path)
