from typing import List
import os
import json
import jsonschema

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_SCRIPT_DIR, "midi-config.schema.json"), "r") as f:
    config_json_schema = json.load(f)

class MidiConfig:
    def __init__(self, config: dict) -> None:
        self.output_dir: str                   = config["output_dir"]
        self.processed_output_dir: str         = config["processed_output_dir"]
        self.output_prefix: str                = config["output_prefix"]
        self.midi_channel: int                 = config["midi_channel"]
        self.midi_notes: List[int]             = config["midi_notes"]
        self.midi_velocities: List[int]        = config["midi_velocities"]
        self.midi_pre_wait_duration: float     = config["midi_pre_wait_duration"]
        self.midi_note_duration: int           = config["midi_note_duration"]
        self.midi_release_duration: float      = config["midi_release_duration"]

def __midi_config_hook(obj: any) -> any:
    if type(obj) == dict:
        jsonschema.validate(obj, config_json_schema)
        return MidiConfig(obj)
    else:
        return obj

def load(config_path: str) -> MidiConfig:
    with open(config_path, "r") as f:
        return json.load(f, object_hook=__midi_config_hook)
