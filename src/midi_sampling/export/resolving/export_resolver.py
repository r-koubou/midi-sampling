from dataclasses import dataclass
from logging import getLogger
from pathlib import Path, PurePosixPath, PureWindowsPath

from midi_sampling.export.audio import resolve_flac_bit_depth
from midi_sampling.export.definitions import InstrumentDefinition, SourceReference
from midi_sampling.export.exceptions import (
    ExportDefinitionError,
    ExportSourceError,
)
from midi_sampling.postprocess.exceptions import PostprocessError
from midi_sampling.postprocess.manifest import (
    PostprocessManifest,
    PostprocessManifestRepository,
)
from midi_sampling.sampling.loading import YamlDefinitionLoader

logger = getLogger(__name__)


@dataclass(frozen=True)
class ResolvedToneSource:
    """
    One completed tone of the postprocess output, validated and ready to
    be exported. Strictly read-only input.
    """
    tone_id: str
    directory: Path
    manifest_path: Path
    manifest: PostprocessManifest


@dataclass(frozen=True)
class ResolvedInstrument:
    """
    A fully resolved instrument definition. Planning and execution never
    have to touch YAML files again.
    """
    definition_path: Path
    definition: InstrumentDefinition
    tones: tuple[ResolvedToneSource, ...]


class ExportResolver:
    """
    Resolve an instrument definition file into a ResolvedInstrument.

    Only postprocess manifests are accepted as sources: a tone that
    skipped postprocessing has no loop or frame data, so it must be run
    through a (possibly trim/loop-free) postprocess session first.
    """

    def __init__(
        self,
        loader: YamlDefinitionLoader | None = None,
        manifest_repository: PostprocessManifestRepository | None = None,
    ) -> None:
        self._loader = loader if loader is not None else YamlDefinitionLoader()
        self._manifest_repository = (
            manifest_repository
            if manifest_repository is not None
            else PostprocessManifestRepository()
        )

    def resolve(self, definition_path: Path) -> ResolvedInstrument:
        definition_path = Path(definition_path)
        if not definition_path.is_file():
            raise ExportDefinitionError(
                f"instrument definition file not found: {definition_path}"
            )
        definition_path = definition_path.resolve()
        definition_dir = definition_path.parent

        try:
            definition = self._loader.load(definition_path, InstrumentDefinition)
        except Exception as e:
            raise ExportDefinitionError(str(e)) from e

        logger.info(f"Loaded instrument definition: {definition_path}")

        tones = []
        seen_manifest_paths: dict[Path, str] = {}
        for source in definition.sources:
            tone = self._resolve_tone(definition_path, definition_dir, source)
            previous = seen_manifest_paths.get(tone.manifest_path)
            if previous is not None:
                raise ExportDefinitionError(
                    f"{definition_path}: sources {previous!r} and "
                    f"{source.tone!r} reference the same manifest: "
                    f"{tone.manifest_path}"
                )
            seen_manifest_paths[tone.manifest_path] = source.tone
            tones.append(tone)

        resolved = ResolvedInstrument(
            definition_path=definition_path,
            definition=definition,
            tones=tuple(tones),
        )
        self._validate_exclusive_group_notes(resolved)
        self._validate_flac_bit_depths(resolved)

        logger.info(
            f"Resolved {len(tones)} tone(s), "
            f"{sum(len(tone.manifest.samples) for tone in resolved.tones)} sample(s)"
        )
        return resolved

    def _resolve_tone(
        self, definition_path: Path, definition_dir: Path, source: SourceReference
    ) -> ResolvedToneSource:
        context = f"{definition_path}: sources[{source.tone!r}].manifest"
        self._reject_unsupported_reference(source.manifest, context)

        manifest_path = (definition_dir / source.manifest).resolve()
        if not manifest_path.is_file():
            raise ExportSourceError(
                f"{context}: manifest not found: {manifest_path}"
            )

        try:
            manifest = self._manifest_repository.read(manifest_path)
        except PostprocessError as e:
            raise ExportSourceError(str(e)) from e

        if manifest.definition.id != source.tone:
            raise ExportSourceError(
                f"{manifest_path}: manifest definition id "
                f"{manifest.definition.id!r} does not match the declared "
                f"tone {source.tone!r}"
            )

        if manifest.status != "completed":
            raise ExportSourceError(
                f"{manifest_path}: manifest status is {manifest.status!r}; "
                f"only 'completed' postprocess output can be exported"
            )

        incomplete = [
            sample.file
            for sample in manifest.samples
            if sample.status != "completed"
        ]
        if incomplete:
            raise ExportSourceError(
                f"{manifest_path}: sample(s) not completed: "
                + ", ".join(incomplete)
            )

        directory = manifest_path.parent
        missing = [
            sample.file
            for sample in manifest.samples
            if not (directory / sample.file).is_file()
        ]
        if missing:
            raise ExportSourceError(
                f"{directory}: audio file(s) missing: " + ", ".join(missing)
            )

        logger.debug(
            f"Resolved tone {source.tone!r}: {len(manifest.samples)} sample(s)"
        )

        return ResolvedToneSource(
            tone_id=source.tone,
            directory=directory,
            manifest_path=manifest_path,
            manifest=manifest,
        )

    def _validate_exclusive_group_notes(self, resolved: ResolvedInstrument) -> None:
        """
        Every explicit member root_note must exist in the referenced
        tone's mapping; a silently empty choke member is always a
        definition mistake.
        """
        notes_by_tone = {
            tone.tone_id: {
                sample.mapping.root_note for sample in tone.manifest.samples
            }
            for tone in resolved.tones
        }
        for group in resolved.definition.exclusive_groups:
            for member in group.members:
                if member.root_note is None:
                    continue
                if member.root_note not in notes_by_tone[member.tone]:
                    raise ExportDefinitionError(
                        f"{resolved.definition_path}: exclusive group "
                        f"{group.name!r} references root_note "
                        f"{member.root_note} which no sample of tone "
                        f"{member.tone!r} has"
                    )

    def _validate_flac_bit_depths(self, resolved: ResolvedInstrument) -> None:
        """
        Fail during resolution, before any file is written, when a FLAC
        export would need an implicit bit depth reduction.
        """
        audio = resolved.definition.audio
        if audio.format != "flac":
            return
        for tone in resolved.tones:
            try:
                resolve_flac_bit_depth(
                    tone.manifest.audio.data_format, audio.bit_depth
                )
            except ExportDefinitionError as e:
                raise ExportDefinitionError(
                    f"{resolved.definition_path}: tone {tone.tone_id!r}: {e}"
                ) from e

    def _reject_unsupported_reference(self, raw: str, context: str) -> None:
        """
        Same reference rules as the sampling and postprocess definitions:
        relative paths only, no URL, no `~`, no glob, no absolute paths.
        """
        if raw == "":
            raise ExportDefinitionError(f"{context}: path must not be empty")
        if "://" in raw:
            raise ExportDefinitionError(
                f"{context}: URL references are not allowed: {raw!r}"
            )
        if raw.startswith("~"):
            raise ExportDefinitionError(
                f"{context}: '~' expansion is not allowed: {raw!r}"
            )
        if any(character in raw for character in "*?["):
            raise ExportDefinitionError(
                f"{context}: glob patterns are not allowed: {raw!r}"
            )

        windows_path = PureWindowsPath(raw)
        posix_path = PurePosixPath(raw)
        if (
            windows_path.is_absolute()
            or posix_path.is_absolute()
            or windows_path.drive != ""
            or windows_path.root != ""
            or posix_path.root != ""
        ):
            raise ExportDefinitionError(
                f"{context}: absolute paths are not allowed: {raw!r}"
            )
