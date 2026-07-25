import dataclasses
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Any

from midi_sampling.postprocess.definitions import (
    AUTO,
    FROM_MANIFEST,
    LoopFailureMode,
    LoopSettingsDefinition,
)
from midi_sampling.postprocess.exceptions import (
    PostprocessDependencyError,
    PostprocessStageError,
)
from midi_sampling.postprocess.manifest.postprocess_manifest import ManifestLoop
from midi_sampling.postprocess.stages.stage import StageContext, StageOutcome

if TYPE_CHECKING:
    from sample_loop_detector.config import DetectionSettings

logger = getLogger(__name__)

KIND = "loop"

_INSTALL_HINT = (
    "the 'loop' stage requires the optional dependency 'sample-loop-detector'; "
    "install it with: pip install 'midi-sampling[postprocess]'"
)

# DetectionSettings fields this stage forwards. `midi_unity_note` is handled
# separately because it is resolved per sample from the source manifest.
_FORWARDED_SETTING_NAMES = (
    "search_start",
    "search_end",
    "min_sustain",
    "min_loop",
    "max_loop",
    "fmin",
    "fmax",
    "crossfade_lengths_ms",
    "top_k",
    "quality_threshold",
    "replace_existing_loop",
)

_PLACEHOLDER_PATH = Path("placeholder.wav")


def _import_detector() -> Any:
    """
    Import sample_loop_detector lazily so that midi-sampling stays usable
    without the optional DSP dependencies installed.
    """
    try:
        from sample_loop_detector import config, pipeline
    except ImportError as e:
        raise PostprocessDependencyError(f"{_INSTALL_HINT} ({e})") from e

    return config, pipeline


@dataclass(frozen=True)
class LoopStage:
    """
    Sustain loop detection and `smpl` chunk embedding via
    `sample-loop-detector`.

    libsndfile cannot write `smpl` chunks, so the library's own
    `write_output_wav` (which splices the chunk into the original RIFF
    bytes) is the required write path.
    """

    kind: str = KIND
    on_failure: LoopFailureMode = "skip"
    unity_note_mode: str = FROM_MANIFEST
    fixed_unity_note: int | None = None
    _settings: "DetectionSettings | None" = None

    @classmethod
    def create(
        cls, settings: LoopSettingsDefinition, on_failure: LoopFailureMode
    ) -> "LoopStage":
        """
        Resolve the declared settings against the library defaults and
        validate them up front, before any sample is read.
        """
        config, _pipeline = _import_detector()

        overrides: dict[str, Any] = {}
        for name in _FORWARDED_SETTING_NAMES:
            value = getattr(settings, name)
            if value is None:
                continue
            if name == "crossfade_lengths_ms":
                value = tuple(float(item) for item in value)
            overrides[name] = value

        template = config.DetectionSettings(
            input_path=_PLACEHOLDER_PATH,
            output_path=_PLACEHOLDER_PATH,
            **overrides,
        )
        _validate(template)

        declared = settings.midi_unity_note
        if declared in (FROM_MANIFEST, AUTO):
            mode = str(declared)
            fixed = None
        else:
            mode = "fixed"
            fixed = int(declared)

        return cls(
            on_failure=on_failure,
            unity_note_mode=mode,
            fixed_unity_note=fixed,
            _settings=template,
        )

    def settings_payload(self) -> dict:
        assert self._settings is not None
        payload: dict[str, Any] = {
            name: _canonical(getattr(self._settings, name))
            for name in _FORWARDED_SETTING_NAMES
        }
        payload["on_failure"] = self.on_failure
        payload["midi_unity_note"] = (
            self.fixed_unity_note
            if self.unity_note_mode == "fixed"
            else self.unity_note_mode
        )
        return payload

    def apply(self, context: StageContext) -> StageOutcome:
        context.validate()
        assert self._settings is not None

        _config, pipeline = _import_detector()

        unity_note = self._resolve_unity_note(context)
        settings = dataclasses.replace(
            self._settings,
            input_path=context.input_path,
            output_path=context.output_path,
            midi_unity_note=unity_note,
            # Existing-output checks belong to the pre-flight validation of
            # this project, so the library must not refuse to write here.
            force=True,
        )

        try:
            output = pipeline.run_detection(settings)
        except Exception as e:
            raise PostprocessStageError(
                f"loop detection failed for {context.input_path.name}: {e}"
            ) from e

        for warning in output.warnings:
            logger.warning(f"{context.input_path.name}: {warning}")

        if not output.succeeded:
            return self._handle_failure(context, output)

        try:
            pipeline.write_output_wav(output, settings)
        except Exception as e:
            raise PostprocessStageError(
                f"writing the looped WAV failed for {context.input_path.name}: {e}"
            ) from e

        assert output.result is not None
        selected = output.result.selected
        resolved_unity = pipeline.resolve_midi_unity_note(settings, output.pitch)

        logger.debug(
            f"Loop found for {context.input_path.name}: "
            f"{selected.start_frame}-{selected.end_frame} "
            f"(crossfade={output.result.best_crossfade_ms} ms, "
            f"confidence={output.result.confidence:.2f} "
            f"{output.result.confidence_label})"
        )

        return StageOutcome(
            manifest_block=ManifestLoop(
                applied=True,
                status="success",
                start_frame=selected.start_frame,
                end_frame=selected.end_frame,
                crossfade_ms=output.result.best_crossfade_ms,
                midi_unity_note=resolved_unity.note,
                confidence=output.result.confidence,
                confidence_label=output.result.confidence_label,
                smpl_chunk_written=True,
            ),
            output_written=True,
        )

    def _resolve_unity_note(self, context: StageContext) -> int | None:
        """
        `from_manifest` is the reason this stage lives inside
        midi-sampling: the recorded note is known exactly, so pitch
        estimation cannot pick the wrong octave.
        """
        if self.unity_note_mode == FROM_MANIFEST:
            return context.root_note
        if self.unity_note_mode == AUTO:
            return None
        return self.fixed_unity_note

    def _handle_failure(self, context: StageContext, output: Any) -> StageOutcome:
        reason = output.failure_reason or output.status
        message = output.failure_message or ""

        if self.on_failure == "error":
            raise PostprocessStageError(
                f"no acceptable loop found for {context.input_path.name}: "
                f"{reason}: {message}"
            )

        logger.info(
            f"No loop for {context.input_path.name}: {reason} "
            f"(on_failure=skip, passing the sample through unchanged)"
        )
        return StageOutcome(
            manifest_block=ManifestLoop(
                applied=False,
                status="not_found",
                smpl_chunk_written=False,
                detail=reason,
            ),
            output_written=False,
        )


def _validate(settings: "DetectionSettings") -> None:
    """
    Duration-independent subset of the library's own validation, run
    before any file is touched so that a bad session definition fails
    during pre-flight instead of on the first sample.
    """
    if not 0.0 < settings.min_loop <= settings.max_loop:
        raise PostprocessStageError(
            "invalid loop settings: must satisfy 0 < min_loop <= max_loop"
        )
    if settings.min_sustain <= settings.min_loop:
        raise PostprocessStageError(
            "invalid loop settings: min_loop must be smaller than min_sustain"
        )
    if not 0.0 <= settings.quality_threshold <= 1.0:
        raise PostprocessStageError(
            "invalid loop settings: quality_threshold must be within [0, 1]"
        )
    if settings.top_k < 1:
        raise PostprocessStageError("invalid loop settings: top_k must be at least 1")
    if (
        settings.search_start is not None
        and settings.search_end is not None
        and settings.search_start >= settings.search_end
    ):
        raise PostprocessStageError(
            "invalid loop settings: search_start must be smaller than search_end"
        )


def _canonical(value: Any) -> Any:
    """
    Normalize a setting for hashing: numbers become float so that `1` and
    `1.0` produce the same digest.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value
