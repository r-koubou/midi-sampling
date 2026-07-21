import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from logging import getLogger

from midi_sampling.devices.audio.abstractions import AudioDevice
from midi_sampling.devices.midi.abstractions import MidiDevice
from midi_sampling.sampling.exceptions import (
    ExistingOutputError,
    ManifestReadError,
    SamplingError,
    SamplingExecutionError,
)
from midi_sampling.sampling.manifest import (
    ManifestError,
    SampleManifest,
    SampleManifestRepository,
    create_initial_manifest,
)
from midi_sampling.sampling.planning import (
    PARTIAL_SUFFIX,
    SamplingPlan,
    SamplingTarget,
    TonePlan,
)
from midi_sampling.sampling.validation import OutputPathValidator

logger = getLogger(__name__)


@dataclass
class _ExecutionState:
    """
    Tracks what is currently being recorded so that an abort can mark
    the right manifest entries as failed.
    """
    tone: TonePlan | None = None
    target: SamplingTarget | None = None


class SamplingExecutor:
    """
    Execute a validated SamplingPlan against real (or fake) devices.

    This class never reads YAML files and never resolves external
    references; it only consumes the fully resolved plan.
    """

    def __init__(
        self,
        audio_device: AudioDevice,
        midi_device: MidiDevice,
        manifest_repository: SampleManifestRepository | None = None,
        output_path_validator: OutputPathValidator | None = None,
        sleep: Callable[[float], None] = time.sleep,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self._audio_device = audio_device
        self._midi_device = midi_device
        self._manifest_repository = (
            manifest_repository
            if manifest_repository is not None
            else SampleManifestRepository()
        )
        self._path_validator = (
            output_path_validator
            if output_path_validator is not None
            else OutputPathValidator()
        )
        self._sleep = sleep
        self._progress = progress if progress is not None else (lambda message: None)

    def execute(self, plan: SamplingPlan) -> None:
        """
        Run the whole session. Stops the entire session on the first
        error; already completed WAV files are never deleted.
        """
        self._ensure_no_existing_outputs(plan)
        self._path_validator.validate_output_root_creatable(plan.output_root)

        plan.output_root.mkdir(parents=True, exist_ok=True)

        manifests: dict[str, SampleManifest] = {}
        for tone in plan.tones:
            tone.directory.mkdir(parents=True, exist_ok=False)
            manifest = create_initial_manifest(plan, tone)
            self._manifest_repository.write(tone.manifest_path, manifest)
            manifests[tone.definition_id] = manifest

        state = _ExecutionState()

        try:
            logger.info("Initializing devices")
            self._audio_device.initialize()
            self._midi_device.initialize()

            for initialization_file in plan.initialization_files:
                logger.info(f"Sending initialization SMF: {initialization_file}")
                self._progress(
                    f"Sending initialization file: {initialization_file.name}"
                )
                self._midi_device.send_message_from_file(str(initialization_file))

            for tone in plan.tones:
                state.tone = tone
                state.target = None
                self._execute_tone(plan, tone, manifests[tone.definition_id], state)
                state.tone = None
        except SamplingError:
            self._abort(manifests, state, None)
            raise
        except Exception as e:
            self._abort(manifests, state, e)
            raise SamplingExecutionError(f"sampling failed: {e}") from e
        finally:
            self._dispose_devices()

    def _execute_tone(
        self,
        plan: SamplingPlan,
        tone: TonePlan,
        manifest: SampleManifest,
        state: _ExecutionState,
    ) -> None:
        total = len(tone.targets)
        logger.info(
            f"Sampling tone {tone.definition_id!r}: {total} samples "
            f"(bank_msb={tone.bank_msb}, bank_lsb={tone.bank_lsb}, "
            f"program={tone.program})"
        )
        self._progress(f"[{tone.definition_id}] {total} samples")

        manifest.status = "in_progress"
        self._manifest_repository.write(tone.manifest_path, manifest)

        logger.info(
            f"Program change: channel={plan.channel}, msb={tone.bank_msb}, "
            f"lsb={tone.bank_lsb}, program={tone.program}"
        )
        self._midi_device.send_program_change(
            plan.channel, tone.bank_msb, tone.bank_lsb, tone.program
        )
        self._sleep(plan.program_change_settle)

        for position, target in enumerate(tone.targets, start=1):
            state.target = target
            self._record_target(plan, tone, manifest, target, position, total)
            state.target = None

        manifest.status = "completed"
        self._manifest_repository.write(tone.manifest_path, manifest)
        logger.info(f"Completed tone {tone.definition_id!r}")

    def _record_target(
        self,
        plan: SamplingPlan,
        tone: TonePlan,
        manifest: SampleManifest,
        target: SamplingTarget,
        position: int,
        total: int,
    ) -> None:
        total_seconds = plan.total_recording_seconds(target)
        logger.info(
            f"Recording {target.file_name} "
            f"(root={target.root_note}, velocity={target.send_velocity}, "
            f"duration={total_seconds}s)"
        )
        self._progress(
            f"[{tone.definition_id}] ({position}/{total}) "
            f"root={target.root_note} velocity={target.send_velocity} "
            f"-> {target.file_name}"
        )

        partial_path = target.output_path.with_name(
            target.file_name + PARTIAL_SUFFIX
        )

        logger.debug(f"Recording start: {total_seconds}s -> {partial_path}")
        self._audio_device.start_recording(total_seconds)
        self._sleep(plan.pre_roll)
        self._midi_device.play_note(
            plan.channel, target.root_note, target.send_velocity, target.note_on
        )
        self._sleep(target.release_capture)
        self._audio_device.stop_recording()
        logger.debug("Recording stop")

        self._audio_device.export_audio(str(partial_path))
        os.replace(partial_path, target.output_path)
        logger.info(f"Completed WAV: {target.output_path}")

        self._set_sample_status(manifest, target.sample_index, "completed")
        self._manifest_repository.write(tone.manifest_path, manifest)

        self._sleep(plan.inter_sample_wait)

    def _set_sample_status(
        self, manifest: SampleManifest, sample_index: int, status: str
    ) -> None:
        for sample in manifest.samples:
            if sample.index == sample_index:
                sample.status = status
                return

    def _abort(
        self,
        manifests: dict[str, SampleManifest],
        state: _ExecutionState,
        error: Exception | None,
    ) -> None:
        """
        Best-effort cleanup after an error: silence the MIDI device, stop
        the recording and mark the current tone manifest as failed.
        Completed WAV files are intentionally left untouched.
        """
        logger.error(f"Sampling aborted: {error}")

        try:
            self._midi_device.stop()
        except Exception:
            logger.exception("MIDI panic/reset failed")

        try:
            self._audio_device.stop_recording()
        except Exception:
            logger.exception("Stopping recording failed")

        if state.tone is None:
            return

        manifest = manifests.get(state.tone.definition_id)
        if manifest is None:
            return

        if state.target is not None:
            self._set_sample_status(manifest, state.target.sample_index, "failed")

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

    def _dispose_devices(self) -> None:
        try:
            self._midi_device.dispose()
        except Exception:
            logger.exception("Disposing MIDI device failed")
        try:
            self._audio_device.dispose()
        except Exception:
            logger.exception("Disposing audio device failed")

    def _ensure_no_existing_outputs(self, plan: SamplingPlan) -> None:
        """
        Refuse to run when any tone output already exists. When a
        readable manifest is present, include the stored and current
        definition hashes in the error message.
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
                message += self._describe_existing_manifest(tone)
            problems.append(message)

        if problems:
            raise ExistingOutputError("\n".join(problems))

    def _describe_existing_manifest(self, tone: TonePlan) -> str:
        try:
            existing = self._manifest_repository.read(tone.manifest_path)
        except ManifestReadError:
            return "\n  existing manifest is present but unreadable"

        existing_hash = existing.provenance.resolved_definition_sha256
        current_hash = tone.resolved_definition_sha256
        relation = "identical" if existing_hash == current_hash else "different"
        return (
            f"\n  existing hash: {existing_hash}"
            f"\n  current hash:  {current_hash}"
            f"\n  definitions are {relation}"
        )
