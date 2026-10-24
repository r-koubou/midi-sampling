"""Unit tests for the detection pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from wav_silence_trimmer.detector import (
    compute_frame_rms,
    detect_trim_region,
    estimate_noise_floor,
    remove_dc_offset,
    to_dbfs,
)
from wav_silence_trimmer.errors import NoSignalDetectedError
from wav_silence_trimmer.models import TrimConfig

from conftest import SAMPLE_RATE, make_noise, make_standard_sample, make_tone

CONFIG = TrimConfig()


def ms_to_samples(ms: float) -> int:
    return round(SAMPLE_RATE * ms / 1000.0)


class TestFrameRms:
    def test_mono_sine(self) -> None:
        tone = make_tone(1.0, amplitude=0.5)
        rms, starts, ends = compute_frame_rms(tone, 441, 88)
        expected = 0.5 / np.sqrt(2.0)
        assert np.allclose(rms[: len(rms) // 2], expected, rtol=0.05)

    def test_stereo_one_side_uses_max(self) -> None:
        tone = make_tone(1.0, amplitude=0.5)
        stereo = np.hstack([tone, np.zeros_like(tone)])
        rms, _, _ = compute_frame_rms(stereo, 441, 88)
        expected = 0.5 / np.sqrt(2.0)
        assert np.allclose(rms[: len(rms) // 2], expected, rtol=0.05)

    def test_silence(self) -> None:
        silence = np.zeros((4410, 1))
        rms, _, _ = compute_frame_rms(silence, 441, 88)
        assert np.all(rms == 0.0)

    def test_input_shorter_than_frame(self) -> None:
        short = np.full((100, 1), 0.25)
        rms, starts, ends = compute_frame_rms(short, 441, 88)
        assert rms.size > 0
        assert np.isclose(rms[0], 0.25)
        assert ends[-1] == 100

    def test_input_not_multiple_of_frame(self) -> None:
        audio = np.full((1000, 1), 0.1)
        rms, starts, ends = compute_frame_rms(audio, 441, 88)
        assert ends[-1] == 1000
        assert np.allclose(rms, 0.1)


class TestDcOffset:
    def test_median_removed(self) -> None:
        audio = make_tone(1.0, amplitude=0.3) + 0.05
        analysis = remove_dc_offset(audio)
        assert abs(np.median(analysis)) < 1e-9
        # Original array untouched.
        assert np.median(audio) > 0.04


class TestNoiseFloor:
    def _floor(self, audio: np.ndarray, config: TrimConfig = CONFIG) -> float:
        analysis = remove_dc_offset(audio)
        frame_length = ms_to_samples(config.frame_ms)
        hop_length = ms_to_samples(config.hop_ms)
        rms, starts, ends = compute_frame_rms(analysis, frame_length, hop_length)
        db = to_dbfs(rms)
        return estimate_noise_floor(
            db, starts, ends, audio.shape[0], SAMPLE_RATE, config
        )

    def test_pure_silence_clamped_to_minimum(self) -> None:
        floor = self._floor(np.zeros((SAMPLE_RATE * 3, 1)))
        assert floor == CONFIG.minimum_noise_floor_dbfs

    def test_constant_white_noise(self) -> None:
        audio, _, _ = make_standard_sample()
        floor = self._floor(audio)
        assert -90.0 < floor < -70.0

    def test_impulse_in_head_is_robust(self) -> None:
        audio, _, _ = make_standard_sample()
        audio[1000:1050, 0] = 0.5  # impulse inside head margin
        floor = self._floor(audio)
        assert -90.0 < floor < -70.0

    def test_short_reverb_in_tail_is_robust(self) -> None:
        audio, _, true_end = make_standard_sample()
        n = audio.shape[0]
        tail_reverb = make_tone(0.1, amplitude=0.01)
        audio[n - 30000 : n - 30000 + tail_reverb.shape[0]] += tail_reverb
        floor = self._floor(audio)
        assert -90.0 < floor < -70.0

    def test_channel_noise_difference_uses_louder(self) -> None:
        left = make_noise(3.0, seed=3)
        right = make_noise(3.0, seed=4) * 10.0
        audio = np.hstack([left, right])
        floor = self._floor(audio)
        # Max-channel RMS means the louder channel dominates.
        assert floor > -70.0

    def test_edge_longer_than_input(self) -> None:
        audio = make_noise(0.5)
        config = TrimConfig(edge_noise_seconds=2.0)
        floor = self._floor(audio, config)
        assert -90.0 < floor < -70.0


class TestDetection:
    def test_clear_attack_boundaries(self) -> None:
        audio, true_start, true_end = make_standard_sample()
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        pre_roll = ms_to_samples(CONFIG.pre_roll_ms)
        post_roll = ms_to_samples(CONFIG.post_roll_ms)
        tolerance_start = ms_to_samples(10.0)
        tolerance_end = ms_to_samples(30.0)
        assert abs(result.start_sample - (true_start - pre_roll)) <= tolerance_start
        assert abs(result.end_sample_exclusive - (true_end + post_roll)) <= tolerance_end

    def test_stereo_one_side_only(self) -> None:
        audio, true_start, _ = make_standard_sample()
        stereo = np.hstack([audio, make_noise(audio.shape[0] / SAMPLE_RATE, seed=9)])
        stereo = stereo[: audio.shape[0]]
        result = detect_trim_region(stereo, SAMPLE_RATE, CONFIG)
        assert result.start_sample <= true_start
        assert result.start_sample >= true_start - ms_to_samples(20.0)

    def test_slow_attack_not_over_trimmed(self) -> None:
        head = make_noise(1.0, seed=1)
        n_ramp = round(0.3 * SAMPLE_RATE)
        t = np.arange(n_ramp) / SAMPLE_RATE
        ramp = (np.linspace(0.0, 0.3, n_ramp) * np.sin(2 * np.pi * 220 * t))[:, None]
        sustain = make_tone(1.5, amplitude=0.3, frequency=220.0)
        tail = make_noise(1.0, seed=2)
        audio = np.vstack([head, ramp, sustain, tail])
        true_start = head.shape[0]
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        # The start must not eat far into the ramp.
        assert result.start_sample <= true_start + ms_to_samples(50.0)

    def test_long_release_preserved(self) -> None:
        head = make_noise(1.0, seed=1)
        tone = make_tone(1.0, amplitude=0.3)
        n_rel = round(1.5 * SAMPLE_RATE)
        t = np.arange(n_rel) / SAMPLE_RATE
        release = (0.3 * np.exp(-t * 4.0) * np.sin(2 * np.pi * 440 * t))[:, None]
        tail = make_noise(1.0, seed=2)
        audio = np.vstack([head, tone, release, tail])
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        # Release decays below off-threshold (-72 dB) around t where
        # 0.212*exp(-4t) = 2.5e-4 -> t ~ 1.68 s; require most of it kept.
        release_end_min = head.shape[0] + tone.shape[0] + round(1.0 * SAMPLE_RATE)
        assert result.end_sample_exclusive >= release_end_min

    def test_tremolo_gaps_bridged(self) -> None:
        head = make_noise(1.0, seed=1)
        burst = make_tone(0.1, amplitude=0.3)
        gap = np.zeros((round(0.06 * SAMPLE_RATE), 1))
        body = np.vstack([burst, gap] * 8 + [burst])
        tail = make_noise(1.0, seed=2)
        audio = np.vstack([head, body, tail])
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        body_end = head.shape[0] + body.shape[0]
        assert result.end_sample_exclusive >= body_end - ms_to_samples(30.0)

    def test_mid_rest_preserved(self) -> None:
        head = make_noise(1.0, seed=1)
        tone1 = make_tone(0.5, amplitude=0.3)
        rest = np.zeros((round(0.5 * SAMPLE_RATE), 1))
        tone2 = make_tone(0.5, amplitude=0.3)
        tail = make_noise(1.0, seed=2)
        audio = np.vstack([head, tone1, rest, tone2, tail])
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        tone2_end = head.shape[0] + tone1.shape[0] + rest.shape[0] + tone2.shape[0]
        assert result.start_sample <= head.shape[0]
        assert result.end_sample_exclusive >= tone2_end - ms_to_samples(30.0)

    def test_head_click_not_detected_as_start(self) -> None:
        config = TrimConfig(minimum_on_ms=20.0)
        head = make_noise(1.0, seed=1)
        click_pos = round(0.4 * SAMPLE_RATE)
        head[click_pos : click_pos + ms_to_samples(2.0)] = 0.5
        tone = make_tone(2.0, amplitude=0.3)
        tail = make_noise(1.0, seed=2)
        audio = np.vstack([head, tone, tail])
        true_start = head.shape[0]
        result = detect_trim_region(audio, SAMPLE_RATE, config)
        assert result.start_sample >= true_start - ms_to_samples(30.0)

    def test_tail_click_not_extending_end(self) -> None:
        config = TrimConfig(minimum_on_ms=20.0)
        head = make_noise(1.0, seed=1)
        tone = make_tone(2.0, amplitude=0.3)
        tail = make_noise(1.0, seed=2)
        click_pos = round(0.6 * SAMPLE_RATE)
        tail[click_pos : click_pos + ms_to_samples(2.0)] = 0.5
        audio = np.vstack([head, tone, tail])
        true_end = head.shape[0] + tone.shape[0]
        result = detect_trim_region(audio, SAMPLE_RATE, config)
        assert result.end_sample_exclusive <= true_end + ms_to_samples(100.0)

    def test_all_silence_raises(self) -> None:
        with pytest.raises(NoSignalDetectedError):
            detect_trim_region(np.zeros((SAMPLE_RATE * 3, 1)), SAMPLE_RATE, CONFIG)

    def test_noise_only_raises(self) -> None:
        with pytest.raises(NoSignalDetectedError):
            detect_trim_region(make_noise(3.0), SAMPLE_RATE, CONFIG)

    def test_empty_raises(self) -> None:
        with pytest.raises(NoSignalDetectedError):
            detect_trim_region(np.zeros((0, 1)), SAMPLE_RATE, CONFIG)

    def test_all_signal_raises(self) -> None:
        # Sound over the entire file violates the ~1 s edge margin
        # precondition: the edge noise floor equals the signal level, so no
        # frame can exceed floor + on_margin (spec 8.5 / 8.7).
        audio = make_tone(3.0, amplitude=0.3)
        with pytest.raises(NoSignalDetectedError):
            detect_trim_region(audio, SAMPLE_RATE, CONFIG)

    def test_signal_with_short_edge_margins_kept_whole(self) -> None:
        # Margins much shorter than edge_noise_seconds still work because the
        # 20th percentile of the combined edge levels tracks the quiet tail.
        head = make_noise(0.2, seed=1)
        tone = make_tone(2.0, amplitude=0.3)
        tail = make_noise(1.0, seed=2)
        audio = np.vstack([head, tone, tail])
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        assert result.start_sample <= head.shape[0]
        assert result.end_sample_exclusive >= head.shape[0] + tone.shape[0]


class TestBoundaries:
    def test_bounds_are_valid(self) -> None:
        audio, _, _ = make_standard_sample()
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        assert 0 <= result.start_sample < result.end_sample_exclusive
        assert result.end_sample_exclusive <= audio.shape[0]

    def test_pre_and_post_roll_applied(self) -> None:
        audio, _, _ = make_standard_sample()
        no_roll = TrimConfig(pre_roll_ms=0.0, post_roll_ms=0.0)
        with_roll = TrimConfig(pre_roll_ms=8.0, post_roll_ms=40.0)
        base = detect_trim_region(audio, SAMPLE_RATE, no_roll)
        rolled = detect_trim_region(audio, SAMPLE_RATE, with_roll)
        assert rolled.start_sample == base.start_sample - ms_to_samples(8.0)
        assert rolled.end_sample_exclusive == base.end_sample_exclusive + ms_to_samples(40.0)

    def test_exclusive_end_slice(self) -> None:
        audio, _, _ = make_standard_sample()
        result = detect_trim_region(audio, SAMPLE_RATE, CONFIG)
        trimmed = audio[result.start_sample : result.end_sample_exclusive]
        assert trimmed.shape[0] == result.end_sample_exclusive - result.start_sample
