from typing import List
import os
import json
import jsonschema

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_SCRIPT_DIR, "sampling-config.schema.json"), "r") as f:
    common_config_json_schema = json.load(f)

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

def __load_config_hook(obj: any) -> any:
    if type(obj) == dict:
        jsonschema.validate(obj, common_config_json_schema)
        return SamplingConfig(obj)
    else:
        return obj

def load(config_path: str) -> SamplingConfig:
    with open(config_path, "r") as f:
        return json.load(f, object_hook=__load_config_hook)
