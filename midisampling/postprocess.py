from typing import List
from logging import getLogger

from midisampling.appconfig.postprocess import PostProcessConfig
from midisampling.exportpath import PostProcessedAudioPath

from midisampling.waveprocess.normalize import normalize_from_list as normalize
from midisampling.waveprocess.trim import trim_from_list as trim

logger = getLogger(__name__)

def run_postprocess(config: PostProcessConfig, process_files: List[PostProcessedAudioPath]) -> None:

    for effect in config.effects:
        name = effect.name
        params = effect.params
        logger.debug(f"effect: name={name}, params={params}")

        if name == "normalize":
            normalize(
                file_list=process_files,
                target_peak_dBFS=float(params["target_db"])
            )
        elif name == "trim":
            trim(
                file_list=process_files,
                threshold_dBFS=float(params["threshold_db"]),
                min_silence_ms=int(params["min_silence_ms"])
            )
        else:
            raise ValueError(f"Unknown postprocess name: {name}")
