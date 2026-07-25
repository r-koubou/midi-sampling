from dataclasses import dataclass
from logging import getLogger
from typing import TYPE_CHECKING, Any

from midi_sampling.postprocess.definitions import (
    TRIM_SETTING_NAMES,
    TrimSettingsDefinition,
)
from midi_sampling.postprocess.exceptions import (
    PostprocessDependencyError,
    PostprocessStageError,
)
from midi_sampling.postprocess.manifest.postprocess_manifest import ManifestTrim
from midi_sampling.postprocess.stages.stage import StageContext, StageOutcome

if TYPE_CHECKING:
    from wav_silence_trimmer.models import TrimConfig

logger = getLogger(__name__)

KIND = "trim"

_INSTALL_HINT = (
    "the 'trim' stage requires the optional dependency 'wav-silence-trimmer'; "
    "install it with: pip install 'midi-sampling[postprocess]'"
)


def _import_trimmer() -> Any:
    """
    Import wav_silence_trimmer lazily so that midi-sampling stays usable
    without the optional DSP dependencies installed.
    """
    try:
        from wav_silence_trimmer import audio_io, config, detector, fade, models
    except ImportError as e:
        raise PostprocessDependencyError(f"{_INSTALL_HINT} ({e})") from e

    return audio_io, config, detector, fade, models


@dataclass(frozen=True)
class TrimStage:
    """
    Leading and trailing silence trimming via `wav-silence-trimmer`.

    The library's own `cli.process_file` is intentionally not used: it
    lives in the CLI layer and reports through `ProcessingResult`. The
    pure functions are composed here instead.
    """

    kind: str = KIND
    _config: "TrimConfig | None" = None

    @classmethod
    def create(cls, settings: TrimSettingsDefinition) -> "TrimStage":
        """
        Resolve the declared settings against the library defaults and
        validate them up front, before any sample is read.
        """
        _audio_io, config, _detector, _fade, models = _import_trimmer()

        overrides = {
            name: value
            for name, value in (
                (name, getattr(settings, name)) for name in TRIM_SETTING_NAMES
            )
            if value is not None
        }
        trim_config = models.TrimConfig(**overrides)

        try:
            config.validate_config(trim_config)
        except Exception as e:
            raise PostprocessStageError(f"invalid trim settings: {e}") from e

        return cls(_config=trim_config)

    def settings_payload(self) -> dict:
        assert self._config is not None
        return {
            name: _canonical(getattr(self._config, name))
            for name in TRIM_SETTING_NAMES
        }

    def apply(self, context: StageContext) -> StageOutcome:
        context.validate()
        assert self._config is not None

        audio_io, _config, detector, fade, _models = _import_trimmer()
        trim_config = self._config

        try:
            audio, metadata = audio_io.read_wav(context.input_path)
            detection = detector.detect_trim_region(
                audio, metadata.sample_rate, trim_config
            )

            start = detection.start_sample
            end = detection.end_sample_exclusive

            # Cut from the original audio, not from the DC-removed analysis copy.
            trimmed = audio[start:end].copy()

            head_trimmed = start > 0
            tail_trimmed = end < metadata.frames
            if trim_config.no_fade:
                fade_in_frames = 0
                fade_out_frames = 0
            else:
                trimmed, fade_in_frames, fade_out_frames = fade.apply_fades(
                    trimmed,
                    metadata.sample_rate,
                    trim_config.fade_in_ms,
                    trim_config.fade_out_ms,
                    apply_fade_in=head_trimmed,
                    apply_fade_out=tail_trimmed,
                )

            audio_io.write_wav(
                context.output_path,
                trimmed,
                metadata.sample_rate,
                metadata.subtype,
                format=metadata.format,
                overwrite=True,
            )
        except PostprocessStageError:
            raise
        except Exception as e:
            raise PostprocessStageError(
                f"trimming failed for {context.input_path.name}: {e}"
            ) from e

        logger.debug(
            f"Trimmed {context.input_path.name}: "
            f"{metadata.frames} -> {end - start} frames "
            f"(head={start}, tail={metadata.frames - end}, "
            f"noise_floor={detection.noise_floor_dbfs:.1f} dBFS)"
        )

        return StageOutcome(
            manifest_block=ManifestTrim(
                applied=True,
                start_sample=start,
                end_sample_exclusive=end,
                removed_head_frames=start,
                removed_tail_frames=metadata.frames - end,
                removed_head_seconds=start / metadata.sample_rate,
                removed_tail_seconds=(metadata.frames - end) / metadata.sample_rate,
                noise_floor_dbfs=detection.noise_floor_dbfs,
                fade_in_frames=fade_in_frames,
                fade_out_frames=fade_out_frames,
            ),
            output_written=True,
        )


def _canonical(value: Any) -> Any:
    """
    Normalize a setting for hashing: numbers become float so that `1` and
    `1.0` produce the same digest.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value
