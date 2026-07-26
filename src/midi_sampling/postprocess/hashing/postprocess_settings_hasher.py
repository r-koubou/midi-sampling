import hashlib
from collections.abc import Sequence
from pathlib import Path

from midi_sampling.postprocess.exceptions import PostprocessSourceError
from midi_sampling.postprocess.stages import PostprocessStage
from midi_sampling.sampling.hashing import ResolvedDefinitionHasher

_READ_CHUNK_SIZE = 1024 * 1024


class PostprocessSettingsHasher:
    """
    SHA-256 over the canonical JSON form of the effective postprocess
    settings, plus the SHA-256 of the source manifest bytes.

    Together with the tone's `resolved_definition_sha256` these let a
    future audit tell apart "the recording changed", "the tone definition
    changed" and "the postprocess settings changed".
    """

    def __init__(self, hasher: ResolvedDefinitionHasher | None = None) -> None:
        self._hasher = hasher if hasher is not None else ResolvedDefinitionHasher()

    def hash_settings(self, stages: Sequence[PostprocessStage]) -> str:
        """
        Hash the ordered list of stages with their effective settings.

        Deliberately excluded: source and output directory paths, the
        selected tone list, timestamps, execution state and the
        application version.
        """
        return self._hasher.hash_payload(self.build_payload(stages))

    def build_payload(self, stages: Sequence[PostprocessStage]) -> dict:
        return {
            "stages": [
                {
                    "kind": stage.kind,
                    "settings": stage.settings_payload(),
                }
                for stage in stages
            ]
        }

    def hash_source_manifest(self, manifest_path: Path) -> str:
        """
        Hash the raw bytes of a source manifest. Byte level identity is
        enough here and avoids depending on the source schema.
        """
        digest = hashlib.sha256()
        try:
            with open(manifest_path, "rb") as f:
                while chunk := f.read(_READ_CHUNK_SIZE):
                    digest.update(chunk)
        except OSError as e:
            raise PostprocessSourceError(
                f"{manifest_path}: cannot read source manifest: {e}"
            ) from e
        return digest.hexdigest()
