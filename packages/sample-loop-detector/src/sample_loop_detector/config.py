"""Central configuration for all analysis parameters and score thresholds.

Every tunable constant lives here so that thresholds are never scattered
through the analysis code as magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Input constraints
# ---------------------------------------------------------------------------

MIN_SAMPLE_RATE = 8_000
MAX_SAMPLE_RATE = 384_000
MIN_DURATION_SECONDS = 1.5

# Fraction of samples allowed to be NaN/Inf before the input is rejected.
MAX_INVALID_SAMPLE_RATIO = 0.001

# ---------------------------------------------------------------------------
# Framing (section 9)
# ---------------------------------------------------------------------------

TARGET_WINDOW_SECONDS = 0.046
FRAME_LENGTH_MIN = 1024
FRAME_LENGTH_MAX = 8192
HOP_SECONDS = 0.010
MEL_BANDS = 64

# ---------------------------------------------------------------------------
# Silence / noise floor (section 8.4)
# ---------------------------------------------------------------------------

SILENCE_PEAK_THRESHOLD = 1e-5
NOISE_FLOOR_MARGIN_DB = 12.0
PEAK_RMS_FLOOR_DB = 45.0

# ---------------------------------------------------------------------------
# Attack estimation (section 11.2)
# ---------------------------------------------------------------------------

ATTACK_SEARCH_MAX_SECONDS = 2.0
ATTACK_SEARCH_MAX_RATIO = 0.35
ATTACK_EXCLUSION_SECONDS = 0.200

# ---------------------------------------------------------------------------
# Sustain detection (section 11)
# ---------------------------------------------------------------------------

STABILITY_WINDOW_SECONDS = 0.500
STABILITY_SCORE_THRESHOLD = 0.45
SHORT_GAP_MERGE_SECONDS = 0.100
RELEASE_GUARD_SECONDS = 0.150
ROBUST_Z_CLIP = 6.0

STABILITY_WEIGHTS: dict[str, float] = {
    "energy_residual": 0.25,
    "spectral_flux": 0.25,
    "spectral_variation": 0.20,
    "centroid_variation": 0.10,
    "pitch_variation": 0.15,
    "other_modulation": 0.05,
}

# ---------------------------------------------------------------------------
# Pitch (sections 10.3, 12)
# ---------------------------------------------------------------------------

DEFAULT_FMIN = 40.0
DEFAULT_FMAX = 4000.0
PITCH_STABLE_VOICED_RATIO = 0.60
PITCH_STABLE_MEDIAN_PROB = 0.60
PITCH_STABLE_MAX_MAD_CENTS = 30.0

# Modulation extraction band (section 10.4), Hz.
MODULATION_FMIN_HZ = 0.5
MODULATION_FMAX_HZ = 12.0

# ---------------------------------------------------------------------------
# Candidate generation (section 13)
# ---------------------------------------------------------------------------

MAX_START_CANDIDATES = 100
TOP_ENDS_PER_START = 5
MAX_COARSE_CANDIDATES = 256
ENDPOINT_DESCRIPTOR_SECONDS = 0.100

# Loop length penalty bands (section 13.6), seconds.
LENGTH_REJECT_BELOW_SECONDS = 0.5
LENGTH_STRONG_PENALTY_BELOW_SECONDS = 1.0
LENGTH_LIGHT_PENALTY_BELOW_SECONDS = 2.0
LENGTH_STRONG_PENALTY = 0.6
LENGTH_LIGHT_PENALTY = 0.2

PERIOD_ERROR_WEIGHT = 0.35

# Only the best coarse candidates receive sample-accurate refinement and
# full seam rendering (section 30).
MAX_REFINED_CANDIDATES = 48
MAX_DETAILED_CANDIDATES = 24

# ---------------------------------------------------------------------------
# Refinement (section 14)
# ---------------------------------------------------------------------------

REFINE_MAX_RANGE_SECONDS = 0.020
REFINE_UNPITCHED_RANGE_SECONDS = 0.010
REFINE_PERIOD_FACTOR = 0.5
REFINE_WINDOW_SECONDS = 0.030
ZERO_CROSS_ADJUST_SECONDS = 0.002
TIE_BREAK_SCORE_DELTA = 0.02

# ---------------------------------------------------------------------------
# Seam evaluation (sections 15, 16)
# ---------------------------------------------------------------------------

SEAM_WINDOW_SECONDS = 0.030
RENDER_REPEAT_COUNT = 4
DEFAULT_CROSSFADE_LENGTHS_MS = (20.0, 50.0, 100.0, 200.0)
CROSSFADE_MAX_RATIO = 0.20
CROSSFADE_MAX_SECONDS = 0.400
CROSSFADE_MIN_SAMPLES = 8

# ---------------------------------------------------------------------------
# Scoring weights (sections 16.5, 17)
# ---------------------------------------------------------------------------

TOTAL_WEIGHTS: dict[str, float] = {
    "hard_seam": 0.55,
    "crossfade_seam": 0.30,
    "sustain_quality": 0.10,
    "loop_length_penalty": 0.05,
}

HARD_SEAM_WEIGHTS: dict[str, float] = {
    "waveform_correlation": 0.25,
    "amplitude_jump": 0.10,
    "derivative_jump": 0.10,
    "spectral_continuity": 0.25,
    "level_continuity": 0.10,
    "pitch_continuity": 0.10,
    "modulation_continuity": 0.05,
    "stereo_continuity": 0.05,
}

# Normalization scales that map raw seam measurements to the 0..1 cost range.
AMPLITUDE_JUMP_SCALE = 0.5
DERIVATIVE_JUMP_SCALE = 0.5
SPECTRAL_RELATIVE_SCALE = 3.0
LEVEL_DB_SCALE = 3.0
LEVEL_SLOPE_SCALE = 20.0
PITCH_CENTS_SCALE = 50.0
MODULATION_PHASE_SCALE = 1.0
STEREO_SIDE_DB_SCALE = 6.0
STEREO_CORR_SCALE = 0.5

# ---------------------------------------------------------------------------
# Acceptance thresholds (section 17.4)
# ---------------------------------------------------------------------------

DEFAULT_QUALITY_THRESHOLD = 0.35
HARD_SEAM_MAX_SCORE = 0.45
SUSTAIN_MIN_CONFIDENCE = 0.50

# ---------------------------------------------------------------------------
# Confidence (section 18)
# ---------------------------------------------------------------------------

CONFIDENCE_HIGH_THRESHOLD = 0.75
CONFIDENCE_MEDIUM_THRESHOLD = 0.45

# ---------------------------------------------------------------------------
# smpl chunk defaults (section 19)
# ---------------------------------------------------------------------------

DEFAULT_MIDI_UNITY_NOTE = 60

# ---------------------------------------------------------------------------
# Preview (section 21)
# ---------------------------------------------------------------------------

PREVIEW_CONTEXT_SECONDS = 1.0
PREVIEW_REPEAT_COUNT = 4
PREVIEW_GAP_SECONDS = 0.5

# ---------------------------------------------------------------------------
# CLI defaults (section 5.4)
# ---------------------------------------------------------------------------

DEFAULT_MIN_SUSTAIN_SECONDS = 0.75
DEFAULT_MIN_LOOP_SECONDS = 0.50
DEFAULT_MAX_LOOP_SECONDS = 8.00
DEFAULT_TOP_K = 10


@dataclass(frozen=True)
class DetectionSettings:
    """Resolved runtime settings for one detection run."""

    input_path: Path
    output_path: Path
    report_path: Path | None = None
    preview_path: Path | None = None
    search_start: float | None = None
    search_end: float | None = None
    min_sustain: float = DEFAULT_MIN_SUSTAIN_SECONDS
    min_loop: float = DEFAULT_MIN_LOOP_SECONDS
    max_loop: float = DEFAULT_MAX_LOOP_SECONDS
    fmin: float = DEFAULT_FMIN
    fmax: float = DEFAULT_FMAX
    crossfade_lengths_ms: tuple[float, ...] = DEFAULT_CROSSFADE_LENGTHS_MS
    top_k: int = DEFAULT_TOP_K
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD
    midi_unity_note: int | None = None
    replace_existing_loop: bool = False
    force: bool = False
    dry_run: bool = False
    verbose: bool = False


@dataclass(frozen=True)
class FrameConfig:
    """Frame/STFT layout derived from the sample rate (section 9)."""

    sample_rate: int
    frame_length: int
    hop_length: int
    mel_bands: int = MEL_BANDS

    def frame_to_sample(self, frame_index: int) -> int:
        """Return the first sample of an analysis frame (center=False)."""
        return frame_index * self.hop_length

    def sample_to_frame(self, sample_index: int) -> int:
        """Return the frame whose window starts at or before the sample."""
        return sample_index // self.hop_length

    def seconds_to_frames(self, seconds: float) -> int:
        return round(seconds * self.sample_rate / self.hop_length)


def next_power_of_two(value: int) -> int:
    result = 1
    while result < value:
        result *= 2
    return result


def make_frame_config(sample_rate: int) -> FrameConfig:
    frame_length = next_power_of_two(round(sample_rate * TARGET_WINDOW_SECONDS))
    frame_length = max(FRAME_LENGTH_MIN, min(FRAME_LENGTH_MAX, frame_length))
    hop_length = round(sample_rate * HOP_SECONDS)
    return FrameConfig(
        sample_rate=sample_rate,
        frame_length=frame_length,
        hop_length=hop_length,
    )


@dataclass(frozen=True)
class _ConfigSnapshot:
    """Configuration echoed into JSON reports."""

    min_loop_seconds: float
    max_loop_seconds: float
    quality_threshold: float
    crossfade_lengths_ms: tuple[float, ...] = field(default=DEFAULT_CROSSFADE_LENGTHS_MS)
