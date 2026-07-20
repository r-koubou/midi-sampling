from midi_sampling.devices.midi.abstractions.midi_device_information import MidiDeviceInformation
from typing import Protocol


class MidiDeviceInformationLoader(Protocol):
    """
    Load MidiDeviceInformation from a file or other source.
    """

    def load(self, file_path: str) -> MidiDeviceInformation:
        ...
