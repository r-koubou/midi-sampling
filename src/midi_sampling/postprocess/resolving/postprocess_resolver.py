from dataclasses import dataclass
from logging import getLogger
from pathlib import Path, PurePosixPath, PureWindowsPath

from midi_sampling.postprocess.definitions import (
    PostprocessSessionDefinition,
    StageDefinition,
)
from midi_sampling.postprocess.exceptions import (
    PostprocessDefinitionError,
    PostprocessSourceError,
)
from midi_sampling.sampling.exceptions import ManifestReadError
from midi_sampling.sampling.loading import YamlDefinitionLoader
from midi_sampling.sampling.manifest import SampleManifest, SampleManifestRepository

logger = getLogger(__name__)

MANIFEST_FILENAME = "manifest.yaml"


@dataclass(frozen=True)
class ResolvedSourceTone:
    """
    One tone of the sampling output, ready to be post-processed.
    """
    definition_id: str
    directory: Path
    manifest_path: Path
    manifest: SampleManifest


@dataclass(frozen=True)
class ResolvedPostprocessSession:
    """
    A fully resolved postprocess session. The planning and execution
    stages never have to touch YAML files again.
    """
    session_path: Path
    source_root: Path
    output_root: Path
    stages: tuple[StageDefinition, ...]
    tones: tuple[ResolvedSourceTone, ...]


class PostprocessResolver:
    """
    Resolve a postprocess session file into a ResolvedPostprocessSession.

    Strictly read-only with respect to the sampling output: it opens
    source manifests to validate them and never writes anything.
    """

    def __init__(
        self,
        loader: YamlDefinitionLoader | None = None,
        manifest_repository: SampleManifestRepository | None = None,
    ) -> None:
        self._loader = loader if loader is not None else YamlDefinitionLoader()
        self._manifest_repository = (
            manifest_repository
            if manifest_repository is not None
            else SampleManifestRepository()
        )

    def resolve(self, session_path: Path) -> ResolvedPostprocessSession:
        session_path = Path(session_path)
        if not session_path.is_file():
            raise PostprocessDefinitionError(
                f"postprocess session file not found: {session_path}"
            )
        session_path = session_path.resolve()
        session_dir = session_path.parent

        try:
            session = self._loader.load(session_path, PostprocessSessionDefinition)
        except Exception as e:
            raise PostprocessDefinitionError(str(e)) from e

        logger.info(f"Loaded postprocess session definition: {session_path}")

        source_root = self._resolve_directory(
            session_dir, session.source.directory, f"{session_path}: source.directory"
        )
        output_root = self._resolve_directory(
            session_dir, session.output.directory, f"{session_path}: output.directory"
        )

        if not source_root.is_dir():
            raise PostprocessSourceError(
                f"{session_path}: source directory not found: {source_root}"
            )
        if source_root == output_root:
            raise PostprocessDefinitionError(
                f"{session_path}: output.directory must differ from "
                f"source.directory ({source_root}); postprocessing never "
                f"modifies the recorded output in place"
            )

        tone_ids = self._select_tone_ids(session, source_root, session_path)
        tones = tuple(
            self._resolve_tone(source_root, tone_id) for tone_id in tone_ids
        )

        logger.info(
            f"Resolved {len(tones)} tone(s), "
            f"{sum(len(tone.manifest.samples) for tone in tones)} sample(s)"
        )

        return ResolvedPostprocessSession(
            session_path=session_path,
            source_root=source_root,
            output_root=output_root,
            stages=tuple(session.stages),
            tones=tones,
        )

    def _select_tone_ids(
        self,
        session: PostprocessSessionDefinition,
        source_root: Path,
        session_path: Path,
    ) -> tuple[str, ...]:
        if session.tones is not None:
            missing = [
                tone_id
                for tone_id in session.tones
                if not (source_root / tone_id).is_dir()
            ]
            if missing:
                raise PostprocessSourceError(
                    f"{session_path}: tone(s) not found under {source_root}: "
                    + ", ".join(repr(tone_id) for tone_id in missing)
                )
            return tuple(sorted(session.tones))

        discovered = sorted(
            entry.name
            for entry in source_root.iterdir()
            if entry.is_dir() and (entry / MANIFEST_FILENAME).is_file()
        )
        if not discovered:
            raise PostprocessSourceError(
                f"{session_path}: no tone directory containing "
                f"{MANIFEST_FILENAME} found under {source_root}"
            )
        return tuple(discovered)

    def _resolve_tone(self, source_root: Path, tone_id: str) -> ResolvedSourceTone:
        directory = source_root / tone_id
        manifest_path = directory / MANIFEST_FILENAME

        if not manifest_path.is_file():
            raise PostprocessSourceError(
                f"{directory}: {MANIFEST_FILENAME} not found"
            )

        try:
            manifest = self._manifest_repository.read(manifest_path)
        except ManifestReadError as e:
            raise PostprocessSourceError(str(e)) from e

        if manifest.definition.id != tone_id:
            raise PostprocessSourceError(
                f"{manifest_path}: manifest definition id "
                f"{manifest.definition.id!r} does not match the directory "
                f"name {tone_id!r}"
            )

        if manifest.status != "completed":
            raise PostprocessSourceError(
                f"{manifest_path}: source manifest status is "
                f"{manifest.status!r}; only 'completed' sampling output can "
                f"be post-processed"
            )

        missing = [
            sample.file
            for sample in manifest.samples
            if not (directory / sample.file).is_file()
        ]
        if missing:
            raise PostprocessSourceError(
                f"{directory}: source WAV file(s) missing: "
                + ", ".join(missing)
            )

        logger.debug(
            f"Resolved source tone {tone_id!r}: {len(manifest.samples)} sample(s)"
        )

        return ResolvedSourceTone(
            definition_id=tone_id,
            directory=directory,
            manifest_path=manifest_path,
            manifest=manifest,
        )

    def _resolve_directory(self, base_dir: Path, raw: str, context: str) -> Path:
        """
        Resolve a directory reference. Non-strict on purpose: the output
        root does not exist yet on the first run.
        """
        self._reject_unsupported_reference(raw, context)
        return (base_dir / raw).resolve()

    def _reject_unsupported_reference(self, raw: str, context: str) -> None:
        """
        Same reference rules as the sampling definitions: relative paths
        only, no URL, no `~`, no glob, no absolute paths.
        """
        if raw == "":
            raise PostprocessDefinitionError(
                f"{context}: directory must not be empty"
            )
        if "://" in raw:
            raise PostprocessDefinitionError(
                f"{context}: URL references are not allowed: {raw!r}"
            )
        if raw.startswith("~"):
            raise PostprocessDefinitionError(
                f"{context}: '~' expansion is not allowed: {raw!r}"
            )
        if any(character in raw for character in "*?["):
            raise PostprocessDefinitionError(
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
            raise PostprocessDefinitionError(
                f"{context}: absolute paths are not allowed: {raw!r}"
            )
