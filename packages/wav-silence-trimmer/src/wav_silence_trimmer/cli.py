"""Command-line interface for wav-silence-trimmer."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .audio_io import read_wav, write_wav
from .config import validate_config
from .detector import detect_trim_region
from .errors import (
    InvalidConfigurationError,
    InvalidInputError,
    NoSignalDetectedError,
    OutputExistsError,
    UnsupportedFormatError,
    WavTrimmerError,
)
from .fade import apply_fades
from .models import ProcessingResult, TrimConfig, TrimResult

logger = logging.getLogger("wav_silence_trimmer")

EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_INVALID_ARGS = 2
EXIT_INVALID_INPUT = 3
EXIT_NO_SIGNAL = 4
EXIT_WRITE_FAILURE = 5


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the wav-trim command."""
    parser = argparse.ArgumentParser(
        prog="wav-trim",
        description=(
            "Trim leading and trailing silence from sampled WAV files using a "
            "noise floor estimated from ~1 second of margin at each edge."
        ),
    )
    parser.add_argument("input", type=Path, help="Input WAV file or directory")
    parser.add_argument(
        "--output", type=Path, help="Output WAV path (single file input)"
    )
    parser.add_argument(
        "--output-dir", type=Path, help="Output directory (directory input)"
    )

    detect = parser.add_argument_group("detection parameters")
    detect.add_argument("--edge-noise-seconds", type=float, default=1.0)
    detect.add_argument("--frame-ms", type=float, default=10.0)
    detect.add_argument("--hop-ms", type=float, default=2.0)
    detect.add_argument("--noise-percentile", type=float, default=20.0)
    detect.add_argument("--on-margin-db", type=float, default=15.0)
    detect.add_argument("--off-margin-db", type=float, default=8.0)
    detect.add_argument("--minimum-noise-floor-dbfs", type=float, default=-120.0)
    detect.add_argument("--minimum-on-ms", type=float, default=10.0)
    detect.add_argument("--bridge-gap-ms", type=float, default=80.0)
    detect.add_argument("--pre-roll-ms", type=float, default=8.0)
    detect.add_argument("--post-roll-ms", type=float, default=40.0)

    fade = parser.add_argument_group("fade parameters")
    fade.add_argument("--fade-in-ms", type=float, default=1.0)
    fade.add_argument("--fade-out-ms", type=float, default=5.0)
    fade.add_argument("--no-fade", action="store_true")

    behavior = parser.add_argument_group("behavior options")
    behavior.add_argument("--recursive", action="store_true")
    behavior.add_argument("--overwrite", action="store_true")
    behavior.add_argument("--dry-run", action="store_true")
    behavior.add_argument("--report-json", type=Path)
    behavior.add_argument("--fail-on-no-signal", action="store_true")
    behavior.add_argument("--verbose", action="store_true")
    behavior.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def config_from_args(args: argparse.Namespace) -> TrimConfig:
    """Build and validate a TrimConfig from parsed CLI arguments."""
    config = TrimConfig(
        edge_noise_seconds=args.edge_noise_seconds,
        frame_ms=args.frame_ms,
        hop_ms=args.hop_ms,
        noise_percentile=args.noise_percentile,
        on_margin_db=args.on_margin_db,
        off_margin_db=args.off_margin_db,
        minimum_noise_floor_dbfs=args.minimum_noise_floor_dbfs,
        minimum_on_ms=args.minimum_on_ms,
        bridge_gap_ms=args.bridge_gap_ms,
        pre_roll_ms=args.pre_roll_ms,
        post_roll_ms=args.post_roll_ms,
        fade_in_ms=args.fade_in_ms,
        fade_out_ms=args.fade_out_ms,
        no_fade=args.no_fade,
    )
    validate_config(config)
    return config


def process_file(
    input_path: Path,
    output_path: Path,
    config: TrimConfig,
    *,
    overwrite: bool,
    dry_run: bool,
) -> ProcessingResult:
    """Process a single WAV file: detect, trim, fade, and write.

    Returns a ProcessingResult; detection or IO errors are converted into an
    error result by the caller, not here.
    """
    if input_path.resolve() == output_path.resolve() and not overwrite:
        raise OutputExistsError(
            f"Output equals input (use --overwrite): {output_path}"
        )

    audio, metadata = read_wav(input_path)
    logger.debug(
        "%s: subtype=%s sample_rate=%d channels=%d frames=%d",
        input_path, metadata.subtype, metadata.sample_rate,
        metadata.channels, metadata.frames,
    )

    detection = detect_trim_region(audio, metadata.sample_rate, config)
    start = detection.start_sample
    end = detection.end_sample_exclusive

    # The output is cut from the original audio, not the DC-removed analysis.
    trimmed = audio[start:end].copy()

    head_trimmed = start > 0
    tail_trimmed = end < metadata.frames
    if config.no_fade:
        fade_in_frames = 0
        fade_out_frames = 0
    else:
        trimmed, fade_in_frames, fade_out_frames = apply_fades(
            trimmed,
            metadata.sample_rate,
            config.fade_in_ms,
            config.fade_out_ms,
            apply_fade_in=head_trimmed,
            apply_fade_out=tail_trimmed,
        )

    result = TrimResult(
        start_sample=start,
        end_sample_exclusive=end,
        original_frames=metadata.frames,
        output_frames=end - start,
        sample_rate=metadata.sample_rate,
        channels=metadata.channels,
        noise_floor_dbfs=detection.noise_floor_dbfs,
        threshold_on_dbfs=detection.threshold_on_dbfs,
        threshold_off_dbfs=detection.threshold_off_dbfs,
        removed_head_frames=start,
        removed_tail_frames=metadata.frames - end,
        removed_head_seconds=start / metadata.sample_rate,
        removed_tail_seconds=(metadata.frames - end) / metadata.sample_rate,
        fade_in_frames=fade_in_frames,
        fade_out_frames=fade_out_frames,
    )

    if not dry_run:
        write_wav(
            output_path,
            trimmed,
            metadata.sample_rate,
            metadata.subtype,
            format=metadata.format,
            overwrite=overwrite,
        )

    _log_success(input_path, output_path, result, dry_run=dry_run)
    return ProcessingResult(
        input=input_path, output=output_path, status="success", trim=result
    )


def _log_success(
    input_path: Path, output_path: Path, result: TrimResult, *, dry_run: bool
) -> None:
    """Log the per-file summary in the spec section 12 format."""
    suffix = " (dry run)" if dry_run else ""
    logger.info(
        "%s\n"
        "  noise floor : %.1f dBFS\n"
        "  threshold on: %.1f dBFS\n"
        "  threshold off: %.1f dBFS\n"
        "  trim head   : %.3f s\n"
        "  trim tail   : %.3f s\n"
        "  output      : %s%s",
        input_path,
        result.noise_floor_dbfs,
        result.threshold_on_dbfs,
        result.threshold_off_dbfs,
        result.removed_head_seconds,
        result.removed_tail_seconds,
        output_path,
        suffix,
    )
    logger.debug(
        "  fade in     : %d frames\n  fade out    : %d frames",
        result.fade_in_frames,
        result.fade_out_frames,
    )


def _collect_wav_files(directory: Path, recursive: bool) -> list[Path]:
    """Collect .wav/.WAV files from a directory, optionally recursively."""
    pattern = "**/*" if recursive else "*"
    files = [
        p
        for p in sorted(directory.glob(pattern))
        if p.is_file() and p.suffix.lower() == ".wav"
    ]
    return files


def _error_result(input_path: Path, exc: Exception) -> ProcessingResult:
    return ProcessingResult(
        input=input_path,
        output=None,
        status="error",
        error_type=type(exc).__name__,
        message=str(exc),
    )


def _write_report(report_path: Path, results: list[ProcessingResult]) -> None:
    """Write the JSON report described in spec section 11."""
    report = {
        "version": 1,
        "files": [result.to_json_dict() for result in results],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _run_single(args: argparse.Namespace, config: TrimConfig) -> int:
    """Handle a single-file input; returns an exit code."""
    if args.output is None:
        logger.error("--output is required for single file input")
        return EXIT_INVALID_ARGS
    if args.output_dir is not None:
        logger.error("--output-dir cannot be used with single file input")
        return EXIT_INVALID_ARGS

    results: list[ProcessingResult] = []
    exit_code = EXIT_SUCCESS
    try:
        results.append(
            process_file(
                args.input,
                args.output,
                config,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
        )
    except NoSignalDetectedError as exc:
        results.append(_error_result(args.input, exc))
        if args.fail_on_no_signal:
            logger.error("%s: %s", args.input, exc)
            exit_code = EXIT_NO_SIGNAL
        else:
            logger.warning("%s: %s (skipped)", args.input, exc)
    except (InvalidInputError, UnsupportedFormatError) as exc:
        results.append(_error_result(args.input, exc))
        logger.error("%s", exc)
        exit_code = EXIT_INVALID_INPUT
    except (OutputExistsError, OSError) as exc:
        results.append(_error_result(args.input, exc))
        logger.error("%s", exc)
        exit_code = EXIT_WRITE_FAILURE
    except WavTrimmerError as exc:
        results.append(_error_result(args.input, exc))
        logger.error("%s", exc)
        exit_code = EXIT_PARTIAL_FAILURE

    if args.report_json is not None:
        _write_report(args.report_json, results)
    return exit_code


def _run_directory(args: argparse.Namespace, config: TrimConfig) -> int:
    """Handle a directory input; returns an exit code."""
    if args.output_dir is None:
        logger.error("--output-dir is required for directory input")
        return EXIT_INVALID_ARGS
    if args.output is not None:
        logger.error("--output cannot be used with directory input")
        return EXIT_INVALID_ARGS

    files = _collect_wav_files(args.input, args.recursive)
    if not files:
        logger.error("No WAV files found in %s", args.input)
        return EXIT_INVALID_INPUT

    results: list[ProcessingResult] = []
    failures = 0
    for input_path in files:
        relative = input_path.relative_to(args.input)
        output_path = args.output_dir / relative
        try:
            results.append(
                process_file(
                    input_path,
                    output_path,
                    config,
                    overwrite=args.overwrite,
                    dry_run=args.dry_run,
                )
            )
        except NoSignalDetectedError as exc:
            results.append(_error_result(input_path, exc))
            if args.fail_on_no_signal:
                logger.error("%s: %s", input_path, exc)
                failures += 1
            else:
                logger.warning("%s: %s (skipped)", input_path, exc)
        except (WavTrimmerError, OSError) as exc:
            results.append(_error_result(input_path, exc))
            logger.error("%s: %s", input_path, exc)
            failures += 1

    if args.report_json is not None:
        _write_report(args.report_json, results)

    if failures:
        logger.error("%d of %d files failed", failures, len(files))
        return EXIT_PARTIAL_FAILURE
    return EXIT_SUCCESS


def _configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    if quiet:
        level = logging.ERROR
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout)
    logging.getLogger("wav_silence_trimmer").setLevel(level)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose, args.quiet)

    try:
        config = config_from_args(args)
    except InvalidConfigurationError as exc:
        logger.error("%s", exc)
        return EXIT_INVALID_ARGS

    if args.input.is_dir():
        return _run_directory(args, config)
    if args.input.is_file():
        if args.input.suffix.lower() != ".wav":
            logger.error("Input is not a WAV file: %s", args.input)
            return EXIT_INVALID_INPUT
        return _run_single(args, config)
    logger.error("Input not found: %s", args.input)
    return EXIT_INVALID_INPUT


if __name__ == "__main__":
    sys.exit(main())
