from typing import List, Protocol
from midi_sampling.devices.audio.abstractions.audio_data_format import AudioDataFormat


class AudioDeviceInformation:
    """
    Audio device options for initialization.
    """

    def __init__(
        self,
        device_name: str,
        device_platform: str,
        sample_rate: int,
        channels: int,
        data_format: AudioDataFormat,
        input_ports: List[int],
    ) -> None:
        self.device_name: str = device_name
        self.device_platform: str = device_platform
        self.sample_rate: int = sample_rate
        self.channels: int = channels
        self.data_format: AudioDataFormat = data_format
        self.input_ports: List[int] = input_ports

    def __str__(self) -> str:
        return f"device_name={self.device_name}, device_platform={self.device_platform}, sample_rate={self.sample_rate}, channels={self.channels}, data_format={self.data_format}, input_ports={self.input_ports}"


class AudioDeviceInformationLoader(Protocol):
    """
    Load AudioDeviceInformation from a file or other source.
    """

    def load(self, file_path: str) -> AudioDeviceInformation:
        ...
