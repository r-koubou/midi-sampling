import json
import math
import os
import sys
import time

import waveprocess.normalize as normalize
import waveprocess.trim as trim

import utility

from device.mididevice import IMidiDevice
from device.RtmidiMidiDevice import RtmidiMidiDevice

from device.audiodevice import IAudioDevice, AudioDeviceOption, AudioDataFormat
from device.SdAudioDevice import SdAudioDevice


from appconfig.sampling import SamplingConfig
from appconfig.sampling import load as load_samplingconfig

from appconfig.midi import MidiConfig
from appconfig.midi import load as load_midi_config


THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_output_file_prefix(config: SamplingConfig, channel: int, note: int, velocity: int):
    return f"{config.sampling_file_name_base}_{note}_{velocity}"

def dump_as_json(obj: object) -> str:
    return json.dumps(obj.__dict__, ensure_ascii=False, indent=2)

def main(args):

    config_common_path = args[0]
    config_path = args[1]
    common_config: SamplingConfig = load_samplingconfig(config_common_path)
    config: MidiConfig = load_midi_config(config_path)
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
    print(utility.as_json_structure(sampling_config))
    print(utility.as_json_structure(midi_config))

    sampling_midi_notes                 = midi_config.sampling_midi_notes
    sampling_midi_velocities            = midi_config.sampling_midi_velocities
    sampling_midi_note_duration         = midi_config.sampling_midi_note_duration
    sampling_midi_pre_duration          = midi_config.sampling_midi_pre_wait_duration
    sampling_midi_channel               = midi_config.sampling_midi_channel
    sampling_midi_release_duration      = midi_config.sampling_midi_release_duration
    sampling_target_peak                = sampling_config.sampling_target_peak
    sampling_output_dir                 = midi_config.sampling_output_dir
    sampling_processed_output_dir       = midi_config.sampling_processed_output_dir
    sampling_trim_threshold             = sampling_config.sampling_trim_threshold
    sampling_trim_min_silence_duration  = sampling_config.sampling_trim_min_silence_duration

    #---------------------------------------------------------------------------
    # MIDI
    #---------------------------------------------------------------------------
    midi_device: IMidiDevice = RtmidiMidiDevice(common_config.midi_out_device)

    #---------------------------------------------------------------------------
    # Audio
    #---------------------------------------------------------------------------
    audio_data_format: AudioDataFormat = AudioDataFormat.parse(
        f"{common_config.audio_sample_bits_format}{common_config.audio_sample_bits}"
    )

    audio_option: AudioDeviceOption = AudioDeviceOption(
        device_name=common_config.audio_in_device,
        sample_rate=common_config.audio_sample_rate,
        channels=common_config.audio_channels,
        data_format=audio_data_format,
        input_ports=common_config.asio_audio_ins,
        use_asio=common_config.use_asio
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
        total_sampling_count = len(config.sampling_midi_notes) * len(config.sampling_midi_velocities)

        os.makedirs(sampling_output_dir, exist_ok=True)

        print("Sampling...")

        process_count = 1

        for note in sampling_midi_notes:
            for velocity in sampling_midi_velocities:
                # Record Audio
                record_duration = math.floor(sampling_midi_pre_duration + sampling_midi_note_duration + sampling_midi_release_duration)

                audio_device.start_recording(record_duration)
                time.sleep(sampling_midi_pre_duration)

                # Play MIDI
                print(f"[{process_count: 4d} / {total_sampling_count:4d}] Channel: {sampling_midi_channel:2d}, Note: {note:3d}, Velocity: {velocity:3d}")
                midi_device.play_note(sampling_midi_channel, note, velocity, sampling_midi_note_duration)

                time.sleep(sampling_midi_release_duration)

                audio_device.stop_recording()

                # Save Audio
                output_path = os.path.join(sampling_output_dir, get_output_file_prefix(config, sampling_midi_channel, note, velocity) + ".wav")
                audio_device.export_audio(output_path)

                process_count += 1
        #endregion ~Sampling

        #region Waveform Processing
        #---------------------------------------------------------------------------
        # Normalize, Trim
        #---------------------------------------------------------------------------
        normalize.normalize_across_mitiple(
            input_directory=sampling_output_dir,
            output_directory=sampling_processed_output_dir,
            target_peak_dBFS=sampling_target_peak
        )

        trim.batch_trim(
            input_directory=sampling_processed_output_dir,
            output_directory=sampling_processed_output_dir,
            threshold_dBFS=sampling_trim_threshold,
            min_silence_ms=sampling_trim_min_silence_duration
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
