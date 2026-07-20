from typing import List
import abc

class MidiDevice(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def dispose(self) -> None:
        """
        Release resources.
        (e.g. MIDI device, native resources etc.)
        """
        pass

    @abc.abstractmethod
    def initialize(self) -> None:
        """
        Initialize the MIDI device.
        """
        pass

    @abc.abstractmethod
    def get_midi_device_names(self) -> List[str]:
        """
        Get a list of MIDI device names.
        """
        pass

    @abc.abstractmethod
    def play_note(
        self, channel: int, note: int, velocity: int, duration: float
    ) -> None:
        """
        Send to MIDI note on/off to the device.

        Args:
            channel:  MIDI channel (0-15)
            note:     MIDI note (0-127)
            velocity: MIDI velocity (0-127)
            duration: Duration in seconds
        """
        pass

    @abc.abstractmethod
    def send_program_change(
        self, channel: int, msb: int, lsb: int, program: int
    ) -> None:
        """
        Send to MIDI program change message.

        Args:
            channel: MIDI channel (0-15)
            msb:     MSB value of the program change message.
            lsb:     LSB value of the program change message.
            program: Program value of the program change message.
        """
        pass

    @abc.abstractmethod
    def send_message_from_file(self, midi_file_path: str) -> None:
        """
        Send to MIDI messages via given file.

        Args:
            midi_file_path: A midi file path. (*.mid)
        """
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        """
        Stop all notes, playback etc.
        """
        pass
