from typing import List
import os
import json
import jsonschema

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


def _parse_midi_byte_range(json_body: dict) -> List[int]:
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

    for data in json_body:
        # from - to value
        if type(data) == dict:
            for i in range(data["from"], data["to"]+1):
                result.append(i)
        # single integer
        elif type(data) == int:
            result.append(data)
        else:
            raise ValueError(f"Invalid data format (={json_body})")

    return result

class MidiConfig:

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

    def __init__(self, config_path: str) -> None:
        with open(config_path, "r") as f:
            config_json = json.load(f)
            jsonschema.validate(config_json, config_json_schema)

        self.config_path: str                                       = config_path
        self.config_dir: str                                        = os.path.abspath(os.path.dirname(config_path))
        self.output_dir: str                                        = config_json["output_dir"]
        self.processed_output_dir: str                              = config_json["processed_output_dir"]
        self.output_prefix_format: str                              = config_json["output_prefix_format"]
        self.pre_send_smf_path_list: List[str]                      = config_json["pre_send_smf_path_list"]
        self.midi_channel: int                                      = config_json["midi_channel"]
        self.program_change_list: List[MidiConfig.ProgramChange]    = []
        self.midi_notes: List[int]                                  = _parse_midi_byte_range(config_json["midi_notes"])
        self.midi_velocity_layers: List[MidiConfig.VelocityLayer]   = []
        self.midi_pre_wait_duration: float                          = config_json["midi_pre_wait_duration"]
        self.midi_note_duration: int                                = config_json["midi_note_duration"]
        self.midi_release_duration: float                           = config_json["midi_release_duration"]

        for pc in config_json["midi_program_change_list"]:
            self.program_change_list.append(MidiConfig.ProgramChange(pc))

        for x in config_json["midi_velocity_layers"]:
            self.midi_velocity_layers.append(MidiConfig.VelocityLayer(x))

        # Convert to a path starting from the directory where the config file is located
        self.output_dir = _to_abs_filepath(self.config_dir, self.output_dir)
        self.processed_output_dir = _to_abs_filepath(self.config_dir, self.processed_output_dir)
        self.pre_send_smf_path_list = _to_abs_filepath_list(self.config_dir, self.pre_send_smf_path_list)

    def to_send_velocity_values(self) -> List[int]:
        """
        Returns the list of send velocity values to be used in the MIDI note on message
        """
        return [x.send_velocity for x in self.velocity_layers]

def load(config_path: str) -> MidiConfig:
    return MidiConfig(config_path)
