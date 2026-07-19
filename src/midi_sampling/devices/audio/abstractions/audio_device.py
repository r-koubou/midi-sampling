from typing import List
import abc

from midi_sampling.devices.audio.abstractions.audio_device_information import AudioDeviceInformation

class AudioDevice(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def dispose(self) -> None:
        """
        Release resources.
        (e.g. Audio device, native resources etc.)
        """
        pass

    @abc.abstractmethod
    def initialize(self) -> None:
        """
        Initialize the Audio device.
        """
        pass

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
