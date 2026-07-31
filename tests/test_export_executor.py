from pathlib import Path

from conftest import make_wav_bytes
from midi_sampling.export.abstractions import (
    InstrumentEnvelope,
    InstrumentModel,
    InstrumentPatchWriter,
    InstrumentRegion,
    PatchWriteContext,
    PatchWriteOutcome,
)
from midi_sampling.export.audio import AudioExporter
from midi_sampling.export.export_executor import ExportExecutor
from midi_sampling.export.planning import AudioExportTask, ExportPlan

PATCH_SUFFIX = ".fake"


class FakePatchWriter(InstrumentPatchWriter):
    """
    Records the context it was handed, so the layout the executor builds
    is observable without depending on a real patch format.
    """

    def __init__(self) -> None:
        self.contexts: list[PatchWriteContext] = []

    @property
    def format_id(self) -> str:
        return "fake"

    def write(self, context: PatchWriteContext) -> PatchWriteOutcome:
        self.contexts.append(context)
        patch_path = (
            context.patch_directory / f"{context.instrument.name}{PATCH_SUFFIX}"
        )
        patch_path.write_text("patch", encoding="utf-8")
        return PatchWriteOutcome(patch_path=patch_path)


def make_plan(
    source: Path,
    name: str = "test-instrument",
    files: tuple[str, ...] = ("a.wav", "b.wav"),
) -> ExportPlan:
    """
    One tone with several samples, so that warnings emitted per tone
    directory are distinguishable from warnings emitted per file.
    """
    relative_paths = tuple(f"Samples/tone-1/{file}" for file in files)
    return ExportPlan(
        instrument=InstrumentModel(
            name=name,
            envelope=InstrumentEnvelope(attack=0.0, release=0.3),
            regions=tuple(
                InstrumentRegion(
                    tone_id="tone-1",
                    source_path=source,
                    sample_path=f"../{relative_path}",
                    root_note=38,
                    key_low=36,
                    key_high=40,
                    velocity_low=1,
                    velocity_high=127,
                    loop=None,
                    exclusive_group=None,
                    trigger="attack",
                    rt_decay=None,
                )
                for relative_path in relative_paths
            ),
            exclusive_groups=(),
        ),
        audio_format="wav",
        bit_depth=None,
        audio_tasks=tuple(
            AudioExportTask(
                source_path=source,
                relative_path=relative_path,
                data_format="int16",
            )
            for relative_path in relative_paths
        ),
    )


def make_executor(writer: InstrumentPatchWriter) -> ExportExecutor:
    return ExportExecutor(writer=writer, audio_exporter=AudioExporter("wav"))


def make_source(tmp_path: Path, frames: int = 100) -> Path:
    source = tmp_path / "source.wav"
    source.write_bytes(make_wav_bytes(frames))
    return source


class TestExportExecutorLayout:
    def test_splits_samples_and_instruments(self, tmp_path: Path):
        source = make_source(tmp_path)
        writer = FakePatchWriter()
        output_root = tmp_path / "out"

        patch_path = make_executor(writer).execute(make_plan(source), output_root)

        assert patch_path == (
            output_root / "Instruments" / f"test-instrument{PATCH_SUFFIX}"
        )
        assert (output_root / "Samples" / "tone-1" / "a.wav").is_file()
        assert writer.contexts[0].patch_directory == output_root / "Instruments"

    def test_region_paths_resolve_from_the_patch_directory(self, tmp_path: Path):
        source = make_source(tmp_path)
        writer = FakePatchWriter()
        output_root = tmp_path / "out"

        make_executor(writer).execute(make_plan(source), output_root)

        context = writer.contexts[0]
        region = context.instrument.regions[0]
        assert (context.patch_directory / region.sample_path).is_file()


class TestExportExecutorExistingOutput:
    def test_existing_output_root_is_accepted(self, tmp_path: Path):
        source = make_source(tmp_path)
        output_root = tmp_path / "out"
        (output_root / "Samples").mkdir(parents=True)
        (output_root / "leftover.txt").write_text("keep me", encoding="utf-8")

        make_executor(FakePatchWriter()).execute(make_plan(source), output_root)

        assert (output_root / "Instruments").is_dir()
        # Unrelated files are left alone; nothing is cleaned up.
        assert (output_root / "leftover.txt").read_text(encoding="utf-8") == "keep me"

    def test_re_export_overwrites_and_warns(self, tmp_path: Path, caplog):
        source = make_source(tmp_path)
        output_root = tmp_path / "out"
        executor = make_executor(FakePatchWriter())
        executor.execute(make_plan(source), output_root)

        # A second instrument reusing tone-1 writes over the same sample.
        source.write_bytes(make_wav_bytes(frames=200))
        with caplog.at_level("WARNING"):
            executor.execute(make_plan(source, name="second"), output_root)

        # One warning for the shared tone directory, not one per file.
        assert caplog.text.count("overwriting existing sample files") == 1
        exported = output_root / "Samples" / "tone-1" / "a.wav"
        assert exported.read_bytes() == source.read_bytes()
        assert sorted(
            path.name for path in (output_root / "Instruments").iterdir()
        ) == [f"second{PATCH_SUFFIX}", f"test-instrument{PATCH_SUFFIX}"]

    def test_first_export_does_not_warn(self, tmp_path: Path, caplog):
        source = make_source(tmp_path)

        with caplog.at_level("WARNING"):
            make_executor(FakePatchWriter()).execute(
                make_plan(source), tmp_path / "out"
            )

        assert "overwriting" not in caplog.text
