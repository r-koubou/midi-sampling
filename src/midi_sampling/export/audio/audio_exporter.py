import shutil
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

from midi_sampling.export.definitions import AudioFormat
from midi_sampling.export.exceptions import ExportAudioError, ExportDefinitionError

logger = getLogger(__name__)

WAV_SUFFIX = ".wav"
FLAC_SUFFIX = ".flac"

_FLAC_SUBTYPES = {16: "PCM_16", 24: "PCM_24"}
_PASSTHROUGH_DEPTHS = {"int16": 16, "int24": 24}
_INTEGER_FORMATS = ("int16", "int24", "int32")
_FLOAT_FORMATS = ("float32", "float64")

_INSTALL_HINT = (
    "FLAC export requires the 'soundfile' package; "
    "install it with: pip install soundfile"
)


def resolve_flac_bit_depth(data_format: str, declared: int | None) -> int:
    """
    Decide the FLAC bit depth for one source format.

    libsndfile writes 16 and 24 bit FLAC only. int16/int24 sources pass
    through losslessly by default; everything else loses precision, so
    the definition must opt in with an explicit `audio.bit_depth`.
    """
    if data_format not in _INTEGER_FORMATS and data_format not in _FLOAT_FORMATS:
        raise ExportDefinitionError(
            f"cannot encode data_format {data_format!r} to FLAC"
        )
    if declared is not None:
        return declared

    depth = _PASSTHROUGH_DEPTHS.get(data_format)
    if depth is None:
        raise ExportDefinitionError(
            f"audio.bit_depth (16 or 24) is required to encode "
            f"{data_format!r} sources to FLAC; libsndfile writes 16/24 bit "
            f"FLAC only and this project never reduces bit depth implicitly"
        )
    return depth


@dataclass(frozen=True)
class AudioExporter:
    """
    Write one source sample into the patch output directory.

    `wav` is a byte-exact copy that also preserves the `smpl` loop
    chunk. `flac` re-encodes losslessly for int16/int24 sources; the
    frame count is verified after encoding because every loop frame in
    the manifest must stay valid in the exported file.
    """

    audio_format: AudioFormat = "wav"
    bit_depth: int | None = None

    @property
    def suffix(self) -> str:
        return FLAC_SUFFIX if self.audio_format == "flac" else WAV_SUFFIX

    def export(
        self, source_path: Path, destination_path: Path, data_format: str
    ) -> None:
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ExportAudioError(
                f"{destination_path.parent}: cannot create directory: {e}"
            ) from e

        if self.audio_format == "wav":
            try:
                shutil.copyfile(source_path, destination_path)
            except OSError as e:
                raise ExportAudioError(
                    f"{source_path}: cannot copy to {destination_path}: {e}"
                ) from e
            return

        self._encode_flac(source_path, destination_path, data_format)

    def _encode_flac(
        self, source_path: Path, destination_path: Path, data_format: str
    ) -> None:
        try:
            import soundfile as sf
        except ImportError as e:
            raise ExportAudioError(f"{_INSTALL_HINT} ({e})") from e

        depth = resolve_flac_bit_depth(data_format, self.bit_depth)

        try:
            if data_format in _FLOAT_FORMATS:
                import numpy as np

                data, sample_rate = sf.read(
                    str(source_path), dtype="float64", always_2d=True
                )
                data = np.clip(data, -1.0, 1.0)
            else:
                # int32 covers every integer source: libsndfile converts
                # between left-justified integer widths by bit shifting,
                # so an int16/int24 pass-through stays bit-exact.
                data, sample_rate = sf.read(
                    str(source_path), dtype="int32", always_2d=True
                )
        except ExportAudioError:
            raise
        except Exception as e:
            raise ExportAudioError(f"{source_path}: cannot read audio: {e}") from e

        try:
            sf.write(
                str(destination_path),
                data,
                sample_rate,
                format="FLAC",
                subtype=_FLAC_SUBTYPES[depth],
            )
        except Exception as e:
            raise ExportAudioError(
                f"{destination_path}: FLAC encoding failed: {e}"
            ) from e

        written_frames = int(sf.info(str(destination_path)).frames)
        if written_frames != len(data):
            raise ExportAudioError(
                f"{destination_path}: FLAC frame count mismatch: "
                f"source has {len(data)} frames, output has {written_frames}; "
                f"loop points in the manifest would be invalid"
            )

        logger.debug(
            f"Encoded {source_path.name} -> {destination_path.name} "
            f"(FLAC {depth} bit, {written_frames} frames)"
        )
