from pathlib import Path

import pytest

from midi_sampling.devices.audio.abstractions import (
    AudioDataFormat,
    AudioDevice,
    AudioDeviceInformation,
)
from midi_sampling.devices.midi.abstractions import MidiDevice
from midi_sampling.sampling.planning import SamplingPlan, SamplingPlanBuilder
from midi_sampling.sampling.resolving import DefinitionResolver, ResolvedSession


class FakeAudioInformationLoader:
    """
    AudioDeviceInformationLoader that returns fixed information without
    depending on the sounddevice implementation.
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        channels: int = 2,
        data_format: AudioDataFormat = AudioDataFormat.INT24,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.data_format = data_format

    def load(self, file_path: str) -> AudioDeviceInformation:
        assert Path(file_path).is_file()
        return AudioDeviceInformation(
            device_name="Fake Audio Device",
            device_platform="FAKE",
            sample_rate=self.sample_rate,
            channels=self.channels,
            data_format=self.data_format,
            input_ports=[0, 1],
        )


class FakeAudioDevice(AudioDevice):
    """
    Records every call into a shared event list and writes dummy bytes
    on export. Can be configured to fail on the N-th export.
    """

    def __init__(self, events: list | None = None, fail_on_export_index: int | None = None):
        self.events = events if events is not None else []
        self.fail_on_export_index = fail_on_export_index
        self.export_count = 0

    def initialize(self) -> None:
        self.events.append(("audio.initialize",))

    def dispose(self) -> None:
        self.events.append(("audio.dispose",))

    def get_device_names(self) -> list[str]:
        return ["Fake Audio Device"]

    def start_recording(self, duration: float) -> None:
        self.events.append(("audio.start_recording", duration))

    def stop_recording(self) -> None:
        self.events.append(("audio.stop_recording",))

    def export_audio(self, file_path: str) -> None:
        if (
            self.fail_on_export_index is not None
            and self.export_count == self.fail_on_export_index
        ):
            self.export_count += 1
            raise RuntimeError("Recording failed")
        self.export_count += 1
        self.events.append(("audio.export_audio", file_path))
        Path(file_path).write_bytes(b"RIFF-fake-wav-data")


class FakeMidiDevice(MidiDevice):
    def __init__(self, events: list | None = None):
        self.events = events if events is not None else []

    def initialize(self) -> None:
        self.events.append(("midi.initialize",))

    def dispose(self) -> None:
        self.events.append(("midi.dispose",))

    def get_midi_device_names(self) -> list[str]:
        return ["Fake MIDI Device"]

    def play_note(self, channel: int, note: int, velocity: int, duration: float) -> None:
        self.events.append(("midi.play_note", channel, note, velocity, duration))

    def send_program_change(self, channel: int, msb: int, lsb: int, program: int) -> None:
        self.events.append(("midi.send_program_change", channel, msb, lsb, program))

    def send_message_from_file(self, midi_file_path: str) -> None:
        self.events.append(("midi.send_message_from_file", midi_file_path))

    def stop(self) -> None:
        self.events.append(("midi.stop",))


DEFAULT_ZONES_YAML = """\
schema_version: 1
kind: zone_layout

zones:
  - low: 36
    root: 38
    high: 40

  - low: 41
    root: 43
    high: 45
"""

DEFAULT_VELOCITIES_YAML = """\
schema_version: 1
kind: velocity_profile

layers:
  - low: 1
    high: 63
    send: 48

  - low: 64
    high: 127
    send: 112
"""

DEFAULT_TONE_YAML = """\
schema_version: 1
kind: sampling_definition

id: tone-1
name: Tone 1

midi_program:
  bank_msb: 0
  bank_lsb: 0
  program: 41

zone_layout:
  file: ../presets/zones.yaml

velocity_profile:
  file: ../presets/velocities.yaml

timing:
  note_on: 4.0
  release_capture: 3.0
"""

DEFAULT_SESSION_YAML = """\
schema_version: 1
kind: sampling_session

audio_device:
  file: devices/audio_device.yaml

midi_device:
  file: devices/midi_device.yaml

midi:
  channel: 0
  initialization_files: []

timing:
  program_change_settle: 0.5
  pre_roll: 1.0
  inter_sample_wait: 0.5

output:
  directory: recorded

definitions:
  - file: tones/tone1.yaml
"""

AUDIO_DEVICE_YAML = """\
device_name: "Fake Audio Device"
device_platform: "FAKE"
input_ports: [0, 1]
channels: 2
sample_rate: 48000
data_format: "int24"
"""

MIDI_DEVICE_YAML = """\
device_name: "Fake MIDI Device"
"""


def make_session(
    root: Path,
    session_yaml: str = DEFAULT_SESSION_YAML,
    tone_yaml: str = DEFAULT_TONE_YAML,
    zones_yaml: str = DEFAULT_ZONES_YAML,
    velocities_yaml: str = DEFAULT_VELOCITIES_YAML,
    extra_files: dict[str, str] | None = None,
) -> Path:
    """
    Write a complete session definition tree under `root` and return the
    session file path.
    """
    files = {
        "session.yaml": session_yaml,
        "tones/tone1.yaml": tone_yaml,
        "presets/zones.yaml": zones_yaml,
        "presets/velocities.yaml": velocities_yaml,
        "devices/audio_device.yaml": AUDIO_DEVICE_YAML,
        "devices/midi_device.yaml": MIDI_DEVICE_YAML,
    }
    if extra_files:
        files.update(extra_files)

    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return root / "session.yaml"


def resolve_session(session_path: Path) -> ResolvedSession:
    resolver = DefinitionResolver(FakeAudioInformationLoader())
    return resolver.resolve(session_path)


def build_plan(session_path: Path) -> SamplingPlan:
    return SamplingPlanBuilder().build(resolve_session(session_path))


@pytest.fixture
def session_path(tmp_path: Path) -> Path:
    return make_session(tmp_path)


@pytest.fixture
def plan(session_path: Path) -> SamplingPlan:
    return build_plan(session_path)
