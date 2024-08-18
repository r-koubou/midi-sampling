from typing import override

import time
import re
from logging import getLogger

import mido

from .mididevice import (
    IMidiDevice,
    MidiDeviceInfo,
    NotFoundMidiDeviceError
)

logger = getLogger(__name__)

class MidoMidiDevice(IMidiDevice):
    """
    Implementation of the IMidiDevice interface using the mido library.
    """
    def __init__(self, midi_out_device_name: str) -> None:
        """
        Parameters
        ----------
            midi_out_device_name:
                MIDI output device name.
        """
        self.midi_out_device_name = midi_out_device_name
        self.midi_devices: list[MidiDeviceInfo] = []

        self.midiout = None

        # Separate the device name and the port index number to enable description in a library-independent format in the configuration file.
        # In mido mido.get_output_names() implementation, the device name includes a internal port index number e.g. "Roland SC-8850 PART A 1". (" 1" is internal index number.)
        #
        # see also: https://mido.readthedocs.io/en/stable/backends/rtmidi.html
        #
        regex_trim  = re.compile(r'\s[0-9]+$')
        regex_index = re.compile(r'.*?\s([0-9]+$)')

        for name in mido.get_output_names():
            logger.debug(f"Found MIDI device: {name}")
            device_inedx = -1
            m = regex_index.match(name)
            if m:
                device_inedx = int(m.group(1).strip())
            trimed_name = regex_trim.sub('', name)
            self.midi_devices.append(MidiDeviceInfo(device_inedx, trimed_name))

    @override
    def initialize(self) -> None:
        devices = self.get_midi_devices()
        use_device: MidiDeviceInfo = None
        if not devices or len(devices) == 0:
            raise NotFoundMidiDeviceError()
        for device in devices:
            if device.name.find(self.midi_out_device_name) != -1:
                use_device = device
                break
        if not use_device:
            raise NotFoundMidiDeviceError(self.midi_out_device_name)

        try:
            # MidiDeviceInfo.name is indepent format of mido.get_output_names() implementation.
            self.midiout = mido.open_output(f"{use_device.name} {use_device.index}" )
        except:
            # Trying to open the port without the port index number.
            self.midiout = mido.open_output(self.midi_out_device_name )

        logger.info(f"Opened MIDI port: {self.midi_out_device_name}")

    @override
    def dispose(self) -> None:
        self.stop()
        try:
            self.midiout.close()
        except:
            pass

    @override
    def get_midi_devices(self) -> list[MidiDeviceInfo]:
        return self.midi_devices.copy()

    @override
    def play_note(self, channel: int, note: int, velocity: int, duration: float) -> None:
        note_on  = mido.Message('note_on', channel=channel, note=note, velocity=velocity)
        note_off = mido.Message('note_off', channel=channel, note=note, velocity=0)

        self.midiout.send(note_on)
        time.sleep(duration)
        self.midiout.send(note_off)

    @override
    def send_progam_change(self, channel: int, msb: int, lsb: int, program: int) -> None:
        msb_message = mido.Message('control_change', channel=channel, control=0, value=msb)
        lsb_message = mido.Message('control_change', channel=channel, control=32, value=lsb)
        program_change_message = mido.Message('program_change', channel=channel, program=program)

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
