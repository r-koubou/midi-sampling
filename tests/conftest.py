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


# ---------------------------------------------------------------------------
# Postprocess helpers
# ---------------------------------------------------------------------------

DEFAULT_POSTPROCESS_SESSION_YAML = """\
schema_version: 1
kind: postprocess_session

source:
  directory: recorded

output:
  directory: processed

stages:
  - kind: trim
"""


def make_recorded_output(root: Path) -> Path:
    """
    Produce a real, completed sampling output tree under `root/recorded`
    using the fake devices, and return the recorded root.

    Going through SamplingExecutor rather than hand-writing a manifest
    keeps the postprocess tests honest about the actual contract between
    the two stages.
    """
    from midi_sampling.sampling import SamplingExecutor

    session = make_session(root)
    sampling_plan = build_plan(session)

    SamplingExecutor(
        audio_device=FakeAudioDevice(),
        midi_device=FakeMidiDevice(),
        sleep=lambda seconds: None,
    ).execute(sampling_plan)

    return sampling_plan.output_root


def make_postprocess_session(
    root: Path, session_yaml: str = DEFAULT_POSTPROCESS_SESSION_YAML
) -> Path:
    path = root / "postprocess.yaml"
    path.write_text(session_yaml, encoding="utf-8")
    return path


class FakeStage:
    """
    PostprocessStage implementation that records its calls and copies the
    input to the output, so the executor can be tested without the
    optional DSP packages installed.
    """

    def __init__(
        self,
        kind: str = "trim",
        *,
        marker: str = "default",
        output_written: bool = True,
        fail_on_sample_index: int | None = None,
    ) -> None:
        self.kind = kind
        self.marker = marker
        self.output_written = output_written
        self.fail_on_sample_index = fail_on_sample_index
        self.calls: list[tuple[Path, Path, int]] = []

    def settings_payload(self) -> dict:
        return {"marker": self.marker}

    def apply(self, context):
        from midi_sampling.postprocess.exceptions import PostprocessStageError
        from midi_sampling.postprocess.manifest import ManifestLoop, ManifestTrim
        from midi_sampling.postprocess.stages import StageOutcome

        context.validate()
        self.calls.append(
            (context.input_path, context.output_path, context.root_note)
        )

        if (
            self.fail_on_sample_index is not None
            and len(self.calls) - 1 == self.fail_on_sample_index
        ):
            raise PostprocessStageError(f"{self.kind} stage failed on purpose")

        if self.output_written:
            context.output_path.parent.mkdir(parents=True, exist_ok=True)
            context.output_path.write_bytes(context.input_path.read_bytes())

        if self.kind == "loop":
            block = ManifestLoop(
                applied=self.output_written,
                status="success" if self.output_written else "not_found",
                midi_unity_note=context.root_note if self.output_written else None,
                smpl_chunk_written=self.output_written,
            )
        else:
            block = ManifestTrim(applied=self.output_written, start_sample=0)

        return StageOutcome(manifest_block=block, output_written=self.output_written)


def build_postprocess_plan(session_path: Path, stages=None):
    """
    Resolve and plan a postprocess session with injectable stages, so
    that planning works without the optional DSP packages.
    """
    from midi_sampling.postprocess.planning import PostprocessPlanBuilder
    from midi_sampling.postprocess.resolving import PostprocessResolver

    if stages is None:
        stages = (FakeStage(),)

    session = PostprocessResolver().resolve(session_path)
    return PostprocessPlanBuilder().build(session, stages=tuple(stages))
