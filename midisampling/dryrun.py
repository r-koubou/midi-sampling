from typing import List
import math
import os
import time
from logging import getLogger

from midisampling.appconfig.sampling import SamplingConfig
from midisampling.appconfig.sampling import load as load_samplingconfig

from midisampling.appconfig.midi import MidiConfig, SampleZone
from midisampling.appconfig.midi import load as load_midi_config

from midisampling.exportpath import RecordedAudioPath, ProcessedAudioPath

from midisampling.sampling import SamplingArguments, expand_path_placeholder


THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = getLogger(__name__)

def execute(args: SamplingArguments):
    """
    Dry run the sampling process. This will load configuration files.
    But print out the sampling process without actually doing it.
    """

    #---------------------------------------------------------------------------
    # Load config values
    #---------------------------------------------------------------------------
    sampling_config: SamplingConfig = load_samplingconfig(args.sampling_config_path)
    midi_config: MidiConfig = load_midi_config(args.midi_config_path)

    total_sampling_count = len(midi_config.program_change_list) * SampleZone.get_total_sample_count(midi_config.sample_zone)
    process_count = 1

    recorded_path_list: List[RecordedAudioPath] = []

    try:
        for program in midi_config.program_change_list:
            for zone in midi_config.sample_zone:
                for velocity in zone.velocity_layers:

                    output_file_path = expand_path_placeholder(
                        format_string=midi_config.output_prefix_format,
                        pc_msb=program.msb,
                        pc_lsb=program.lsb,
                        pc_value=program.program,
                        key_root=zone.key_root,
                        key_low=zone.key_low,
                        key_high=zone.key_high,
                        min_velocity=velocity.min_velocity,
                        max_velocity=velocity.max_velocity,
                        velocity=velocity.send_velocity,
                        use_scale_spn_format=midi_config.scale_name_format == "SPN"
                    )

                    export_path = RecordedAudioPath(base_dir=midi_config.output_dir, file_path=output_file_path + ".wav")

                    logger.info(f"[{process_count:4d}/{total_sampling_count:4d}] Export recorded data to: {export_path.path()}")

                    # Check recorded file has already existed
                    # If over_write_recorded is False, raise exception
                    if not args.overwrite_recorded and export_path in recorded_path_list:
                        raise FileExistsError(f"Recorded file already exists. Duplecate sample zone(s) {export_path.path()}")

                    recorded_path_list.append(export_path)
                    process_count += 1

        logger.info(f"Dry run successed.")

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        logger.error(f"Dry run failed.")
