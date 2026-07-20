from pydantic import BaseModel
from typing import List, Literal
import yaml

from midi_sampling.devices.audio.abstractions import (
    AudioDeviceInformation,
    AudioDataFormat,
    AudioDeviceInformationLoader
)

class _AudioDeviceInformationModel(BaseModel):
    device_name: str
    device_platform: str
    sample_rate: int
    channels: int
    data_format: Literal["int16", "int24", "int32", "float32", "float64"]
    input_ports: List[int]


class SdAudioDeviceInformationLoader(AudioDeviceInformationLoader):
    """
    Load AudioDeviceInformation from a yaml file
    """

    def load(self, file_path: str) -> AudioDeviceInformation:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        model = _AudioDeviceInformationModel(**data)

        return AudioDeviceInformation(
            device_name=model.device_name,
            device_platform=model.device_platform,
            sample_rate=model.sample_rate,
            channels=model.channels,
            data_format=AudioDataFormat.parse(model.data_format),
            input_ports=model.input_ports,
        )
