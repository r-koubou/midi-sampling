from typing import List
from logging import getLogger

from midisampling.appconfig.postprocess import PostProcessConfig
from midisampling.exportpath import PostProcessedAudioPath

from midisampling.waveprocess.normalize import normalize_from_list as normalize
from midisampling.waveprocess.trim import trim_from_list as trim

logger = getLogger(__name__)

def run_postprocess(config: PostProcessConfig, process_files: List[PostProcessedAudioPath]) -> None:

    divider = "-" * 80

    for effect in config.effects:
        name = effect.name
        params = effect.params

        begin_message = f"Begin {name}: {params}"
        end_message   = f"End {name} done"

        logger.info(divider)
        logger.info(begin_message)
        logger.info(divider)

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

        logger.info(end_message)


def validate_postprocess(config: PostProcessConfig) -> None:
    """
    Validate the postprocess configuration values.
    """

    logger.info("Validating postprocess configuration")

    for effect in config.effects:
        name   = effect.name
        params = effect.params
        logger.debug(f"effect: name={name}, params={params}")

        if name == "normalize":
            if "target_db" not in params:
                raise ValueError(f"target_db is required for {name}")
        elif name == "trim":
            if "threshold_db" not in params:
                raise ValueError(f"threshold_db is required for {name}")
            if "min_silence_ms" not in params:
                raise ValueError(f"min_silence_ms is required for {name}")
        else:
            raise ValueError(f"Unknown postprocess name: {name}")
