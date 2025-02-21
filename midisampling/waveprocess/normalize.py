from typing import List

import os
import sys
from logging import getLogger
from pydub import AudioSegment

from midisampling.exportpath import RecordedAudioPath, ProcessedAudioPath
from midisampling.appconfig.audioprocess import AudioProcessConfig

import midisampling.waveprocess.pydubutil as pydubutil

logger = getLogger(__name__)

PARAM_KEY_TARGET_PEAK_DBFS = "target_dBFS"
"""
Effect parameter key for target_dBFS.
"""

def __get_target_peak_dBFS(effect_parameters: dict) -> float:
    if PARAM_KEY_TARGET_PEAK_DBFS in effect_parameters:
        return float(effect_parameters[PARAM_KEY_TARGET_PEAK_DBFS])
    return -1.0

def normalize_from_list(config: AudioProcessConfig, file_list: List[ProcessedAudioPath], effect_parameters: dict):
    """
    Normalize with respect to the highest peak of the audio file(s) in the input directory.

    Parameters
    ----------
    file_list : List[ProcessedAudioPath]
        List of ProcessedAudioPath instances.

    effect_parameters : dict
        Effect parameters for normalize.
        - target_dBFS : float (default=-1.0)
    """

    if file_list is None:
        raise ValueError("file_list is None")
    if len(file_list) == 0:
        raise ValueError("file_list is empty")

    max_peak_dBFS = -sys.float_info.max
    audio_segments = []
    export_parameters = []

    target_dBFS = __get_target_peak_dBFS(effect_parameters)

    pydubutil.to_export_parameters_from_config(config, export_parameters)
    if len(export_parameters) == 0:
        export_parameters = None

    # 全てのファイルの最大ピークレベルを探す
    for file in file_list:
        input_filepath  = file.recorded_audio_path.path()
        output_filepath = file.path()
        audio           = AudioSegment.from_wav(input_filepath)
        peak_dBFS = audio.max_dBFS
        audio = None

        logger.debug(f"wip - {os.path.basename(input_filepath)}: Peak dBFS={peak_dBFS:.3f}")
        if peak_dBFS > max_peak_dBFS:
            max_peak_dBFS = peak_dBFS
            logger.debug(f"wip - Max Peak dBFS Updated={max_peak_dBFS:.3f}")

        audio_segments.append((audio, output_filepath))

    change_in_dBFS = target_dBFS - max_peak_dBFS

    # 各ファイルに対して同じゲインを適用
    for file in file_list:
        input_filepath  = file.working_path()
        output_filepath = file.working_path()
        audio           = AudioSegment.from_wav(input_filepath)

        file.makeworkingdirs()
        normalized_audio = audio.apply_gain(change_in_dBFS)
        normalized_audio.export(output_filepath, format="wav", parameters=export_parameters)

        audio = None
        normalized_audio = None

        logger.info(f"Normalized: file={file.file_path}")

    logger.info(f"Max Peak dBFS={max_peak_dBFS:.3f} dBFS")
    logger.info(f"Target dBFS={target_dBFS:.3f} dBFS")
    logger.info(f"Normalize gain={change_in_dBFS:.3f} dBFS")

def normalize_from_directory(config: AudioProcessConfig, input_directory: str, output_directory: str, effect_parameters: dict, overwrite: bool = False):
    """
    Normalize with respect to the highest peak of the audio file(s) in the input directory.

    Parameters
    ----------
    config : AudioProcessConfig
        Audio processing configuration.

    input_directory : str
        Input directory containing audio files (*.wav).

    output_directory : str
        Output directory to save normalized audio files.

    effect_parameters : dict
        Effect parameters for normalize.
        - target_peak_dBFS : float (default=-1.0)
    """

    process_files: List[ProcessedAudioPath] = ProcessedAudioPath.from_directory(
        input_directory=input_directory,
        output_directory=output_directory,
        overwrite=overwrite
    )

    normalize_from_list(
        config=config,
        file_list=process_files,
        effect_parameters=effect_parameters
    )
