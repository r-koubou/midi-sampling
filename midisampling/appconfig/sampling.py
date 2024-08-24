from typing import List
import os
import json
import jsonschema

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_SCRIPT_DIR, "sampling-config.schema.json"), "r") as f:
    json_schema = json.load(f)

class SamplingConfig:
    def __init__(self, config_path: str) -> None:
        config = validate(config_path)

        self.config_path: str               = config_path
        self.config_dir: str                = os.path.abspath(os.path.dirname(config_path))
        self.audio_channels: int            = config["audio_channels"]
        self.audio_sample_rate: int         = config["audio_sample_rate"]
        self.audio_sample_bits: int         = config["audio_sample_bits"]
        self.audio_sample_bits_format:str   = config["audio_sample_bits_format"]
        self.audio_in_device: str           = config["audio_in_device"]["name"]
        self.audio_in_device_platform: str  = config["audio_in_device"]["platform"]
        self.asio_audio_ins: List[int]      = config.get("asio_audio_ins", [])
        self.midi_out_device: str           = config["midi_out_device"]

def validate(config_path: str) -> dict:
    with open(config_path, "r") as f:
        config_json = json.load(f)
        jsonschema.validate(config_json, json_schema)
    return config_json

def load(config_path: str) -> SamplingConfig:
    return SamplingConfig(config_path)
