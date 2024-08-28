from typing import List
import math
import os
import time
from logging import getLogger

import midisampling.waveprocess.normalize as normalize
import midisampling.waveprocess.trim as trim

from midisampling.device.mididevice import IMidiDevice
from midisampling.device.MidoMidiDevice import MidoMidiDevice

from midisampling.device.audiodevice import IAudioDevice, AudioDeviceOption, AudioDataFormat
from midisampling.device.SdAudioDevice import SdAudioDevice


from midisampling.appconfig.sampling import SamplingConfig
from midisampling.appconfig.sampling import load as load_samplingconfig

from midisampling.appconfig.midi import MidiConfig, SampleZone
from midisampling.appconfig.midi import load as load_midi_config

import midisampling.dynamic_format as dynamic_format

from midisampling.exportpath import RecordedAudioPath, ProcessedAudioPath
from midisampling.appconfig.audioprocess import AudioProcessConfig
from midisampling.waveprocess.processing import process as run_postprocess
from midisampling.waveprocess.processing import validate_process_config

import midisampling.notenumber as notenumber_util


THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = getLogger(__name__)


class SamplingArguments:
    """
    Composite of sampling, MIDI, and post process configurations.
    """
    def __init__(self, sampling_config_path: str, midi_config_path: str, postprocess_config_path:str = None, overwrite_recorded: bool = False):
        self.sampling_config_path = sampling_config_path
        self.midi_config_path = midi_config_path
        self.postprocess_config_path = postprocess_config_path
        self.overwrite_recorded = overwrite_recorded

def expand_path_placeholder(format_string:str, pc_msb:int, pc_lsb:int, pc_value, key_root: int, key_low: int, key_high: int, min_velocity:int, max_velocity:int, velocity: int, use_scale_spn_format: bool):
    """
    Expand placeholders in format_string with given values

    Args:
        format_string (str): string.format compatible format string. available placeholders are
            {pc_msb}, {pc_lsb}, {pc},
            {key_root}, {key_low}, {key_high},
            {key_root_scale}, {key_low_scale}, {key_high_scale},
            {velocity}, {min_velocity}, {max_velocity}
            and Python format specifiers are also available.
        pc_msb (int): Program Change MSB
        pc_lsb (int): Program Change LSB
        pc_value: Program Change Value
        key_root (int): Zone: Root key (Send as MIDI note number to device)
        key_low (int): Zone: Low key
        key_high (int): Zone: High key
        min_velocity (int): Velocity Layer: Minimum definition
        max_velocity (int): Velocity Layer: Maximum definition
        velocity (int): Send as MIDI velocity to device
        use_scale_spn_format (bool): True: Scientific pitch notation format, False: Yamaha format

    Returns:
        str: formatted string
    """

    format_value = {
        # MIDI Controll Change
        "pc_msb": pc_msb,
        "pc_lsb": pc_lsb,
        "pc": pc_value,
        # MIDI Note number
        "key_root": key_root,
        "key_low": key_low,
        "key_high": key_high,
        # Note name
        "key_root_scale": notenumber_util.as_scalename(key_root, spn_format=use_scale_spn_format),
        "key_low_scale": notenumber_util.as_scalename(key_low, spn_format=use_scale_spn_format),
        "key_high_scale": notenumber_util.as_scalename(key_high, spn_format=use_scale_spn_format),
        # MIDI Velocity
        "velocity": velocity,
        "min_velocity": min_velocity,
        "max_velocity": max_velocity,
    }

    return dynamic_format.format(format_string=format_string, data=format_value)

def main(args: SamplingArguments) -> None:

    #---------------------------------------------------------------------------
    # Load config values
    #---------------------------------------------------------------------------
    sampling_config: SamplingConfig = load_samplingconfig(args.sampling_config_path)
    midi_config: MidiConfig = load_midi_config(args.midi_config_path)

    postprocess_config: AudioProcessConfig = None
    if args.postprocess_config_path:
        postprocess_config = AudioProcessConfig(args.postprocess_config_path)
        validate_process_config(postprocess_config)

    #---------------------------------------------------------------------------
    # Get config values
    #---------------------------------------------------------------------------

    audio_device_name           = sampling_config.audio_in_device
    audio_device_platform       = sampling_config.audio_in_device_platform
    audio_sample_rate           = sampling_config.audio_sample_rate
    audio_channels              = sampling_config.audio_channels
    audio_data_format           = AudioDataFormat.parse(
                                    f"{sampling_config.audio_sample_bits_format}{sampling_config.audio_sample_bits}"
                                )
    audio_input_ports           = sampling_config.asio_audio_ins

    midi_out_device_name        = sampling_config.midi_out_device
    pre_send_smf_path_list      = midi_config.pre_send_smf_path_list

    program_change_list         = midi_config.program_change_list
    midi_channel                = midi_config.midi_channel
    sample_zone                 = midi_config.sample_zone
    midi_note_duration          = midi_config.midi_note_duration
    midi_pre_duration           = midi_config.midi_pre_wait_duration
    midi_release_duration       = midi_config.midi_release_duration
    output_dir                  = midi_config.output_dir
    output_prefix_format        = midi_config.output_prefix_format
    scale_name_format           = midi_config.scale_name_format
    processed_output_dir        = midi_config.processed_output_dir

    #---------------------------------------------------------------------------
    # MIDI
    #---------------------------------------------------------------------------
    midi_device: IMidiDevice = MidoMidiDevice(midi_out_device_name)

    #---------------------------------------------------------------------------
    # Audio
    #---------------------------------------------------------------------------
    audio_option: AudioDeviceOption = AudioDeviceOption(
        device_name=audio_device_name,
        device_platform=audio_device_platform,
        sample_rate=audio_sample_rate,
        channels=audio_channels,
        data_format=audio_data_format,
        input_ports=audio_input_ports,
    )
    audio_device: IAudioDevice = SdAudioDevice(audio_option)

    try:
        #---------------------------------------------------------------------------
        # Setup MIDI
        #---------------------------------------------------------------------------
        logger.debug("Initialize MIDI")
        midi_device.initialize()

        #---------------------------------------------------------------------------
        # Setup Audio
        #---------------------------------------------------------------------------
        logger.debug("Initialize audio")
        audio_device.initialize()

        #region Sampling
        #---------------------------------------------------------------------------
        # Sampling
        #---------------------------------------------------------------------------

        # Calculate total sampling count
        total_sampling_count = len(program_change_list) * SampleZone.get_total_sample_count(sample_zone)

        if total_sampling_count == 0:
            logger.warning("No sampling target (Sample zone is empty)")
            return

        # Send MIDI from file to device before sampling
        if len(pre_send_smf_path_list) > 0:
            for file in pre_send_smf_path_list:
                logger.info(f"Send MIDI from file: {file}")
                midi_device.send_message_from_file(file)


        os.makedirs(output_dir, exist_ok=True)

        recorded_path_list: List[RecordedAudioPath] = []

        logger.info("Sampling...")

        process_count = 1

        for program in program_change_list:
            # Send program change
            logger.info(f"Program Change - MSB: {program.msb}, LSB: {program.lsb}, Program: {program.program}")
            midi_device.send_progam_change(midi_channel, program.msb, program.lsb, program.program)
            time.sleep(0.5)

            for zone in sample_zone:
                for velocity in zone.velocity_layers:
                    # Record Audio
                    record_duration = math.floor(midi_pre_duration + midi_note_duration + midi_release_duration)

                    audio_device.start_recording(record_duration)
                    time.sleep(midi_pre_duration)

                    # Play MIDI
                    logger.info(f"[{process_count: 4d} / {total_sampling_count:4d}] Note on - Channel: {midi_channel:2d}, Note: {zone.key_root:3d}, Velocity: {velocity.send_velocity:3d} (Key Low:{zone.key_low:3d}, Key High:{zone.key_high:3d}, Min Velocity:{velocity.min_velocity:3d}, Max Velocity:{velocity.max_velocity:3d})")
                    midi_device.play_note(midi_channel, zone.key_root, velocity.send_velocity, midi_note_duration)

                    time.sleep(midi_release_duration)

                    audio_device.stop_recording()

                    # Save Audio
                    output_file_path = expand_path_placeholder(
                        format_string=output_prefix_format,
                        pc_msb=program.msb,
                        pc_lsb=program.lsb,
                        pc_value=program.program,
                        key_root=zone.key_root,
                        key_low=zone.key_low,
                        key_high=zone.key_high,
                        min_velocity=velocity.min_velocity,
                        max_velocity=velocity.max_velocity,
                        velocity=velocity.send_velocity,
                        use_scale_spn_format=scale_name_format == "SPN"
                    )

                    export_path = RecordedAudioPath(base_dir=output_dir, file_path=output_file_path + ".wav")
                    export_path.makedirs()

                    logger.debug(f"  -> Export recorded data to: {export_path.path()}")

                    # Check recorded file has already existed
                    # If over_write_recorded is False, raise exception
                    if not args.overwrite_recorded and os.path.exists(export_path.path()):
                        logger.error(f"Recorded file already exists: {export_path.path()}")
                        logger.error("If you want to overwrite anyway, please set overwrite option.")
                        raise FileExistsError(f"Recorded file already exists: {export_path.path()}")

                    audio_device.export_audio(export_path.path())

                    recorded_path_list.append(export_path)

                    process_count += 1
        #endregion ~Sampling

        #region Post Process

        logger.info("#" * 80)
        logger.info("Post process")
        logger.info("#" * 80)
        run_postprocess(
            config=postprocess_config,
            recorded_files=recorded_path_list,
            output_dir=processed_output_dir
        )
        #endregion ~Post Process

        logger.info("done")

    finally:
        audio_device.dispose() if audio_device else None
        midi_device.dispose() if midi_device else None
