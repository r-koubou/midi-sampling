"""Dataclasses describing configuration, metadata, and processing results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import (
    DEFAULT_BRIDGE_GAP_MS,
    DEFAULT_EDGE_NOISE_SECONDS,
    DEFAULT_FADE_IN_MS,
    DEFAULT_FADE_OUT_MS,
    DEFAULT_FRAME_MS,
    DEFAULT_HOP_MS,
    DEFAULT_MINIMUM_NOISE_FLOOR_DBFS,
    DEFAULT_MINIMUM_ON_MS,
    DEFAULT_NOISE_PERCENTILE,
    DEFAULT_OFF_MARGIN_DB,
    DEFAULT_ON_MARGIN_DB,
    DEFAULT_POST_ROLL_MS,
    DEFAULT_PRE_ROLL_MS,
)


@dataclass(frozen=True)
class TrimConfig:
    """Detection and fade parameters for the trimming pipeline."""

    edge_noise_seconds: float = DEFAULT_EDGE_NOISE_SECONDS
    frame_ms: float = DEFAULT_FRAME_MS
    hop_ms: float = DEFAULT_HOP_MS
    noise_percentile: float = DEFAULT_NOISE_PERCENTILE
    on_margin_db: float = DEFAULT_ON_MARGIN_DB
    off_margin_db: float = DEFAULT_OFF_MARGIN_DB
    minimum_noise_floor_dbfs: float = DEFAULT_MINIMUM_NOISE_FLOOR_DBFS
    minimum_on_ms: float = DEFAULT_MINIMUM_ON_MS
    bridge_gap_ms: float = DEFAULT_BRIDGE_GAP_MS
    pre_roll_ms: float = DEFAULT_PRE_ROLL_MS
    post_roll_ms: float = DEFAULT_POST_ROLL_MS
    fade_in_ms: float = DEFAULT_FADE_IN_MS
    fade_out_ms: float = DEFAULT_FADE_OUT_MS
    no_fade: bool = False


@dataclass(frozen=True)
class AudioMetadata:
    """Metadata read from an input WAV file."""

    path: Path
    sample_rate: int
    channels: int
    frames: int
    subtype: str
    format: str


@dataclass(frozen=True)
class DetectionResult:
    """Raw boundary detection result before fades are applied."""

    start_sample: int
    end_sample_exclusive: int
    noise_floor_dbfs: float
    threshold_on_dbfs: float
    threshold_off_dbfs: float
    coarse_start: int
    coarse_end: int
    refined_start: int
    refined_end: int


@dataclass(frozen=True)
class TrimResult:
    """Complete result of trimming a single file."""

    start_sample: int
    end_sample_exclusive: int
    original_frames: int
    output_frames: int
    sample_rate: int
    channels: int
    noise_floor_dbfs: float
    threshold_on_dbfs: float
    threshold_off_dbfs: float
    removed_head_frames: int
    removed_tail_frames: int
    removed_head_seconds: float
    removed_tail_seconds: float
    fade_in_frames: int
    fade_out_frames: int


@dataclass
class ProcessingResult:
    """Outcome of processing one input file, used for reporting."""

    input: Path
    output: Path | None
    status: str
    trim: TrimResult | None = None
    error_type: str | None = None
    message: str | None = None

    def to_json_dict(self) -> dict:
        """Convert to the JSON report entry format."""
        if self.status != "success" or self.trim is None:
            return {
                "input": str(self.input),
                "status": "error",
                "error_type": self.error_type or "WavTrimmerError",
                "message": self.message or "",
            }
        trim = self.trim
        return {
            "input": str(self.input),
            "output": str(self.output) if self.output is not None else None,
            "status": "success",
            "sample_rate": trim.sample_rate,
            "channels": trim.channels,
            "original_frames": trim.original_frames,
            "output_frames": trim.output_frames,
            "start_sample": trim.start_sample,
            "end_sample_exclusive": trim.end_sample_exclusive,
            "removed_head_frames": trim.removed_head_frames,
            "removed_tail_frames": trim.removed_tail_frames,
            "removed_head_seconds": trim.removed_head_seconds,
            "removed_tail_seconds": trim.removed_tail_seconds,
            "noise_floor_dbfs": trim.noise_floor_dbfs,
            "threshold_on_dbfs": trim.threshold_on_dbfs,
            "threshold_off_dbfs": trim.threshold_off_dbfs,
            "fade_in_frames": trim.fade_in_frames,
            "fade_out_frames": trim.fade_out_frames,
        }
