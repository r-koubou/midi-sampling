from typing import List, override
import numpy as np
import sounddevice as sd
import wave

from .audiodevice import (
    IAudioDevice,
    AudioDeviceOption,
    AudioDataFormat,
    AudioDeviceInfo,
    NotFoundAudioDeviceError
)

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

        for sd_device in sd.query_devices():
            if sd_device["max_input_channels"] > 0:
                hostapi_info = sd.query_hostapis(sd_device["hostapi"])
                self.audio_devices.append(
                    AudioDeviceInfo(sd_device["index"], sd_device["name"], hostapi_info["name"])
                )

        self.recorded: any = None

    @override
    def initialize(self) -> None:
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

        sd_type_table = {
            AudioDataFormat.INT16: np.int16,
            AudioDataFormat.INT32: np.int32,
            AudioDataFormat.INT64: np.int64,
            AudioDataFormat.FLOAT32: np.float32,
            AudioDataFormat.FLOAT64: np.float64
        }

        if sd_type_table.get(self.option.data_format) is None:
            raise ValueError(f"Not supported data format. (={self.option.data_format})")

        print(self.option)
        sd.default.device       = [audio_in_device_index, None] # input, output. (Use input only)
        sd.default.dtype        = sd_type_table[self.option.data_format]
        sd.default.samplerate   = self.option.sample_rate
        sd.default.channels     = self.option.channels

        if self.option.device_platform.lower() == "asio":
            asio_in = sd.AsioSettings(channel_selectors=self.option.input_ports)
            sd.default.extra_settings = asio_in

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
        with wave.open(file_path, "wb") as f:
            f.setnchannels(option.channels)
            f.setsampwidth(option.data_format.bit_depth() // 8)
            f.setframerate(option.sample_rate)
            f.writeframes(self.recorded)
