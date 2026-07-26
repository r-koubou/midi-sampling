import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

from midi_sampling.postprocess.exceptions import (
    PostprocessError,
    PostprocessExecutionError,
    PostprocessExistingOutputError,
)
from midi_sampling.postprocess.manifest import (
    ManifestLoop,
    ManifestSampleAudio,
    ManifestTrim,
    PostprocessManifest,
    PostprocessManifestRepository,
    create_initial_manifest,
)
from midi_sampling.postprocess.planning import (
    PostprocessPlan,
    PostprocessTarget,
    TonePostprocessPlan,
)
from midi_sampling.postprocess.stages import StageContext
from midi_sampling.sampling.manifest import ManifestError
from midi_sampling.sampling.validation import OutputPathValidator

logger = getLogger(__name__)


@dataclass
class _ExecutionState:
    """
    Tracks what is currently being processed so that an abort can mark
    the right manifest entries as failed.
    """
    tone: TonePostprocessPlan | None = None
    target: PostprocessTarget | None = None


class PostprocessExecutor:
    """
    Execute a validated PostprocessPlan.

    This class never reads YAML definitions and never resolves external
    references; it only consumes the fully resolved plan. It never writes
    anything below the source directory.
    """

    def __init__(
        self,
        manifest_repository: PostprocessManifestRepository | None = None,
        output_path_validator: OutputPathValidator | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self._manifest_repository = (
            manifest_repository
            if manifest_repository is not None
            else PostprocessManifestRepository()
        )
        self._path_validator = (
            output_path_validator
            if output_path_validator is not None
            else OutputPathValidator()
        )
        self._progress = progress if progress is not None else (lambda message: None)

    def execute(self, plan: PostprocessPlan) -> None:
        """
        Run the whole session. Stops on the first error; already
        completed WAV files are never deleted.
        """
        self._ensure_no_existing_outputs(plan)
        self._path_validator.validate_output_root_creatable(plan.output_root)

        plan.output_root.mkdir(parents=True, exist_ok=True)

        manifests: dict[str, PostprocessManifest] = {}
        for tone in plan.tones:
            tone.directory.mkdir(parents=True, exist_ok=False)
            manifest = create_initial_manifest(plan, tone)
            self._manifest_repository.write(tone.manifest_path, manifest)
            manifests[tone.definition_id] = manifest

        state = _ExecutionState()

        try:
            for tone in plan.tones:
                state.tone = tone
                state.target = None
                self._process_tone(plan, tone, manifests[tone.definition_id], state)
                state.tone = None
        except PostprocessError as e:
            self._abort(manifests, state, e)
            raise
        except Exception as e:
            self._abort(manifests, state, e)
            raise PostprocessExecutionError(f"postprocessing failed: {e}") from e

    def _process_tone(
        self,
        plan: PostprocessPlan,
        tone: TonePostprocessPlan,
        manifest: PostprocessManifest,
        state: _ExecutionState,
    ) -> None:
        total = len(tone.targets)
        logger.info(
            f"Postprocessing tone {tone.definition_id!r}: {total} sample(s), "
            f"stages: {', '.join(plan.stage_kinds)}"
        )
        self._progress(f"[{tone.definition_id}] {total} samples")

        manifest.status = "in_progress"
        self._manifest_repository.write(tone.manifest_path, manifest)

        tone.work_directory.mkdir(parents=True, exist_ok=True)

        for position, target in enumerate(tone.targets, start=1):
            state.target = target
            self._process_target(plan, tone, manifest, target, position, total)
            state.target = None

        self._remove_work_directory(tone)

        manifest.status = "completed"
        self._manifest_repository.write(tone.manifest_path, manifest)
        logger.info(f"Completed tone {tone.definition_id!r}")

    def _process_target(
        self,
        plan: PostprocessPlan,
        tone: TonePostprocessPlan,
        manifest: PostprocessManifest,
        target: PostprocessTarget,
        position: int,
        total: int,
    ) -> None:
        logger.info(f"Processing {target.file_name} ({position}/{total})")
        self._progress(
            f"[{tone.definition_id}] ({position}/{total}) {target.file_name}"
        )

        current_input = target.source_path
        blocks: dict[str, object] = {}

        for stage_position, stage in enumerate(plan.stages, start=1):
            work_path = target.work_path(stage_position, stage.kind)
            context = StageContext(
                input_path=current_input,
                output_path=work_path,
                root_note=target.mapping.root_note,
                sample_rate=tone.audio.sample_rate,
                channels=tone.audio.channels,
            )
            outcome = stage.apply(context)
            blocks[stage.kind] = outcome.manifest_block
            if outcome.output_written:
                current_input = work_path

        if current_input == target.source_path:
            # No stage produced a file (for example loop detection that
            # found nothing while running with on_failure: skip). Copy so
            # that the source is never moved out of the recording output.
            shutil.copyfile(current_input, target.output_path)
        else:
            os.replace(current_input, target.output_path)

        logger.debug(f"Completed WAV: {target.output_path}")

        self._update_sample(manifest, target, blocks)
        self._manifest_repository.write(tone.manifest_path, manifest)

    def _update_sample(
        self,
        manifest: PostprocessManifest,
        target: PostprocessTarget,
        blocks: dict[str, object],
    ) -> None:
        for sample in manifest.samples:
            if sample.index != target.sample_index:
                continue

            trim = blocks.get("trim")
            if isinstance(trim, ManifestTrim):
                sample.trim = trim

            loop = blocks.get("loop")
            if isinstance(loop, ManifestLoop):
                sample.loop = loop

            sample.audio = self._measure(target.output_path)
            sample.status = "completed"
            return

    def _measure(self, path: Path) -> ManifestSampleAudio | None:
        """
        Read back the frame count of the finished WAV. Best effort: a
        missing soundfile must not fail an otherwise successful run.
        """
        try:
            import soundfile as sf

            info = sf.info(str(path))
        except Exception:
            logger.debug(f"Could not measure {path}", exc_info=True)
            return None

        return ManifestSampleAudio(
            frame_count=int(info.frames),
            duration_seconds=float(info.duration),
        )

    def _remove_work_directory(self, tone: TonePostprocessPlan) -> None:
        """
        Best effort cleanup. Intermediates are deliberately left behind
        when something failed, so that a stage result can be auditioned.
        """
        try:
            shutil.rmtree(tone.work_directory)
        except OSError:
            logger.debug(
                f"Could not remove work directory: {tone.work_directory}",
                exc_info=True,
            )

    def _abort(
        self,
        manifests: dict[str, PostprocessManifest],
        state: _ExecutionState,
        error: Exception | None,
    ) -> None:
        """
        Mark the current tone manifest as failed. Completed WAV files and
        the whole source directory are left untouched.
        """
        logger.error(f"Postprocessing aborted: {error}")

        if state.tone is None:
            return

        manifest = manifests.get(state.tone.definition_id)
        if manifest is None:
            return

        if state.target is not None:
            for sample in manifest.samples:
                if sample.index == state.target.sample_index:
                    sample.status = "failed"
                    break

        manifest.status = "failed"
        if error is not None:
            manifest.error = ManifestError(
                type=type(error).__name__,
                message=str(error),
            )
        try:
            self._manifest_repository.write(state.tone.manifest_path, manifest)
        except Exception:
            logger.exception("Writing failed-state manifest failed")

    def _ensure_no_existing_outputs(self, plan: PostprocessPlan) -> None:
        """
        Refuse to run when any tone output already exists. When a
        readable derived manifest is present, include the stored and
        current hashes in the error message.
        """
        problems: list[str] = []

        for tone in plan.tones:
            if not tone.directory.exists():
                continue

            message = (
                f"output directory already exists: {tone.directory}\n"
                f"  (automatic overwrite / resume is not supported; "
                f"move or delete it manually)"
            )
            if tone.manifest_path.is_file():
                message += self._describe_existing_manifest(plan, tone)
            problems.append(message)

        if problems:
            raise PostprocessExistingOutputError("\n".join(problems))

    def _describe_existing_manifest(
        self, plan: PostprocessPlan, tone: TonePostprocessPlan
    ) -> str:
        try:
            existing = self._manifest_repository.read(tone.manifest_path)
        except PostprocessError:
            return "\n  existing manifest is present but unreadable"

        lines = []
        for label, stored, current in (
            (
                "source manifest",
                existing.provenance.source_manifest_sha256,
                tone.source_manifest_sha256,
            ),
            (
                "definition",
                existing.provenance.resolved_definition_sha256,
                tone.resolved_definition_sha256,
            ),
            (
                "settings",
                existing.provenance.postprocess_settings_sha256,
                plan.settings_sha256,
            ),
        ):
            relation = "identical" if stored == current else "different"
            lines.append(
                f"\n  {label} hash: {stored} vs {current} ({relation})"
            )
        return "".join(lines)
