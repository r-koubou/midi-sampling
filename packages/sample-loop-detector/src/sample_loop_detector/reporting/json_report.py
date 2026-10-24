"""JSON analysis report generation (section 22)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sample_loop_detector import __version__
from sample_loop_detector.config import DetectionSettings
from sample_loop_detector.models import LoopScore, ScoredCandidate
from sample_loop_detector.pipeline import DetectionOutput


def _score_dict(score: LoopScore) -> dict[str, Any]:
    return {
        "total": round(score.total, 4),
        "hard_seam": round(score.hard_seam, 4),
        "crossfade_seam": round(score.crossfade_seam, 4),
        "sustain": round(score.sustain, 4),
        "length_penalty": round(score.length_penalty, 4),
        "waveform": round(score.waveform, 4),
        "spectral": round(score.spectral, 4),
        "level": round(score.level, 4),
        "pitch": None if score.pitch is None else round(score.pitch, 4),
        "modulation": None if score.modulation is None else round(score.modulation, 4),
        "stereo": None if score.stereo is None else round(score.stereo, 4),
    }


def _candidate_dict(scored: ScoredCandidate, sample_rate: int) -> dict[str, Any]:
    candidate = scored.candidate
    return {
        "start_frame": candidate.start_frame,
        "end_frame": candidate.end_frame,
        "start_seconds": round(candidate.start_frame / sample_rate, 6),
        "end_seconds": round(candidate.end_frame / sample_rate, 6),
        "length_frames": candidate.length_frames,
        "length_seconds": round(candidate.length_frames / sample_rate, 6),
        "best_crossfade_ms": round(scored.best_crossfade_ms, 3),
        "score": _score_dict(scored.score),
    }


def build_report(output: DetectionOutput, settings: DetectionSettings) -> dict[str, Any]:
    metadata = output.metadata
    report: dict[str, Any] = {
        "version": __version__,
        "status": "success" if output.succeeded else "no_acceptable_loop",
        "input": {
            "path": str(settings.input_path),
            "sample_rate": metadata.sample_rate,
            "channels": metadata.channels,
            "frames": metadata.frame_count,
            "duration_seconds": round(metadata.duration_seconds, 6),
            "format": metadata.subtype,
        },
    }

    if output.analysis is not None:
        analysis = output.analysis
        report["analysis"] = {
            "attack_end_seconds": round(analysis.attack_end_seconds, 4),
            "sustain_start_seconds": round(analysis.sustain_start_seconds, 4),
            "sustain_end_seconds": round(analysis.sustain_end_seconds, 4),
            "sustain_confidence": round(analysis.sustain_confidence, 4),
            "f0_hz": None if analysis.f0_hz is None else round(analysis.f0_hz, 3),
            "f0_confidence": round(analysis.f0_confidence, 4),
            "voiced_ratio": round(analysis.voiced_ratio, 4),
        }

    sample_rate = metadata.sample_rate
    if output.succeeded and output.result is not None:
        selected = output.scored[0]
        selected_dict = _candidate_dict(selected, sample_rate)
        selected_dict["confidence"] = {
            "value": round(output.result.confidence, 4),
            "label": output.result.confidence_label,
        }
        report["selected_loop"] = selected_dict
        report["alternatives"] = [_candidate_dict(sc, sample_rate) for sc in output.scored[1:]]
    else:
        report["failure"] = {
            "reason": output.failure_reason,
            "message": output.failure_message,
        }
        if output.best_rejected is not None:
            report["best_rejected_candidate"] = _candidate_dict(output.best_rejected, sample_rate)

    report["warnings"] = list(output.warnings)
    report["configuration"] = {
        "min_loop_seconds": settings.min_loop,
        "max_loop_seconds": settings.max_loop,
        "quality_threshold": settings.quality_threshold,
        "crossfade_lengths_ms": list(settings.crossfade_lengths_ms),
    }
    return report


def build_error_report(settings: DetectionSettings, reason: str, message: str) -> dict[str, Any]:
    """Report for failures that occur before analysis produced metadata."""
    return {
        "version": __version__,
        "status": "no_acceptable_loop" if reason in _ANALYSIS_REASONS else "error",
        "input": {"path": str(settings.input_path)},
        "failure": {"reason": reason, "message": message},
        "warnings": [],
    }


_ANALYSIS_REASONS = {
    "no_stable_sustain_region",
    "sustain_region_too_short",
    "no_loop_candidates",
    "all_candidates_above_threshold",
    "hard_seam_above_threshold",
    "no_active_signal",
}


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
