from logging import getLogger
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from midi_sampling.sampling.resolving import ResolvedSession

import typer

from midi_sampling import logging_management
from midi_sampling.exceptions import MidiSamplingError
from midi_sampling.sampling.audit import (
    AuditService,
    SessionAuditResult,
    ToneAuditStatus,
)
from midi_sampling.sampling.exceptions import SamplingError
from midi_sampling.sampling.planning import SamplingPlan, SamplingPlanBuilder

logger = getLogger(__name__)

app = typer.Typer(
    help="Automated MIDI sound module sampler.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

EXIT_OK = 0
EXIT_RESAMPLING_REQUIRED = 1
EXIT_EXECUTION_FAILED = 1
EXIT_DEFINITION_ERROR = 2

SessionFileArgument = Annotated[
    Path,
    typer.Argument(
        help="Path to a sampling session definition file (kind: sampling_session).",
        show_default=False,
    ),
]

PostprocessSessionFileArgument = Annotated[
    Path,
    typer.Argument(
        help=(
            "Path to a postprocess session definition file "
            "(kind: postprocess_session)."
        ),
        show_default=False,
    ),
]

InstrumentFileArgument = Annotated[
    Path,
    typer.Argument(
        help=(
            "Path to an instrument definition file "
            "(kind: instrument_definition)."
        ),
        show_default=False,
    ),
]

PatchFormatOption = Annotated[
    str,
    typer.Option("--format", help="Patch format to generate."),
]

OutputDirectoryOption = Annotated[
    Path | None,
    typer.Option(
        "--output",
        "-o",
        help=(
            "Output root; the patch is written to <output>/<format>/<name>. "
            "Defaults to patches/ next to the instrument definition file."
        ),
        show_default=False,
    ),
]

VerboseOption = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable debug logging."),
]


def _init_logging(verbose: bool) -> None:
    logging_management.init_logging_as_stdout(verbose=verbose)


def _build_plan(session_file: Path) -> "tuple[SamplingPlan, ResolvedSession]":
    """
    Resolve the session file and build a validated sampling plan.
    Raises SamplingError subclasses on any definition problem.
    """
    from midi_sampling.devices.audio.sounddevice_impl.sd_audio_device_information_loader import (
        SdAudioDeviceInformationLoader,
    )
    from midi_sampling.sampling.resolving import DefinitionResolver

    resolver = DefinitionResolver(SdAudioDeviceInformationLoader())
    session = resolver.resolve(session_file)
    return SamplingPlanBuilder().build(session), session


@app.command()
def run(session_file: SessionFileArgument, verbose: VerboseOption = False) -> None:
    """
    Record all samples defined by a sampling session.
    """
    _init_logging(verbose)

    try:
        plan, session = _build_plan(session_file)
    except SamplingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_DEFINITION_ERROR)

    from midi_sampling.devices.audio.sounddevice_impl.sd_audio_device import (
        SdAudioDevice,
    )
    from midi_sampling.devices.midi.mido_impl.mido_midi_device import MidoMidiDevice
    from midi_sampling.sampling import SamplingExecutor

    audio_device = SdAudioDevice(str(session.audio_device_file))
    midi_device = MidoMidiDevice(str(session.midi_device_file))

    executor = SamplingExecutor(
        audio_device=audio_device,
        midi_device=midi_device,
        progress=typer.echo,
    )

    try:
        executor.execute(plan)
    except SamplingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_EXECUTION_FAILED)

    total_samples = sum(len(tone.targets) for tone in plan.tones)
    typer.echo(
        f"Completed: {len(plan.tones)} tones, {total_samples} samples "
        f"-> {plan.output_root}"
    )


@app.command()
def audit(session_file: SessionFileArgument, verbose: VerboseOption = False) -> None:
    """
    Check existing sampling outputs against the current definitions.
    Read-only: never opens devices and never modifies any file.
    """
    _init_logging(verbose)

    try:
        plan, _session = _build_plan(session_file)
        result = AuditService().audit(plan)
    except SamplingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_DEFINITION_ERROR)

    _print_audit_report(result)

    raise typer.Exit(
        EXIT_OK if result.all_up_to_date else EXIT_RESAMPLING_REQUIRED
    )


@app.command()
def postprocess(
    session_file: PostprocessSessionFileArgument, verbose: VerboseOption = False
) -> None:
    """
    Trim and loop existing sampling output into a derived sample set.

    Never modifies the recorded output: results and a derived manifest
    are written to a separate directory.
    """
    _init_logging(verbose)

    from midi_sampling.postprocess.planning import PostprocessPlanBuilder
    from midi_sampling.postprocess.resolving import PostprocessResolver

    try:
        session = PostprocessResolver().resolve(session_file)
        plan = PostprocessPlanBuilder().build(session)
    except MidiSamplingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_DEFINITION_ERROR)

    from midi_sampling.postprocess import PostprocessExecutor

    executor = PostprocessExecutor(progress=typer.echo)

    try:
        executor.execute(plan)
    except MidiSamplingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_EXECUTION_FAILED)

    typer.echo(
        f"Completed: {len(plan.tones)} tones, {plan.total_sample_count} samples "
        f"-> {plan.output_root}"
    )


@app.command()
def export(
    instrument_file: InstrumentFileArgument,
    patch_format: PatchFormatOption = "sfz",
    output: OutputDirectoryOption = None,
    verbose: VerboseOption = False,
) -> None:
    """
    Generate a sampler patch from postprocessed sampling output.

    Reads an instrument definition, copies (or encodes) the processed
    samples into a self-contained output directory and writes the patch
    file next to them. Never modifies the recorded or processed trees.
    """
    _init_logging(verbose)

    from midi_sampling.export import create_patch_writer
    from midi_sampling.export.planning import ExportPlanBuilder
    from midi_sampling.export.resolving import ExportResolver

    try:
        writer = create_patch_writer(patch_format)
        resolved = ExportResolver().resolve(instrument_file)
        plan = ExportPlanBuilder().build(resolved)
    except MidiSamplingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_DEFINITION_ERROR)

    output_root = (
        output if output is not None else resolved.definition_path.parent / "patches"
    )
    output_directory = output_root / writer.directory_name / plan.instrument.name

    from midi_sampling.export.audio import AudioExporter
    from midi_sampling.export.export_executor import ExportExecutor

    executor = ExportExecutor(
        writer=writer,
        audio_exporter=AudioExporter(
            audio_format=plan.audio_format, bit_depth=plan.bit_depth
        ),
        progress=typer.echo,
    )

    try:
        patch_path = executor.execute(plan, output_directory)
    except MidiSamplingError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(EXIT_EXECUTION_FAILED)

    typer.echo(
        f"Completed: {len(resolved.tones)} tones, "
        f"{len(plan.instrument.regions)} regions -> {patch_path}"
    )


def _print_audit_report(result: SessionAuditResult) -> None:
    typer.echo("Sampling audit")

    for tone in result.tones:
        typer.echo("")
        if tone.status is ToneAuditStatus.UP_TO_DATE:
            typer.echo(f"[UP TO DATE] {tone.definition_id}")
            typer.echo(f"  samples: {tone.planned_sample_count}")
            continue

        typer.echo(f"[RESAMPLE] {tone.definition_id}")
        typer.echo(f"  reason: {tone.status.value}")

        if tone.status is ToneAuditStatus.DEFINITION_CHANGED:
            typer.echo(f"  existing hash: {tone.existing_hash}")
            typer.echo(f"  current hash:  {tone.current_hash}")
        elif tone.status is ToneAuditStatus.MISSING_SAMPLES:
            typer.echo("  missing:")
            for file_name in tone.missing_files:
                typer.echo(f"    {file_name}")
        elif tone.detail is not None:
            typer.echo(f"  detail: {tone.detail}")

    typer.echo("")
    typer.echo("Summary:")
    typer.echo(f"  up to date: {result.up_to_date_count}")
    typer.echo(f"  resampling required: {result.resampling_required_count}")


if __name__ == "__main__":
    app()
