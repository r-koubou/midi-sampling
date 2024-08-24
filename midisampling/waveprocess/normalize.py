from typing import List

import os
import pathlib
from logging import getLogger
from pydub import AudioSegment

from midisampling.exportpath import RecordedAudioPath, PostProcessedAudioPath

logger = getLogger(__name__)

def normalize_from_list(file_list: List[PostProcessedAudioPath], target_peak_dBFS:float =-1.0):
    """
    Normalize with respect to the highest peak of the audio file(s) in the input directory.

    Parameters
    ----------
    file_list : List[PostProcessedAudioPath]
        List of PostProcessedAudioPath instances.

    target_peak_dBFS : float (default=-1.0)
    """

    if file_list is None:
        raise ValueError("file_list is None")
    if len(file_list) == 0:
        raise ValueError("file_list is empty")

    max_peak_dBFS = None
    audio_segments = []

    # 全てのファイルの最大ピークレベルを探す
    for file in file_list:
        input_filepath  = file.recorded_audio_path.path()
        output_filepath = file.path()
        audio           = AudioSegment.from_wav(input_filepath)
        peak_dBFS = audio.max_dBFS
        audio = None

        if max_peak_dBFS is None or peak_dBFS > max_peak_dBFS:
            max_peak_dBFS = peak_dBFS

        audio_segments.append((audio, output_filepath))

    change_in_dBFS = target_peak_dBFS - max_peak_dBFS

    # 各ファイルに対して同じゲインを適用
    for file in file_list:
        input_filepath  = file.working_path()
        output_filepath = file.working_path()
        audio           = AudioSegment.from_wav(input_filepath)

        file.makeworkingdirs()
        normalized_audio = audio.apply_gain(change_in_dBFS)
        normalized_audio.export(output_filepath, format="wav")

        audio = None
        normalized_audio = None

        logger.info(f"Normalized: file={file.file_path}")

    logger.info(f"Normalize gain={change_in_dBFS:.3f} dBFS")

def normalize_from_directory(input_directory: str, output_directory: str, target_peak_dBFS:float =-1.0, overwrite: bool = False):
    """
    Normalize with respect to the highest peak of the audio file(s) in the input directory.

    Parameters
    ----------
    input_directory : str
        Input directory containing audio files (*.wav).

    output_directory : str
        Output directory to save normalized audio files.

    target_peak_dBFS : float (default=-1.0)
    """

    process_files: List[PostProcessedAudioPath] = PostProcessedAudioPath.from_directory(
        input_directory=input_directory,
        output_directory=output_directory,
        overwrite=overwrite
    )

    normalize_from_list(process_files, target_peak_dBFS)
