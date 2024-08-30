from typing import List, override
from logging import getLogger

import numpy as np
import sounddevice as sd
import soundfile as sf
import wave

from .audiodevice import (
    IAudioDevice,
    AudioDeviceOption,
    AudioDataFormat,
    AudioDeviceInfo,
    NotFoundAudioDeviceError
)

logger = getLogger(__name__)

class SdAudioDevice(IAudioDevice):
    """
    Implementation of the IAudioDevice interface using the sounddevice library.
    """
    def __init__(self, option: AudioDeviceOption) -> None:
        """
        Parameters
        ----------
            option:
                Audio device options for initialization.
        """
        self.option = option
        self.audio_devices: List[AudioDeviceInfo] = []

        sd_device_list = sorted(sd.query_devices(), key=lambda x: x["name"])

        for sd_device in sd_device_list:
            logger.debug(f"Found audio device: {sd_device}")
            if sd_device["max_input_channels"] > 0:
                hostapi_info = sd.query_hostapis(sd_device["hostapi"])
                self.audio_devices.append(
                    AudioDeviceInfo(sd_device["index"], sd_device["name"], hostapi_info["name"])
                )

        self.recorded: np.ndarray = None

    @override
    def initialize(self) -> None:
        logger.debug(f"AudioDeviceOption: {self.option}")

        audio_in_device_index = -1
        audio_devices = self.get_audio_devices()

        if len(audio_devices) == 0:
            raise NotFoundAudioDeviceError()

        for device in audio_devices:
            if device.name.find(self.option.device_name) != -1 and device.platform_name.find(self.option.device_platform) != -1:
                audio_in_device_index = device.index
                break
        if audio_in_device_index == -1:
            raise NotFoundAudioDeviceError(self.option.device_name)

        if self.option.data_format == AudioDataFormat.UNKNOWN:
            raise ValueError(f"Audio data format is unknown. (option.data_format={self.option.data_format})")

        logger.debug(f"Initialize audio device: {self.option.device_name}")

        sd.default.device       = [audio_in_device_index, None] # input, output. (Use input only)
        sd.default.samplerate   = self.option.sample_rate
        sd.default.channels     = self.option.channels

        if self.option.device_platform.lower() == "asio":
            asio_in = sd.AsioSettings(channel_selectors=self.option.input_ports)
            sd.default.extra_settings = asio_in
            logger.debug(f"ASIO input ports: {self.option.input_ports}")

    @override
    def dispose(self) -> None:
        try:
            self.stop_recording()
        finally:
            pass

    @override
    def get_audio_devices(self) -> List[AudioDeviceInfo]:
        return self.audio_devices.copy()

    @override
    def start_recording(self, duration: int) -> None:
        self.recorded = sd.rec(duration * self.option.sample_rate)

    @override
    def stop_recording(self) -> None:
        sd.wait()

    @override
    def export_audio(self, file_path: str) -> None:
        option = self.option

        #------------------------------------------------------
        # Sub-type check for soundfile
        #------------------------------------------------------
        sub_type = None

        if option.data_format == AudioDataFormat.INT16:
            sub_type = "PCM_16"
        elif option.data_format == AudioDataFormat.INT24:
            sub_type = "PCM_24"
        elif option.data_format == AudioDataFormat.INT32:
            sub_type = "PCM_32"
        elif option.data_format == AudioDataFormat.FLOAT32:
            sub_type = "FLOAT"

        logger.debug(f"sub_type: {sub_type}")

        sf.write(
            file=file_path,
            data=self.recorded,
            samplerate=option.sample_rate,
            subtype=sub_type
        )
