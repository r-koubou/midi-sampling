"""End-to-end detection pipeline (section 7) and output WAV writing."""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from sample_loop_detector.analysis.candidates import generate_candidates
from sample_loop_detector.analysis.features import FrameFeatures, extract_features
from sample_loop_detector.analysis.modulation import ModulationFeatures, extract_modulation
from sample_loop_detector.analysis.pitch import estimate_pitch
from sample_loop_detector.analysis.preprocessing import (
    compute_floors,
    prepare_analysis_audio,
    validate_activity,
)
from sample_loop_detector.analysis.refinement import refine_candidate
from sample_loop_detector.analysis.render import (
    allowed_crossfade_samples,
    evaluate_crossfade,
    evaluate_hard_seam,
)
from sample_loop_detector.analysis.scoring import (
    check_acceptance,
    combine_scores,
    compute_confidence,
    select_best,
)
from sample_loop_detector.analysis.sustain import SustainAnalysis, detect_sustain
from sample_loop_detector.audio.decoder import decode_wave
from sample_loop_detector.audio.riff import WaveFile, insert_smpl_chunk, parse_wave_file
from sample_loop_detector.audio.smpl import (
    MidiUnityNote,
    build_smpl_chunk,
    estimate_midi_unity_note,
)
from sample_loop_detector.config import (
    CROSSFADE_MAX_SECONDS,
    MAX_DETAILED_CANDIDATES,
    MAX_REFINED_CANDIDATES,
    DetectionSettings,
    FrameConfig,
    make_frame_config,
)
from sample_loop_detector.exceptions import (
    ExistingSmplChunkError,
    InvalidArgumentsError,
    LoopCandidateNotFoundError,
    SustainNotFoundError,
    WaveWriteError,
)
from sample_loop_detector.models import (
    AnalysisSummary,
    AudioMetadata,
    LoopCandidate,
    LoopResult,
    PitchEstimate,
    ScoredCandidate,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DetectionOutput:
    """Everything the CLI and reporters need after one detection run."""

    status: str  # "success" or a failure reason code
    wave: WaveFile
    metadata: AudioMetadata
    analysis: AnalysisSummary | None
    pitch: PitchEstimate | None
    result: LoopResult | None
    scored: tuple[ScoredCandidate, ...]  # ranked, selected first
    failure_reason: str | None
    failure_message: str | None
    best_rejected: ScoredCandidate | None
    warnings: tuple[str, ...]

    @property
    def succeeded(self) -> bool:
        return self.status == "success"


def _validate_settings(settings: DetectionSettings, duration: float) -> None:
    start = settings.search_start if settings.search_start is not None else 0.0
    end = settings.search_end if settings.search_end is not None else duration
    if not (0.0 <= start < end <= duration):
        raise InvalidArgumentsError(
            f"search range must satisfy 0 <= start < end <= duration ({duration:.3f} s)"
        )
    if not (0.0 < settings.min_loop <= settings.max_loop):
        raise InvalidArgumentsError("loop length must satisfy 0 < min_loop <= max_loop")
    if not (0.0 <= settings.quality_threshold <= 1.0):
        raise InvalidArgumentsError("quality threshold must be within [0, 1]")
    if settings.top_k < 1:
        raise InvalidArgumentsError("top_k must be at least 1")
    if settings.min_sustain <= settings.min_loop:
        raise InvalidArgumentsError("min_loop must be smaller than min_sustain")
    if settings.midi_unity_note is not None and not (0 <= settings.midi_unity_note <= 127):
        raise InvalidArgumentsError("midi unity note must be within [0, 127]")


def run_detection(settings: DetectionSettings) -> DetectionOutput:
    wave = parse_wave_file(settings.input_path)
    if wave.smpl_chunks and not settings.replace_existing_loop:
        raise ExistingSmplChunkError(
            "input already contains an smpl chunk (use --replace-existing-loop)"
        )

    audio, metadata = decode_wave(wave)
    _validate_settings(settings, metadata.duration_seconds)

    config = make_frame_config(metadata.sample_rate)
    analysis_audio = prepare_analysis_audio(audio)
    features = extract_features(analysis_audio, config, settings.fmin, settings.fmax)
    floors = compute_floors(features.rms_db)
    # Only a completely inactive file is an input error; material whose
    # active region is merely shorter than the sustain requirement fails
    # later with exit code 2 (section 29.4).
    validate_activity(features.rms_db, floors.active_floor_db, 3)

    warnings: list[str] = []

    def failure(reason: str, message: str) -> DetectionOutput:
        return DetectionOutput(
            status=reason,
            wave=wave,
            metadata=metadata,
            analysis=None,
            pitch=None,
            result=None,
            scored=(),
            failure_reason=reason,
            failure_message=message,
            best_rejected=None,
            warnings=tuple(warnings),
        )

    try:
        sustain = detect_sustain(
            features,
            config,
            floors.active_floor_db,
            settings.min_sustain,
            settings.search_start,
            settings.search_end,
        )
    except SustainNotFoundError as error:
        return failure(error.reason, error.message)

    pitch = estimate_pitch(features, sustain, config)
    if pitch.f0_hz is None:
        warnings.append("pitch is unreliable; using spectral similarity without period constraints")
    modulation = extract_modulation(features, config)

    analysis_summary = AnalysisSummary(
        attack_end_seconds=sustain.attack_end_seconds,
        sustain_start_seconds=sustain.region.start_frame / metadata.sample_rate,
        sustain_end_seconds=sustain.region.end_frame / metadata.sample_rate,
        sustain_confidence=sustain.region.confidence,
        f0_hz=pitch.f0_hz,
        f0_confidence=pitch.confidence,
        voiced_ratio=pitch.voiced_ratio,
    )

    max_crossfade_seconds = min(
        CROSSFADE_MAX_SECONDS, max(settings.crossfade_lengths_ms, default=0.0) / 1000.0
    )
    try:
        coarse = generate_candidates(
            features,
            sustain,
            config,
            pitch,
            modulation,
            settings.min_loop,
            settings.max_loop,
            max_crossfade_seconds,
        )
    except LoopCandidateNotFoundError as error:
        output = failure(error.reason, error.message)
        return _with_analysis(output, analysis_summary, pitch)

    logger.debug("coarse candidates: %d", len(coarse))

    scored_entries, crossfade_consistency, shift_ratio = _evaluate_candidates(
        analysis_audio,
        features,
        config,
        coarse,
        pitch,
        modulation,
        sustain,
        settings,
    )
    if not scored_entries:
        output = failure(
            "no_loop_candidates",
            "No candidates survived refinement and rendering constraints.",
        )
        return _with_analysis(output, analysis_summary, pitch)

    best_index = select_best(
        [(sc.candidate, sc.score, abs_start) for sc, abs_start in scored_entries],
        sustain.region,
    )
    # Ranked list: selected candidate first, remaining by total score.
    selected = scored_entries[best_index][0]
    rest = sorted(
        (sc for i, (sc, _) in enumerate(scored_entries) if i != best_index),
        key=lambda sc: sc.score.total,
    )
    ranked = [selected, *rest][: max(settings.top_k, 1)]

    length_seconds = selected.candidate.length_frames / metadata.sample_rate
    decision = check_acceptance(
        selected.score,
        sustain.region.confidence,
        settings.quality_threshold,
        settings.min_loop,
        length_seconds,
    )
    if not decision.accepted:
        assert decision.reason is not None
        output = DetectionOutput(
            status=decision.reason,
            wave=wave,
            metadata=metadata,
            analysis=analysis_summary,
            pitch=pitch,
            result=None,
            scored=tuple(ranked),
            failure_reason=decision.reason,
            failure_message="No candidate satisfied the acceptance thresholds.",
            best_rejected=selected,
            warnings=tuple(warnings),
        )
        return output

    second_total = rest[0].score.total if rest else None
    confidence, confidence_label = compute_confidence(
        selected.score,
        second_total,
        len(scored_entries),
        sustain.region.confidence,
        pitch,
        crossfade_consistency,
        shift_ratio,
    )
    if confidence_label == "low":
        warnings.append("detection confidence is low; audition the result carefully")

    result = LoopResult(
        selected=selected.candidate,
        score=selected.score,
        confidence=confidence,
        confidence_label=confidence_label,
        alternatives=tuple(sc.candidate for sc in ranked[1:]),
        best_crossfade_ms=selected.best_crossfade_ms,
        alternative_scores=tuple(sc.score for sc in ranked[1:]),
    )
    return DetectionOutput(
        status="success",
        wave=wave,
        metadata=metadata,
        analysis=analysis_summary,
        pitch=pitch,
        result=result,
        scored=tuple(ranked),
        failure_reason=None,
        failure_message=None,
        best_rejected=None,
        warnings=tuple(warnings),
    )


def _with_analysis(
    output: DetectionOutput, analysis: AnalysisSummary, pitch: PitchEstimate
) -> DetectionOutput:
    return DetectionOutput(
        status=output.status,
        wave=output.wave,
        metadata=output.metadata,
        analysis=analysis,
        pitch=pitch,
        result=output.result,
        scored=output.scored,
        failure_reason=output.failure_reason,
        failure_message=output.failure_message,
        best_rejected=output.best_rejected,
        warnings=output.warnings,
    )


def _evaluate_candidates(
    analysis_audio: NDArray[np.float64],
    features: FrameFeatures,
    config: FrameConfig,
    coarse: tuple[LoopCandidate, ...],
    pitch: PitchEstimate,
    modulation: ModulationFeatures,
    sustain: SustainAnalysis,
    settings: DetectionSettings,
) -> tuple[list[tuple[ScoredCandidate, float]], float, float]:
    """Refine and fully evaluate the best coarse candidates.

    Returns (entries, crossfade_consistency, mean_refinement_shift_ratio)
    where each entry is (scored_candidate, |mono[start]|) for tie-breaks.
    """
    sample_rate = config.sample_rate
    mono = analysis_audio.mean(axis=1)

    refined: list[tuple[LoopCandidate, float]] = []  # candidate, shift ratio
    seen: set[tuple[int, int]] = set()
    for candidate in coarse[:MAX_REFINED_CANDIDATES]:
        adjusted = refine_candidate(
            analysis_audio,
            candidate,
            sample_rate,
            pitch,
            sustain.region.start_frame,
            sustain.region.end_frame,
        )
        key = (adjusted.start_frame, adjusted.end_frame)
        if key in seen:
            continue
        seen.add(key)
        shift = abs(adjusted.end_frame - candidate.end_frame)
        shift_ratio = shift / max(1, candidate.length_frames)
        min_len = round(settings.min_loop * sample_rate)
        if adjusted.length_frames < min_len:
            continue
        refined.append((adjusted, shift_ratio))

    entries: list[tuple[ScoredCandidate, float]] = []
    consistency_terms: list[float] = []
    shift_ratios: list[float] = []
    for candidate, shift_ratio in refined[:MAX_DETAILED_CANDIDATES]:
        metrics = evaluate_hard_seam(
            analysis_audio,
            features,
            config,
            candidate.start_frame,
            candidate.end_frame,
            pitch,
            modulation,
        )
        loop = analysis_audio[candidate.start_frame : candidate.end_frame + 1]
        crossfades = allowed_crossfade_samples(
            settings.crossfade_lengths_ms, candidate.length_frames, sample_rate
        )
        cf_scores: dict[int, float] = {
            cf: evaluate_crossfade(loop, cf, sample_rate) for cf in crossfades
        }
        if cf_scores:
            best_cf = min(cf_scores, key=lambda k: cf_scores[k])
            crossfade_score = cf_scores[best_cf]
            best_cf_ms = best_cf / sample_rate * 1000.0
            spread = float(np.std(list(cf_scores.values())))
            consistency_terms.append(float(np.clip(1.0 - spread * 5.0, 0.0, 1.0)))
        else:
            # No admissible crossfade length: rate the seam by itself.
            best_cf = 0
            crossfade_score = 1.0
            best_cf_ms = 0.0

        score = combine_scores(candidate, metrics, crossfade_score, sustain.region, sample_rate)
        final_candidate = LoopCandidate(
            start_frame=candidate.start_frame,
            end_frame=candidate.end_frame,
            crossfade_frames=best_cf,
            coarse_score=candidate.coarse_score,
        )
        entries.append(
            (
                ScoredCandidate(
                    candidate=final_candidate, score=score, best_crossfade_ms=best_cf_ms
                ),
                float(abs(mono[candidate.start_frame])),
            )
        )
        shift_ratios.append(shift_ratio)

    consistency = float(np.mean(consistency_terms)) if consistency_terms else 0.0
    mean_shift = float(np.mean(shift_ratios)) if shift_ratios else 0.0
    return entries, consistency, mean_shift


def resolve_midi_unity_note(
    settings: DetectionSettings, pitch: PitchEstimate | None
) -> MidiUnityNote:
    if settings.midi_unity_note is not None:
        return MidiUnityNote(note=settings.midi_unity_note, pitch_fraction=0)
    return estimate_midi_unity_note(pitch.f0_hz if pitch is not None else None)


def write_output_wav(output: DetectionOutput, settings: DetectionSettings) -> Path:
    """Atomically write the smpl-tagged WAV next to the requested path."""
    assert output.result is not None
    if settings.output_path.exists() and not settings.force:
        raise WaveWriteError(f"output file already exists: {settings.output_path} (use --force)")

    unity = resolve_midi_unity_note(settings, output.pitch)
    smpl = build_smpl_chunk(
        output.metadata.sample_rate,
        output.result.selected.start_frame,
        output.result.selected.end_frame,
        unity,
    )
    payload = insert_smpl_chunk(output.wave, smpl, settings.replace_existing_loop)

    target = settings.output_path
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, suffix=".tmp", delete=False
        ) as handle:
            temp_path = handle.name
            handle.write(payload)
        os.replace(temp_path, target)
        temp_path = None
    except OSError as error:
        raise WaveWriteError(f"failed to write output WAV: {error}") from error
    finally:
        if temp_path is not None and os.path.exists(temp_path):
            os.unlink(temp_path)
    return target
