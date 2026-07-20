from logging import getLogger
import typer

from midi_sampling.logging_management import init_logging_as_stdout

from midi_sampling.devices.midi.abstractions.midi_device_information import (
    MidiDeviceInformationLoader,
    MidiDeviceInformation,
)

from midi_sampling.devices.midi.mido_impl.mido_midi_device import (
    MidoMidiDevice,
    MidiDeviceInformation
)

from midi_sampling.devices.midi.mido_impl.mido_midi_device_information_loader import (
    MidoMidiDeviceInformationLoader,
)

logger = getLogger(__name__)


def main(midi_device_info_file_path: str):
    init_logging_as_stdout()

    loader: MidiDeviceInformationLoader = MidoMidiDeviceInformationLoader()
    info: MidiDeviceInformation = loader.load(midi_device_info_file_path)

    try:
        midi_out = MidoMidiDevice(info)

        logger.info("=" * 80)
        logger.info("Available MIDI device names")
        logger.info("=" * 80)
        for name in midi_out.get_midi_device_names():
            logger.info(name)
        logger.info("=" * 80)

        midi_out.initialize()

        logger.info("Sending MIDI note on/off message to the device...")
        midi_out.play_note(channel=0, note=60, velocity=100, duration=1.0)

    finally:
        if midi_out is not None:
            midi_out.dispose()


if __name__ == "__main__":
    typer.run(main)
