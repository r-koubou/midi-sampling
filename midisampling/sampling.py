import math
import os
import sys
import time
import numpy as np
import rtmidi
import sounddevice as sd
import wave

import normalize
import trim

import config as cfg


THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_output_file_prefix(config: cfg.SamplingConfig, channel: int, note: int, velocity: int):
    return f"{config.sampling_file_name_base}_{note}_{velocity}"

def play_note(midiout, channel, note, velocity, duration):
    MIDI_ON  = 0x90
    MIDI_OFF = 0x80

    note_on = [MIDI_ON + channel - 1, note, velocity]
    midiout.send_message(note_on)
    time.sleep(duration)
    note_off = [MIDI_OFF + channel - 1, note, 0]
    midiout.send_message(note_off)

def main(args):

    config_common_path = args[0]
    config_path = args[1]
    common_config: cfg.CommonConfig = cfg.load_sampling_config(config_common_path)
    config: cfg.MidiConfig = cfg.load_midi_config(config_path)

    #---------------------------------------------------------------------------
    # MIDI
    #---------------------------------------------------------------------------
    midiout = rtmidi.MidiOut()
    available_midi_ports = midiout.get_ports()

    #---------------------------------------------------------------------------
    # Audio
    #---------------------------------------------------------------------------
    audio_channels    = common_config.audio_channels
    audio_samplerate  = common_config.audio_sample_rate
    audio_bits        = common_config.audio_sample_bits
    audio_bits_format = common_config.audio_sample_bits_format

    sd_format_table = {
        "int8": np.int8,
        "int16": np.int16,
        "int32": np.int32,
        "float32": np.float32,
        "float64": np.float64
    }
    sd_format = sd_format_table.get(f"{audio_bits}{audio_bits_format}", np.int32)

    try:
        #region Setup MIDI
        #---------------------------------------------------------------------------
        # Setup MIDI
        #---------------------------------------------------------------------------
        midiout_port = -1
        if not available_midi_ports:
            print("No MIDI devices found")
            sys.exit(1)
        for note, x in enumerate(available_midi_ports):
            if x.find(common_config.midi_out_device) != -1:
                midiout_port = note
                break
        if midiout_port == -1:
            print("No MIDI devices found")
            sys.exit(1)

        midiout.open_port(midiout_port)
        #endregion ~Setup MIDI

        #region Setup Audio
        #---------------------------------------------------------------------------
        # Setup Audio
        #---------------------------------------------------------------------------
        audio_devices = sd.query_devices()

        audio_in_device_id = -1
        for note, x in enumerate(audio_devices):
            if x["name"].find(common_config.audio_in_device) != -1:
                audio_in_device_id = note
                break
        if audio_in_device_id == -1:
            print("No Audio in device found")
            sys.exit(1)

        print("initialize audio")
        sd.default.device       = [audio_in_device_id, None] # input, output. (Use input only)
        sd.default.dtype        = sd_format
        sd.default.samplerate   = audio_samplerate
        sd.default.channels     = audio_channels
        if common_config.use_asio:
            asio_in = sd.AsioSettings(channel_selectors=common_config.asio_audio_ins)
            sd.default.extra_settings = asio_in
        #endregion ~Setup Audio

        common_config.dump()
        config.dump()

        sampling_midi_notes                 = config.sampling_midi_notes
        sampling_midi_velocities            = config.sampling_midi_velocities
        sampling_midi_note_duration         = config.sampling_midi_note_duration
        sampling_midi_pre_duration          = config.sampling_midi_pre_wait_duration
        sampling_midi_channel               = config.sampling_midi_channel
        sampling_midi_release_duration      = config.sampling_midi_release_duration
        sampling_target_peak                = common_config.sampling_target_peak
        sampling_output_dir                 = config.sampling_output_dir
        sampling_processed_output_dir       = config.sampling_processed_output_dir
        sampling_trim_threshold             = common_config.sampling_trim_threshold
        sampling_trim_min_silence_duration  = common_config.sampling_trim_min_silence_duration

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

                recorded = sd.rec(record_duration * audio_samplerate) # 録音時間を指定する必要がある seconds * samplerate
                time.sleep(sampling_midi_pre_duration)

                # Play MIDI
                print(f"[{process_count: 4d} / {total_sampling_count:4d}] Channel: {sampling_midi_channel:2d}, Note: {note:3d}, Velocity: {velocity:3d}")
                play_note(midiout, sampling_midi_channel, note, velocity, sampling_midi_note_duration)

                time.sleep(sampling_midi_release_duration)

                sd.wait()

                # Save Audio
                output_path = os.path.join(sampling_output_dir, get_output_file_prefix(config, sampling_midi_channel, note, velocity) + ".wav")
                with wave.open(output_path, "wb") as f:
                    f.setnchannels(audio_channels)
                    f.setsampwidth(audio_bits // 8)
                    f.setframerate(audio_samplerate)
                    f.writeframes(recorded)

                process_count += 1
        #endregion ~Sampling

        #region Waveform Processing
        #---------------------------------------------------------------------------
        # Normalize, Trim
        #---------------------------------------------------------------------------
        normalize.normalize_to_peak_level(
            input_directory=sampling_output_dir,
            output_directory=sampling_processed_output_dir,
            target_peak_dBFS=sampling_target_peak)

        trim.batch_trim(
            input_directory=sampling_processed_output_dir,
            output_directory=sampling_processed_output_dir,
            threshold_dBFS=sampling_trim_threshold,
            min_silence_ms=sampling_trim_min_silence_duration
        )
        #endregion ~Waveform Processing

    finally:
        del midiout

if __name__ == "__main__":

    if len(sys.argv) < 3:
        print(f"Usage: python {os.path.basename(__file__)} <path/to/sampling-config.json> <path/to/midi-config.json>")
        sys.exit(1)

    main(sys.argv[1:])
