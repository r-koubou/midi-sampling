import os

# Enable ASIO support if available
os.environ["SD_ENABLE_ASIO"] = "1"

import logging
import numpy as np
import sounddevice as sd
import soundfile as sf

from midi_sampling.devices.audio.abstractions import (
    NotFoundAudioDeviceError,
    AudioDataFormat,
    AudioDevice,
)


from midi_sampling.devices.audio.sounddevice_impl.sd_audio_device_information_loader import (
    SdAudioDeviceInformationLoader,
)

logger = logging.getLogger(__name__)


class SdAudioDevice(AudioDevice):
    """
    Implementation of the AudioDevice interface using the sounddevice library.
    """

    def __init__(self, audio_information_file_path: str) -> None:
        """
        Args:
            audio_information_file_path:
                Path to the YAML file containing AudioDeviceInformation.
        """
        self.audio_information = SdAudioDeviceInformationLoader().load(
            audio_information_file_path
        )

        self.audio_device = None
        self.recorded: np.ndarray = None

    def initialize(self):

        # Search for the audio device that matches the specified name and platform

        sd_device_list = sorted(sd.query_devices(), key=lambda x: x["name"])
        sd_input_device = None

        for sd_device in sd_device_list:
            logger.debug(f"Found audio device: {sd_device}")
            if (
                sd_device["max_input_channels"] > 0
                and sd_device["name"] == self.audio_information.device_name
                and sd.query_hostapis(sd_device["hostapi"])["name"]
                == self.audio_information.device_platform
            ):
                sd_input_device = sd_device

        if sd_input_device is None:
            raise NotFoundAudioDeviceError()

        self.audio_device = sd_input_device

        # Set the default audio device and parameters
        sd.default.device = self.audio_device["index"]
        sd.default.samplerate = self.audio_information.sample_rate
        sd.default.channels = self.audio_information.channels

        # Set thr parameter if platform is "ASIO"
        extra_settings = None
        logger.debug(
            f"AudioDeviceOption: {self.audio_information.device_name}, "
            f"Platform: {self.audio_information.device_platform}, "
            f"Sample Rate: {self.audio_information.sample_rate}, "
            f"Channels: {self.audio_information.channels}"
        )
        if self.audio_information.device_platform.lower() == "asio":
            extra_settings = sd.AsioSettings(
                channel_selectors=self.audio_information.input_ports
            )
            logger.info(
                "Configured ASIO input ports: " f"{self.audio_information.input_ports}"
            )

        # Set the extra settings for the audio device if applicable
        if extra_settings is not None:
            sd.default.extra_settings = extra_settings

        logger.info(
            f"Initialized audio device: {self.audio_device['name']} with sample rate {self.audio_information.sample_rate} and channels {self.audio_information.channels}"
        )

    def dispose(self):
        try:
            self.stop_recording()
        finally:
            pass

    def get_device_names(self) -> list[str]:
        result = []

        for device in sd.query_devices():
            if device["max_input_channels"] > 0:
                result.append(
                    f"{device['name']}, platform: {sd.query_hostapis(device['hostapi'])['name']}, input channels: {device['max_input_channels']}"
                )

        result.sort()
        return result

    def start_recording(self, duration):
        # Convert seconds to frames immediately before recording.
        self.recorded = sd.rec(round(duration * sd.default.samplerate))

    def stop_recording(self):
        sd.wait()

    def export_audio(self, file_path):
        info = self.audio_information

        # ------------------------------------------------------
        # Sub-type check for soundfile
        # ------------------------------------------------------
        sub_type = None

        if info.data_format == AudioDataFormat.INT16:
            sub_type = "PCM_16"
        elif info.data_format == AudioDataFormat.INT24:
            sub_type = "PCM_24"
        elif info.data_format == AudioDataFormat.INT32:
            sub_type = "PCM_32"
        elif info.data_format == AudioDataFormat.FLOAT32:
            sub_type = "FLOAT"

        logger.debug(f"sub_type: {sub_type}")

        sf.write(
            file=file_path,
            data=self.recorded,
            samplerate=info.sample_rate,
            subtype=sub_type,
        )
