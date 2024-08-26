from typing import List

import struct

from logging import getLogger

logger = getLogger(__name__)

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

    class ChunkData:
        def __init__(self, chunk_name: str, chunk_data: bytes, chunk_size: int, chunk_start: int):
            self.chunk_name: str    = chunk_name
            self.chunk_data: bytes  = chunk_data
            self.chunk_size: int    = chunk_size
            self.chunk_start: int   = chunk_start

        def __str__(self) -> str:
            return f"ChunkData(chunk_name={self.chunk_name}, chunk_start={self.chunk_start}, chunk_size={self.chunk_size})"

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
        self.chunk_data_list: List[WavChunkKeeper.ChunkData] = []

    @classmethod
    def __exist_chunk(cls, chunk_name: str, file_bytes: bytes) -> bool:
        chunk_index = file_bytes.find(chunk_name.encode('ascii'))
        return chunk_index != -1

    @classmethod
    def __find_chunk(cls, chunk_name: str, file_bytes: bytes) -> ChunkData:
        chunk_index = file_bytes.find(chunk_name.encode('ascii'))

        if not WavChunkKeeper.__exist_chunk(chunk_name, file_bytes):
            return None

        # Chunk format
        # | 'xxxx' (chunk name: 4 bytes) | chunk size (4 bytes) | data ...
        chunk_size  = struct.unpack('<I', file_bytes[chunk_index + 4:chunk_index + 8])[0]
        chunk_bytes = file_bytes[chunk_index:chunk_index+chunk_size + 8] # + 8: chunk name + chunk size

        return WavChunkKeeper.ChunkData(
            chunk_name=chunk_name,
            chunk_data=chunk_bytes,
            chunk_size=chunk_size,
            chunk_start=chunk_index
        )

    def read(self):
        """
        Read source wav file and extract chunks that are specified in keep_chunk_names
        """
        with open(self.source_path, 'rb') as f:
            file_bytes = f.read()

            for chunk_name in self.keep_chunk_names:
                chunk_data = WavChunkKeeper.__find_chunk(chunk_name, file_bytes)
                if chunk_data:
                    self.chunk_data_list.append(chunk_data)
                    print(chunk_data)

    def restore(self):
        """
        Restore the chunks to target_path
        """
        with open(self.target_path, 'rb') as f:
            file_bytes = f.read()

        # Check if the chunk to restore exists in the target file
        exists_indexes: List[int] = []
        for i, chunk_data in enumerate(self.chunk_data_list):
            chunk_name  = chunk_data.chunk_name
            chunk_index = file_bytes.find(chunk_name.encode('ascii'))
            if chunk_index != -1:
                exists_indexes.append(i)



        # If there is no chunk to restore, do nothing
        if len(exists_indexes) == 0:
            return

        with open(self.target_path, 'wb') as f:

            riff_index = file_bytes.find(b'RIFF')
            fmt_index  = file_bytes.find(b'fmt ')
            data_start = fmt_index + 8 + struct.unpack('<I', file_bytes[fmt_index + 4:fmt_index + 8])[0]

            f.write(file_bytes[:data_start])

            for i in self.chunk_data_list:
                if WavChunkKeeper.__exist_chunk(i.chunk_name, file_bytes):
                    continue

                f.write(i.chunk_data)

            f.write(file_bytes[data_start:])

            # Update RIFF chunk size
            riff_size = len(file_bytes) - 8
            f.seek(4)
            f.write(struct.pack('<I', riff_size))


from pydub import AudioSegment

input  = "C:\\UserData\\Develop\\Project\\OSS\\midi-sampling\\examples\\_processed\\40_40_40_127_96_127.wav"
output = "C:\\UserData\\Develop\\Project\\OSS\\midi-sampling\\examples\\_processed\\40_40_40_127_96_127_zzz.wav"

audio = AudioSegment.from_file(input, format='wav')
processed_audio = audio + 5
processed_audio.export(output, format='wav')

keeper = WavChunkKeeper(input, output, ['smpl'])
keeper.read()
keeper.restore()
