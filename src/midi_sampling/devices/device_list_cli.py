import typer

from midi_sampling import logging_management
from midi_sampling.devices.audio.sounddevice_impl import SdAudioDevice
from midi_sampling.devices.midi.mido_impl import MidoMidiDevice


def app() -> None:
    typer.echo("Available audio devices")

    typer.echo("="*80)
    typer.echo("Audio")
    typer.echo("="*80)

    for device in SdAudioDevice.get_device_names():
        typer.echo(device)

    typer.echo("="*80)
    typer.echo("MIDI")
    typer.echo("="*80)

    for device in MidoMidiDevice.get_device_names():
        typer.echo(device)

if __name__ == "__main__":
    typer.run(app, help="Shows available devices")
