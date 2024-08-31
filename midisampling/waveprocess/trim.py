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


PARAM_KEY_THRESHOLD_DBFS = "threshold_dBFS"
"""
Effect parameter key for threshold_dBFS.
"""

PARAM_KEY_MIN_SILENCE_MS = "min_silence_ms"
"""
Effect parameter key for min_silence_ms.
"""

def __get_threshold_dBFS(effect_parameters: dict) -> float:
    if PARAM_KEY_THRESHOLD_DBFS in effect_parameters:
        return float(effect_parameters[PARAM_KEY_THRESHOLD_DBFS])
    return -50.0

def __get_min_silence_ms(effect_parameters: dict) -> int:
    if PARAM_KEY_MIN_SILENCE_MS in effect_parameters:
        return int(effect_parameters[PARAM_KEY_MIN_SILENCE_MS])
    return 250

def trim(config: AudioProcessConfig, input_path:str, output_path: str, effect_parameters: dict):
    """
    Trim silent segments from the audio file.

    Parameters
    ----------
    input_path : str
        Input audio file path (*.wav).

    output_path : str
        Output audio file path (*.wav).

    effect_parameters : dict
        Effect parameters for trim.
        - threshold_dBFS : float (default=-50.0)
        - min_silence_ms : int (default=250)
    """

    threshold_dBFS = __get_threshold_dBFS(effect_parameters)
    min_silence_ms = __get_min_silence_ms(effect_parameters)

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


def trim_from_list(config: AudioProcessConfig, file_list: List[ProcessedAudioPath], effect_parameters: dict):
    """
    Trim silent segments from all audio files in the input directory.

    Parameters
    ----------
    file_list : List[ProcessedAudioPath]
        List of ProcessedAudioPath instances.

    effect_parameters : dict
        Effect parameters for trim.
        - threshold_dBFS : float (default=-50.0)
        - min_silence_ms : int (default=250)
    """

    if file_list is None:
        raise ValueError("file_list is None")
    if len(file_list) == 0:
        raise ValueError("file_list is empty")

    for file in file_list:
        input_path  = file.working_path()
        output_path = file.working_path()
        file.makeworkingdirs()
        trim(
            config=config,
            input_path=input_path,
            output_path=output_path,
            effect_parameters=effect_parameters
        )
        logger.info(f"Trimmed: {file.file_path}")

def trim_from_directory(config: AudioProcessConfig, input_directory: str, output_directory: str, effect_parameters: dict, overwrite: bool = False):
    """
    Trim silent segments from all audio files in the input directory.

    Parameters
    ----------
    input_directory : str
        Input directory containing audio files (*.wav).

    output_directory : str
        Output directory to save trimmed audio files.

    effect_parameters : dict
        Effect parameters for trim.
        - threshold_dBFS : float (default=-50.0)
        - min_silence_ms : int (default=250)
    """

    process_files: List[ProcessedAudioPath] = ProcessedAudioPath.from_directory(
        input_directory=input_directory,
        output_directory=output_directory,
        overwrite=overwrite
    )

    trim_from_list(
        config=config,
        file_list=process_files,
        effect_parameters=effect_parameters
    )
