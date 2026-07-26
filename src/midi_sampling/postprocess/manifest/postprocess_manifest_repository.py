from midi_sampling.postprocess.exceptions import (
    PostprocessManifestReadError,
    PostprocessManifestWriteError,
)
from midi_sampling.postprocess.manifest.postprocess_manifest import PostprocessManifest
from midi_sampling.yaml_document_repository import YamlDocumentRepository


class PostprocessManifestRepository(YamlDocumentRepository[PostprocessManifest]):
    """
    Read and write per-tone derived manifests.

    Writes always go through a temporary file in the same directory and
    are finalized with an atomic replace, so an existing manifest is
    never left half-written.
    """

    document_type = PostprocessManifest
    read_error = PostprocessManifestReadError
    write_error = PostprocessManifestWriteError
    description = "postprocess manifest"
