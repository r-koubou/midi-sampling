from midi_sampling.devices.audio.abstractions.audio_device_information import AudioDeviceInformation
from typing import Protocol


class AudioDeviceInformationLoader(Protocol):
    """
    Load AudioDeviceInformation from a file or other source.
    """

    def load(self, file_path: str) -> AudioDeviceInformation: ...
