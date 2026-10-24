"""Core immutable data models shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AudioMetadata:
    sample_rate: int
    channels: int
    frame_count: int
    duration_seconds: float
    format_tag: int
    bits_per_sample: int
    subtype: str


@dataclass(frozen=True)
class SustainRegion:
    start_frame: int
    end_frame: int
    stability_score: float
    confidence: float


@dataclass(frozen=True)
class PitchEstimate:
    f0_hz: float | None
    confidence: float
    voiced_ratio: float
    period_samples: float | None


@dataclass(frozen=True)
class LoopCandidate:
    start_frame: int
    end_frame: int
    crossfade_frames: int
    coarse_score: float

    @property
    def length_frames(self) -> int:
        return self.end_frame - self.start_frame + 1


@dataclass(frozen=True)
class LoopScore:
    total: float
    hard_seam: float
    crossfade_seam: float
    waveform: float
    spectral: float
    level: float
    pitch: float | None
    modulation: float | None
    stereo: float | None
    sustain: float
    length_penalty: float


@dataclass(frozen=True)
class ScoredCandidate:
    """A refined candidate together with its full evaluation."""

    candidate: LoopCandidate
    score: LoopScore
    best_crossfade_ms: float


@dataclass(frozen=True)
class LoopResult:
    selected: LoopCandidate
    score: LoopScore
    confidence: float
    confidence_label: str
    alternatives: tuple[LoopCandidate, ...]
    best_crossfade_ms: float = 0.0
    alternative_scores: tuple[LoopScore, ...] = field(default=())


@dataclass(frozen=True)
class AnalysisSummary:
    """High-level analysis values reported to the user."""

    attack_end_seconds: float
    sustain_start_seconds: float
    sustain_end_seconds: float
    sustain_confidence: float
    f0_hz: float | None
    f0_confidence: float
    voiced_ratio: float
