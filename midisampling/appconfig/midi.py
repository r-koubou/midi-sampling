from typing import List
import abc
import os
import sys
import json
import jsonschema

import traceback

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(THIS_SCRIPT_DIR, "midi-config.schema.json"), "r") as f:
    config_json_schema = json.load(f)

def _to_abs_filepath(base_dir: str, file_path: str) -> str:
    """
    Returns the absolute path of file_path starting from base_dir

    Parameters
    ----------
    base_dir : str
        Starting Directory
    file_path : str
        File path

    Returns
    -------
    Absolute path of file_path starting from base_dir. If file_path is already an absolute path, it will be returned as is.
    """

    base_dir  = os.path.abspath(base_dir)
    file_path = os.path.normpath(file_path)

    if not os.path.isabs(file_path):
        return os.path.join(base_dir, file_path)

    return file_path

def _to_abs_filepath_list(base_dir: str, file_path_list: List[str]) -> str:
    """
    Returns the absolute path of file_path starting from base_dir

    Parameters
    ----------
    base_dir : str
        Starting Directory
    file_path_list : List[str]
        List of file paths

    Returns
    -------
    List of absolute paths of file_path starting from base_dir. If file_path is already an absolute path, it will be returned as is.
    """

    result = []
    for file_path in file_path_list:
        result.append(_to_abs_filepath(base_dir, file_path))

    return result

def _parse_midi_byte_range(json_body: any) -> List[int]:
    """
    Parse MIDI byte range from JSON body to list of int
    Parameters
    ----------
    json_body : dict
        JSON body to parse (schema:midi-byte-range.schema.json)

    Returns
    -------
    List[int]
        List of int values of MIDI byte range
    """
    result: List[int] = []

    # from - to value
    if type(json_body) == dict:
        for i in range(json_body["from"], json_body["to"]+1):
            result.append(i)
    # single integer
    elif type(json_body) == int:
        result.append(json_body)
    else:
        raise ValueError(f"Invalid data format type={type(json_body)}, (={json_body})")

    return result

class ProgramChange:
    def __init__(self, progarm_change: dict) -> None:
        self.msb: int     = progarm_change["msb"]
        self.lsb: int     = progarm_change["lsb"]
        self.program: int = progarm_change["program"]

class VelocityLayer:
    def __init__(self, velocity_layer: dict) -> None:
        self.min_velocity: int  = velocity_layer["min"]
        self.max_velocity: int  = velocity_layer["max"]
        self.send_velocity: int = velocity_layer["send"]

class KeyMapUnit:
    """
    Represents the smallest unit of keymap data
    """
    def __init__(self, key_root: int, key_low: int, key_high: int, velocity_layers: List[VelocityLayer]) -> None:
        self.key_root: int  = key_root
        self.key_low: int   = key_low
        self.key_high: int  = key_high
        self.velocity_layers: List[VelocityLayer] = velocity_layers

    def __str__(self) -> str:
        return f"{self.__dict__}"

    @classmethod
    def __from_keymap_complex(cls, keymap_complex: dict) -> List['KeyMapUnit']:
        """
        Create KeyMapUnit list from json data (keymap_complex)
        """
        result: List['KeyMapUnit'] = []

        for key in keymap_complex:
            key_root = key["key_root"]
            key_low  = key["key_low"]
            key_high = key["key_high"]

            velocity_layers: List[VelocityLayer] = []

            for x in key["velocity_layers"]:
                velocity_layers.append(VelocityLayer(x))

            result.append(
                KeyMapUnit(
                    key_root=key_root, key_low=key_low, key_high=key_high,
                    velocity_layers=velocity_layers
                )
            )

        return result

    @classmethod
    def __from_keymap_simple(cls, keymap_simple: dict) -> List['KeyMapUnit']:
        """
        Create KeyMapUnit list from json data (keymap_simple)
        """
        result: List['KeyMapUnit'] = []

        for key in keymap_simple:
            notes = _parse_midi_byte_range(key["key_root"])
            velocity_layers: List[VelocityLayer] = []

            for x in key["velocity_layers"]:
                velocity_layers.append(VelocityLayer(x))

            for note in notes:
                result.append(
                    KeyMapUnit(
                        key_root=note, key_low=note, key_high=note,
                        velocity_layers=velocity_layers
                    )
                )

        return result

    @classmethod
    def from_keymap(cls, config_json: dict) -> List['KeyMapUnit']:
        """
        Create KeyMapUnit list from json data
        """
        result: List['KeyMapUnit'] = []
        if "midi_keymaps_complex" in config_json:
            result.extend(KeyMapUnit.__from_keymap_complex(config_json["midi_keymaps_complex"]))
        if "midi_keymaps" in config_json:
            result.extend(KeyMapUnit.__from_keymap_simple(config_json["midi_keymaps"]))

        return result

class MidiConfig:
    def __init__(self, config_path: str) -> None:
        with open(config_path, "r") as f:
            config_json = json.load(f)
            jsonschema.validate(config_json, config_json_schema)

        self.config_path: str                           = config_path
        self.config_dir: str                            = os.path.abspath(os.path.dirname(config_path))
        self.output_dir: str                            = config_json["output_dir"]
        self.processed_output_dir: str                  = config_json["processed_output_dir"]
        self.output_prefix_format: str                  = config_json["output_prefix_format"]
        self.pre_send_smf_path_list: List[str]          = config_json["pre_send_smf_path_list"]
        self.midi_channel: int                          = config_json["midi_channel"]
        self.program_change_list: List[ProgramChange]   = []
        self.midi_pre_wait_duration: float              = config_json["midi_pre_wait_duration"]
        self.midi_note_duration: int                    = config_json["midi_note_duration"]
        self.midi_release_duration: float               = config_json["midi_release_duration"]

        for pc in config_json["midi_program_change_list"]:
            self.program_change_list.append(ProgramChange(pc))

        # Convert to a path starting from the directory where the config file is located
        self.output_dir = _to_abs_filepath(self.config_dir, self.output_dir)
        self.processed_output_dir = _to_abs_filepath(self.config_dir, self.processed_output_dir)
        self.pre_send_smf_path_list = _to_abs_filepath_list(self.config_dir, self.pre_send_smf_path_list)

        # Keymap
        self.keymaps = KeyMapUnit.from_keymap(config_json)

def load(config_path: str) -> MidiConfig:
    return MidiConfig(config_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Validation tool for MIDI config file")
        print(f"Usage: python -m {__spec__.name} <config_file>")
        sys.exit(1)

    config_path = sys.argv[1]

    try:
        with open(config_path, "r") as f:
            config_json = json.load(f)
            jsonschema.validate(config_json, config_json_schema)
        print("Validation OK")
        MidiConfig(config_path)
    except Exception as e:
        print(f"Validation failed: {e}")
        traceback.print_exc()
