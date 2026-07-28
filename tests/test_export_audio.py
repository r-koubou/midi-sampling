from pathlib import Path

import pytest

from midi_sampling.export.audio import AudioExporter, resolve_flac_bit_depth
from midi_sampling.export.exceptions import ExportDefinitionError

sf = pytest.importorskip("soundfile")
np = pytest.importorskip("numpy")

SAMPLE_RATE = 48000


def write_wav(path: Path, subtype: str, frames: int = 4800) -> None:
    """
    A full-scale ramp exercises every bit of the sample width, so a
    lossy conversion would be caught by the equality assertions below.
    """
    ramp = np.linspace(-1.0, 1.0, frames, endpoint=False)
    data = np.column_stack([ramp, -ramp])
    sf.write(str(path), data, SAMPLE_RATE, format="WAV", subtype=subtype)


class TestResolveFlacBitDepth:
    def test_integer_sources_pass_through(self):
        assert resolve_flac_bit_depth("int16", None) == 16
        assert resolve_flac_bit_depth("int24", None) == 24

    def test_declared_depth_wins(self):
        assert resolve_flac_bit_depth("int24", 16) == 16
        assert resolve_flac_bit_depth("float32", 24) == 24

    def test_lossy_sources_require_declared_depth(self):
        with pytest.raises(ExportDefinitionError, match="bit_depth"):
            resolve_flac_bit_depth("float32", None)
        with pytest.raises(ExportDefinitionError, match="bit_depth"):
            resolve_flac_bit_depth("int32", None)

    def test_unknown_format_is_rejected(self):
        with pytest.raises(ExportDefinitionError, match="cannot encode"):
            resolve_flac_bit_depth("mp3", 16)


class TestWavExport:
    def test_copy_is_byte_exact(self, tmp_path: Path):
        source = tmp_path / "source.wav"
        destination = tmp_path / "out" / "copy.wav"
        source.write_bytes(b"RIFF-with-smpl-chunk")

        AudioExporter(audio_format="wav").export(source, destination, "int24")

        assert destination.read_bytes() == source.read_bytes()


class TestFlacExport:
    @pytest.mark.parametrize(
        "subtype,data_format",
        [("PCM_16", "int16"), ("PCM_24", "int24")],
    )
    def test_integer_passthrough_is_lossless(
        self, tmp_path: Path, subtype: str, data_format: str
    ):
        source = tmp_path / "source.wav"
        destination = tmp_path / "out" / "sample.flac"
        write_wav(source, subtype)

        AudioExporter(audio_format="flac").export(source, destination, data_format)

        original, _ = sf.read(str(source), dtype="int32", always_2d=True)
        encoded, encoded_rate = sf.read(
            str(destination), dtype="int32", always_2d=True
        )
        assert encoded_rate == SAMPLE_RATE
        assert np.array_equal(original, encoded)

    def test_float_source_encodes_with_declared_depth(self, tmp_path: Path):
        source = tmp_path / "source.wav"
        destination = tmp_path / "out" / "sample.flac"
        write_wav(source, "FLOAT")

        AudioExporter(audio_format="flac", bit_depth=24).export(
            source, destination, "float32"
        )

        info = sf.info(str(destination))
        assert info.format == "FLAC"
        assert info.subtype == "PCM_24"
        assert info.frames == sf.info(str(source)).frames

    def test_frame_count_is_preserved(self, tmp_path: Path):
        """
        Loop frames in the manifest stay valid only if FLAC encoding
        never changes the frame count.
        """
        source = tmp_path / "source.wav"
        destination = tmp_path / "sample.flac"
        write_wav(source, "PCM_24", frames=12345)

        AudioExporter(audio_format="flac").export(source, destination, "int24")

        assert sf.info(str(destination)).frames == 12345
