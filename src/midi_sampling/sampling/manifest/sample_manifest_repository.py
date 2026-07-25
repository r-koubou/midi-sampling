from midi_sampling.sampling.exceptions import ManifestReadError, ManifestWriteError
from midi_sampling.sampling.manifest.sample_manifest import SampleManifest
from midi_sampling.yaml_document_repository import TEMP_SUFFIX, YamlDocumentRepository

MANIFEST_TEMP_SUFFIX = TEMP_SUFFIX


class SampleManifestRepository(YamlDocumentRepository[SampleManifest]):
    """
    Read and write per-tone sampling manifests.

    Writes always go through a temporary file in the same directory and
    are finalized with an atomic replace, so an existing manifest is
    never left half-written.
    """

    document_type = SampleManifest
    read_error = ManifestReadError
    write_error = ManifestWriteError
    description = "manifest"
