import struct
from dataclasses import dataclass
from pathlib import Path

from midi_sampling.export.exceptions import ExportWriteError

_RIFF_HEADER = struct.Struct("<4sI4s")
_CHUNK_HEADER = struct.Struct("<4sI")


@dataclass(frozen=True)
class WavDataInfo:
    """
    The part of a WAV file the NKI writer needs: the payload size of
    the `data` chunk (for the header's total-sample-data field) and the
    frame count derived from it (for the zone's `sampleEnd`).
    """
    frame_count: int
    data_size: int


def read_wav_data_info(path: Path) -> WavDataInfo:
    """
    Scan the RIFF chunks of an exported WAV file. The stdlib `wave`
    module is not used because it rejects float PCM (format code 3),
    which is a legal source format in this project.
    """
    try:
        raw = path.read_bytes()
    except OSError as e:
        raise ExportWriteError(f"{path}: cannot read sample file: {e}") from e

    if len(raw) < _RIFF_HEADER.size:
        raise ExportWriteError(f"{path}: not a RIFF/WAVE file: too short")
    riff, _, wave_id = _RIFF_HEADER.unpack_from(raw, 0)
    if riff != b"RIFF" or wave_id != b"WAVE":
        raise ExportWriteError(f"{path}: not a RIFF/WAVE file")

    block_align: int | None = None
    data_size: int | None = None
    offset = _RIFF_HEADER.size
    while offset + _CHUNK_HEADER.size <= len(raw):
        chunk_id, chunk_size = _CHUNK_HEADER.unpack_from(raw, offset)
        payload_start = offset + _CHUNK_HEADER.size
        if payload_start + chunk_size > len(raw):
            raise ExportWriteError(
                f"{path}: truncated {chunk_id!r} chunk"
            )
        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise ExportWriteError(f"{path}: malformed 'fmt ' chunk")
            block_align = struct.unpack_from("<H", raw, payload_start + 12)[0]
        elif chunk_id == b"data":
            data_size = chunk_size
        # Chunks are word aligned: an odd payload is followed by a pad byte.
        offset = payload_start + chunk_size + (chunk_size & 1)

    if block_align is None or data_size is None:
        raise ExportWriteError(
            f"{path}: missing 'fmt ' or 'data' chunk"
        )
    if block_align == 0:
        raise ExportWriteError(f"{path}: 'fmt ' chunk has zero block align")

    return WavDataInfo(
        frame_count=data_size // block_align, data_size=data_size
    )
