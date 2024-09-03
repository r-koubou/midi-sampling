from typing import List
import os
import json

from midisampling.jsonvalidation.validator import JsonSchemaInfo, JsonValidator

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILES_DIR = os.path.join(THIS_SCRIPT_DIR, "json.schema.files", "sampling")

def _schema_path(schema_file_name: str) -> str:
    return os.path.join(SCHEMA_FILES_DIR, schema_file_name)

def _load_json_with_validate(file_path: str, validator: JsonValidator) -> dict:
    with open(file_path, "r") as f:
        json_body = json.load(f)
        validator.validate(json_body)
    return json_body

#-----------------------------------------
# JSON Validator setup with schema files
#-----------------------------------------

# Sub Schema list
sub_schemas: List[JsonSchemaInfo] = JsonSchemaInfo.from_files([
    ("sampling-platform.schema.json", _schema_path("sampling-platform.schema.json")),
])

# MIDI Config file schema
config_file_validator: JsonValidator = JsonValidator(
    main_schema_info=JsonSchemaInfo.from_file(
        schema_uri="main",
        schema_file_path=_schema_path("sampling-config.schema.json")
    ),
    sub_schema_info_list=sub_schemas
)



with open(os.path.join(SCHEMA_FILES_DIR, "sampling-config.schema.json"), "r") as f:
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
    return _load_json_with_validate(config_path, config_file_validator)

def load(config_path: str) -> SamplingConfig:
    return SamplingConfig(config_path)
