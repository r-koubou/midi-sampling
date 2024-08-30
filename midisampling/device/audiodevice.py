from typing import List
from enum import Enum
import abc

class NotFoundAudioDeviceError(Exception):
    def __init__(self, device_name: str = None) -> None:
        self.device_name = device_name

    def __str__(self) -> str:
        if self.device_name:
            return f"Audio Device `{self.device_name}` is not found."
        else:
            return "Audio Device is not found."

class AudioDeviceInfo:
    def __init__(self, index: int, name: str, platform_name: str = "") -> None:
        self.index = index
        self.name = name
        self.platform_name = platform_name

class AudioDataFormat(Enum):
    """
    Audio data format.
    """
    UNKNOWN = 0
    INT16   = 1
    INT24   = 2
    INT32   = 3
    FLOAT32 = 4

    def bit_depth(self):
        data_table = {
            AudioDataFormat.INT16: 16,
            AudioDataFormat.INT24: 24,
            AudioDataFormat.INT32: 32,
            AudioDataFormat.FLOAT32: 32,
        }
        return data_table[self]

    @classmethod
    def parse(cls, data_format: str) -> 'AudioDataFormat':
        data_table = {
            "int16": AudioDataFormat.INT16,
            "int24": AudioDataFormat.INT24,
            "int32": AudioDataFormat.INT32,
            "float32": AudioDataFormat.FLOAT32,
        }

        result = data_table.get(data_format.lower(), AudioDataFormat.UNKNOWN)
        if result == AudioDataFormat.UNKNOWN:
            raise ValueError(f"Unknown audio data format: {data_format}")

        return result

class AudioDeviceOption:
    """
    Audio device options for initialization.
    """
    def __init__(self, device_name: str, device_platform: str, sample_rate: int, channels: int, data_format: AudioDataFormat, input_ports: List[int]) -> None:
        self.device_name: str               = device_name
        self.device_platform: str           = device_platform
        self.sample_rate: int               = sample_rate
        self.channels: int                  = channels
        self.data_format: AudioDataFormat   = data_format
        self.input_ports: List[int]         = input_ports


    def __str__(self) -> str:
        return f"device_name={self.device_name}, device_platform={self.device_platform}, sample_rate={self.sample_rate}, channels={self.channels}, data_format={self.data_format}, input_ports={self.input_ports}"

class IAudioDevice(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def dispose(self) -> None:
        """
        Release resources.
        (e.g. Audio device, native resources etc.)
        """
        pass

    @abc.abstractmethod
    def initialize(self, option: AudioDeviceOption) -> None:
        """
        Initialize the Audio device.
        """
        pass

    @abc.abstractmethod
    def get_audio_devices(self) -> List[AudioDeviceInfo]:
        """
        Get a list of Audio devices.
        """
        return []

    @abc.abstractmethod
    def start_recording(self, duration: int) -> None:
        """
        Start recording audio. This function should be non-blocking.
        """
        pass

    @abc.abstractmethod
    def stop_recording(self) -> None:
        """
        Stop recording audio.
        """
        pass

    @abc.abstractmethod
    def export_audio(self, file_path: str) -> None:
        """
        Export recorded audio to a file.
        """
        pass
