"""
Render the NiSS XML of a KONTAKT 1 program.

Everything static (element order, version attributes, parameter names
and neutral values) is copied from a program saved by KONTAKT 1 itself
(examples/kontakt/example_kontakt_v1.nki); only the instrument name,
groups, zones and the volume envelope are generated. Line endings are
CRLF with no trailing newline, as in the reference file.
"""

from midi_sampling.export.abstractions import (
    InstrumentModel,
    InstrumentRegion,
)
from midi_sampling.export.nki_impl.nki_grouping import KontaktGroup

LINE_ENDING = "\r\n"
BOOL_TRUE = "yes"
BOOL_FALSE = "no"

PROGRAM_VERSION = "0.50"
VOICE_GROUP_VERSION = "0.60"
GROUP_VERSION = "0.60"
ZONE_VERSION = "0.60"
INT_MOD_VERSION = "0.50"
EXT_MOD_VERSION = "0.80"
ENVELOPE_VERSION = "0.60"
# The reference file has no looped zone; 0.60 is the prevailing element
# version in it and has not been verified against a real looped NKI.
LOOP_VERSION = "0.60"

# Sustained-note defaults confirmed with the user: full sustain (linear
# 1.0 = 0.0 dB), no hold, half-second decay that full sustain makes inert.
ENVELOPE_HOLD_MS = 0.0
ENVELOPE_DECAY_MS = 500.0
ENVELOPE_SUSTAIN = 1.0

_ESCAPES = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&apos;"),
)


def escape_attribute(value: str) -> str:
    for character, entity in _ESCAPES:
        value = value.replace(character, entity)
    return value


def render_program(
    instrument: InstrumentModel,
    groups: tuple[KontaktGroup, ...],
    region_groups: tuple[int, ...],
    frame_counts: tuple[int, ...],
) -> str:
    lines: list[str] = ['<?xml version="1.0"?>']
    lines.append(
        f'<NiSS_Program index="0" '
        f'name="{escape_attribute(instrument.name)}" '
        f'version="{PROGRAM_VERSION}">'
    )
    _append_program_parameters(lines)
    _append_polyphony(lines, instrument)
    _append_program_fx(lines)

    lines.append("  <Groups>")
    for group in groups:
        _append_group(lines, instrument, group)
    lines.append("  </Groups>")

    lines.append("  <Zones>")
    for index, region in enumerate(instrument.regions):
        _append_zone(
            lines, index, region, region_groups[index], frame_counts[index]
        )
    lines.append("  </Zones>")

    lines.append("</NiSS_Program>")
    return LINE_ENDING.join(lines)


def _v(indent: int, name: str, value: str) -> str:
    return f'{" " * indent}<V name="{name}" value="{value}"/>'


def _append_program_parameters(lines: list[str]) -> None:
    lines.append("  <Parameters>")
    for name, value in (
        ("midiChannel", "0"),
        ("output", "0"),
        ("transpose", "0"),
        ("masterVolume", "0.5"),
        ("masterPan", "0.5"),
        ("masterTune", "1"),
        ("lowVelocity", "1"),
        ("highVelocity", "127"),
        ("lowKey", "0"),
        ("highKey", "127"),
        ("fingerPrint", "256"),
        ("activeGroupIdx", "0"),
        ("inputQuantizeMode", "off"),
        ("inputQuantizeNoteValue", "1"),
        ("muteMode", "none"),
        ("songTempo", "0"),
    ):
        lines.append(_v(4, name, value))
    lines.append("  </Parameters>")


def _append_polyphony(lines: list[str], instrument: InstrumentModel) -> None:
    lines.append("  <Polyphony>")
    _append_voice_group(
        lines,
        index=0,
        name="<instrument>",
        max_voices=128,
    )
    # One single-voice pool per exclusive group: a new note in the pool
    # kills the sounding one, which is the KONTAKT 1 way to choke.
    for group in instrument.exclusive_groups:
        _append_voice_group(
            lines, index=group.number, name=group.name, max_voices=1
        )
    lines.append("  </Polyphony>")


def _append_voice_group(
    lines: list[str], index: int, name: str, max_voices: int
) -> None:
    lines.append(
        f'    <VoiceGroup index="{index}" version="{VOICE_GROUP_VERSION}">'
    )
    for parameter, value in (
        ("name", escape_attribute(name)),
        ("mode", "kill_oldest"),
        ("preferReleased", BOOL_TRUE),
        ("maxNumVoices", str(max_voices)),
        ("msFadeTime", "10"),
        ("exclusionGroup", "-1"),
    ):
        lines.append(_v(6, parameter, value))
    lines.append("    </VoiceGroup>")


def _append_program_fx(lines: list[str]) -> None:
    # KONTAKT's NiSS parser reads elements in a fixed order and fails
    # with a syntax error when a known slot is missing, so the empty FX
    # slots must be present even though no effect is used.
    lines += [
        '  <FXDelay version="0.50"/>',
        '  <FXChorus version="0.50"/>',
        '  <FXFlanger version="0.50"/>',
        '  <FXPhaser version="0.50"/>',
        '  <FXReverb version="0.50"/>',
        '  <FXCompressor version="0.60"/>',
        '  <FXInverter version="0.60"/>',
        '  <FXLoFi version="0.60"/>',
        '  <FXShaper version="0.60"/>',
        '  <FXStereo version="0.70"/>',
        '  <FXFilter version="0.60"/>',
        '  <FXDistortion version="0.60"/>',
    ]


def _append_group(
    lines: list[str], instrument: InstrumentModel, group: KontaktGroup
) -> None:
    lines.append(
        f'    <NiSS_Group index="{group.index}" '
        f'name="{escape_attribute(group.name)}" '
        f'version="{GROUP_VERSION}">'
    )
    lines.append("      <Parameters>")
    release = BOOL_TRUE if group.release_trigger else BOOL_FALSE
    voice_group = -1 if group.voice_group is None else group.voice_group
    selected = BOOL_TRUE if group.index == 0 else BOOL_FALSE
    for name, value in (
        ("volume", "1.0"),
        ("pan", "0.5"),
        ("tune", "1.0"),
        ("keyTracking", BOOL_TRUE),
        ("reverse", BOOL_FALSE),
        ("releaseTrigger", release),
        ("releaseTriggerNoteMonophonic", BOOL_FALSE),
        ("m_bMuted", BOOL_FALSE),
        ("m_bSolo", BOOL_FALSE),
        ("m_iRow", "-1"),
        ("m_iCol", "-1"),
        ("rlsTrigCounter", "0"),
        ("output", "0"),
        ("midiChannel", "0"),
        ("voiceGroup", str(voice_group)),
        ("selectedForEdit", selected),
    ):
        lines.append(_v(8, name, value))
    lines.append("      </Parameters>")

    lines += [
        '      <PlayPosOffset version="0.50"/>',
        '      <LoopOffset version="0.50"/>',
        '      <SendLevels version="0.50"/>',
        "      <GroupStart>",
        '        <StartCriteria index="0" version="0.70"/>',
        '        <StartCriteria index="1" version="0.70"/>',
        '        <StartCriteria index="2" version="0.70"/>',
        '        <StartCriteria index="3" version="0.70"/>',
        "      </GroupStart>",
        '      <Grain version="0.70"/>',
        # Same fixed-order rule as the program FX: the filter and FX
        # slots must exist. The filter is bypassed instead of removed.
        '      <Filter version="0.70">',
        _v(8, "type", "lp2pole"),
        _v(8, "executionOrder", "1"),
        _v(8, "bypass", BOOL_TRUE),
        _v(8, "cutoff", "0.983333"),
        _v(8, "resonance", "0.000000"),
        "      </Filter>",
        '      <FXCompressor version="0.60"/>',
        '      <FXInverter version="0.60"/>',
        '      <FXLoFi version="0.60"/>',
        '      <FXShaper version="0.60"/>',
        '      <FXStereo version="0.70"/>',
        '      <FXDistortion version="0.60"/>',
    ]
    _append_int_modulators(lines, instrument)
    _append_ext_modulators(lines)
    lines.append("    </NiSS_Group>")


def _append_int_modulators(
    lines: list[str], instrument: InstrumentModel
) -> None:
    # Only the volume AHDSR: cutoff/pitch envelope slots the reference
    # file carried were dropped after loading feedback in real KONTAKT.
    lines.append("      <IntModulators>")
    envelope = instrument.envelope
    lines += [
        f'        <NiSS_IntMod index="0" version="{INT_MOD_VERSION}">',
        _v(10, "target", "volume"),
        _v(10, "intensity", "1"),
        _v(10, "bypass", BOOL_FALSE),
        _v(10, "retrigger", BOOL_TRUE),
        f'          <Envelope type="ahdsr" version="{ENVELOPE_VERSION}">',
        _v(12, "atkCurving", "0"),
        _v(12, "attack", f"{envelope.attack * 1000.0:.6f}"),
        _v(12, "decay", f"{ENVELOPE_DECAY_MS:.6f}"),
        _v(12, "hold", f"{ENVELOPE_HOLD_MS:.6f}"),
        _v(12, "release", f"{envelope.release * 1000.0:.6f}"),
        _v(12, "sustain", f"{ENVELOPE_SUSTAIN:.6f}"),
        "          </Envelope>",
        "        </NiSS_IntMod>",
    ]
    lines.append("      </IntModulators>")


def _append_ext_modulators(lines: list[str]) -> None:
    lines += [
        "      <ExtModulators>",
        f'        <NiSS_ExtMod index="0" version="{EXT_MOD_VERSION}">',
        _v(10, "target", "volume"),
        _v(10, "intensity", "1"),
        _v(10, "bypass", BOOL_FALSE),
        _v(10, "delay", "0"),
        _v(10, "source", "velocity"),
        "        </NiSS_ExtMod>",
        f'        <NiSS_ExtMod index="1" version="{EXT_MOD_VERSION}">',
        _v(10, "target", "pitch"),
        _v(10, "intensity", "0.16666667"),
        _v(10, "bypass", BOOL_FALSE),
        _v(10, "delay", "0"),
        _v(10, "source", "pitchBend"),
        "        </NiSS_ExtMod>",
        "      </ExtModulators>",
    ]


def _append_zone(
    lines: list[str],
    index: int,
    region: InstrumentRegion,
    group_index: int,
    frame_count: int,
) -> None:
    lines.append(
        f'    <NiSS_Zone index="{index}" groupIdx="{group_index}" '
        f'version="{ZONE_VERSION}">'
    )
    lines.append("      <Parameters>")
    for name, value in (
        ("sampleStart", "0"),
        ("sampleEnd", str(frame_count)),
        ("lowVelocity", str(region.velocity_low)),
        ("highVelocity", str(region.velocity_high)),
        ("lowKey", str(region.key_low)),
        ("highKey", str(region.key_high)),
        ("fadeLowVelo", "0"),
        ("fadeHighVelo", "0"),
        ("fadeLowKey", "0"),
        ("fadeHighKey", "0"),
        ("rootKey", str(region.root_note)),
        ("zoneVolume", "1.000000"),
        ("zonePan", "0.50000"),
        ("zoneTune", "1.00000000"),
        ("slicerSens", "0"),
        ("sourceZoneIdx", "-1"),
        ("sourceZoneSliceIdx", "-1"),
        ("expandedSliceKey", "-1"),
        ("origTempo", "-1"),
        ("mRetriggerInfo.active", BOOL_FALSE),
        ("mRetriggerInfo.clockCount", "0"),
        ("mRetriggerInfo.lengthMode", "-1"),
        ("mRetriggerInfo.bars", "-1"),
        ("mRetriggerInfo.beats", "-1"),
        ("mRetriggerInfo.signNominator", "-1"),
        ("mRetriggerInfo.signDenominator", "-1"),
    ):
        lines.append(_v(8, name, value))
    lines.append("      </Parameters>")

    _append_loops(lines, region)

    sample_path = escape_attribute(region.sample_path.replace("/", "\\"))
    lines += [
        "      <Sample>",
        f'        <V name="file" value="{sample_path}"/>',
        "      </Sample>",
        "    </NiSS_Zone>",
    ]


def _append_loops(lines: list[str], region: InstrumentRegion) -> None:
    loop = region.loop
    if loop is None:
        lines.append("      <Loops/>")
        return
    # RegionLoop.end_frame is inclusive (smpl chunk convention);
    # loopEnd = loopStart + loopLength per the format research.
    lines += [
        "      <Loops>",
        f'        <Loop index="0" version="{LOOP_VERSION}">',
        _v(10, "loopStart", str(loop.start_frame)),
        _v(10, "loopLength", str(loop.end_frame - loop.start_frame + 1)),
        _v(10, "loopCount", "0"),
        _v(10, "mode", "until_end"),
        _v(10, "alternatingLoop", BOOL_FALSE),
        # Frequency ratio like every tune parameter; 0 was read back by
        # KONTAKT as -12 semitones and broke the sustain loop.
        _v(10, "loopTuning", "1"),
        _v(10, "xfadeLength", "0"),
        "        </Loop>",
        "      </Loops>",
    ]
