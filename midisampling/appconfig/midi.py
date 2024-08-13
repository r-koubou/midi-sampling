from typing import List
import os
import json
import jsonschema

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_SCRIPT_DIR, "midi-config.schema.json"), "r") as f:
    config_json_schema = json.load(f)

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

def __midi_config_hook(obj: any) -> any:
    if type(obj) == dict:
        jsonschema.validate(obj, config_json_schema)
        return MidiConfig(obj)
    else:
        return obj

def load(config_path: str) -> MidiConfig:
    with open(config_path, "r") as f:
        return json.load(f, object_hook=__midi_config_hook)
