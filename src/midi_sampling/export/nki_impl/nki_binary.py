import struct
import zlib
from logging import getLogger

logger = getLogger(__name__)

NKI_MAGIC = b"\x5e\xe5\x6e\xb3"
HEADER_SIZE = 0x24
HEADER_VERSION = 0x0050
# Meaning unknown; a program saved by KONTAKT 1 itself carries 2 here.
HEADER_FIELD_0X0A = 2

_HEADER = struct.Struct("<4sIHH6I")
_U32_MAX = 0xFFFF_FFFF


def build_nki_bytes(
    xml_text: str, sample_data_size: int, timestamp: int
) -> bytes:
    """
    Assemble a KONTAKT 1 NKI file: the 36-byte little-endian header
    followed by the zlib-compressed NiSS XML. `sample_data_size` is the
    total payload size of the referenced WAV `data` chunks.
    """
    if sample_data_size > _U32_MAX:
        logger.warning(
            f"total sample data size {sample_data_size} exceeds 32 bit; "
            f"clamping the NKI header field"
        )
        sample_data_size = _U32_MAX

    header = _HEADER.pack(
        NKI_MAGIC,
        HEADER_SIZE,
        HEADER_VERSION,
        HEADER_FIELD_0X0A,
        0,
        0,
        1,
        timestamp,
        sample_data_size,
        0,
    )
    return header + zlib.compress(xml_text.encode("utf-8"))
