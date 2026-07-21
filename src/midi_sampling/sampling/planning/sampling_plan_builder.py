from logging import getLogger
from pathlib import Path

from midi_sampling.sampling.exceptions import (
    DefinitionValidationError,
    DuplicateOutputFilenameError,
)
from midi_sampling.sampling.hashing import ResolvedDefinitionHasher
from midi_sampling.sampling.naming import SampleFilenameFormatter
from midi_sampling.sampling.planning.sampling_plan import (
    MANIFEST_FILENAME,
    WAV_SUFFIX,
    AudioFormatSpec,
    SamplingPlan,
    TonePlan,
    VelocityLayerSpec,
    ZoneSpec,
)
from midi_sampling.sampling.planning.sampling_target import SamplingTarget
from midi_sampling.sampling.resolving import ResolvedSession, ResolvedTone
from midi_sampling.sampling.validation import OutputPathValidator

logger = getLogger(__name__)


class SamplingPlanBuilder:
    """
    Build a validated SamplingPlan from a ResolvedSession.

    - Generates the zone x velocity-layer product per tone.
    - Fixes the execution order (root_note asc, velocity_low asc).
    - Generates and validates every output filename and path before any
      device is opened.
    - Computes the resolved definition hash per tone.
    """

    def __init__(
        self,
        output_path_validator: OutputPathValidator | None = None,
        hasher: ResolvedDefinitionHasher | None = None,
    ) -> None:
        self._path_validator = (
            output_path_validator
            if output_path_validator is not None
            else OutputPathValidator()
        )
        self._hasher = hasher if hasher is not None else ResolvedDefinitionHasher()

    def build(self, session: ResolvedSession) -> SamplingPlan:
        formatter = SampleFilenameFormatter(session.sample_filename_template)
        audio_format = AudioFormatSpec(
            sample_rate=session.audio_information.sample_rate,
            channels=session.audio_information.channels,
            data_format=session.audio_information.data_format.name.lower(),
        )

        output_root = session.output_directory

        tones = tuple(
            self._build_tone_plan(session, tone, formatter, audio_format, output_root)
            for tone in session.tones
        )

        plan = SamplingPlan(
            channel=session.channel,
            initialization_files=session.initialization_files,
            program_change_settle=session.program_change_settle,
            pre_roll=session.pre_roll,
            inter_sample_wait=session.inter_sample_wait,
            audio_format=audio_format,
            sample_filename_template=session.sample_filename_template,
            output_root=output_root,
            tones=tones,
        )

        total_targets = sum(len(tone.targets) for tone in plan.tones)
        logger.info(
            f"Built sampling plan: {len(plan.tones)} tones, "
            f"{total_targets} samples, output root: {output_root}"
        )
        return plan

    def _build_tone_plan(
        self,
        session: ResolvedSession,
        tone: ResolvedTone,
        formatter: SampleFilenameFormatter,
        audio_format: AudioFormatSpec,
        output_root: Path,
    ) -> TonePlan:
        context = f"definition {tone.id!r}"
        self._path_validator.validate_component(tone.id, context)

        tone_directory = output_root / tone.id
        manifest_path = tone_directory / MANIFEST_FILENAME

        zones = tuple(
            ZoneSpec(low=zone.low, root=zone.root, high=zone.high)
            for zone in tone.zones
        )
        velocity_layers = tuple(
            VelocityLayerSpec(low=layer.low, high=layer.high, send=layer.send)
            for layer in tone.velocity_layers
        )

        combinations = [
            (zone, layer) for zone in zones for layer in velocity_layers
        ]
        combinations.sort(
            key=lambda pair: (
                pair[0].root,
                pair[1].low,
                pair[0].low,
                pair[0].high,
                pair[1].send,
            )
        )

        targets: list[SamplingTarget] = []
        seen_filenames: set[str] = set()
        for sample_index, (zone, layer) in enumerate(combinations):
            values = {
                "definition_id": tone.id,
                "bank_msb": tone.bank_msb,
                "bank_lsb": tone.bank_lsb,
                "program": tone.program,
                "root_note": zone.root,
                "key_low": zone.low,
                "key_high": zone.high,
                "velocity_low": layer.low,
                "velocity_high": layer.high,
                "send_velocity": layer.send,
                "sample_index": sample_index,
            }
            stem = formatter.format(values)
            file_name = f"{stem}{WAV_SUFFIX}"
            sample_context = f"{context}: sample {sample_index}"

            self._path_validator.validate_component(file_name, sample_context)

            if file_name in seen_filenames:
                raise DuplicateOutputFilenameError(
                    f"{context}: duplicate output filename {file_name!r}; "
                    f"the naming template does not distinguish all samples"
                )
            seen_filenames.add(file_name)

            output_path = tone_directory / file_name
            self._path_validator.validate_full_path(output_path, sample_context)

            total_seconds = session.pre_roll + tone.note_on + tone.release_capture
            if total_seconds <= 0:
                raise DefinitionValidationError(
                    f"{context}: total recording time must be greater than 0 "
                    f"(pre_roll + note_on + release_capture = {total_seconds})"
                )

            targets.append(
                SamplingTarget(
                    definition_id=tone.id,
                    sample_index=sample_index,
                    root_note=zone.root,
                    key_low=zone.low,
                    key_high=zone.high,
                    velocity_low=layer.low,
                    velocity_high=layer.high,
                    send_velocity=layer.send,
                    note_on=tone.note_on,
                    release_capture=tone.release_capture,
                    file_name=file_name,
                    output_path=output_path,
                )
            )

        self._path_validator.validate_full_path(manifest_path, context)

        resolved_definition_sha256 = self._hasher.hash_payload(
            self._hasher.build_payload(
                channel=session.channel,
                bank_msb=tone.bank_msb,
                bank_lsb=tone.bank_lsb,
                program=tone.program,
                zones=[
                    {"low": zone.low, "root": zone.root, "high": zone.high}
                    for zone in zones
                ],
                velocity_layers=[
                    {"low": layer.low, "high": layer.high, "send": layer.send}
                    for layer in velocity_layers
                ],
                program_change_settle=session.program_change_settle,
                pre_roll=session.pre_roll,
                note_on=tone.note_on,
                release_capture=tone.release_capture,
                inter_sample_wait=session.inter_sample_wait,
                sample_rate=audio_format.sample_rate,
                audio_channels=audio_format.channels,
                data_format=audio_format.data_format,
                sample_filename_template=session.sample_filename_template,
            )
        )

        return TonePlan(
            definition_id=tone.id,
            name=tone.name,
            bank_msb=tone.bank_msb,
            bank_lsb=tone.bank_lsb,
            program=tone.program,
            note_on=tone.note_on,
            release_capture=tone.release_capture,
            zones=zones,
            velocity_layers=velocity_layers,
            resolved_definition_sha256=resolved_definition_sha256,
            directory=tone_directory,
            manifest_path=manifest_path,
            targets=tuple(targets),
        )
