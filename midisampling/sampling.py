import json
import math
import os
import sys
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

from midisampling.appconfig.midi import MidiConfig, VelocityLayer, KeyMapUnit
from midisampling.appconfig.midi import load as load_midi_config

import midisampling.dynamic_format as dynamic_format

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = getLogger(__name__)

def get_output_file_prefix(format_string:str, pc_msb:int, pc_lsb:int, pc_value, key_root: int, key_low: int, key_high: int, min_velocity:int, max_velocity:int, velocity: int):
    """
    Get output file prefix from dynamic format string

    Args:
        format_string (str): string.format compatible format string. available placeholders are {pc_msb}, {pc_lsb}, {pc}, {note}, {velocity} and Python format specifiers are also available.
        pc_msb (int): Program Change MSB
        pc_lsb (int): Program Change LSB
        pc_value: Program Change Value
        note (int): MIDI Note
        min_velocity (int): Velocity Layer: Minimum definition
        max_velocity (int): Velocity Layer: Maximum definition
        velocity (int): MIDI Velocity

    Returns:
        str: formatted string
    """
    format_value = {
        "pc_msb": pc_msb,
        "pc_lsb": pc_lsb,
        "pc": pc_value,
        "note": key_root, # deprecated
        "key_root": key_root,
        "key_low": key_low,
        "key_high": key_high,
        "min_velocity": min_velocity,
        "max_velocity": max_velocity,
        "velocity": velocity # deprecated
    }

    return dynamic_format.format(format_string=format_string, data=format_value)

def main(args):

    #---------------------------------------------------------------------------
    # Load config values
    #---------------------------------------------------------------------------
    sampling_config_path = args[0]
    midi_config_path = args[1]
    sampling_config: SamplingConfig = load_samplingconfig(sampling_config_path)
    midi_config: MidiConfig = load_midi_config(midi_config_path)

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
    midi_keymaps                = midi_config.keymaps
    midi_notes                  = midi_config.midi_notes
    midi_velocities             = midi_config.midi_velocity_layers
    midi_note_duration          = midi_config.midi_note_duration
    midi_pre_duration           = midi_config.midi_pre_wait_duration
    midi_release_duration       = midi_config.midi_release_duration
    target_peak                 = sampling_config.target_peak
    output_dir                  = midi_config.output_dir
    output_prefix_format        = midi_config.output_prefix_format
    processed_output_dir        = midi_config.processed_output_dir

    trim_threshold              = sampling_config.trim_threshold
    trim_min_silence_duration   = sampling_config.trim_min_silence_duration

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
        total_sampling_count = len(program_change_list) * len(midi_keymaps)
        for k in midi_keymaps:
            total_sampling_count *= len(k.velocity_layers)

        if total_sampling_count == 0:
            logger.warning("No sampling target (Notes or Velocity Layer in Keymap is empty)")
            return

        # Send MIDI from file to device before sampling
        if len(pre_send_smf_path_list) > 0:
            for file in pre_send_smf_path_list:
                logger.info(f"Send MIDI from file: {file}")
                midi_device.send_message_from_file(file)


        os.makedirs(output_dir, exist_ok=True)

        logger.info("Sampling...")

        process_count = 1

        for program in program_change_list:
            # Send program change
            logger.info(f"Program Change - MSB: {program.msb}, LSB: {program.lsb}, Program: {program.program}")
            midi_device.send_progam_change(midi_channel, program.msb, program.lsb, program.program)
            time.sleep(0.5)

            for keymap in midi_keymaps:
                for velocity in keymap.velocity_layers:
                    # Record Audio
                    record_duration = math.floor(midi_pre_duration + midi_note_duration + midi_release_duration)

                    audio_device.start_recording(record_duration)
                    time.sleep(midi_pre_duration)

                    # Play MIDI
                    logger.info(f"[{process_count: 4d} / {total_sampling_count:4d}] Note on - Channel: {midi_channel:2d}, Note: {keymap.key_root:3d}, Velocity: {velocity.send_velocity:3d} (Key Low:{keymap.key_low:3d}, Key High:{keymap.key_high:3d}, Min Velocity:{velocity.min_velocity:3d}, Max Velocity:{velocity.max_velocity:3d})")
                    midi_device.play_note(midi_channel, keymap.key_root, velocity.send_velocity, midi_note_duration)

                    time.sleep(midi_release_duration)

                    audio_device.stop_recording()

                    # Save Audio
                    output_file_name = get_output_file_prefix(
                        format_string=output_prefix_format,
                        pc_msb=program.msb,
                        pc_lsb=program.lsb,
                        pc_value=program.program,
                        key_root=keymap.key_root,
                        key_low=keymap.key_low,
                        key_high=keymap.key_high,
                        min_velocity=velocity.min_velocity,
                        max_velocity=velocity.max_velocity,
                        velocity=velocity.send_velocity
                    )
                    output_path = os.path.join(output_dir, output_file_name + ".wav")
                    audio_device.export_audio(output_path)

                    process_count += 1
        #endregion ~Sampling

        #region Waveform Processing
        #---------------------------------------------------------------------------
        # Normalize, Trim
        #---------------------------------------------------------------------------
        normalize.normalize_across_mitiple(
            input_directory=output_dir,
            output_directory=processed_output_dir,
            target_peak_dBFS=target_peak
        )

        trim.batch_trim(
            input_directory=processed_output_dir,
            output_directory=processed_output_dir,
            threshold_dBFS=trim_threshold,
            min_silence_ms=trim_min_silence_duration
        )
        #endregion ~Waveform Processing

    finally:
        audio_device.dispose() if audio_device else None
        midi_device.dispose() if midi_device else None
