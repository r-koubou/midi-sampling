from typing import List
import os
import json
import jsonschema

from logging import getLogger

THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
logger = getLogger(__name__)

with open(os.path.join(THIS_SCRIPT_DIR, "audioprocess-config.schema.json"), "r") as f:
    json_schema = json.load(f)

class AudioProcessFormat:
    def __init__(self, config: dict) -> None:
        self.bit_depth: str = config.get("bit_depth", None)
        self.sample_rate: int = config.get("sample_rate", None)
        self.channels: int = config.get("channels", None)

    def __str__(self) -> str:
        return f"bit_depth={self.bit_depth}, sample_rate={self.sample_rate}, channels={self.channels}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AudioProcessFormat):
            return False
        return (
            self.bit_depth == other.bit_depth
            and self.sample_rate == other.sample_rate
            and self.channels == other.channels
        )

class AudioProcessInfo:
    def __init__(self, index: int, name: str, params: dict) -> None:
        self.index: int   = index
        self.name: str    = name
        self.params: dict = params

    def __str__(self) -> str:
        return f"index={self.index}, name={self.name}, params={self.params}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AudioProcessInfo):
            return False
        return (
            self.index == other.index
            and self.name == other.name
            and self.params == other.params
        )

    def __hash__(self) -> int:
        return hash((self.index, self.name, tuple(self.params.items())))

class AudioProcessConfig:
    def __init__(self, config_path: str) -> None:
        config = validate(config_path)
        self.effects: List[AudioProcessInfo] = []
        self.keep_wav_chunks: List[str] = config.get("keep_wav_chunks", [])
        self.format: AudioProcessFormat = None

        if "format" in config:
            self.format = AudioProcessFormat(config["format"])

        for effect in config.get("effects", []):
            self.effects.append(
                AudioProcessInfo(
                    index=effect["index"],
                    name=effect["name"],
                    params=effect["params"]
                )
            )

        self.effects = sorted(self.effects, key=lambda x: x.index)

        # Check index is not duplicated
        index_list = [effect.index for effect in self.effects]
        if len(index_list) != len(set(index_list)):
            raise ValueError("Effect index must be unique")

    def __str__(self) -> str:
        result = "["
        for effect in self.effects:
            result += f"[{effect}], "
        result += f"keep_wav_chunks={self.keep_wav_chunks}"
        result += "]"

        return result

def validate(config_path: str) -> dict:
    with open(config_path, "r") as f:
        config_json = json.load(f)
        jsonschema.validate(config_json, json_schema)
    return config_json

def load(config_path: str) -> AudioProcessConfig:
    return AudioProcessConfig(config_path)
