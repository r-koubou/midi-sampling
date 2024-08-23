import abc
from typing import List, override

import os
import pathlib

class IExportingAudioPath(metaclass=abc.ABCMeta):
    """
    Exporting audio path information.
    Implementations should implement __eq__ and __hash__ methods for comparison.
    """

    @abc.abstractmethod
    def path(self) -> str:
        """
        Get joined path of base_dir and file_path
        """
        raise NotImplementedError

    @abc.abstractmethod
    def makedirs(self):
        """
        Create directory by using `base_dir + file_path`
        """
        raise NotImplementedError

class RecordedAudioPath(IExportingAudioPath):
    """
    Exporting audio path information
    """

    def __init__(self, base_dir:str, file_path:str):
        self.base_dir: str  = base_dir
        self.file_path: str = os.path.normpath(file_path)

    @override
    def path(self) -> str:
        """
        Get joined path of base_dir and file_path
        """
        return os.path.join(self.base_dir, self.file_path)

    @override
    def makedirs(self):
        """
        Create directory by using `base_dir + file_path`
        """

        target = os.path.dirname(self.path())
        if len(target) > 0:
            os.makedirs(target, exist_ok=True)

    def __str__(self):
        return f"base_dir={self.base_dir}, file_path={self.file_path}"

    def __eq__(self, other):
        if not isinstance(other, RecordedAudioPath):
            return False

        return (
            self.base_dir == other.base_dir
            and self.file_path == other.file_path
        )

    def __hash__(self):
        return hash((self.base_dir, self.file_path))

class PostProcessedAudioPath(IExportingAudioPath):
    """
    Exporting audio path information for post process
    """
    def __init__(self, recorded_audio_path: RecordedAudioPath, base_dir: str, overwrite: bool = False):

        if base_dir == recorded_audio_path.base_dir and not overwrite:
            raise ValueError("base_dir and recorded_audio_path.base_dir must be different. If you want to force overwrite, set overwrite to enable.")

        self.recorded_audio_path: RecordedAudioPath = recorded_audio_path
        self.base_dir: str  = base_dir
        self.file_path: str = os.path.normpath(recorded_audio_path.file_path)

    @classmethod
    def from_directory(cls, input_directory: str, output_directory: str, search_extension: str = ".wav", overwrite: bool = False) -> List['PostProcessedAudioPath']:

        input_directory = os.path.normpath(os.path.abspath(input_directory))
        output_directory = os.path.normpath(os.path.abspath(output_directory))

        if not os.path.exists(input_directory):
            raise FileNotFoundError(f"input_directory not found: {input_directory}")

        directory = pathlib.Path(input_directory)
        files = list(directory.glob(f"**/*{search_extension}"))

        result: List[PostProcessedAudioPath] = []

        for f in files:
            file_path = os.path.normpath(str(f.relative_to(directory)))
            source    = RecordedAudioPath(base_dir=input_directory, file_path=file_path)
            result.append(PostProcessedAudioPath(recorded_audio_path=source, base_dir=output_directory, overwrite=overwrite))

        return result

    @override
    def path(self) -> str:
        return os.path.join(self.base_dir, self.file_path)

    @override
    def makedirs(self):
        target = os.path.dirname(self.path())
        if len(target) > 0:
            os.makedirs(target, exist_ok=True)

    def __str__(self):
        return f"base_dir={self.base_dir}, file_path={self.file_path}, recorded_audio_path={self.recorded_audio_path}"


    def __eq__(self, other):
        if not isinstance(other, RecordedAudioPath):
            return False

        return (
            self.base_dir == other.base_dir
            and self.file_path == other.file_path
        )

    def __hash__(self):
        return hash((self.base_dir, self.file_path))
