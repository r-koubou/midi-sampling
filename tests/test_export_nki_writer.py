import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import pytest

from conftest import make_wav_bytes
from midi_sampling.export.abstractions import (
    InstrumentEnvelope,
    InstrumentExclusiveGroup,
    InstrumentModel,
    InstrumentPatchWriter,
    InstrumentRegion,
    PatchWriteContext,
    RegionLoop,
)
from midi_sampling.export.exceptions import ExportWriteError
from midi_sampling.export.nki_impl import NkiPatchWriter
from midi_sampling.export.nki_impl.nki_grouping import partition_groups
from midi_sampling.export.nki_impl.wav_info import read_wav_data_info

DEFAULT_ENVELOPE = InstrumentEnvelope(attack=0.0, release=0.3)

FIXED_TIME = 1_234_567_890


def make_region(**overrides) -> InstrumentRegion:
    values = dict(
        tone_id="tone-1",
        source_path=Path("processed/tone-1/a.wav"),
        sample_path="Samples/tone-1/a.wav",
        root_note=38,
        key_low=36,
        key_high=40,
        velocity_low=1,
        velocity_high=63,
        loop=None,
        exclusive_group=None,
        trigger="attack",
        rt_decay=None,
    )
    values.update(overrides)
    return InstrumentRegion(**values)


def make_instrument(regions, exclusive_groups=(), **overrides) -> InstrumentModel:
    values = dict(
        name="test-instrument",
        envelope=DEFAULT_ENVELOPE,
        regions=tuple(regions),
        exclusive_groups=tuple(exclusive_groups),
    )
    values.update(overrides)
    return InstrumentModel(**values)


def write_region_wavs(
    output_directory: Path, instrument: InstrumentModel, frames: int = 100
) -> None:
    for region in instrument.regions:
        path = output_directory / region.sample_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(make_wav_bytes(frames))


def write_patch(tmp_path: Path, instrument: InstrumentModel, frames: int = 100):
    write_region_wavs(tmp_path, instrument, frames=frames)
    writer = NkiPatchWriter(clock=lambda: FIXED_TIME + 0.9)
    return writer.write(
        PatchWriteContext(instrument=instrument, output_directory=tmp_path)
    )


def decompress_xml(patch_path: Path) -> str:
    return zlib.decompress(patch_path.read_bytes()[0x24:]).decode("utf-8")


class TestWavInfo:
    def test_reads_frame_count_and_data_size(self, tmp_path: Path):
        path = tmp_path / "a.wav"
        path.write_bytes(make_wav_bytes(frames=100, channels=2))

        info = read_wav_data_info(path)

        assert info.frame_count == 100
        assert info.data_size == 400

    def test_skips_chunks_before_data_with_padding(self, tmp_path: Path):
        path = tmp_path / "a.wav"
        path.write_bytes(
            make_wav_bytes(
                frames=10, extra_chunks=((b"smpl", b"\x01" * 61),)
            )
        )

        info = read_wav_data_info(path)

        assert info.frame_count == 10
        assert info.data_size == 20

    def test_rejects_non_wav_content(self, tmp_path: Path):
        path = tmp_path / "a.wav"
        path.write_bytes(b"RIFF-fake-wav-data")

        with pytest.raises(ExportWriteError, match="not a RIFF/WAVE"):
            read_wav_data_info(path)

    def test_rejects_truncated_data_chunk(self, tmp_path: Path):
        path = tmp_path / "a.wav"
        path.write_bytes(make_wav_bytes(frames=100)[:-50])

        with pytest.raises(ExportWriteError, match="truncated"):
            read_wav_data_info(path)

    def test_rejects_missing_file(self, tmp_path: Path):
        with pytest.raises(ExportWriteError, match="cannot read"):
            read_wav_data_info(tmp_path / "missing.wav")


class TestNkiGrouping:
    def test_attack_regions_share_the_default_group(self):
        groups, region_groups = partition_groups(
            make_instrument([make_region(), make_region(root_note=43)])
        )

        assert [(g.index, g.name) for g in groups] == [(0, "default")]
        assert groups[0].voice_group is None
        assert groups[0].release_trigger is False
        assert region_groups == (0, 0)

    def test_default_group_exists_even_when_empty(self):
        groups, region_groups = partition_groups(
            make_instrument(
                [make_region(exclusive_group=1)],
                [InstrumentExclusiveGroup(number=1, name="pair")],
            )
        )

        assert [g.name for g in groups] == ["default", "exec_00"]
        assert region_groups == (1,)

    def test_exclusive_groups_use_definition_order_ordinals(self):
        groups, region_groups = partition_groups(
            make_instrument(
                [
                    make_region(exclusive_group=2),
                    make_region(exclusive_group=1),
                ],
                [
                    InstrumentExclusiveGroup(number=1, name="pair"),
                    InstrumentExclusiveGroup(number=2, name="hats"),
                ],
            )
        )

        assert [(g.name, g.voice_group) for g in groups] == [
            ("default", None),
            ("exec_01", 2),
            ("exec_00", 1),
        ]
        assert region_groups == (1, 2)

    def test_release_tones_are_numbered_by_first_appearance(self):
        groups, region_groups = partition_groups(
            make_instrument(
                [
                    make_region(tone_id="rel-b", trigger="release"),
                    make_region(tone_id="rel-a", trigger="release"),
                    make_region(tone_id="rel-b", trigger="release"),
                ]
            )
        )

        assert [(g.name, g.release_trigger) for g in groups] == [
            ("default", False),
            ("release_00", True),
            ("release_01", True),
        ]
        assert region_groups == (1, 2, 1)

    def test_combined_exclusive_and_release_gets_a_composite_group(self):
        groups, _ = partition_groups(
            make_instrument(
                [
                    make_region(
                        tone_id="rel-a", trigger="release", exclusive_group=1
                    )
                ],
                [InstrumentExclusiveGroup(number=1, name="pair")],
            )
        )

        composite = groups[1]
        assert composite.name == "exec_00_release_00"
        assert composite.voice_group == 1
        assert composite.release_trigger is True


class TestNkiPatchWriter:
    def test_implements_the_patch_writer_base_class(self):
        writer = NkiPatchWriter()
        assert isinstance(writer, InstrumentPatchWriter)
        assert writer.format_id == "nki"
        assert writer.directory_name == "nki"
        assert writer.supported_audio_formats == ("wav",)

    def test_writes_the_documented_binary_header(self, tmp_path: Path):
        instrument = make_instrument(
            [
                make_region(),
                make_region(
                    tone_id="tone-2", sample_path="Samples/tone-2/b.wav"
                ),
            ]
        )

        outcome = write_patch(tmp_path, instrument, frames=100)

        assert outcome.patch_path == tmp_path / "test-instrument.nki"
        raw = outcome.patch_path.read_bytes()
        header = struct.unpack("<4sIHH6I", raw[:0x24])
        assert header[0] == b"\x5e\xe5\x6e\xb3"
        assert header[1] == 0x24
        assert header[2] == 0x0050
        assert header[3] == 2
        assert header[4:7] == (0, 0, 1)
        assert header[7] == FIXED_TIME
        # 100 frames x 2 bytes x mono, one `data` chunk per unique file.
        assert header[8] == 400
        assert header[9] == 0

    def test_xml_is_zlib_compressed_and_well_formed(self, tmp_path: Path):
        outcome = write_patch(tmp_path, make_instrument([make_region()]))

        xml_text = decompress_xml(outcome.patch_path)
        program = ET.fromstring(xml_text)
        assert program.tag == "NiSS_Program"
        assert program.get("name") == "test-instrument"
        assert program.get("version") == "0.50"

    def test_uses_crlf_line_endings_without_trailing_newline(
        self, tmp_path: Path
    ):
        outcome = write_patch(tmp_path, make_instrument([make_region()]))

        xml_text = decompress_xml(outcome.patch_path)
        assert xml_text.startswith('<?xml version="1.0"?>\r\n')
        assert "\r\n" in xml_text
        assert xml_text.replace("\r\n", "").count("\r") == 0
        assert xml_text.endswith("</NiSS_Program>")

    def test_renders_groups_zones_and_voice_groups(self, tmp_path: Path):
        instrument = make_instrument(
            [
                make_region(loop=RegionLoop(start_frame=10, end_frame=60)),
                make_region(exclusive_group=1),
                make_region(tone_id="rel-a", trigger="release"),
                make_region(
                    tone_id="rel-b", trigger="release", exclusive_group=2
                ),
            ],
            [
                InstrumentExclusiveGroup(number=1, name="pair"),
                InstrumentExclusiveGroup(number=2, name="hats"),
            ],
        )

        outcome = write_patch(tmp_path, instrument, frames=100)
        program = ET.fromstring(decompress_xml(outcome.patch_path))

        voice_groups = program.findall("Polyphony/VoiceGroup")
        assert [
            (
                vg.get("index"),
                vg.find("V[@name='name']").get("value"),
                vg.find("V[@name='maxNumVoices']").get("value"),
            )
            for vg in voice_groups
        ] == [
            ("0", "<instrument>", "128"),
            ("1", "pair", "1"),
            ("2", "hats", "1"),
        ]

        groups = program.findall("Groups/NiSS_Group")
        assert [
            (
                g.get("index"),
                g.get("name"),
                g.find("Parameters/V[@name='voiceGroup']").get("value"),
                g.find("Parameters/V[@name='releaseTrigger']").get("value"),
            )
            for g in groups
        ] == [
            ("0", "default", "-1", "no"),
            ("1", "exec_00", "1", "no"),
            ("2", "release_00", "-1", "yes"),
            ("3", "exec_01_release_01", "2", "yes"),
        ]

        zones = program.findall("Zones/NiSS_Zone")
        assert [
            (z.get("index"), z.get("groupIdx")) for z in zones
        ] == [("0", "0"), ("1", "1"), ("2", "2"), ("3", "3")]

        first = zones[0]
        parameters = {
            v.get("name"): v.get("value")
            for v in first.findall("Parameters/V")
        }
        assert parameters["sampleStart"] == "0"
        assert parameters["sampleEnd"] == "100"
        assert parameters["lowKey"] == "36"
        assert parameters["highKey"] == "40"
        assert parameters["rootKey"] == "38"
        assert parameters["lowVelocity"] == "1"
        assert parameters["highVelocity"] == "63"
        assert first.find("Sample/V[@name='file']").get("value") == (
            "Samples\\tone-1\\a.wav"
        )

        loop = first.find("Loops/Loop")
        loop_values = {
            v.get("name"): v.get("value") for v in loop.findall("V")
        }
        assert loop_values == {
            "loopStart": "10",
            "loopLength": "51",
            "loopCount": "0",
            "mode": "until_end",
            "alternatingLoop": "no",
            # Neutral frequency ratio; 0 detunes -12 st in real KONTAKT.
            "loopTuning": "1",
            "xfadeLength": "0",
        }
        # Unlooped zones keep an empty <Loops/> element like real files.
        assert zones[1].find("Loops") is not None
        assert len(zones[1].find("Loops")) == 0

    def test_renders_the_volume_envelope_in_milliseconds(
        self, tmp_path: Path
    ):
        instrument = make_instrument(
            [make_region()],
            envelope=InstrumentEnvelope(attack=0.005, release=1.2),
        )

        outcome = write_patch(tmp_path, instrument)
        xml_text = decompress_xml(outcome.patch_path)
        program = ET.fromstring(xml_text)

        modulators = program.findall(
            "Groups/NiSS_Group/IntModulators/NiSS_IntMod"
        )
        assert [
            m.find("V[@name='target']").get("value") for m in modulators
        ] == ["volume"]

        envelope = {
            v.get("name"): v.get("value")
            for v in modulators[0].findall("Envelope/V")
        }
        assert envelope == {
            "atkCurving": "0",
            "attack": "5.000000",
            "decay": "500.000000",
            "hold": "0.000000",
            "release": "1200.000000",
            "sustain": "1.000000",
        }
        # Exact serialization stays byte-comparable with real files.
        assert '          <V name="attack" value="5.000000"/>' in xml_text

    def test_keeps_required_fx_slots_inert(self, tmp_path: Path):
        outcome = write_patch(tmp_path, make_instrument([make_region()]))
        program = ET.fromstring(decompress_xml(outcome.patch_path))

        # The NiSS parser reads elements in a fixed order; the FX slots
        # must exist but stay empty, and the group filter is bypassed.
        program_fx = [
            element.tag
            for element in program
            if element.tag.startswith("FX")
        ]
        assert program_fx == [
            "FXDelay",
            "FXChorus",
            "FXFlanger",
            "FXPhaser",
            "FXReverb",
            "FXCompressor",
            "FXInverter",
            "FXLoFi",
            "FXShaper",
            "FXStereo",
            "FXFilter",
            "FXDistortion",
        ]
        assert all(len(program.find(tag)) == 0 for tag in program_fx)

        group = program.find("Groups/NiSS_Group")
        group_filter = group.find("Filter")
        assert group_filter.find("V[@name='bypass']").get("value") == "yes"
        group_fx = [
            element.tag
            for element in group
            if element.tag.startswith("FX")
        ]
        assert len(group_fx) == 6
        assert all(len(group.find(tag)) == 0 for tag in group_fx)

    def test_escapes_xml_attribute_values(self, tmp_path: Path):
        instrument = make_instrument(
            [make_region(sample_path="Samples/tone-1/a&b.wav")],
            name="amp&name's",
        )

        outcome = write_patch(tmp_path, instrument)
        xml_text = decompress_xml(outcome.patch_path)

        assert 'name="amp&amp;name&apos;s"' in xml_text
        assert 'value="Samples\\tone-1\\a&amp;b.wav"' in xml_text
        program = ET.fromstring(xml_text)
        assert program.get("name") == "amp&name's"

    def test_warns_when_rt_decay_is_ignored(self, tmp_path: Path, caplog):
        instrument = make_instrument(
            [make_region(tone_id="rel-a", trigger="release", rt_decay=6.0)]
        )

        with caplog.at_level("WARNING"):
            write_patch(tmp_path, instrument)

        assert "rt_decay is not supported by KONTAKT 1" in caplog.text
        assert "rel-a" in caplog.text

    def test_missing_sample_file_fails_loudly(self, tmp_path: Path):
        instrument = make_instrument([make_region()])
        writer = NkiPatchWriter()

        with pytest.raises(ExportWriteError):
            writer.write(
                PatchWriteContext(
                    instrument=instrument, output_directory=tmp_path
                )
            )
