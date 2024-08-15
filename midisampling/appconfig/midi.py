from typing import List
import os
import json
import jsonschema

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_SCRIPT_DIR, "midi-config.schema.json"), "r") as f:
    config_json_schema = json.load(f)

class MidiConfig:

    class ProgramChange:
        def __init__(self, progarm_change: dict) -> None:
            self.msb: int       = progarm_change["msb"]
            self.lsb: int       = progarm_change["lsb"]
            self.program: int   = progarm_change["program"]

    def __init__(self, config_json: dict) -> None:
        self.output_dir: str                    = config_json["output_dir"]
        self.processed_output_dir: str          = config_json["processed_output_dir"]
        self.output_prefix: str                 = config_json["output_prefix"]
        self.pre_send_smf_path_list: List[str]  = config_json["pre_send_smf_path_list"]
        self.midi_channel: int                  = config_json["midi_channel"]
        self.midi_notes: List[int]              = config_json["midi_notes"]
        self.midi_velocities: List[int]         = config_json["midi_velocities"]
        self.midi_pre_wait_duration: float      = config_json["midi_pre_wait_duration"]
        self.midi_note_duration: int            = config_json["midi_note_duration"]
        self.midi_release_duration: float       = config_json["midi_release_duration"]

        self.program_change_list: List[MidiConfig.ProgramChange] = []
        for pc in config_json["midi_program_change_list"]:
            print(pc)
            self.program_change_list.append(MidiConfig.ProgramChange(pc))

def load(config_path: str) -> MidiConfig:
    with open(config_path, "r") as f:
        json_body = json.load(f)
        jsonschema.validate(json_body, config_json_schema)
        return MidiConfig(json_body)
