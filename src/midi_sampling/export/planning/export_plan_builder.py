from logging import getLogger

from midi_sampling.export.abstractions import (
    InstrumentEnvelope,
    InstrumentExclusiveGroup,
    InstrumentModel,
    InstrumentRegion,
    RegionLoop,
    TriggerMode,
)
from midi_sampling.export.audio import WAV_SUFFIX, AudioExporter
from midi_sampling.export.exceptions import ExportDefinitionError
from midi_sampling.export.planning.export_plan import (
    SAMPLES_DIRECTORY_NAME,
    AudioExportTask,
    ExportPlan,
)
from midi_sampling.export.resolving import ResolvedInstrument, ResolvedToneSource
from midi_sampling.postprocess.manifest import ManifestSample

logger = getLogger(__name__)


class ExportPlanBuilder:
    """
    Expand a resolved instrument into the sampler-agnostic model and the
    list of audio files to write. Group numbers are assigned here (1-based,
    in definition order) so that every writer sees the same ids.
    """

    def build(self, resolved: ResolvedInstrument) -> ExportPlan:
        definition = resolved.definition
        suffix = AudioExporter(definition.audio.format).suffix

        release_decays: dict[str, float | None] = {
            trigger.plays.tone: trigger.rt_decay
            for trigger in definition.release_triggers
        }

        groups = tuple(
            InstrumentExclusiveGroup(number=number, name=group.name)
            for number, group in enumerate(definition.exclusive_groups, start=1)
        )

        regions = []
        tasks = []
        for tone in resolved.tones:
            trigger: TriggerMode = (
                "release" if tone.tone_id in release_decays else "attack"
            )
            rt_decay = release_decays.get(tone.tone_id)

            for sample in tone.manifest.samples:
                relative_path = self._relative_sample_path(
                    tone, sample, suffix
                )
                regions.append(
                    InstrumentRegion(
                        tone_id=tone.tone_id,
                        source_path=tone.directory / sample.file,
                        sample_path=relative_path,
                        root_note=sample.mapping.root_note,
                        key_low=sample.mapping.key_low,
                        key_high=sample.mapping.key_high,
                        velocity_low=sample.mapping.velocity_low,
                        velocity_high=sample.mapping.velocity_high,
                        loop=self._resolve_loop(sample),
                        exclusive_group=self._resolve_group_number(
                            resolved, tone, sample
                        ),
                        trigger=trigger,
                        rt_decay=rt_decay,
                    )
                )
                tasks.append(
                    AudioExportTask(
                        source_path=tone.directory / sample.file,
                        relative_path=relative_path,
                        data_format=tone.manifest.audio.data_format,
                    )
                )

        logger.info(
            f"Planned {len(regions)} region(s), "
            f"{len(groups)} exclusive group(s)"
        )

        return ExportPlan(
            instrument=InstrumentModel(
                name=definition.name,
                envelope=InstrumentEnvelope(
                    attack=definition.envelope.attack,
                    release=definition.envelope.release,
                ),
                regions=tuple(regions),
                exclusive_groups=groups,
            ),
            audio_format=definition.audio.format,
            bit_depth=definition.audio.bit_depth,
            audio_tasks=tuple(tasks),
        )

    def _relative_sample_path(
        self, tone: ResolvedToneSource, sample: ManifestSample, suffix: str
    ) -> str:
        stem = (
            sample.file[: -len(WAV_SUFFIX)]
            if sample.file.lower().endswith(WAV_SUFFIX)
            else sample.file
        )
        return f"{SAMPLES_DIRECTORY_NAME}/{tone.tone_id}/{stem}{suffix}"

    def _resolve_loop(self, sample: ManifestSample) -> RegionLoop | None:
        loop = sample.loop
        if (
            loop is None
            or not loop.applied
            or loop.status != "success"
            or loop.start_frame is None
            or loop.end_frame is None
        ):
            return None
        return RegionLoop(
            start_frame=loop.start_frame, end_frame=loop.end_frame
        )

    def _resolve_group_number(
        self,
        resolved: ResolvedInstrument,
        tone: ResolvedToneSource,
        sample: ManifestSample,
    ) -> int | None:
        matched: int | None = None
        for number, group in enumerate(
            resolved.definition.exclusive_groups, start=1
        ):
            for member in group.members:
                if member.tone != tone.tone_id:
                    continue
                if (
                    member.root_note is not None
                    and member.root_note != sample.mapping.root_note
                ):
                    continue
                if matched is not None and matched != number:
                    raise ExportDefinitionError(
                        f"{resolved.definition_path}: sample "
                        f"{sample.file!r} of tone {tone.tone_id!r} belongs "
                        f"to more than one exclusive group"
                    )
                matched = number
        return matched
