from typing import List

import io
import struct

from logging import getLogger

logger = getLogger(__name__)

class ChunkData:
    def __init__(self, chunk_name: str, chunk_data: bytes, chunk_size):
        self.chunk_name: str    = chunk_name
        self.chunk_data: bytes  = chunk_data
        self.chunk_size: int    = chunk_size
        self.padding_count: int = 0 if len(chunk_data) % 2 == 0 else 1

    def write(self, f: io.BufferedWriter):
        """
        Write chunk data to given file object
        """
        start = f.tell()

        if self.chunk_name == "RIFF":
            f.write(self.chunk_name.encode('ascii'))
            f.write(self.chunk_size.to_bytes(4, byteorder='little'))
            f.write("WAVE".encode('ascii'))
        else:
            f.write(self.chunk_name.encode('ascii'))
            f.write((len(self.chunk_data)).to_bytes(4, byteorder='little'))
            f.write(self.chunk_data)

        written_size = f.tell() - start
        logger.debug(f"written: {self} - size={written_size}/0x{written_size:x} bytes")

    SIZEOF_CHUNK_NAME_AND_CHUNK_SIZE = 8
    """
    Size of chunk name and chunk size (4byte + 4byte)
    """

    @classmethod
    def from_bytes(cls, file_bytes: bytes) -> List['ChunkData']:
        result: List['ChunkData'] = []
        length = len(file_bytes)
        current_index = 0

        while current_index < length:

            # Chunk format

            # | 'xxxx' (chunk name: 4 byte)  |  chunk size (4 byte) |    chunk data ...   |
            # |<<-------SIZEOF_CHUNK_NAME_AND_CHUNK_SIZE --------->>|<<-- chunk_size-- >> |
            # ^                                                     ^
            # |                                                     |
            # current_index                                         chunk_data_start_index

            chunk_name = file_bytes[current_index:current_index + 4].decode('ascii')
            chunk_size = struct.unpack(
                '<I',
                file_bytes[
                    current_index + 4:
                    current_index + ChunkData.SIZEOF_CHUNK_NAME_AND_CHUNK_SIZE
                ]
            )[0]

            chunk_data_start_index = current_index + ChunkData.SIZEOF_CHUNK_NAME_AND_CHUNK_SIZE

            padding_count = 0
            if chunk_size % 2 != 0:
                padding_count = 1

            if chunk_name == "RIFF":
                chunk_data = "WAVE".encode('ascii')
            else:
                chunk_data = file_bytes[
                    chunk_data_start_index:
                    chunk_data_start_index + chunk_size + padding_count
                ]

            chunk_data = ChunkData(
                chunk_name=chunk_name,
                chunk_data=chunk_data,
                chunk_size=chunk_size
            )
            result.append(chunk_data)

            logger.debug(f"read: {chunk_data}")

            if chunk_name == "RIFF":
                # RIFF `chunk size` is `file size - 8` stored
                #
                # | 'RIFF' (4byte) | chunk size (4byte) | 'WAVE' (4byte) |
                #
                # -> (Next chunk start index is + 12)
                current_index += 12
            else:
                current_index += chunk_size + ChunkData.SIZEOF_CHUNK_NAME_AND_CHUNK_SIZE + padding_count

        return result

    @classmethod
    def calc_riff_chunk_size(cls, chunks: List['ChunkData']) -> int:
        """
        Calculate RIFF chunk size from given chunks
        """
        result = 0
        for x in chunks:
            if x.chunk_name == "RIFF":
                result += 4 # sizeof 'WAVE' in chunk_data
            else:
                logger.debug(f"calc: {x}")
                result += (
                    ChunkData.SIZEOF_CHUNK_NAME_AND_CHUNK_SIZE
                    + len(x.chunk_data)
                    + x.padding_count
                )

        return result

    @classmethod
    def update_riff_chunk_size(cls, chunks: List['ChunkData']) -> bool:
        """
        Update RIFF chunk size in given chunks

        Parameters
        ----------
        chunks : List['ChunkData']
            List of chunks

        Returns
        -------
        bool
            If RIFF chunk is found and updated, return True. Otherwise, return False.
        """
        logger.debug(f"update_riff_chunk_size")
        new_size = ChunkData.calc_riff_chunk_size(chunks)
        for x in chunks:
            if x.chunk_name == "RIFF":
                x.chunk_size = new_size
                return True

        return False

    def __str__(self) -> str:
        return f"chunk_name={self.chunk_name}, chunk_size={self.chunk_size}/0x{self.chunk_size:x}, data={len(self.chunk_data)}, padding_count={self.padding_count}"


class WavChunkKeeper:
    """
    As a response to the case where the waveform processing library does not consider keeping chunks of the wav file,
    if the chunks before waveform processing are not included in the file after waveform processing,
    the corresponding chunks in the file before waveform processing will be inserted as is.

    As a typical example, we assume chunks unique to waveform editing software or music production software.

    Examples
    --------

    ```python
    # initialize
    keeper = WavChunkKeeper("source.wav", "target.wav")

    # waveform processings and output to "target.wav"
    # ...
    # processing
    # ...

    # restore the chunks to "target.wav"
    keeper.restore()
    ```
    """

    def __init__(self, source_path: str, target_path: str, keep_chunk_names: List[str] = []):
        """
        Parameters
        ----------
        source_path : str
            Source wav file path

        target_path : str
            Target wav file path

        keep_chunk_names : List[str] (default: [])
            A list of chunk names to be retained explicitly. Only the specified chunk names will be retained.
            If not specified, retain all chunks.
        """
        self.source_path: str = source_path
        self.target_path: str = target_path
        self.source_file_chunk_list: List[ChunkData] = []

        with(open(self.source_path, 'rb')) as f:
            source_file_bytes = f.read()
            self.source_file_chunk_list = ChunkData.from_bytes(source_file_bytes)

        if len(keep_chunk_names) > 0:
            logger.debug(f"Request to keep only specified chunks: {keep_chunk_names}")
            self.source_file_chunk_list = [
                x for x in self.source_file_chunk_list if x.chunk_name in keep_chunk_names
            ]

    def restore(self):
        """
        Restore the chunks to target_path
        """

        with open(self.target_path, 'rb') as f:
            file_bytes = f.read()

        file_chunk_list        = ChunkData.from_bytes(file_bytes)
        appenging_chunk_list   = []

        for source_chunk in self.source_file_chunk_list:
            found = False
            for file_chunk in file_chunk_list:
                if source_chunk.chunk_name == file_chunk.chunk_name:
                    found = True
                    break
            if not found:
                appenging_chunk_list.append(source_chunk)

        logger.info(f"write to {self.target_path}")
        with open(self.target_path, 'wb') as f:

            write_chunk_list = file_chunk_list + appenging_chunk_list
            ChunkData.update_riff_chunk_size(write_chunk_list)

            for x in write_chunk_list:
                x.write(f)

            logger.debug(f"Validate RIFF chunk size")
            expected_riff_size = f.tell() - 8
            actual_riff_size   = ChunkData.calc_riff_chunk_size(write_chunk_list)
            logger.debug(f"expected_riff_size: 0x{expected_riff_size:x}")
            logger.debug(f"actual_riff_size: 0x{actual_riff_size:x}")

            if expected_riff_size != actual_riff_size:
                raise ValueError("RIFF chunk size is not matched")

            logger.debug(f"restored: {self.target_path}")
