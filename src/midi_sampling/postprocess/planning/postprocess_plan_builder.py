from logging import getLogger

from midi_sampling.postprocess.exceptions import (
    PostprocessDefinitionError,
    PostprocessSourceError,
)
from midi_sampling.postprocess.hashing import PostprocessSettingsHasher
from midi_sampling.postprocess.manifest.postprocess_manifest import (
    ManifestSampleMapping,
)
from midi_sampling.postprocess.planning.postprocess_plan import (
    MANIFEST_FILENAME,
    PostprocessPlan,
    TonePostprocessPlan,
)
from midi_sampling.postprocess.planning.postprocess_target import (
    WAV_SUFFIX,
    WORK_DIRECTORY_NAME,
    PostprocessTarget,
)
from midi_sampling.postprocess.resolving import (
    ResolvedPostprocessSession,
    ResolvedSourceTone,
)
from midi_sampling.postprocess.stages import PostprocessStage, create_stages
from midi_sampling.sampling.validation import OutputPathValidator

logger = getLogger(__name__)


class PostprocessPlanBuilder:
    """
    Turn a resolved postprocess session into a fully validated execution
    plan.

    Every output name and intermediate path is generated and validated
    here, before the first WAV is opened.
    """

    def __init__(
        self,
        settings_hasher: PostprocessSettingsHasher | None = None,
        output_path_validator: OutputPathValidator | None = None,
    ) -> None:
        self._settings_hasher = (
            settings_hasher
            if settings_hasher is not None
            else PostprocessSettingsHasher()
        )
        self._path_validator = (
            output_path_validator
            if output_path_validator is not None
            else OutputPathValidator()
        )

    def build(
        self,
        session: ResolvedPostprocessSession,
        stages: tuple[PostprocessStage, ...] | None = None,
    ) -> PostprocessPlan:
        """
        `stages` is injectable so that tests can plan without the
        optional DSP packages installed. When omitted the adapters are
        created here, which is also what detects a missing dependency
        during pre-flight.
        """
        if stages is None:
            stages = create_stages(list(session.stages))

        if not stages:
            raise PostprocessDefinitionError("at least one stage is required")

        settings_sha256 = self._settings_hasher.hash_settings(stages)
        logger.debug(
            f"Postprocess settings hash: {settings_sha256} "
            f"(stages: {', '.join(stage.kind for stage in stages)})"
        )

        tones = tuple(
            self._build_tone(session, tone) for tone in session.tones
        )

        return PostprocessPlan(
            session_path=session.session_path,
            source_root=session.source_root,
            output_root=session.output_root,
            stages=stages,
            settings_sha256=settings_sha256,
            tones=tones,
        )

    def _build_tone(
        self, session: ResolvedPostprocessSession, source: ResolvedSourceTone
    ) -> TonePostprocessPlan:
        manifest = source.manifest
        definition_id = source.definition_id

        self._path_validator.validate_component(
            definition_id, f"tone directory for {definition_id!r}"
        )

        directory = session.output_root / definition_id
        work_directory = directory / WORK_DIRECTORY_NAME
        manifest_path = directory / MANIFEST_FILENAME

        targets: list[PostprocessTarget] = []
        seen_names: set[str] = set()

        for sample in manifest.samples:
            file_name = sample.file
            context = f"{definition_id}: sample {sample.index}"

            if not file_name.lower().endswith(WAV_SUFFIX):
                raise PostprocessSourceError(
                    f"{context}: source file name must end with "
                    f"{WAV_SUFFIX!r}: {file_name!r}"
                )

            self._path_validator.validate_component(file_name, context)

            if file_name in seen_names:
                raise PostprocessSourceError(
                    f"{context}: duplicate output file name: {file_name!r}"
                )
            seen_names.add(file_name)

            target = PostprocessTarget(
                definition_id=definition_id,
                sample_index=sample.index,
                file_name=file_name,
                source_path=source.directory / file_name,
                output_path=directory / file_name,
                work_directory=work_directory,
                mapping=ManifestSampleMapping(
                    root_note=sample.mapping.root_note,
                    key_low=sample.mapping.key_low,
                    key_high=sample.mapping.key_high,
                    velocity_low=sample.mapping.velocity_low,
                    velocity_high=sample.mapping.velocity_high,
                ),
            )

            self._path_validator.validate_full_path(target.output_path, context)
            # Intermediate names are the longest ones, so validate the worst case.
            self._path_validator.validate_full_path(
                target.work_path(len(session.stages), "postprocess"), context
            )

            targets.append(target)

        if not targets:
            raise PostprocessSourceError(
                f"{source.manifest_path}: manifest contains no samples"
            )

        source_manifest_sha256 = self._settings_hasher.hash_source_manifest(
            source.manifest_path
        )

        logger.debug(
            f"Planned tone {definition_id!r}: {len(targets)} sample(s) "
            f"-> {directory}"
        )

        return TonePostprocessPlan(
            definition_id=definition_id,
            name=manifest.definition.name,
            source_directory=source.directory,
            source_manifest_path=source.manifest_path,
            source_manifest_sha256=source_manifest_sha256,
            resolved_definition_sha256=manifest.provenance.resolved_definition_sha256,
            midi=manifest.midi,
            audio=manifest.audio,
            naming=manifest.naming,
            resolved_definition=manifest.resolved_definition,
            directory=directory,
            manifest_path=manifest_path,
            work_directory=work_directory,
            targets=tuple(targets),
        )
