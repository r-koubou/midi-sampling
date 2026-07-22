import typer
import os
import os.path

from logging import getLogger

from midi_sampling.devices.audio.abstractions import AudioDevice
from midi_sampling.devices.audio.sounddevice_impl import SdAudioDevice

from midi_sampling.logging_management import init_logging_as_stdout

logger = getLogger(__name__)

def main(audio_information_file_path: str):

    init_logging_as_stdout()

    audio_device: AudioDevice = SdAudioDevice(audio_information_file_path)

    logger.info("=" * 80)
    logger.info("Available audio devices:")
    logger.info("=" * 80)
    for name in SdAudioDevice.get_device_names():
        logger.info(name)
    logger.info("=" * 80)

    audio_device.initialize()

    try:
        duration = 2
        audio_device.start_recording(duration)
        audio_device.stop_recording()

        output_file_path = ".temp/output.wav"
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        audio_device.export_audio(output_file_path)
        logger.info(f"Audio exported to {output_file_path}")
    finally:
        audio_device.dispose()

if __name__ == "__main__":
    typer.run(main)
