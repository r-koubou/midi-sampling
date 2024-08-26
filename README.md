midi-sampling
================

[日本語](README_ja.md)

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
python -m midisampling <sampling-config-file.json> <MIDI-config-file.json>
```

### Listing Devices

Run the following command:

```bash
python -m midisampling.device
```

#### Output example

```
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

<!-- [BEGIN] Generated by documenttool/jsonschema_to_markdown.py -->
### Sampling Configuration

*Configuration for device, sampling.*

#### Properties

- **`audio_channels`** *(integer, required)*: Number of channels in the sampled audio file.
- **`audio_sample_rate`** *(integer, required)*: Sampling rate of the audio file.
- **`audio_sample_bits`** *(integer, required)*: Bit depth of the sampled audio file. Must be one of: `[16, 32]`.
- **`audio_sample_bits_format`** *(string, required)*: Format of the bit depth of the sampled audio file. Must be one of: `["int", "float"]`.
- **`audio_in_device`** *(object, required)*
  - **`name`** *(string, required)*: Name of the input device for the sampled audio file.
  - **`platform`** *(string, required)*: Platform of the input device for the sampled audio file (e.g., `ASIO`, `MME`, `Windows DirectSound`, `Windows WASAPI`, `Core Audio` etc.).
- **`asio_audio_ins`** *(array)*: Default: `[]`.
  - **Items** *(integer)*: List of ASIO input channel numbers. Specify the input channel numbers of your device. The format starts from 0 (e.g., to use inputs 1 and 2, specify `[0, 1]`).
- **`midi_out_device`** *(string, required)*: Name of the MIDI device used for sampling.
#### Examples

  ```json
  {
      "audio_channels": 2,
      "audio_sample_rate": 48000,
      "audio_sample_bits": 32,
      "audio_sample_bits_format": "int",
      "audio_in_device": {
          "name": "Yamaha Steinberg USB ASIO",
          "platform": "ASIO"
      },
      "asio_audio_ins": [
          2,
          3
      ],
      "midi_out_device": "Roland SC-8850 PART A"
  }
  ```

### MIDI Sampling Configuration

*Structure of the MIDI sampling configuration.*

#### Definitions

- <a id="definitions/def_midi_config"></a>**`def_midi_config`** *(object)*: The main configuration body. Cannot contain additional properties.
  - **`output_dir`** *(string, required)*: Directory for the output of the sampled audio files.
  - **`processed_output_dir`** *(string, required)*: Directory for the output of processed sampled audio files.
  - **`output_prefix_format`** *(string)*: Prefix for the filenames of the sampled audio files. The following placeholders can be used: {pc_msb}, {pc_lsb}, {pc}, {key_root}, {key_low}, {key_high}, {key_root_scale}, {key_low_scale}, {key_high_scale}, {min_velocity} {max_velocity} {velocity}. Default: `"{pc}_{pc_msb}_{pc_lsb}_{key_root}_{velocity}"`.
  - **`scale_name_format`** *(string)*: Format for representation by keyscale name, e.g. Scientific pitch notation with C3 = 60 or Yamaha method with C4 = 60. Works as a placeholder replacement. Must be one of: `["SPN", "Yamaha"]`. Default: `"Yamaha"`.
  - **`pre_send_smf_path_list`** *(array)*: These file(s) will be sent to the MIDI device before sampling once e.g. GM Reset, CC Reset, etc. Default: `[]`.
    - **Items** *(string)*: Path to the SMF(*.mid/*.midi) file(s).
  - **`midi_channel`** *(integer, required)*: MIDI channel number for sampling. Minimum: `0`. Maximum: `15`.
  - **`midi_program_change_list`** *(array, required)*: List of MIDI program change (MSB, LSB, Program No) for sampling.
    - **Items** *(object)*: Cannot contain additional properties.
      - **`msb`** *(integer)*: MSB value for the MIDI program change. Minimum: `0`. Maximum: `127`.
      - **`lsb`** *(integer)*: LSB value for the MIDI program change. Minimum: `0`. Maximum: `127`.
      - **`program`** *(integer)*: Program number for the MIDI program change. Minimum: `0`. Maximum: `127`.
  - **`velocity_layers_presets`** *(array)*: List of velocity layers presets. In addition to defining individual layers with `sample_zone_complex` and `sample_zone`, you can also refer to this preset by ID.
    - **Items**: Refer to *[#/definitions/def_velocity_layers_preset](#definitions/def_velocity_layers_preset)*.
  - **`sample_zone_complex`** *(array)*: List of keymaps for the sampled MIDI notes.
    - **Items**: Refer to *[#/definitions/def_sample_zone_complex](#definitions/def_sample_zone_complex)*.
  - **`sample_zone`** *(array)*: List of keymaps for the sampled MIDI notes.
    - **Items**: Refer to *[#/definitions/def_sample_zone](#definitions/def_sample_zone)*.
  - **`midi_pre_wait_duration`** *(number, required)*: Pre-wait time (in seconds) before sampling. A value of `0.6` or higher is recommended.
  - **`midi_note_duration`** *(number, required)*: Length of the MIDI note to be sampled (in seconds).
  - **`midi_release_duration`** *(number, required)*: Wait time (in seconds) after the release of the sampled MIDI note. Only integer values can be specified.

  Examples:
  ```json
  {
      "output_dir": "_recorded",
      "processed_output_dir": "_processed",
      "output_prefix_format": "{pc}_{pc_msb}_{pc_lsb}_{key_root}_{key_low}_{key_high}_{velocity}_{min_velocity}_{max_velocity}",
      "pre_send_smf_path_list": [
          "GS_Reset.mid",
          "Reverb_Chorus_Delay_Set_0.mid"
      ],
      "midi_channel": 0,
      "midi_program_change_list": [
          {
              "msb": 0,
              "lsb": 0,
              "program": 48
          }
      ],
      "velocity_layers_presets": [
          {
              "id": 0,
              "velocities": [
                  {
                      "min": 0,
                      "max": 31,
                      "send": 31
                  },
                  {
                      "min": 32,
                      "max": 63,
                      "send": 63
                  },
                  {
                      "min": 64,
                      "max": 95,
                      "send": 95
                  },
                  {
                      "min": 96,
                      "max": 127,
                      "send": 127
                  }
              ]
          }
      ],
      "sample_zone_complex": [
          {
              "key_low": 0,
              "key_high": 32,
              "key_root": 16,
              "velocity_layers": [
                  {
                      "min": 0,
                      "max": 31,
                      "send": 31
                  },
                  {
                      "min": 32,
                      "max": 63,
                      "send": 63
                  },
                  {
                      "min": 64,
                      "max": 95,
                      "send": 95
                  },
                  {
                      "min": 96,
                      "max": 127,
                      "send": 127
                  }
              ]
          },
          {
              "key_low": 32,
              "key_high": 64,
              "key_root": 48,
              "velocity_layers_preset_id": 0
          }
      ],
      "sample_zone": [
          {
              "keys": {
                  "from": 40,
                  "to": 40
              },
              "velocity_layers": [
                  {
                      "min": 0,
                      "max": 31,
                      "send": 31
                  },
                  {
                      "min": 32,
                      "max": 63,
                      "send": 63
                  },
                  {
                      "min": 64,
                      "max": 95,
                      "send": 95
                  },
                  {
                      "min": 96,
                      "max": 127,
                      "send": 127
                  }
              ]
          },
          {
              "keys": {
                  "from": 41,
                  "to": 41
              },
              "velocity_layers_preset_id": 0
          }
      ],
      "midi_pre_wait_duration": 0.6,
      "midi_note_duration": 2.5,
      "midi_release_duration": 1.5
  }
  ```

- <a id="definitions/def_midi_message_byte"></a>**`def_midi_message_byte`** *(integer)*: Represents the value of the MIDI message byte (0-127). Minimum: `0`. Maximum: `127`.
- <a id="definitions/def_integer_range"></a>**`def_integer_range`** *(object)*: Represents an integer value range. Cannot contain additional properties.
  - **`from`** *(integer, required)*
  - **`to`** *(integer, required)*

  Examples:
  ```json
  {
      "from": 10,
      "to": 100
  }
  ```

- <a id="definitions/def_midi_message_byte_range"></a>**`def_midi_message_byte_range`** *(object)*: Represents the value range (0-127) of the MIDI message byte. Cannot contain additional properties.
  - **`from`**: Refer to *[#/definitions/def_midi_message_byte](#definitions/def_midi_message_byte)*.
  - **`to`**: Refer to *[#/definitions/def_midi_message_byte](#definitions/def_midi_message_byte)*.

  Examples:
  ```json
  {
      "from": 10,
      "to": 100
  }
  ```

- <a id="definitions/def_midivelocity_layer"></a>**`def_midivelocity_layer`** *(object)*: Velocity layer configuration. Cannot contain additional properties.
  - **`min`** *(integer, required)*: Minimum velocity value. Minimum: `0`. Maximum: `127`.
  - **`max`** *(integer, required)*: Maximum velocity value. Minimum: `0`. Maximum: `127`.
  - **`send`** *(integer, required)*: Velocity value actually sent to the MIDI device when sampling. Minimum: `0`. Maximum: `127`.

  Examples:
  ```json
  {
      "min": 0,
      "max": 127,
      "send": 127
  }
  ```

- <a id="definitions/def_velocity_layers_preset"></a>**`def_velocity_layers_preset`** *(object)*: Velocity layers preset configuration. Cannot contain additional properties.
  - **`id`** *(integer, required)*: ID of the velocity layer preset.
  - **`velocities`** *(array, required)*
    - **Items**:
        - : Refer to *[#/definitions/def_midivelocity_layer](#definitions/def_midivelocity_layer)*.

  Examples:
  ```json
  {
      "id": 0,
      "velocities": [
          {
              "min": 0,
              "max": 31,
              "send": 31
          },
          {
              "min": 32,
              "max": 63,
              "send": 63
          },
          {
              "min": 64,
              "max": 95,
              "send": 95
          },
          {
              "min": 96,
              "max": 127,
              "send": 127
          }
      ]
  }
  ```

- <a id="definitions/def_sample_zone_complex"></a>**`def_sample_zone_complex`** *(object)*: Sample zone complex configuration. The key range, root key, must be specified explicitly. Cannot contain additional properties.
  - **`key_low`** *(integer, required)*: Lowest key number (note number) in the keymap. This value is intended to be used as information for mapping with third-party sampler software. Minimum: `0`. Maximum: `127`.
  - **`key_high`** *(integer, required)*: Highest key number (note number) in the keymap. This value is intended to be used as information for mapping with third-party sampler software. Minimum: `0`. Maximum: `127`.
  - **`key_root`** *(integer, required)*: Root key number (note number) in the keymap. This value is intended to be used as information for mapping note-on messages sent to MIDI devices and third-party sampler software when sampling. Minimum: `0`. Maximum: `127`.
  - **`velocity_layers`** *(array)*
    - **Items**:
        - : Refer to *[#/definitions/def_midivelocity_layer](#definitions/def_midivelocity_layer)*.
  - **`velocity_layers_preset_id`** *(integer)*: ID of the velocity layer preset.

  Examples:
  ```json
  {
      "key_low": 0,
      "key_high": 32,
      "key_root": 16,
      "velocity_layers": [
          {
              "min": 0,
              "max": 31,
              "send": 31
          },
          {
              "min": 32,
              "max": 63,
              "send": 63
          },
          {
              "min": 64,
              "max": 95,
              "send": 95
          },
          {
              "min": 96,
              "max": 127,
              "send": 127
          }
      ]
  }
  ```

  ```json
  {
      "key_low": 0,
      "key_high": 32,
      "key_root": 16,
      "velocity_layers_preset_id": 0
  }
  ```

- <a id="definitions/def_sample_zone"></a>**`def_sample_zone`** *(object)*: A simple configuration of sample zone. Unlike the complex version, only the root key can be specified, and individual values of `key_range` are applied as `root key`, `low key` and `high key`. Cannot contain additional properties.
  - **`keys`**: Root key number (note number) in the keymap. Refer to *[#/definitions/def_midi_message_byte_range](#definitions/def_midi_message_byte_range)*.
  - **`velocity_layers`** *(array)*
    - **Items**:
        - : Refer to *[#/definitions/def_midivelocity_layer](#definitions/def_midivelocity_layer)*.
  - **`velocity_layers_preset_id`** *(integer)*: ID of the velocity layer preset.

  Examples:
  ```json
  {
      "keys": {
          "from": 10,
          "to": 100
      },
      "velocity_layers": [
          {
              "min": 0,
              "max": 31,
              "send": 31
          },
          {
              "min": 32,
              "max": 63,
              "send": 63
          },
          {
              "min": 64,
              "max": 95,
              "send": 95
          },
          {
              "min": 96,
              "max": 127,
              "send": 127
          }
      ]
  }
  ```

  ```json
  {
      "keys": {
          "from": 10,
          "to": 100
      },
      "velocity_layers_preset_id": 0
  }
  ```

### Audio process Configuration

*Structure of the post process configuration.*

#### Definitions

- <a id="definitions/def_postprocess_config"></a>**`def_postprocess_config`** *(object)*: Cannot contain additional properties.
  - **`effects`** *(array)*: A list of post process configurations.
    - **Items**: Refer to *[#/definitions/def_effect](#definitions/def_effect)*.
- <a id="definitions/def_effect"></a>**`def_effect`** *(object)*: Effect configuration. Cannot contain additional properties.
  - **`index`** *(integer, required)*: The index of the effect in the chain.
  - **`name`** *(string, required)*: A effect name.
  - **`params`** *(object, required)*: A dictionary of parameters for the effect. Can contain additional properties.
#### Examples

  ```json
  [
      {
          "index": 0,
          "name": "normalize",
          "params": {
              "target_db": -10.0
          }
      },
      {
          "index": 1,
          "name": "trim",
          "params": {
              "threshold_db": -65.0,
              "min_silence_duration": 250
          }
      }
  ]
  ```

<!-- [END] Generated by documenttool/jsonschema_to_md.py -->

For individual settings, please refer to the following:
- [Audio Process Parameters](midisampling/waveprocess/Parameters.md)
