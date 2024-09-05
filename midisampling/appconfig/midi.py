from typing import List, Dict
import os
import json

from midisampling.jsonvalidation.validator import JsonSchemaInfo, JsonValidator

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILES_DIR = os.path.join(THIS_SCRIPT_DIR, "json.schema.files", "midi")

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
        ("midi-channel.schema.json", _schema_path("midi-channel.schema.json")),
        ("integer-range.schema.json", _schema_path("integer-range.schema.json")),
        ("midi-message-byte.schema.json", _schema_path("midi-message-byte.schema.json")),
        ("midi-message-byte-range.schema.json", _schema_path("midi-message-byte-range.schema.json")),
        ("midi-notenumber.schema.json", _schema_path("midi-notenumber.schema.json")),
        ("midi-notenumber-range.schema.json", _schema_path("midi-notenumber-range.schema.json")),
        ("midi-note-duration.schema.json", _schema_path("midi-note-duration.schema.json")),
        ("midi-velocity.schema.json", _schema_path("midi-velocity.schema.json")),
        ("midi-velocity-layer.schema.json", _schema_path("midi-velocity-layer.schema.json")),
        ("midi-velocity-layer-preset.schema.json", _schema_path("midi-velocity-layer-preset.schema.json")),
        ("midi-program-change.schema.json", _schema_path("midi-program-change.schema.json")),
        ("sample-zone-complex.schema.json", _schema_path("sample-zone-complex.schema.json")),
        ("sample-zone.schema.json", _schema_path("sample-zone.schema.json")),
        ("sample-zone-note-duration.schema.json", _schema_path("sample-zone-note-duration.schema.json"))
])

# MIDI Config file schema
config_file_validator: JsonValidator = JsonValidator(
    main_schema_info=JsonSchemaInfo.from_file(
        schema_uri="main",
        schema_file_path=_schema_path("midi-config.schema.json")
    ),
    sub_schema_info_list=sub_schemas
)

# MIDI Velocity Layer file schema
velocity_layer_file_validator: JsonValidator = JsonValidator(
    main_schema_info=JsonSchemaInfo.from_file(
        schema_uri="main",
        schema_file_path=_schema_path("midi-velocity-layers-file.schema.json")
    ),
    sub_schema_info_list=sub_schemas
)

# Sample Zone file schema
sample_zone_file_validator: JsonValidator = JsonValidator(
    main_schema_info=JsonSchemaInfo.from_file(
        schema_uri="main",
        schema_file_path=_schema_path("sample-zone-file.schema.json")
    ),
    sub_schema_info_list=sub_schemas
)

# Sample Zone Complex file schema
sample_zone_complex_file_validator: JsonValidator = JsonValidator(
    main_schema_info=JsonSchemaInfo.from_file(
        schema_uri="main",
        schema_file_path=_schema_path("sample-zone-complex-file.schema.json")
    ),
    sub_schema_info_list=sub_schemas
)

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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProgramChange):
            return False
        return (
            self.msb == other.msb
            and self.lsb == other.lsb
            and self.program == other.program
        )

    def __hash__(self) -> int:
        return hash((self.msb, self.lsb, self.program))

class VelocityLayer:
    def __init__(self, velocity_layer: dict) -> None:
        self.min_velocity: int  = velocity_layer["min"]
        self.max_velocity: int  = velocity_layer["max"]
        self.send_velocity: int = velocity_layer["send"]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VelocityLayer):
            return False
        return (
            self.min_velocity == other.min_velocity
            and self.max_velocity == other.max_velocity
            and self.send_velocity == other.send_velocity
        )

    def __hash__(self) -> int:
        return hash((self.min_velocity, self.max_velocity, self.send_velocity))

    def __str__(self) -> str:
        return f"min={self.min_velocity}, max={self.max_velocity}, send={self.send_velocity}"

class VelocityLayerPreset:
    def __init__(self, config_dir: str, velocity_layer_preset: dict) -> None:
        self.id: int = int(velocity_layer_preset["id"])
        self.layers: List[VelocityLayer] = []

        if "file" in velocity_layer_preset:
            file_path  = _to_abs_filepath(config_dir, velocity_layer_preset["file"])
            velocities = _load_json_with_validate(file_path, velocity_layer_file_validator)
            for x in velocities:
                self.layers.append(VelocityLayer(x))

        if "velocities" in velocity_layer_preset:
            for x in velocity_layer_preset["velocities"]:
                self.layers.append(VelocityLayer(x))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VelocityLayerPreset):
            return False
        return (
            self.id == other.id
            and self.layers == other.layers
        )

    def __hash__(self) -> int:
        return hash((self.id, self.layers))

    def __str__(self) -> str:
        return f"id={self.id}, layers[{len(self.layers)}]=[{[f"[{x}]" for x in self.layers]}]"

    @classmethod
    def from_json(cls, config_dir: str, velocity_layer_presets: dict) -> List['VelocityLayerPreset']:
        """
        Create VelocityLayerPreset list from json data
        """
        result: List['VelocityLayerPreset'] = []

        for x in velocity_layer_presets:
            result.append(VelocityLayerPreset(config_dir, x))

        return result

    @classmethod
    def get_velocity_layer_preset(cls, velocity_layer_presets: List['VelocityLayerPreset'], id: int) -> 'VelocityLayerPreset':
        """
        Get VelocityLayerPreset by id

        Parameters
        ----------
        velocity_layer_presets : List['VelocityLayerPreset']
            List of VelocityLayerPreset

        id : int
            ID to search
        """
        for x in velocity_layer_presets:
            if x.id == id:
                return x

        raise ValueError(f"VelocityLayerPreset not found. id={id}")

class SampleZone:
    """
    Represents the smallest unit of sample zone data
    """
    def __init__(self, key_root: int, key_low: int, key_high: int, velocity_layers: List[VelocityLayer], note_duration: float = -1, release_duration: float = -1) -> None:
        self.key_root: int  = key_root
        self.key_low: int   = key_low
        self.key_high: int  = key_high
        self.velocity_layers: List[VelocityLayer] = velocity_layers
        self.note_duration: float = note_duration
        self.release_duration: float = release_duration

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SampleZone):
            return False
        return (
            self.key_root == other.key_root
            and self.key_low == other.key_low
            and self.key_high == other.key_high
            and self.velocity_layers == other.velocity_layers
        )

    def __hash__(self) -> int:
        return hash((self.key_root, self.key_low, self.key_high, self.velocity_layers))

    def __str__(self) -> str:
        return f"key_root={self.key_root}, key_low={self.key_low}, key_high={self.key_high}, velocity_layers[{len(self.velocity_layers)}]=[{[f"[{x}]" for x in self.velocity_layers]}]"

    @classmethod
    def __parse_velocity_layer(cls, zone: dict, presets: List[VelocityLayerPreset] ) -> List[VelocityLayer]:
        """
        Parse velocity layer data to list
        """

        result: List[VelocityLayer] = []

        if "velocity_layers_preset_id" in zone:
            id = int(zone["velocity_layers_preset_id"])
            preset: VelocityLayerPreset = VelocityLayerPreset.get_velocity_layer_preset(presets, id)
            for preset_data in preset.layers:
                result.append(preset_data)

        if "velocity_layers" in zone:
            for x in zone["velocity_layers"]:
                result.append(VelocityLayer(x))

        return result

    @classmethod
    def __parse_sample_zone_file(cls, config_dir: str, file_path: str, velocity_layers_presets: List[VelocityLayerPreset]) -> List['SampleZone']:
        """
        Parse sample zone data from external file
        """
        file_path = _to_abs_filepath(config_dir, file_path)
        zone_json = _load_json_with_validate(file_path, sample_zone_file_validator)

        return SampleZone.__from_sample_simple_json(
            config_dir=config_dir,
            zone_simple=zone_json,
            velocity_layers_presets=velocity_layers_presets
        )

    @classmethod
    def __parse_sample_zone_complex_file(cls, config_dir: str, file_path: str, velocity_layers_presets: List[VelocityLayerPreset]) -> List['SampleZone']:
        """
        Parse sample zone complex data from external file
        """
        file_path = _to_abs_filepath(config_dir, file_path)
        zone_complex_json = _load_json_with_validate(file_path, sample_zone_complex_file_validator)

        return SampleZone.__from_zone_complex_json(
            config_dir=config_dir,
            zone_complex=zone_complex_json,
            velocity_layers_presets=velocity_layers_presets
        )

    @classmethod
    def __from_zone_complex_json(cls, config_dir: str, zone_complex: dict, velocity_layers_presets: List[VelocityLayerPreset]) -> List['SampleZone']:
        """
        Create SampleZone list from json data (sample_zone_complex)
        """
        result: List['SampleZone'] = []

        for zone in zone_complex:

            if "file" in zone:
                result.extend(SampleZone.__parse_sample_zone_complex_file(
                    config_dir=config_dir,
                    file_path=zone["file"],
                    velocity_layers_presets=velocity_layers_presets
                ))
                continue

            key_root = zone["key_root"]
            key_low  = zone["key_low"]
            key_high = zone["key_high"]

            velocity_layers: List[VelocityLayer] = SampleZone.__parse_velocity_layer(zone, velocity_layers_presets)

            if len(velocity_layers) == 0:
                raise ValueError(f"velocity layers is empty.")

            note_duration    = -1
            release_duration = -1

            if "note_duration" in zone:
                duration = zone["note_duration"]
                note_duration = duration["note_time"]
                if "release_time" in duration:
                    release_duration = duration["release_time"]

            result.append(
                SampleZone(
                    key_root=key_root, key_low=key_low, key_high=key_high,
                    velocity_layers=velocity_layers,
                    note_duration=note_duration,
                    release_duration=release_duration
                )
            )

        return result

    @classmethod
    def __from_sample_simple_json(cls, config_dir: str, zone_simple: dict, velocity_layers_presets: List[VelocityLayerPreset]) -> List['SampleZone']:
        """
        Create SampleZone list from json data (sample_zone)
        """
        result: List['SampleZone'] = []

        for zone in zone_simple:

            if "file" in zone:
                file_path  = _to_abs_filepath(config_dir, zone["file"])
                return SampleZone.__parse_sample_zone_file(
                    config_dir=config_dir,
                    file_path=file_path,
                    velocity_layers_presets=velocity_layers_presets
                )

            notes = _parse_midi_byte_range(zone["keys"])
            velocity_layers: List[VelocityLayer] = SampleZone.__parse_velocity_layer(zone, velocity_layers_presets)

            min_note = min(notes)
            max_note = max(notes)

            if len(velocity_layers) == 0:
                raise ValueError(f"velocity layers is empty.")

            note_durations: Dict[int, float] = {}
            note_relese_durations: Dict[int, float] = {}

            if "note_durations" in zone:
                for duration in zone["note_durations"]:
                    for duration_note in duration["notes"]:
                        # Note is out of range in this Zone
                        if min_note > duration_note or duration_note > max_note:
                            raise ValueError(f"note_duration: note is out of range in this Zone. from={min_note}, to={max_note}, note={duration_note}")
                        if "note_time" in duration["duration"]:
                            note_durations[duration_note] = duration["duration"]["note_time"]
                        if "release_time" in duration["duration"]:
                            note_relese_durations[duration_note] = duration["duration"]["release_time"]

            for note in notes:
                note_duration    = note_durations.get(note, -1)
                release_duration = note_relese_durations.get(note, -1)

                result.append(
                    SampleZone(
                        key_root=note, key_low=note, key_high=note,
                        velocity_layers=velocity_layers,
                        note_duration=note_duration,
                        release_duration=release_duration
                    )
                )

        return result

    @classmethod
    def from_json(cls, config_dir: str, config_json: dict, velocity_layers_presets: List[VelocityLayerPreset]) -> List['SampleZone']:
        """
        Create SampleZone list from json data
        """
        result: List['SampleZone'] = []
        if "sample_zone_complex" in config_json:
            result.extend(SampleZone.__from_zone_complex_json(
                config_dir=config_dir,
                zone_complex=config_json["sample_zone_complex"],
                velocity_layers_presets=velocity_layers_presets
            ))
        if "sample_zone" in config_json:
            result.extend(SampleZone.__from_sample_simple_json(
                config_dir=config_dir,
                zone_simple=config_json["sample_zone"],
                velocity_layers_presets=velocity_layers_presets
            ))

        return result

    @classmethod
    def get_total_sample_count(cls, sample_zones: List['SampleZone']) -> int:
        """
        Get total sample count from SampleZone list
        """

        if sample_zones is None or len(sample_zones) == 0:
            return 0

        total = 0
        for zone in sample_zones:
            total += len(zone.velocity_layers)

        return total

class MidiConfig:
    def __init__(self, config_path: str) -> None:
        config_json = validate(config_path)

        self.config_path: str                           = config_path
        self.config_dir: str                            = os.path.abspath(os.path.dirname(config_path))
        self.output_dir: str                            = config_json["output_dir"]
        self.processed_output_dir: str                  = config_json["processed_output_dir"]
        self.output_prefix_format: str                  = config_json["output_prefix_format"]
        self.scale_name_format: str                     = config_json.get("scale_name_format", "Yamaha")
        self.pre_send_smf_path_list: List[str]          = config_json["pre_send_smf_path_list"]
        self.midi_channel: int                          = config_json["midi_channel"]
        self.program_change_list: List[ProgramChange]   = []
        self.velocity_layer_presets: List[VelocityLayerPreset] = []
        self.midi_pre_wait_duration: float              = config_json["midi_pre_wait_duration"]
        self.midi_note_duration: float                  = config_json["midi_note_duration"]
        self.midi_release_duration: float               = config_json["midi_release_duration"]

        # Program Change
        for pc in config_json["midi_program_change_list"]:
            self.program_change_list.append(ProgramChange(pc))

        # Velocity Layer Preset
        if "velocity_layers_presets" in config_json:
            self.velocity_layer_presets = VelocityLayerPreset.from_json(self.config_dir, config_json["velocity_layers_presets"])

        # Convert to a path starting from the directory where the config file is located
        self.output_dir = _to_abs_filepath(self.config_dir, self.output_dir)
        self.processed_output_dir = _to_abs_filepath(self.config_dir, self.processed_output_dir)
        self.pre_send_smf_path_list = _to_abs_filepath_list(self.config_dir, self.pre_send_smf_path_list)

        if self.output_dir == self.processed_output_dir or self.processed_output_dir.startswith(self.output_dir):
            raise ValueError(f"processed_output_dir must be outside of output_dir.\n\toutput_dir={self.output_dir}\n\tprocessed_output_dir={self.processed_output_dir})")

        # Zone
        self.sample_zone = SampleZone.from_json(self.config_dir,config_json, self.velocity_layer_presets)

def validate(config_path: str) -> dict:
    return _load_json_with_validate(config_path, config_file_validator)

def load(config_path: str) -> MidiConfig:
    return MidiConfig(config_path)
