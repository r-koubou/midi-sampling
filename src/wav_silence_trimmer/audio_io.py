"""WAV reading and writing with atomic replacement and overwrite control."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from .errors import InvalidInputError, OutputExistsError, UnsupportedFormatError
from .models import AudioMetadata

logger = logging.getLogger(__name__)

# WAVEX is WAVE_FORMAT_EXTENSIBLE, RF64 is the >4 GB WAV extension; both are
# WAV container variants and are accepted as input.
_WAV_FORMATS = {"WAV", "WAVEX", "RF64"}


def read_wav(path: Path) -> tuple[np.ndarray, AudioMetadata]:
    """Read a WAV file as float64 with shape (samples, channels).

    Args:
        path: Input WAV path.

    Returns:
        Tuple of (audio, metadata). Mono audio is returned as (samples, 1).

    Raises:
        InvalidInputError: If the file does not exist or cannot be read.
        UnsupportedFormatError: If the file is not a WAV file.
    """
    if not path.is_file():
        raise InvalidInputError(f"Input file not found: {path}")
    try:
        info = sf.info(str(path))
    except sf.LibsndfileError as exc:
        raise UnsupportedFormatError(
            f"Cannot read as audio file: {path}: {exc}"
        ) from exc
    if info.format not in _WAV_FORMATS:
        raise UnsupportedFormatError(
            f"Only WAV input is supported, got {info.format}: {path}"
        )
    try:
        audio, sample_rate = sf.read(str(path), dtype="float64", always_2d=True)
    except (sf.LibsndfileError, RuntimeError) as exc:
        raise InvalidInputError(f"Failed to read {path}: {exc}") from exc
    metadata = AudioMetadata(
        path=path,
        sample_rate=int(sample_rate),
        channels=audio.shape[1],
        frames=audio.shape[0],
        subtype=info.subtype,
        format=info.format,
    )
    return audio, metadata


def write_wav(
    path: Path,
    audio: np.ndarray,
    sample_rate: int,
    subtype: str,
    *,
    format: str = "WAV",
    overwrite: bool = False,
) -> None:
    """Write audio to a WAV file atomically, preserving the given subtype.

    Data is written to a temporary file in the destination directory and then
    moved into place, so a failed write never leaves a partial output and an
    input file at the same path is never destroyed mid-write.

    Args:
        path: Output WAV path.
        audio: Audio shaped (samples, channels).
        sample_rate: Sample rate in Hz.
        subtype: libsndfile subtype of the original input (e.g. "PCM_16").
        format: WAV container variant ("WAV", "WAVEX", or "RF64").
        overwrite: Allow replacing an existing file.

    Raises:
        OutputExistsError: If path exists and overwrite is False.
    """
    if path.exists() and not overwrite:
        raise OutputExistsError(
            f"Output already exists (use --overwrite): {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.stem + ".", suffix=".tmp.wav", dir=path.parent
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        sf.write(
            str(temp_path),
            audio,
            sample_rate,
            subtype=subtype,
            format=format if format in _WAV_FORMATS else "WAV",
        )
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
