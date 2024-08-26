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

    def write(self, f: io.BufferedWriter):
        """
        Write chunk data to given file object
        """
        if self.chunk_name == "RIFF":
            f.write(self.chunk_name.encode('ascii'))
            f.write(self.chunk_size.to_bytes(4, byteorder='little'))
            f.write("WAVE".encode('ascii'))
        else:
            f.write(self.chunk_name.encode('ascii'))
            f.write((len(self.chunk_data)).to_bytes(4, byteorder='little'))
            f.write(self.chunk_data)

    @classmethod
    def from_bytes(cls, file_bytes: bytes) -> List['ChunkData']:
        result: List['ChunkData'] = []
        length = len(file_bytes)
        current_index = 0

        NAME_AND_SIZE_LENGTH = 8

        while current_index < length:

            # Chunk format

            # | 'xxxx' (chunk name: 4 byte)  |  chunk size (4 byte) |    chunk data ...   |
            # |<<-----------------NAME_AND_SIZE_LENGTH ----------->>|<<-- chunk_size-- >> |
            # ^                                                     ^
            # |                                                     |
            # current_index                                         chunk_data_start_index

            chunk_name = file_bytes[current_index:current_index + 4].decode('ascii')
            chunk_size = struct.unpack(
                '<I',
                file_bytes[
                    current_index + 4:
                    current_index + NAME_AND_SIZE_LENGTH
                ]
            )[0]

            chunk_data_start_index = current_index + NAME_AND_SIZE_LENGTH

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

            result.append(ChunkData(
                chunk_name=chunk_name,
                chunk_data=chunk_data,
                chunk_size=chunk_size
            ))

            print(f"index={current_index}, chunk_name={chunk_name}, chunk_size={chunk_size}, data={len(chunk_data)}, padding_count={padding_count}")

            if chunk_name == "RIFF":
                # RIFF `chunk size` is `file size - 8` stored
                #
                # | 'RIFF' (4byte) | chunk size (4byte) | 'WAVE' (4byte) |
                #
                # -> (Next chunk start index is + 12)
                current_index += 12
            else:
                current_index += chunk_size + NAME_AND_SIZE_LENGTH + padding_count

        return result

    def __str__(self) -> str:
        return f"ChunkData(chunk_name={self.chunk_name}, chunk_start={self.chunk_start}, chunk_size={self.chunk_size})"


class WavChunkKeeper:
    """
    Retain the specified chunks in case the waveform processing library is not considered to retain chunks in the wav file
    during the course of successive wav file processing.

    Examples
    --------
    ```python
    # initialize
    keeper = WavChunkKeeper("source.wav", "target.wav", ['smpl'])

    # read source wav file and extract chunks that are specified in keep_chunk_names
    keeper.read()

    # waveform processings and output to target.wav
    # ...
    # processing
    # ...

    # restore the chunks to target.wav
    keeper.restore()
    ```
    """


    def __init__(self, source_path: str, target_path: str, keep_chunk_names: List[str] = ['smpl']):
        """
        Parameters
        ----------
        source_path : str
            Source wav file path

        target_path : str
            Target wav file path

        keep_chunk_names : List[str]
            List of chunk names to keep (default: ['smpl'])
        """
        self.source_path: str               = source_path
        self.target_path: str               = target_path
        self.keep_chunk_names: List[str]    = keep_chunk_names
        self.keep_chunk_list: List[ChunkData] = []

    def read(self):
        """
        Read source wav file and extract chunks that are specified in keep_chunk_names
        """
        with open(self.source_path, 'rb') as f:
            file_bytes = f.read()

        file_chunk_list = ChunkData.from_bytes(file_bytes)
        self.keep_chunk_list = [i for i in file_chunk_list if i.chunk_name in self.keep_chunk_names]

        for i in self.keep_chunk_list:
            print(f"keep_chunk_list: {i.chunk_name}")

    def restore(self):
        """
        Restore the chunks to target_path
        """
        print("------------- Restore -------------")
        with open(self.target_path, 'rb') as f:
            file_bytes = f.read()

        file_chunk_list = ChunkData.from_bytes(file_bytes)
        appenging_chunk_list = []

        # If keep chunk does not exist in the target file, append it to the end of the file
        for keep_chunk in self.keep_chunk_list:
            found = False
            for file_chunk in file_chunk_list:
                if keep_chunk.chunk_name == file_chunk.chunk_name:
                    found = True
                    break
            if not found:
                appenging_chunk_list.append(keep_chunk)

        with open(self.target_path, 'wb') as f:
            for x in file_chunk_list:
                print(f"write: {x.chunk_name}")
                x.write(f)

            for x in appenging_chunk_list:
                print(f"appending_chunk_list: {x.chunk_name}")
                x.write(f)

from pydub import AudioSegment
import shutil

input  = "C:\\UserData\\Develop\\Project\\OSS\\midi-sampling\\examples\\_processed\\40_40_40_127_96_127.wav"
output = "C:\\UserData\\Develop\\Project\\OSS\\midi-sampling\\examples\\_processed\\40_40_40_127_96_127_zzz.wav"

# shutil.copy(input, output)

with open(input, 'rb') as f:
    file_bytes = f.read()

#c = ChunkData.from_bytes(file_bytes)

audio = AudioSegment.from_file(input, format='wav')
processed_audio = audio + 5
processed_audio.export(output, format='wav')

keeper = WavChunkKeeper(input, output, ['smpl'])
keeper.read()
keeper.restore()
