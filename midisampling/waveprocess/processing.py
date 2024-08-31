from typing import List, Dict
import os
import sys
import json
import jsonschema
import pathlib
import tempfile
from logging import getLogger
import argparse
import traceback

from midisampling.appconfig.audioprocess import AudioProcessConfig
from midisampling.exportpath import RecordedAudioPath, ProcessedAudioPath

from midisampling.waveprocess.normalize import normalize_from_list as normalize
from midisampling.waveprocess.trim import trim_from_list as trim

from midisampling.waveprocess.wavchunkkeeper import WavChunkKeeper

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

logger = getLogger(__name__)

def process(config: AudioProcessConfig, recorded_files: List[RecordedAudioPath], output_dir: str) -> None:
    if not config:
        logger.info("Process config is not set. Skip post process.")
        return
    logger.debug(f"Process config: {config}")

    with tempfile.TemporaryDirectory() as working_dir:
        logger.info("Build processed audio files path list")
        logger.debug(f"Working directory: {working_dir}")

        process_files: List[ProcessedAudioPath] = []
        wav_chunk_keepers: List[WavChunkKeeper] = []

        for x in recorded_files:
            # Configure the export path information
            export_path = ProcessedAudioPath(
                recorded_audio_path=x,
                output_dir=output_dir,
                working_dir=working_dir,
                overwrite=True # Overwrite via effect chain
            )
            process_files.append(export_path)

            # Keep the original wav chunks
            keeper = WavChunkKeeper(
                source_path=x.path(),
                target_path=export_path.working_path(),
                keep_chunk_names=config.keep_wav_chunks
            )
            wav_chunk_keepers.append(keeper)

            logger.debug(f"Process export path: {export_path}")

        # Copy recorded files to working directory to process
        logger.info("Copy recorded files to working directory")
        for x in recorded_files:
            logger.info(f"{x.file_path}")
            x.copy_to(working_dir)

        # Procssing
        logger.info("Processing...")
        _process_impl(
            config=config,
            process_files=process_files
        )

        # Restore original wav chunks
        logger.info("Restore original wav chunks which removed by the process")
        for x in wav_chunk_keepers:
            logger.debug(f"Restore wav chunks: {x.source_path}")
            x.restore()

        # Finally, copy processed files in working directory to output directory
        logger.info(f"Copy processed files to output directory ({output_dir})")
        for x in process_files:
            x.copy_working_to(output_dir)

def _process_impl(config: AudioProcessConfig, process_files: List[ProcessedAudioPath]) -> None:

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
                config=config,
                file_list=process_files,
                target_peak_dBFS=float(params["target_db"])
            )
        elif name == "trim":
            trim(
                config=config,
                file_list=process_files,
                threshold_dBFS=float(params["threshold_db"]),
                min_silence_ms=int(params["min_silence_ms"])
            )
        else:
            raise ValueError(f"Unknown processing name: {name}")

        logger.info(end_message)


def validate_effect_config(config: AudioProcessConfig) -> None:
    """
    Validate individual effect configuration.
    """

    def validate_parameter(parameter_json: dict, schema: dict):
        jsonschema.validate(parameter_json, schema)

    directory = pathlib.Path(THIS_SCRIPT_DIR)
    schema_file_path_list = directory.glob(f"**/*.schema.json")

    schema_table: Dict[str, dict] = {}
    for file in schema_file_path_list:
        with open(file, "r") as f:
            schema = json.load(f)

        title = str(schema["title"]).lower()
        schema_table[title] =  schema

    for effect in config.effects:
        name   = effect.name
        params = effect.params

        logger.debug(f"process: name={name}, params={params}")

        if name not in schema_table:
            raise ValueError(f"Unknown process name: {name}")

        validate_parameter(params, schema_table[name])

        logger.info(f"Validation OK: {name}")

def main() -> None:
    from midisampling.logging_management import init_logging_as_stdout

    parser = argparse.ArgumentParser(prog=f"python -m {__package__}")
    parser.add_argument("-v", "--verbose", help="Enable verbose logging.", action="store_true")
    parser.add_argument("processing_config_path", help="Path to the processing configuration file.")

    args = parser.parse_args()

    init_logging_as_stdout(args.verbose)

    logger.info(f"Configuration file: {args.processing_config_path}")

    try:
        process_config = AudioProcessConfig(args.processing_config_path)
        validate_effect_config(process_config)
        logger.info("All validation passed.")
    except Exception as e:
        print(e)
        if args.verbose:
            (_, _, trace) = sys.exc_info()
            traceback.print_tb(trace)

    return

if __name__ == '__main__':
    main()
