from enum import Enum


class AudioDataFormat(Enum):
    """
    Audio data format.
    """
    UNKNOWN = 0
    INT16   = 1
    INT24   = 2
    INT32   = 3
    FLOAT32 = 4

    def bit_depth(self) -> int:
        data_table = {
            AudioDataFormat.INT16: 16,
            AudioDataFormat.INT24: 24,
            AudioDataFormat.INT32: 32,
            AudioDataFormat.FLOAT32: 32,
        }
        return data_table[self]

    @classmethod
    def parse(cls, data_format: str) -> 'AudioDataFormat':
        data_table = {
            "int16": AudioDataFormat.INT16,
            "int24": AudioDataFormat.INT24,
            "int32": AudioDataFormat.INT32,
            "float32": AudioDataFormat.FLOAT32,
        }

        result = data_table.get(data_format.lower(), AudioDataFormat.UNKNOWN)
        if result == AudioDataFormat.UNKNOWN:
            raise ValueError(f"Unknown audio data format: {data_format}")

        return result
