"""Short linear fades applied identically to all channels."""

from __future__ import annotations

import numpy as np


def apply_fades(
    audio: np.ndarray,
    sample_rate: int,
    fade_in_ms: float,
    fade_out_ms: float,
    *,
    apply_fade_in: bool = True,
    apply_fade_out: bool = True,
) -> tuple[np.ndarray, int, int]:
    """Apply linear fade-in and fade-out to a copy of the audio.

    The same gain curve is applied to every channel so the stereo image is
    not altered. Fade lengths are clamped to the audio length, so very short
    audio never raises.

    Args:
        audio: Audio shaped (samples, channels).
        sample_rate: Sample rate in Hz.
        fade_in_ms: Fade-in duration in milliseconds.
        fade_out_ms: Fade-out duration in milliseconds.
        apply_fade_in: Whether to apply the fade-in at all.
        apply_fade_out: Whether to apply the fade-out at all.

    Returns:
        Tuple of (faded_audio, fade_in_frames, fade_out_frames).
    """
    total = audio.shape[0]
    faded = audio.copy()

    fade_in_frames = 0
    if apply_fade_in and fade_in_ms > 0 and total > 0:
        fade_in_frames = min(total, round(sample_rate * fade_in_ms / 1000.0))
        if fade_in_frames > 0:
            curve = np.linspace(0.0, 1.0, fade_in_frames, endpoint=False)
            faded[:fade_in_frames] *= curve[:, None]

    fade_out_frames = 0
    if apply_fade_out and fade_out_ms > 0 and total > 0:
        fade_out_frames = min(total, round(sample_rate * fade_out_ms / 1000.0))
        if fade_out_frames > 0:
            curve = np.linspace(1.0, 0.0, fade_out_frames + 1)[1:]
            faded[total - fade_out_frames:] *= curve[:, None]

    return faded, fade_in_frames, fade_out_frames
