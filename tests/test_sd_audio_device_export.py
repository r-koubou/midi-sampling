import numpy as np
import pytest

soundfile = pytest.importorskip("soundfile")

from midi_sampling.devices.audio.sounddevice_impl.sd_audio_device import SdAudioDevice

from conftest import AUDIO_DEVICE_YAML


@pytest.fixture
def audio_device(tmp_path):
    information_path = tmp_path / "audio_device.yaml"
    information_path.write_text(AUDIO_DEVICE_YAML, encoding="utf-8")
    # export_audio only needs the loaded device information; no device is opened.
    return SdAudioDevice(str(information_path))


class TestExportAudio:
    def test_export_to_partial_wav_path(self, audio_device, tmp_path):
        """
        Recordings are first written to '*.wav.part'; the WAV format must
        be explicit because it cannot be inferred from the extension.
        """
        audio_device.recorded = np.zeros((4800, 2), dtype=np.float32)
        partial_path = tmp_path / "r036__k035-037__v001-063__s048.wav.part"

        audio_device.export_audio(str(partial_path))

        info = soundfile.info(str(partial_path))
        assert info.format == "WAV"
        assert info.samplerate == 48000
        assert info.channels == 2
        assert info.subtype == "PCM_24"
        assert info.frames == 4800
