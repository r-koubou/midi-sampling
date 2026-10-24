"""Typer CLI entry point (section 5) and exit-code mapping (section 6)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from sample_loop_detector import __version__
from sample_loop_detector.config import (
    DEFAULT_FMAX,
    DEFAULT_FMIN,
    DEFAULT_MAX_LOOP_SECONDS,
    DEFAULT_MIN_LOOP_SECONDS,
    DEFAULT_MIN_SUSTAIN_SECONDS,
    DEFAULT_QUALITY_THRESHOLD,
    DEFAULT_TOP_K,
    DetectionSettings,
)
from sample_loop_detector.exceptions import (
    ExistingSmplChunkError,
    InvalidArgumentsError,
    InvalidWaveError,
    LoopDetectorError,
    WaveWriteError,
)

EXIT_SUCCESS = 0
EXIT_NO_LOOP = 2
EXIT_INVALID_INPUT = 3
EXIT_WRITE_ERROR = 4
EXIT_INTERNAL_ERROR = 5

app = typer.Typer(
    name="sample-loop-detector",
    help="Automatic sustain loop point detector for sampled instrument WAV files.",
    add_completion=False,
)

logger = logging.getLogger("sample_loop_detector")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sample-loop-detector {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Detect natural sustain loop points and write them as an smpl chunk."""


def _parse_crossfade_lengths(raw: str) -> tuple[float, ...]:
    try:
        values = tuple(float(part.strip()) for part in raw.split(",") if part.strip())
    except ValueError as error:
        raise typer.BadParameter(f"invalid crossfade length list: {raw!r}") from error
    if not values or any(v <= 0 for v in values):
        raise typer.BadParameter("crossfade lengths must be positive milliseconds")
    return values


@app.command()
def detect(
    input_path: Annotated[
        Path,
        typer.Argument(metavar="INPUT", exists=True, dir_okay=False, readable=True),
    ],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output WAV path")] = None,
    report: Annotated[
        Path | None, typer.Option("--report", help="JSON analysis report path")
    ] = None,
    preview_output: Annotated[
        Path | None,
        typer.Option("--preview-output", help="Audition preview WAV path"),
    ] = None,
    search_start: Annotated[
        float | None, typer.Option("--search-start", help="Search start seconds")
    ] = None,
    search_end: Annotated[
        float | None, typer.Option("--search-end", help="Search end seconds")
    ] = None,
    min_sustain: Annotated[
        float, typer.Option("--min-sustain", help="Minimum sustain seconds")
    ] = DEFAULT_MIN_SUSTAIN_SECONDS,
    min_loop: Annotated[
        float, typer.Option("--min-loop", help="Minimum loop seconds")
    ] = DEFAULT_MIN_LOOP_SECONDS,
    max_loop: Annotated[
        float, typer.Option("--max-loop", help="Maximum loop seconds")
    ] = DEFAULT_MAX_LOOP_SECONDS,
    fmin: Annotated[float, typer.Option("--fmin", help="Pitch lower bound Hz")] = DEFAULT_FMIN,
    fmax: Annotated[float, typer.Option("--fmax", help="Pitch upper bound Hz")] = DEFAULT_FMAX,
    crossfade_lengths: Annotated[
        str,
        typer.Option("--crossfade-lengths", help="Crossfade lengths to evaluate, ms"),
    ] = "20,50,100,200",
    top_k: Annotated[
        int, typer.Option("--top-k", help="Candidates kept in the report")
    ] = DEFAULT_TOP_K,
    quality_threshold: Annotated[
        float, typer.Option("--quality-threshold", help="Maximum acceptable score")
    ] = DEFAULT_QUALITY_THRESHOLD,
    midi_unity_note: Annotated[
        int | None,
        typer.Option("--midi-unity-note", help="MIDI unity note stored in smpl"),
    ] = None,
    replace_existing_loop: Annotated[
        bool, typer.Option("--replace-existing-loop", help="Replace an existing smpl chunk")
    ] = False,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing output")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not write the output WAV")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Verbose logging")] = False,
) -> None:
    """Analyze INPUT and write a copy with a detected smpl loop chunk."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if verbose:
        # Only this package goes to DEBUG; libraries (numba etc.) stay quiet.
        logging.getLogger("sample_loop_detector").setLevel(logging.DEBUG)

    settings = DetectionSettings(
        input_path=input_path,
        output_path=output
        if output is not None
        else input_path.with_name(f"{input_path.stem}.looped.wav"),
        report_path=report,
        preview_path=preview_output,
        search_start=search_start,
        search_end=search_end,
        min_sustain=min_sustain,
        min_loop=min_loop,
        max_loop=max_loop,
        fmin=fmin,
        fmax=fmax,
        crossfade_lengths_ms=_parse_crossfade_lengths(crossfade_lengths),
        top_k=top_k,
        quality_threshold=quality_threshold,
        midi_unity_note=midi_unity_note,
        replace_existing_loop=replace_existing_loop,
        force=force,
        dry_run=dry_run,
        verbose=verbose,
    )

    raise typer.Exit(code=_run(settings))


def _run(settings: DetectionSettings) -> int:
    # Imports are deferred so `--help`/`--version` stay fast.
    from sample_loop_detector.pipeline import run_detection, write_output_wav
    from sample_loop_detector.reporting.json_report import (
        build_error_report,
        build_report,
        write_report,
    )

    def emit_error_report(reason: str, message: str) -> None:
        if settings.report_path is not None:
            write_report(settings.report_path, build_error_report(settings, reason, message))

    try:
        output = run_detection(settings)

        if settings.report_path is not None:
            write_report(settings.report_path, build_report(output, settings))

        if not output.succeeded:
            typer.echo(f"No acceptable loop: {output.failure_reason}", err=True)
            if output.failure_message:
                typer.echo(output.failure_message, err=True)
            return EXIT_NO_LOOP

        assert output.result is not None
        _print_summary(output, settings)

        if settings.preview_path is not None:
            from sample_loop_detector.audio.decoder import decode_wave
            from sample_loop_detector.audio.preview import write_preview

            audio, _ = decode_wave(output.wave)
            write_preview(settings.preview_path, audio, output.result, output.metadata.sample_rate)
            typer.echo(f"Preview: {settings.preview_path}")

        if not settings.dry_run:
            target = write_output_wav(output, settings)
            typer.echo(f"Output: {target}")
        return EXIT_SUCCESS
    except InvalidArgumentsError as error:
        typer.echo(f"Invalid arguments: {error}", err=True)
        emit_error_report("invalid_arguments", str(error))
        return EXIT_INVALID_INPUT
    except ExistingSmplChunkError as error:
        typer.echo(f"Existing smpl chunk: {error}", err=True)
        emit_error_report("existing_smpl_chunk", str(error))
        return EXIT_WRITE_ERROR
    except WaveWriteError as error:
        typer.echo(f"Write error: {error}", err=True)
        emit_error_report("write_failed", str(error))
        return EXIT_WRITE_ERROR
    except InvalidWaveError as error:
        typer.echo(f"Invalid input: {error}", err=True)
        emit_error_report("unsupported_wave_format", str(error))
        return EXIT_INVALID_INPUT
    except LoopDetectorError as error:  # pragma: no cover - defensive
        typer.echo(f"Error: {error}", err=True)
        return EXIT_INTERNAL_ERROR
    except Exception as error:
        typer.echo(f"Internal error: {error}", err=True)
        return EXIT_INTERNAL_ERROR


def _print_summary(output: object, settings: DetectionSettings) -> None:
    from sample_loop_detector.pipeline import DetectionOutput

    assert isinstance(output, DetectionOutput)
    assert output.result is not None and output.analysis is not None
    metadata = output.metadata
    result = output.result
    sr = metadata.sample_rate
    channel_label = "mono" if metadata.channels == 1 else "stereo"

    typer.echo(f"Input: {settings.input_path}")
    typer.echo(f"Format: {sr} Hz / {channel_label} / {metadata.subtype}")
    typer.echo(
        f"Sustain: {output.analysis.sustain_start_seconds:.2f} s"
        f" - {output.analysis.sustain_end_seconds:.2f} s"
    )
    typer.echo(
        f"Loop: {result.selected.start_frame / sr:.3f} s - {result.selected.end_frame / sr:.3f} s"
    )
    typer.echo(f"Length: {result.selected.length_frames / sr:.3f} s")
    typer.echo(f"Score: {result.score.total:.3f}")
    typer.echo(f"Confidence: {result.confidence_label}")
    for warning in output.warnings:
        typer.echo(f"Warning: {warning}", err=True)


if __name__ == "__main__":  # pragma: no cover
    app()
