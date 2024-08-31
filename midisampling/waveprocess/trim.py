from typing import List

import os
import pathlib
import shutil
from logging import getLogger

from pydub import AudioSegment
from pydub.silence import detect_nonsilent

from midisampling.exportpath import RecordedAudioPath, ProcessedAudioPath
from midisampling.appconfig.audioprocess import AudioProcessConfig

import midisampling.waveprocess.pydubutil as pydubutil

logger = getLogger(__name__)

def trim(config: AudioProcessConfig, input_path:str, output_path: str, threshold_dBFS:float=-50, min_silence_ms:int=250):
    """
    Trim silent segments from the audio file.

    Parameters
    ----------
    input_path : str
        Input audio file path (*.wav).

    output_path : str
        Output audio file path (*.wav).

    threshold_dBFS : float (default=-50)
        Silence threshold in dBFS.

    min_silence_ms : int (default=250)
        Minimum silence duration in milliseconds.
    """

    export_parameters = []
    pydubutil.to_export_parameters_from_config(config, export_parameters)
    if len(export_parameters) == 0:
        export_parameters = None

    audio = AudioSegment.from_wav(input_path)
    nonsilent_ranges = detect_nonsilent(audio, min_silence_len=min_silence_ms, silence_thresh=threshold_dBFS)

    if nonsilent_ranges:
        start, end = nonsilent_ranges[0][0], nonsilent_ranges[-1][1]
        trimmed_audio = audio[start:end]
        trimmed_audio.export(output_path, format="wav", parameters=export_parameters)
    else:
        if input_path != output_path:
            shutil.copy(input_path, output_path)


def trim_from_list(config: AudioProcessConfig, file_list: List[ProcessedAudioPath], threshold_dBFS:float=-50, min_silence_ms:int=250):
    """
    Trim silent segments from all audio files in the input directory.

    Parameters
    ----------
    file_list : List[ProcessedAudioPath]
        List of ProcessedAudioPath instances.

    threshold_dBFS : float (default=-50)
        Silence threshold in dBFS.

    min_silence_ms : int (default=250)
        Minimum silence duration in milliseconds.
    """

    if file_list is None:
        raise ValueError("file_list is None")
    if len(file_list) == 0:
        raise ValueError("file_list is empty")

    for file in file_list:
        input_path  = file.working_path()
        output_path = file.working_path()
        file.makeworkingdirs()
        trim(config, input_path, output_path, threshold_dBFS, min_silence_ms)
        logger.info(f"Trimmed: {file.file_path}")

def trim_from_directory(config: AudioProcessConfig, input_directory: str, output_directory: str, threshold_dBFS:float=-50, min_silence_ms:int=250, overwrite: bool = False):
    """
    Trim silent segments from all audio files in the input directory.

    Parameters
    ----------
    input_directory : str
        Input directory containing audio files (*.wav).

    output_directory : str
        Output directory to save trimmed audio files.

    threshold_dBFS : float (default=-50)
        Silence threshold in dBFS.

    min_silence_ms : int (default=250)
        Minimum silence duration in milliseconds.
    """

    process_files: List[ProcessedAudioPath] = ProcessedAudioPath.from_directory(
        input_directory=input_directory,
        output_directory=output_directory,
        overwrite=overwrite
    )
    trim_from_list(config, process_files, threshold_dBFS, min_silence_ms)
