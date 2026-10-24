"""Audition preview rendering (section 21).

The preview WAV is a separate auxiliary file: short context, hard-seam
repeats, a gap of silence, then crossfaded repeats.  It never affects the
smpl-tagged output.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile
from numpy.typing import NDArray

from sample_loop_detector.analysis.render import render_crossfaded_repeats
from sample_loop_detector.config import (
    PREVIEW_CONTEXT_SECONDS,
    PREVIEW_GAP_SECONDS,
    PREVIEW_REPEAT_COUNT,
)
from sample_loop_detector.models import LoopResult

FloatArray = NDArray[np.float64]


def build_preview_signal(audio: FloatArray, result: LoopResult, sample_rate: int) -> FloatArray:
    start = result.selected.start_frame
    end = result.selected.end_frame
    loop = audio[start : end + 1]
    channels = audio.shape[1]

    context_samples = round(PREVIEW_CONTEXT_SECONDS * sample_rate)
    context = audio[max(0, start - context_samples) : start]

    hard = np.concatenate([loop] * PREVIEW_REPEAT_COUNT, axis=0)
    silence = np.zeros((round(PREVIEW_GAP_SECONDS * sample_rate), channels))

    crossfade = result.selected.crossfade_frames
    if 0 < crossfade < loop.shape[0]:
        faded, _ = render_crossfaded_repeats(loop, crossfade, PREVIEW_REPEAT_COUNT)
    else:
        faded = hard

    return np.concatenate([context, hard, silence, faded], axis=0)


def write_preview(path: Path, audio: FloatArray, result: LoopResult, sample_rate: int) -> None:
    signal = build_preview_signal(audio, result, sample_rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(str(path), signal.astype(np.float32), sample_rate, subtype="FLOAT")
