from typing import Protocol

class MidiDeviceInformation:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return self.__str__()


class MidiDeviceInformationLoader(Protocol):
    """
    Load MidiDeviceInformation from a file or other source.
    """

    def load(self, file_path: str) -> MidiDeviceInformation:
        ...
