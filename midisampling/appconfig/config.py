from typing import List
import os
import json
import jsonschema

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_SCRIPT_DIR, "sampling-config.schema.json"), "r") as f:
    common_config_json_schema = json.load(f)

with open(os.path.join(THIS_SCRIPT_DIR, "midi-config.schema.json"), "r") as f:
    config_json_schema = json.load(f)

class SamplingConfig:
    def __init__(self, config: dict) -> None:
        self.audio_channels: int                        = config["audio_channels"]
        self.audio_sample_rate: int                     = config["audio_sample_rate"]
        self.audio_sample_bits: int                     = config["audio_sample_bits"]
        self.audio_sample_bits_format:str               = config["audio_sample_bits_format"]
        self.audio_in_device: str                       = config["audio_in_device"]
        self.use_asio: bool                             = config.get("use_asio", False)
        self.asio_audio_ins: List[int]                  = config.get("asio_audio_ins", [])
        self.midi_out_device: str                       = config["midi_out_device"]
        self.sampling_target_peak: float                = config["sampling_target_peak"]
        self.sampling_trim_threshold: float             = config["sampling_trim_threshold"]
        self.sampling_trim_min_silence_duration: int    = config["sampling_trim_min_silence_duration"]

    def dump(self) -> None:
        print("#### Common Config ####")
        print(f"audio_channels: {self.audio_channels}")
        print(f"audio_sample_rate: {self.audio_sample_rate}")
        print(f"audio_sample_bits: {self.audio_sample_bits}")
        print(f"audio_sample_bits_format: {self.audio_sample_bits_format}")
        print(f"audio_in_device: {self.audio_in_device}")
        print(f"use_asio: {self.use_asio}")
        print(f"asio_audio_ins: {self.asio_audio_ins}")
        print(f"midi_out_device: {self.midi_out_device}")
        print(f"sampling_target_peak: {self.sampling_target_peak}")
        print(f"sampling_trim_threshold: {self.sampling_trim_threshold}")
        print(f"sampling_trim_min_silence_duration: {self.sampling_trim_min_silence_duration}")

class MidiConfig:
    def __init__(self, config: dict) -> None:
        self.sampling_output_dir: str                   = config["sampling_output_dir"]
        self.sampling_processed_output_dir: str         = config["sampling_processed_output_dir"]
        self.sampling_file_name_base: str               = config["sampling_file_name_base"]
        self.sampling_midi_channel: int                 = config["sampling_midi_channel"]
        self.sampling_midi_notes: List[int]             = config["sampling_midi_notes"]
        self.sampling_midi_velocities: List[int]        = config["sampling_midi_velocities"]
        self.sampling_midi_pre_wait_duration: float     = config["sampling_midi_pre_wait_duration"]
        self.sampling_midi_note_duration: int           = config["sampling_midi_note_duration"]
        self.sampling_midi_release_duration: float      = config["sampling_midi_release_duration"]

    def dump(self) -> None:
        print("#### Config ####")
        print(f"sampling_output_dir: {self.sampling_output_dir}")
        print(f"sampling_processed_output_dir: {self.sampling_processed_output_dir}")
        print(f"sampling_file_name_base: {self.sampling_file_name_base}")
        print(f"sampling_midi_channel: {self.sampling_midi_channel}")
        print(f"sampling_midi_notes: {self.sampling_midi_notes}")
        print(f"sampling_midi_velocities: {self.sampling_midi_velocities}")
        print(f"sampling_midi_pre_wait_duration: {self.sampling_midi_pre_wait_duration}")
        print(f"sampling_midi_note_duration: {self.sampling_midi_note_duration}")
        print(f"sampling_midi_release_duration: {self.sampling_midi_release_duration}")

def __sampling_config_hook(obj: any) -> any:
    if type(obj) == dict:
        jsonschema.validate(obj, common_config_json_schema)
        return SamplingConfig(obj)
    else:
        return obj

def __midi_config_hook(obj: any) -> any:
    if type(obj) == dict:
        jsonschema.validate(obj, config_json_schema)
        return MidiConfig(obj)
    else:
        return obj

def load_sampling_config(config_path: str) -> SamplingConfig:
    with open(config_path, "r") as f:
        return json.load(f, object_hook=__sampling_config_hook)


def load_midi_config(config_path: str) -> MidiConfig:
    with open(config_path, "r") as f:
        return json.load(f, object_hook=__midi_config_hook)
