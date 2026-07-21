import os
from logging import getLogger
from pathlib import Path

import yaml
from pydantic import ValidationError

from midi_sampling.sampling.exceptions import ManifestReadError, ManifestWriteError
from midi_sampling.sampling.manifest.sample_manifest import SampleManifest

logger = getLogger(__name__)

MANIFEST_TEMP_SUFFIX = ".tmp"


class SampleManifestRepository:
    """
    Read and write per-tone manifests.

    Writes always go through a temporary file in the same directory and
    are finalized with an atomic replace, so an existing manifest is
    never left half-written.
    """

    def read(self, manifest_path: Path) -> SampleManifest:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except OSError as e:
            raise ManifestReadError(f"{manifest_path}: cannot read manifest: {e}") from e
        except UnicodeDecodeError as e:
            raise ManifestReadError(
                f"{manifest_path}: manifest is not valid UTF-8: {e}"
            ) from e
        except yaml.YAMLError as e:
            raise ManifestReadError(
                f"{manifest_path}: manifest is not valid YAML: {e}"
            ) from e

        if not isinstance(data, dict):
            raise ManifestReadError(
                f"{manifest_path}: manifest must be a YAML mapping, "
                f"got {type(data).__name__}"
            )

        try:
            return SampleManifest.model_validate(data)
        except ValidationError as e:
            raise ManifestReadError(
                f"{manifest_path}: manifest schema validation failed:\n{e}"
            ) from e

    def write(self, manifest_path: Path, manifest: SampleManifest) -> None:
        temporary_path = manifest_path.with_name(
            manifest_path.name + MANIFEST_TEMP_SUFFIX
        )
        data = manifest.model_dump(mode="python", exclude_none=True)

        try:
            with open(temporary_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, manifest_path)
        except (OSError, yaml.YAMLError) as e:
            raise ManifestWriteError(
                f"{manifest_path}: cannot write manifest: {e}"
            ) from e

        logger.debug(f"Updated manifest: {manifest_path} (status={manifest.status})")
