import abc
from typing import List, override

import os
import pathlib
import shutil

class RecordedAudioPath:
    """
    Exporting audio path information
    """

    def __init__(self, base_dir:str, file_path:str):
        self.base_dir: str  = base_dir
        self.file_path: str = os.path.normpath(file_path)

    def path(self) -> str:
        """
        Get joined path of base_dir and file_path
        """
        return os.path.join(self.base_dir, self.file_path)

    def makedirs(self):
        """
        Create directory by using `base_dir + file_path`
        """

        target = os.path.dirname(self.path())
        if len(target) > 0:
            os.makedirs(target, exist_ok=True)

    def copy_to(self, dest_dir: str):
        """
        Copy processed file to dest_dir
        """
        dest = os.path.join(dest_dir, self.file_path) # join sub directory included in file_path
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(self.path(), dest)

    @classmethod
    def from_directory(cls, input_directory: str, search_extension: str = ".wav") -> List['RecordedAudioPath']:

        input_directory = os.path.normpath(os.path.abspath(input_directory))

        if not os.path.exists(input_directory):
            raise FileNotFoundError(f"input_directory not found: {input_directory}")

        directory = pathlib.Path(input_directory)
        files = list(directory.glob(f"**/*{search_extension}"))

        result: List[RecordedAudioPath] = []

        for f in files:
            file_path = os.path.normpath(str(f.relative_to(directory)))
            result.append(RecordedAudioPath(base_dir=input_directory, file_path=file_path))

        return result

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

class ProcessedAudioPath:
    """
    Exporting audio path information for post process
    """
    def __init__(self, recorded_audio_path: RecordedAudioPath, output_dir: str, working_dir: str, overwrite: bool = False):

        if output_dir == recorded_audio_path.base_dir and not overwrite:
            raise ValueError("base_dir and recorded_audio_path.base_dir must be different. If you want to force overwrite, set overwrite to enable.")

        self.recorded_audio_path: RecordedAudioPath = recorded_audio_path
        self.output_dir: str  = output_dir
        self.working_dir: str = working_dir
        self.file_path: str   = os.path.normpath(recorded_audio_path.file_path)

    @classmethod
    def from_directory(cls, input_directory: str, output_directory: str, working_directory: str = None, search_extension: str = ".wav", overwrite: bool = False) -> List['ProcessedAudioPath']:

        input_directory = os.path.normpath(os.path.abspath(input_directory))
        output_directory = os.path.normpath(os.path.abspath(output_directory))

        if not working_directory:
            working_directory = output_directory

        if not os.path.exists(input_directory):
            raise FileNotFoundError(f"input_directory not found: {input_directory}")

        files = RecordedAudioPath.from_directory(input_directory=input_directory, search_extension=search_extension)
        result: List[ProcessedAudioPath] = []

        for f in files:
            result.append(ProcessedAudioPath(recorded_audio_path=f, output_dir=output_directory, working_dir=working_directory, overwrite=overwrite))

        return result

    def path(self) -> str:
        return os.path.join(self.output_dir, self.file_path)

    def working_path(self) -> str:
        return os.path.join(self.working_dir, self.file_path)

    def makedirs(self):
        """
        Create directory by using `output_dir + file_path`
        """
        target = os.path.dirname(self.path())
        if len(target) > 0:
            os.makedirs(target, exist_ok=True)

    def makeworkingdirs(self):
        """
        Create directory by using `working_dir + file_path`
        """
        target = os.path.dirname(self.working_path())
        if len(target) > 0:
            os.makedirs(target, exist_ok=True)

    def copy_working_to(self, dest_dir: str):
        """
        Copy processed file (in working directory) to dest_dir
        """
        dest = os.path.join(dest_dir, self.file_path) # join sub directory included in file_path
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(self.working_path(), dest)

    def __str__(self):
        return f"output_dir={self.output_dir}, file_path={self.file_path}, working_dir={self.working_dir}, recorded_audio_path={self.recorded_audio_path}"


    def __eq__(self, other):
        if not isinstance(other, ProcessedAudioPath):
            return False

        return (
            self.output_dir == other.output_dir
            and self.file_path == other.file_path
        )

    def __hash__(self):
        return hash((self.output_dir, self.file_path))
