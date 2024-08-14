midi-sampling
================


## Overview

`midi-sampling` performs sampling from external MIDI sound sources. It allows you to specify arbitrary MIDI notes and velocities to control MIDI devices and carry out sampling.

Since it operates from a console, it is lightweight and can automate sampling processes.

## Requirements

- Windows OS with Python 3.12 or later
  - It might also work on macOS, but this has not been verified.
- [pipenv](https://github.com/pypa/pipenv)
- [ffmpeg](https://www.ffmpeg.org/)

## Setup

### Installing pipenv

https://github.com/pypa/pipenv?tab=readme-ov-file#installation

### Installing dependencies

Navigate to the project directory and run the following command:

```bash
pipenv install
```

### Installing ffmpeg

https://www.ffmpeg.org/download.html

After installation, add the directory containing `ffmpeg.exe` to the environment variable `PATH`.

## How to Run

### Activating the pipenv environment

Navigate to the project directory and run the following command:

```bash
pipenv shell
```

If the prompt on the left side appears as `(midi-sampling)`, you are inside the pipenv environment.

```bash
(midi-sampling) C:\Path\To\Project\midi-sampling>
~~~~~~~~~~~~~~~
```

### Executing the Sampling

Run the following command:

```bash
python python midisampling/sampling.py <sampling-config-file.json> <MIDI-config-file.json>
```

### Listing Devices

Run the following command:

```bash
python python midisampling/devicelist.py
```

#### Output example

```bash
+------------------------------------------------------+
|                    Audio Devices                     |
+--------------------------------+---------------------+
| Name                           | Platform            |
+--------------------------------+---------------------+
| Line(Steinberg UR28M)          | Windows WDM-KS      |
| Microsoft Sound Mapper - Input | MME                 |
| Primary Sound Capture Driver   | Windows DirectSound |
| UR28M In (Steinberg UR28M)     | MME                 |
| UR28M In (Steinberg UR28M)     | Windows DirectSound |
| UR28M In (Steinberg UR28M)     | Windows WASAPI      |
| Yamaha Steinberg USB ASIO      | ASIO                |
+--------------------------------+---------------------+
+------------------------------+
|         MIDI Devices         |
+------------------------------+
| Name                         |
+------------------------------+
| Impact GX Mini               |
| Microsoft GS Wavetable Synth |
| MIDIOUT2 (Impact GX Mini)    |
| Roland SC-8850 MIDI OUT 1    |
| Roland SC-8850 MIDI OUT 2    |
| Roland SC-8850 PART A        |
| Roland SC-8850 PART B        |
| Roland SC-8850 PART C        |
| Roland SC-8850 PART D        |
+------------------------------+
```

## Configuration Files

Sample files, `sampling-config.json` and `midi-config.example.json`, are included. Please adjust the settings according to your environment.

### Sampling Configuration File

This is written in JSON format.

```json
{
    "audio_channels": 2,
    "audio_sample_rate": 48000,
    "audio_sample_bits": 16,
    "audio_sample_bits_format": "int",
    "audio_in_device": "Yamaha Steinberg USB ASIO",
    "use_asio": true,
    "asio_audio_ins": [
        2, 3
    ],
    "midi_out_device": "Roland SC-8850 PART A",
    "target_peak": -8,
    "trim_threshold": -60,
    "trim_min_silence_duration": 250
}
```

- `audio_channels`
  - Number of channels in the sampled audio file.
- `audio_sample_rate`
  - Sampling rate of the audio file.
- `audio_sample_bits`
  - Bit depth of the sampled audio file.
- `audio_sample_bits_format`
  - Format of the bit depth of the sampled audio file (`int` or `float`).
- `audio_in_device`
  - `name`
    - Name of the input device for the sampled audio file.
  - `platform`
    - Platform of the input device for the sampled audio file (e.g., `ASIO`, `MME`, `Windows DirectSound`, `Windows WASAPI`, `Core Audio` etc.).
  - Run the `List Devices` command to specify the device name and platform to use.
- `asio_audio_ins` (when using ASIO device)
  - List of ASIO input channel numbers.
  - Specify the input channel numbers of your device. The format starts from 0 (e.g., to use inputs 1 and 2, specify `[0, 1]`).
- `midi_out_device`
  - Name of the MIDI device used for sampling.
  - Run the `List Devices` command to specify the device name to use.
- `target_peak`
  - Peak level (in dB) for the sampled audio file.
  - Normalization is performed based on the peak level across the entire sampled file.
- `trim_threshold`
  - Threshold (in dB) for trimming silence.
- `trim_min_silence_duration`
  - Minimum duration (in ms) of silence to be trimmed.

### MIDI Configuration File

This is written in JSON format.

```json
{
    "output_dir": "_recorded",
    "processed_output_dir": "_recorded/_processed",
    "output_prefix": "piano",
    "midi_channel": 0,
    "midi_notes": [
        40
    ],
    "midi_velocities": [
        127
    ],
    "midi_pre_wait_duration": 0.6,
    "midi_note_duration": 2,
    "midi_release_duration": 1.5
}
```

- `output_dir`
  - Directory for the output of the sampled audio files.
- `processed_output_dir`
  - Directory for the output of processed sampled audio files.
- `output_prefix`
  - Prefix for the filenames of the sampled audio files.
- `midi_channel`
  - MIDI channel number for sampling (`0`-`15`).
- `midi_notes`
  - List of MIDI note numbers to be sampled (`0`-`127`).
- `midi_velocities`
  - List of MIDI velocities to be sampled (`0`-`127`).
- `midi_pre_wait_duration`
  - Pre-wait time (in seconds) before sampling.
  - A value of 0.6 or higher is recommended.
- `midi_note_duration`
  - Length of the MIDI note to be sampled (in seconds). Only integer values can be specified.
- `midi_release_duration`
  - Wait time (in seconds) after the release of the sampled MIDI note. Only integer values can be specified.