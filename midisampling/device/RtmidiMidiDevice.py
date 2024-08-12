from typing import override

import time
import rtmidi

from .mididevice import (
    IMidiDevice,
    MidiDeviceInfo,
    NotFoundMidiDeviceError
)

class RtmidiMidiDevice(IMidiDevice):
    """
    Implementation of the IMidiDevice interface using the rtmidi library.
    """
    def __init__(self, midi_out_device_name: str) -> None:
        """
        Parameters
        ----------
            midi_out_device_name:
                MIDI output device name.
        """
        self.midi_out_device_name = midi_out_device_name
        self.midiout = rtmidi.MidiOut()

        self.midi_devices: list[MidiDeviceInfo] = []
        for index, name in enumerate(self.midiout.get_ports()):
            self.midi_devices.append(MidiDeviceInfo(index, name))

    @override
    def initialize(self) -> None:
        midiout_port = -1
        devices = self.get_midi_devices()
        if not devices:
            raise NotFoundMidiDeviceError()
        for i, device in enumerate(devices):
            if device.name.find(self.midi_out_device_name) != -1:
                midiout_port = i
                break
        if midiout_port == -1:
            raise NotFoundMidiDeviceError(self.midi_out_device_name)

        self.midiout.open_port(midiout_port)

    @override
    def dispose(self) -> None:
        try:
            del self.midiout
        finally:
            pass

    @override
    def get_midi_devices(self) -> list[MidiDeviceInfo]:
        return self.midi_devices.copy()

    @override
    def play_note(self, channel: int, note: int, velocity: int, duration: float) -> None:
        MIDI_ON  = 0x90
        MIDI_OFF = 0x80
        self.midiout.send_message([MIDI_ON + channel, note, velocity])
        time.sleep(duration)
        self.midiout.send_message([MIDI_OFF + channel, note, 0])

    @override
    def send_message_from_file(self, midi_file_path: str) -> None:
        pass
