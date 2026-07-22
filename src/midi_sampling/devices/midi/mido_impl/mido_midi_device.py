from typing import override

import time
import re
from logging import getLogger

import mido

from midi_sampling.devices.midi.abstractions.midi_device import MidiDevice
from midi_sampling.devices.midi.abstractions.not_found_midi_device_error import (
    NotFoundMidiDeviceError,
)

from midi_sampling.devices.midi.mido_impl.mido_midi_device_information_loader import (
    MidoMidiDeviceInformationLoader,
)

logger = getLogger(__name__)


class MidoMidiDevice(MidiDevice):
    """
    Implementation of the MidiDevice interface using the mido library.
    """

    def __init__(self, midi_device_information_file_path: str) -> None:
        """
        Args:
            midi_device_information_file_path: Path to the MIDI device information file.
        """
        self.midi_device_information = MidoMidiDeviceInformationLoader().load(
            midi_device_information_file_path
        )
        self.midiout = None

    @classmethod
    def _extract_device_name_and_index(cls, name: str) -> tuple[str, int | None]:
        """
        Extract the device name and index from the mido device name.

        Args:
            name: The device name from mido.get_output_names().

        Returns:
            A tuple containing the device name and the index (or None if not found).
        Note:
            In mido mido.get_output_names() implementation, the device name includes a internal port index number e.g. "Roland SC-8850 PART A 1". (`1` is internal index number.)
            see also: https://mido.readthedocs.io/en/stable/backends/rtmidi.html
        """
        regex_trim = re.compile(r"\s[0-9]+$")
        regex_index = re.compile(r".*?\s([0-9]+$)")

        trimed_name = regex_trim.sub("", name)
        m = regex_index.match(name)
        device_index = int(m.group(1).strip()) if m else None

        return trimed_name, device_index

    @override
    def initialize(self) -> None:

        # Search for the MIDI Out device that matches the specified name
        for name in mido.get_output_names():
            trimed_name, device_index = self._extract_device_name_and_index(name)

            if trimed_name != self.midi_device_information.name:
                continue

            if device_index is not None:
                break

        if device_index is None:
            raise NotFoundMidiDeviceError(self.midi_device_information)

        try:
            # MidiDeviceInfo.name is indepent format of mido.get_output_names() implementation.
            self.midiout = mido.open_output(
                f"{self.midi_device_information.name} {device_index}"
            )
        except:
            # Trying to open the port without the port index number.
            self.midiout = mido.open_output(self.midi_device_information.name)

        logger.info(f"Opened MIDI port: {self.midi_device_information}")

    @override
    def dispose(self) -> None:
        self.stop()
        try:
            self.midiout.close()
            logger.info(f"Closed MIDI port: {self.midi_device_information.name}")
        except:
            pass

    @classmethod
    def get_device_names(cls) -> list[str]:
        result: list[str] = []
        for name in mido.get_output_names():
            trimed_name, device_index = cls._extract_device_name_and_index(name)
            if trimed_name not in result and device_index is not None:
                result.append(trimed_name)
        return result

    @override
    def play_note(
        self, channel: int, note: int, velocity: int, duration: float
    ) -> None:
        note_on = mido.Message("note_on", channel=channel, note=note, velocity=velocity)
        note_off = mido.Message("note_off", channel=channel, note=note, velocity=0)

        self.midiout.send(note_on)
        time.sleep(duration)
        self.midiout.send(note_off)

    @override
    def send_program_change(
        self, channel: int, msb: int, lsb: int, program: int
    ) -> None:
        msb_message = mido.Message(
            "control_change", channel=channel, control=0, value=msb
        )
        lsb_message = mido.Message(
            "control_change", channel=channel, control=32, value=lsb
        )
        program_change_message = mido.Message(
            "program_change", channel=channel, program=program
        )

        self.midiout.send(msb_message)
        self.midiout.send(lsb_message)
        self.midiout.send(program_change_message)

    @override
    def send_message_from_file(self, midi_file_path: str) -> None:
        midi = mido.MidiFile(midi_file_path)
        for msg in midi.play():
            self.midiout.send(msg)

    @override
    def stop(self) -> None:
        try:
            self.midiout.panic()
        except:
            pass
        try:
            self.midiout.reset()
        except:
            pass
