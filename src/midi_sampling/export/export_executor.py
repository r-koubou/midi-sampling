from logging import getLogger
from pathlib import Path
from typing import Callable

from midi_sampling.export.abstractions import (
    InstrumentPatchWriter,
    PatchWriteContext,
)
from midi_sampling.export.audio import AudioExporter
from midi_sampling.export.exceptions import (
    ExportExistingOutputError,
    ExportWriteError,
)
from midi_sampling.export.planning import ExportPlan

logger = getLogger(__name__)


class ExportExecutor:
    """
    Write the audio files and the patch file into the output directory.

    Read-only with respect to the recorded and processed trees, and it
    never overwrites existing export output: a non-empty output
    directory is refused, matching the postprocess rule for derived
    output.
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

    def execute(self, plan: ExportPlan, output_directory: Path) -> Path:
        output_directory = Path(output_directory)
        if output_directory.exists() and any(output_directory.iterdir()):
            raise ExportExistingOutputError(
                f"{output_directory}: output directory is not empty; "
                f"existing export output is never overwritten"
            )

        try:
            output_directory.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ExportWriteError(
                f"{output_directory}: cannot create output directory: {e}"
            ) from e

        self._progress(
            f"Exporting {plan.instrument.name!r}: "
            f"{len(plan.audio_tasks)} sample(s) as {plan.audio_format}"
        )

        for task in plan.audio_tasks:
            logger.debug(f"Writing {task.relative_path}")
            self._audio_exporter.export(
                task.source_path,
                output_directory / task.relative_path,
                task.data_format,
            )

        outcome = self._writer.write(
            PatchWriteContext(
                instrument=plan.instrument,
                output_directory=output_directory,
            )
        )

        self._progress(f"Wrote patch: {outcome.patch_path}")
        return outcome.patch_path
