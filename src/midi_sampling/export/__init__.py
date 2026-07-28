from midi_sampling.export.abstractions import InstrumentPatchWriter
from midi_sampling.export.exceptions import ExportDefinitionError

SUPPORTED_PATCH_FORMATS = ("sfz",)


def create_patch_writer(format_id: str) -> InstrumentPatchWriter:
    """
    Build the writer for one patch format. The explicit branch mirrors
    `postprocess.stages.create_stage`: adding a sampler format means
    adding a `<format>_impl` package and one branch here.
    """
    if format_id == "sfz":
        from midi_sampling.export.sfz_impl import SfzPatchWriter

        return SfzPatchWriter()
    raise ExportDefinitionError(
        f"unknown patch format: {format_id!r} "
        f"(supported: {', '.join(SUPPORTED_PATCH_FORMATS)})"
    )


__all__ = [
    "SUPPORTED_PATCH_FORMATS",
    "create_patch_writer",
]
