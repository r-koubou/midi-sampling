import json
import math
import os
import sys
import time

import waveprocess.normalize as normalize
import waveprocess.trim as trim

import utility

from device.mididevice import IMidiDevice
from device.MidoMidiDevice import MidoMidiDevice

from device.audiodevice import IAudioDevice, AudioDeviceOption, AudioDataFormat
from device.SdAudioDevice import SdAudioDevice


from appconfig.sampling import SamplingConfig
from appconfig.sampling import load as load_samplingconfig

from appconfig.midi import MidiConfig
from appconfig.midi import load as load_midi_config


THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_output_file_prefix(prefix: str, channel: int, note: int, velocity: int):
    return f"{prefix}_{note}_{velocity}"

def dump_as_json(obj: object) -> str:
    return json.dumps(obj.__dict__, ensure_ascii=False, indent=2)

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

    midi_notes                  = midi_config.midi_notes
    midi_velocities             = midi_config.midi_velocities
    midi_note_duration          = midi_config.midi_note_duration
    midi_pre_duration           = midi_config.midi_pre_wait_duration
    midi_channel                = midi_config.midi_channel
    midi_release_duration       = midi_config.midi_release_duration
    target_peak                 = sampling_config.target_peak
    output_dir                  = midi_config.output_dir
    output_prefix               = midi_config.output_prefix
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
        print("Initialize MIDI")
        midi_device.initialize()

        #---------------------------------------------------------------------------
        # Setup Audio
        #---------------------------------------------------------------------------
        print("Initialize audio")
        audio_device.initialize()

        #region Sampling
        #---------------------------------------------------------------------------
        # Sampling
        #---------------------------------------------------------------------------

        # Send MIDI from file to device before sampling
        if len(pre_send_smf_path_list) > 0:
            for file in pre_send_smf_path_list:
                print(f"Send MIDI from file: {file}")
                midi_device.send_message_from_file(file)

        # Calculate total sampling count
        total_sampling_count = len(midi_notes) * len(midi_velocities)

        os.makedirs(output_dir, exist_ok=True)

        print("Sampling...")

        process_count = 1

        for note in midi_notes:
            for velocity in midi_velocities:
                # Record Audio
                record_duration = math.floor(midi_pre_duration + midi_note_duration + midi_release_duration)

                audio_device.start_recording(record_duration)
                time.sleep(midi_pre_duration)

                # Play MIDI
                print(f"[{process_count: 4d} / {total_sampling_count:4d}] Channel: {midi_channel:2d}, Note: {note:3d}, Velocity: {velocity:3d}")
                midi_device.play_note(midi_channel, note, velocity, midi_note_duration)

                time.sleep(midi_release_duration)

                audio_device.stop_recording()

                # Save Audio
                output_path = os.path.join(output_dir, get_output_file_prefix(output_prefix, midi_channel, note, velocity) + ".wav")
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

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print(f"Usage: python {os.path.basename(__file__)} <path/to/sampling-config.json> <path/to/midi-config.json>")
        sys.exit(1)

    main(sys.argv[1:])
