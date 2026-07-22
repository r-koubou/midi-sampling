import pytest

from midi_sampling.sampling import SamplingExecutor
from midi_sampling.sampling.exceptions import (
    ExistingOutputError,
    SamplingExecutionError,
)
from midi_sampling.sampling.manifest import SampleManifestRepository

from conftest import FakeAudioDevice, FakeMidiDevice, make_session, build_plan


class RecordingManifestRepository(SampleManifestRepository):
    """
    Manifest repository that also records write events into the shared
    event list, for call-order verification.
    """

    def __init__(self, events: list):
        self.events = events

    def write(self, manifest_path, manifest):
        self.events.append(("manifest.write", manifest.status))
        super().write(manifest_path, manifest)


def make_executor(events: list, **audio_kwargs):
    audio_device = FakeAudioDevice(events, **audio_kwargs)
    midi_device = FakeMidiDevice(events)
    sleep_calls = []

    def fake_sleep(seconds: float) -> None:
        events.append(("sleep", seconds))
        sleep_calls.append(seconds)

    executor = SamplingExecutor(
        audio_device=audio_device,
        midi_device=midi_device,
        manifest_repository=RecordingManifestRepository(events),
        sleep=fake_sleep,
    )
    return executor, audio_device, midi_device


repository = SampleManifestRepository()


class TestSuccessfulRun:
    def test_files_and_manifest(self, plan):
        events = []
        executor, _, _ = make_executor(events)
        executor.execute(plan)

        tone = plan.tones[0]
        for target in tone.targets:
            assert target.output_path.is_file()
            assert not target.output_path.with_name(
                target.file_name + ".part"
            ).exists()

        manifest = repository.read(tone.manifest_path)
        assert manifest.status == "completed"
        assert all(sample.status == "completed" for sample in manifest.samples)
        assert manifest.error is None

    def test_call_order_for_one_sample(self, plan):
        events = []
        executor, _, _ = make_executor(events)
        executor.execute(plan)

        target = plan.tones[0].targets[0]
        first_recording = events.index(("audio.start_recording", 8.0))
        window = events[first_recording : first_recording + 7]
        assert window == [
            ("audio.start_recording", 8.0),          # pre_roll+note_on+release
            ("sleep", 1.0),                          # pre_roll
            ("midi.play_note", 0, target.root_note, target.send_velocity, 4.0),
            ("sleep", 3.0),                          # release_capture
            ("audio.stop_recording",),
            ("audio.export_audio", str(target.output_path.with_name(target.file_name + ".part"))),
            ("manifest.write", "in_progress"),
        ]
        assert events[first_recording + 7] == ("sleep", 0.5)  # inter_sample_wait

    def test_program_change_before_samples(self, plan):
        events = []
        executor, _, _ = make_executor(events)
        executor.execute(plan)

        program_change_index = events.index(("midi.send_program_change", 0, 0, 0, 41))
        first_recording = events.index(("audio.start_recording", 8.0))
        assert program_change_index < first_recording
        assert events[program_change_index + 1] == ("sleep", 0.5)  # settle
        # Program change is sent exactly once per tone
        assert (
            sum(1 for event in events if event[0] == "midi.send_program_change") == 1
        )

    def test_initialization_files_sent_once_in_order(self, tmp_path):
        from conftest import DEFAULT_SESSION_YAML

        session_yaml = DEFAULT_SESSION_YAML.replace(
            "initialization_files: []",
            "initialization_files:\n    - midi/reset.mid\n    - midi/setup.mid",
        )
        session_path = make_session(
            tmp_path,
            session_yaml=session_yaml,
            extra_files={"midi/reset.mid": "", "midi/setup.mid": ""},
        )
        plan = build_plan(session_path)

        events = []
        executor, _, _ = make_executor(events)
        executor.execute(plan)

        sent = [event for event in events if event[0] == "midi.send_message_from_file"]
        assert len(sent) == 2
        assert sent[0][1].endswith("reset.mid")
        assert sent[1][1].endswith("setup.mid")
        # Sent after device initialization and before any program change
        assert events.index(("midi.initialize",)) < events.index(sent[0])
        assert events.index(sent[1]) < events.index(
            ("midi.send_program_change", 0, 0, 0, 41)
        )

    def test_devices_disposed_at_end(self, plan):
        events = []
        executor, _, _ = make_executor(events)
        executor.execute(plan)
        assert ("midi.dispose",) in events
        assert ("audio.dispose",) in events


class TestFailure:
    def test_error_stops_session_and_marks_manifest(self, plan):
        events = []
        executor, _, _ = make_executor(events, fail_on_export_index=1)

        with pytest.raises(SamplingExecutionError):
            executor.execute(plan)

        tone = plan.tones[0]
        targets = tone.targets

        # First WAV was completed and must be kept
        assert targets[0].output_path.is_file()
        # Failed and subsequent WAVs do not exist
        assert not targets[1].output_path.exists()
        assert not targets[2].output_path.exists()

        # No further samples were started after the failure
        recordings = [e for e in events if e[0] == "audio.start_recording"]
        assert len(recordings) == 2

        # MIDI panic was attempted
        assert ("midi.stop",) in events

        manifest = repository.read(tone.manifest_path)
        assert manifest.status == "failed"
        assert manifest.error is not None
        assert manifest.error.type == "RuntimeError"
        assert manifest.error.message == "Recording failed"
        statuses = [sample.status for sample in manifest.samples]
        assert statuses == ["completed", "failed", "pending", "pending"]


class TestExistingOutput:
    def test_existing_tone_directory_rejected_before_devices_open(self, plan):
        plan.tones[0].directory.mkdir(parents=True)

        events = []
        executor, _, _ = make_executor(events)
        with pytest.raises(ExistingOutputError):
            executor.execute(plan)

        # Devices were never initialized
        assert ("audio.initialize",) not in events
        assert ("midi.initialize",) not in events

    def test_existing_manifest_reports_hash_comparison(self, plan):
        events = []
        executor, _, _ = make_executor(events)
        executor.execute(plan)

        executor2, _, _ = make_executor([])
        with pytest.raises(ExistingOutputError) as excinfo:
            executor2.execute(plan)

        message = str(excinfo.value)
        assert "existing hash" in message
        assert "current hash" in message
        assert "identical" in message
