"""
Utility functions for pydub.
"""

from typing import List
from logging import getLogger

from midisampling.appconfig.audioprocess import AudioProcessConfig

logger = getLogger(__name__)

def to_export_parameters_from_config(config: AudioProcessConfig, dest: List[str]) -> None:
    """
    Create AudioSegment.export() argumet `parameters` from AudioProcessConfig.
    """

    if not config.format:
        return

    bit_depth = config.format.bit_depth

    if bit_depth == "int16":
        dest.append("-acodec")
        dest.append("pcm_s16le")
    elif bit_depth == "int24":
        dest.append("-acodec")
        dest.append("pcm_s24le")
    elif bit_depth == "int32":
        dest.append("-acodec")
        dest.append("pcm_s32le")
    elif bit_depth == "float32":
        dest.append("-acodec")
        dest.append("pcm_f32le")

    logger.debug(f"Export parameters for AudioSegment.export(parameters={dest})")
