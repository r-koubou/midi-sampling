"""Minimal RIFF/WAVE chunk parser and non-destructive writer.

The parser keeps every chunk as raw bytes so the writer can reproduce the
input byte-for-byte, only inserting or replacing an ``smpl`` chunk and
updating the RIFF size field.  Audio data is never re-encoded here.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from sample_loop_detector.config import MAX_SAMPLE_RATE, MIN_SAMPLE_RATE
from sample_loop_detector.exceptions import (
    InvalidWaveError,
    UnsupportedWaveFormatError,
    WaveWriteError,
)

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

# First 2 bytes of the extensible SubFormat GUID hold the actual format tag.
KSDATAFORMAT_SUBTYPE_PCM = bytes.fromhex("0100000000001000800000aa00389b71")
KSDATAFORMAT_SUBTYPE_IEEE_FLOAT = bytes.fromhex("0300000000001000800000aa00389b71")


@dataclass(frozen=True)
class RiffChunk:
    """One chunk: fourcc identifier and raw payload (without padding)."""

    chunk_id: bytes
    data: bytes

    @property
    def padded_size(self) -> int:
        size = len(self.data)
        return size + (size % 2)


@dataclass(frozen=True)
class WaveFormat:
    """Parsed ``fmt `` chunk contents."""

    format_tag: int
    channels: int
    sample_rate: int
    block_align: int
    bits_per_sample: int
    resolved_format_tag: int  # extensible resolved to PCM / IEEE float

    @property
    def is_float(self) -> bool:
        return self.resolved_format_tag == WAVE_FORMAT_IEEE_FLOAT

    @property
    def subtype_name(self) -> str:
        if self.is_float:
            return f"FLOAT_{self.bits_per_sample}"
        return f"PCM_{self.bits_per_sample}"


@dataclass(frozen=True)
class WaveFile:
    """A parsed WAV file: ordered chunks plus decoded format info."""

    chunks: tuple[RiffChunk, ...]
    fmt: WaveFormat

    @property
    def data_chunk(self) -> RiffChunk:
        for chunk in self.chunks:
            if chunk.chunk_id == b"data":
                return chunk
        raise InvalidWaveError("data chunk not found")

    @property
    def smpl_chunks(self) -> tuple[RiffChunk, ...]:
        return tuple(chunk for chunk in self.chunks if chunk.chunk_id == b"smpl")

    @property
    def frame_count(self) -> int:
        if self.fmt.block_align <= 0:
            raise InvalidWaveError("invalid block alignment")
        return len(self.data_chunk.data) // self.fmt.block_align


def parse_wave_bytes(raw: bytes) -> WaveFile:
    """Parse WAV bytes into chunks and validate the format."""
    if len(raw) < 12:
        raise InvalidWaveError("file too small to be a RIFF/WAVE file")

    magic = raw[0:4]
    if magic == b"RF64":
        raise UnsupportedWaveFormatError("RF64 files are not supported")
    if magic != b"RIFF":
        raise InvalidWaveError("not a RIFF file")
    if raw[8:12] != b"WAVE":
        raise InvalidWaveError("not a WAVE file")

    chunks: list[RiffChunk] = []
    offset = 12
    while offset + 8 <= len(raw):
        chunk_id = raw[offset : offset + 4]
        (size,) = struct.unpack_from("<I", raw, offset + 4)
        payload_start = offset + 8
        payload_end = payload_start + size
        if payload_end > len(raw):
            raise InvalidWaveError(f"chunk {chunk_id!r} exceeds file size (corrupt chunk size)")
        chunks.append(RiffChunk(chunk_id=chunk_id, data=raw[payload_start:payload_end]))
        offset = payload_end + (size % 2)

    fmt = _parse_fmt(chunks)
    wave = WaveFile(chunks=tuple(chunks), fmt=fmt)
    # Trigger data-chunk validation early.
    data = wave.data_chunk
    if fmt.block_align <= 0 or len(data.data) < fmt.block_align:
        raise InvalidWaveError("data chunk contains no complete sample frame")
    if len(data.data) % fmt.block_align != 0:
        raise InvalidWaveError("data chunk size is not a multiple of the frame size")
    return wave


def parse_wave_file(path: Path) -> WaveFile:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise InvalidWaveError(f"cannot read input file: {error}") from error
    return parse_wave_bytes(raw)


def _parse_fmt(chunks: list[RiffChunk]) -> WaveFormat:
    fmt_chunk = next((c for c in chunks if c.chunk_id == b"fmt "), None)
    if fmt_chunk is None:
        raise InvalidWaveError("fmt chunk not found")
    if len(fmt_chunk.data) < 16:
        raise InvalidWaveError("fmt chunk is too small")

    format_tag, channels, sample_rate, _byte_rate, block_align, bits_per_sample = (
        struct.unpack_from("<HHIIHH", fmt_chunk.data, 0)
    )

    resolved = format_tag
    if format_tag == WAVE_FORMAT_EXTENSIBLE:
        if len(fmt_chunk.data) < 40:
            raise InvalidWaveError("extensible fmt chunk is too small")
        sub_format = fmt_chunk.data[24:40]
        if sub_format == KSDATAFORMAT_SUBTYPE_PCM:
            resolved = WAVE_FORMAT_PCM
        elif sub_format == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT:
            resolved = WAVE_FORMAT_IEEE_FLOAT
        else:
            raise UnsupportedWaveFormatError("unsupported extensible subformat")

    if resolved == WAVE_FORMAT_PCM:
        if bits_per_sample not in (8, 16, 24, 32):
            raise UnsupportedWaveFormatError(f"unsupported PCM bit depth: {bits_per_sample}")
    elif resolved == WAVE_FORMAT_IEEE_FLOAT:
        if bits_per_sample not in (32, 64):
            raise UnsupportedWaveFormatError(f"unsupported float bit depth: {bits_per_sample}")
    else:
        raise UnsupportedWaveFormatError(
            f"unsupported (possibly compressed) format tag: 0x{format_tag:04x}"
        )

    if channels not in (1, 2):
        raise UnsupportedWaveFormatError(f"unsupported channel count: {channels}")
    if not (MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE):
        raise UnsupportedWaveFormatError(f"unsupported sample rate: {sample_rate}")
    if block_align != channels * (bits_per_sample // 8):
        raise InvalidWaveError("block alignment does not match channels and bit depth")

    return WaveFormat(
        format_tag=format_tag,
        channels=channels,
        sample_rate=sample_rate,
        block_align=block_align,
        bits_per_sample=bits_per_sample,
        resolved_format_tag=resolved,
    )


def build_wave_bytes(chunks: list[RiffChunk]) -> bytes:
    """Serialize chunks back into a complete RIFF/WAVE byte string."""
    body = bytearray()
    for chunk in chunks:
        body += chunk.chunk_id
        body += struct.pack("<I", len(chunk.data))
        body += chunk.data
        if len(chunk.data) % 2 == 1:
            body += b"\x00"
    riff_size = 4 + len(body)
    return b"RIFF" + struct.pack("<I", riff_size) + b"WAVE" + bytes(body)


def insert_smpl_chunk(
    wave: WaveFile,
    smpl_chunk: RiffChunk,
    replace_existing: bool,
) -> bytes:
    """Return output WAV bytes with the smpl chunk inserted before ``data``.

    All other chunks keep their original content and order.
    """
    if wave.smpl_chunks and not replace_existing:
        raise WaveWriteError("input already contains an smpl chunk")

    output: list[RiffChunk] = []
    inserted = False
    for chunk in wave.chunks:
        if chunk.chunk_id == b"smpl":
            continue  # dropped when replace_existing is set
        if chunk.chunk_id == b"data" and not inserted:
            output.append(smpl_chunk)
            inserted = True
        output.append(chunk)
    if not inserted:
        output.append(smpl_chunk)
    return build_wave_bytes(output)
