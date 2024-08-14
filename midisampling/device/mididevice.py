from typing import List
import abc

class NotFoundMidiDeviceError(Exception):
    def __init__(self, device_name: str = None):
        self.device_name = device_name

    def __str__(self):
        if self.device_name:
            return f"MIDI Device `{self.device_name}` is not found."
        else:
            return "MIDI Device is not found."

class MidiDeviceInfo:
    def __init__(self, index: int, name: str):
        self.index = index
        self.name  = name

    def __str__(self):
        return f"{self.index}: {self.name}"

    def __repr__(self):
        return self.__str__()

class IMidiDevice(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def dispose(self) -> None:
        """
        Release resources.
        (e.g. MIDI device, native resources etc.)
        """
        pass

    @abc.abstractmethod
    def initialize() -> None:
        """
        Initialize the MIDI device.
        """
        pass

    @abc.abstractmethod
    def get_midi_devices() -> List[MidiDeviceInfo]:
        """
        Get a list of MIDI devices.
        """
        return []

    @abc.abstractmethod
    def play_note(self, channel: int, note: int, velocity: int, duration: float) -> None:
        """
        Send to MIDI note on/off to the device.

        Parameters
        ----------
            channel:
                MIDI channel (0-15)
            note:
                MIDI note (0-127)
            velocity:
                MIDI velocity (0-127)
            duration:
                Duration in seconds
        """
        pass

    @abc.abstractmethod
    def send_message_from_file(self, midi_file_path: str) -> None:
        """
        Send to MIDI messages via given file.
        Parameters
        ----------
            midi_file_path:
                A midi file path. (*.mid)
        """
        pass
