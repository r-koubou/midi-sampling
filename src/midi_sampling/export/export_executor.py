from logging import getLogger
from pathlib import Path
from typing import Callable

from midi_sampling.export.abstractions import (
    InstrumentPatchWriter,
    PatchWriteContext,
)
from midi_sampling.export.audio import AudioExporter
from midi_sampling.export.exceptions import ExportWriteError
from midi_sampling.export.planning import (
    INSTRUMENTS_DIRECTORY_NAME,
    ExportPlan,
)
from midi_sampling.sampling.exceptions import InvalidOutputPathError
from midi_sampling.sampling.validation import OutputPathValidator

logger = getLogger(__name__)


class ExportExecutor:
    """
    Write the audio files and the patch file into the output root, which
    holds `Samples/<tone-id>/` and `Instruments/` for one patch format.
    The patch goes into `Instruments/` plus the plan's optional
    subdirectory.

    Read-only with respect to the recorded and processed trees. Unlike
    sampling and postprocess, an existing output root is accepted and
    its files are overwritten: several instruments share one root by
    design, so exporting is repeatable and additive.
    """

    def __init__(
        self,
        writer: InstrumentPatchWriter,
        audio_exporter: AudioExporter,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self._writer = writer
        self._audio_exporter = audio_exporter
        self._progress = progress if progress is not None else (lambda message: None)
        self._path_validator = OutputPathValidator()

    def execute(self, plan: ExportPlan, output_root: Path) -> Path:
        output_root = Path(output_root)
        patch_directory = output_root.joinpath(
            INSTRUMENTS_DIRECTORY_NAME, *plan.patch_subdirectory
        )

        # A patch subdirectory can push the path past the Windows limit,
        # so check before writing any sample.
        try:
            self._path_validator.validate_full_path(
                patch_directory, "patch directory"
            )
        except InvalidOutputPathError as e:
            raise ExportWriteError(str(e)) from e

        for directory in (output_root, patch_directory):
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise ExportWriteError(
                    f"{directory}: cannot create output directory: {e}"
                ) from e

        self._progress(
            f"Exporting {plan.instrument.name!r}: "
            f"{len(plan.audio_tasks)} sample(s) as {plan.audio_format}"
        )

        self._warn_on_occupied_sample_directories(plan, output_root)

        for task in plan.audio_tasks:
            logger.debug(f"Writing {task.relative_path}")
            self._audio_exporter.export(
                task.source_path,
                output_root / task.relative_path,
                task.data_format,
            )

        outcome = self._writer.write(
            PatchWriteContext(
                instrument=plan.instrument,
                patch_directory=patch_directory,
            )
        )

        self._progress(f"Wrote patch: {outcome.patch_path}")
        return outcome.patch_path

    def _warn_on_occupied_sample_directories(
        self, plan: ExportPlan, output_root: Path
    ) -> None:
        """
        Warn once per `Samples/<tone-id>/` that already holds files.

        Tone ids are the sample namespace of the whole output root, so an
        occupied directory means this export or another instrument
        already wrote that tone; its files are about to be replaced.
        Warning per directory rather than per file keeps a routine
        re-export from drowning in one line per sample.
        """
        seen: set[Path] = set()
        for task in plan.audio_tasks:
            directory = (output_root / task.relative_path).parent
            if directory in seen:
                continue
            seen.add(directory)
            if directory.exists() and any(directory.iterdir()):
                logger.warning(
                    f"{directory}: overwriting existing sample files"
                )
