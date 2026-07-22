from dataclasses import dataclass
from logging import getLogger
from pathlib import Path, PurePosixPath, PureWindowsPath

from midi_sampling.devices.audio.abstractions import (
    AudioDeviceInformation,
    AudioDeviceInformationLoader,
)
from midi_sampling.sampling.definitions import (
    SamplingDefinition,
    SamplingSessionDefinition,
    VelocityLayerDefinition,
    VelocityProfileDefinition,
    ZoneDefinition,
    ZoneLayoutDefinition,
)
from midi_sampling.sampling.exceptions import (
    DefinitionLoadError,
    DefinitionReferenceError,
    DuplicateDefinitionIdError,
)
from midi_sampling.sampling.loading import YamlDefinitionLoader
from midi_sampling.sampling.validation import SemanticValidator

logger = getLogger(__name__)


@dataclass(frozen=True)
class ResolvedTone:
    """
    A fully resolved tone definition. External references are already
    loaded, semantically validated and normalized.
    """
    id: str
    name: str | None
    bank_msb: int
    bank_lsb: int
    program: int
    zones: tuple[ZoneDefinition, ...]
    velocity_layers: tuple[VelocityLayerDefinition, ...]
    note_on: float
    release_capture: float
    source_path: Path


@dataclass(frozen=True)
class ResolvedSession:
    """
    A fully resolved sampling session. The execution stage never has to
    touch YAML files or file references again.
    """
    session_path: Path
    audio_device_file: Path
    midi_device_file: Path
    audio_information: AudioDeviceInformation
    channel: int
    initialization_files: tuple[Path, ...]
    program_change_settle: float
    pre_roll: float
    inter_sample_wait: float
    output_directory: Path
    sample_filename_template: str
    tones: tuple[ResolvedTone, ...]


class DefinitionResolver:
    """
    Resolve a sampling session file into a ResolvedSession.

    - Relative paths are resolved against the directory of the YAML file
      that contains the reference.
    - Absolute paths, URL, `~`, environment variables, glob patterns and
      re-references between presets are rejected.
    - The `kind` of every referenced definition file is verified.
    """

    def __init__(
        self,
        audio_information_loader: AudioDeviceInformationLoader,
        loader: YamlDefinitionLoader | None = None,
        semantic_validator: SemanticValidator | None = None,
    ) -> None:
        self._audio_information_loader = audio_information_loader
        self._loader = loader if loader is not None else YamlDefinitionLoader()
        self._semantic_validator = (
            semantic_validator if semantic_validator is not None else SemanticValidator()
        )

    def resolve(self, session_path: Path) -> ResolvedSession:
        session_path = Path(session_path)
        if not session_path.is_file():
            raise DefinitionLoadError(f"session file not found: {session_path}")
        session_path = session_path.resolve()
        session_dir = session_path.parent

        session = self._loader.load(session_path, SamplingSessionDefinition)
        logger.info(f"Loaded session definition: {session_path}")

        audio_device_file = self._resolve_reference(
            session_dir, session.audio_device.file, f"{session_path}: audio_device"
        )
        midi_device_file = self._resolve_reference(
            session_dir, session.midi_device.file, f"{session_path}: midi_device"
        )
        audio_information = self._load_audio_information(audio_device_file)

        initialization_files = tuple(
            self._resolve_reference(
                session_dir, raw, f"{session_path}: midi.initialization_files"
            )
            for raw in session.midi.initialization_files
        )

        tones: list[ResolvedTone] = []
        seen_ids: set[str] = set()
        for reference in session.definitions:
            definition_path = self._resolve_reference(
                session_dir, reference.file, f"{session_path}: definitions"
            )
            tone = self._resolve_tone(definition_path)
            if tone.id in seen_ids:
                raise DuplicateDefinitionIdError(
                    f"{session_path}: duplicate definition id: {tone.id!r}"
                )
            seen_ids.add(tone.id)
            tones.append(tone)

        output_directory = session_dir / session.output.directory

        return ResolvedSession(
            session_path=session_path,
            audio_device_file=audio_device_file,
            midi_device_file=midi_device_file,
            audio_information=audio_information,
            channel=session.midi.channel,
            initialization_files=initialization_files,
            program_change_settle=session.timing.program_change_settle,
            pre_roll=session.timing.pre_roll,
            inter_sample_wait=session.timing.inter_sample_wait,
            output_directory=output_directory,
            sample_filename_template=session.sample_filename_template(),
            tones=tuple(tones),
        )

    def _resolve_tone(self, definition_path: Path) -> ResolvedTone:
        definition_dir = definition_path.parent
        self._verify_kind(definition_path, "sampling_definition")
        definition = self._loader.load(definition_path, SamplingDefinition)

        if definition.zone_layout.file is not None:
            zone_file = self._resolve_reference(
                definition_dir,
                definition.zone_layout.file,
                f"{definition_path}: zone_layout",
            )
            self._verify_kind(zone_file, "zone_layout")
            layout = self._loader.load(zone_file, ZoneLayoutDefinition)
            zones = layout.zones
        else:
            zones = definition.zone_layout.zones

        if definition.velocity_profile.file is not None:
            velocity_file = self._resolve_reference(
                definition_dir,
                definition.velocity_profile.file,
                f"{definition_path}: velocity_profile",
            )
            self._verify_kind(velocity_file, "velocity_profile")
            profile = self._loader.load(velocity_file, VelocityProfileDefinition)
            layers = profile.layers
        else:
            layers = definition.velocity_profile.layers

        context = f"definition {definition.id!r}"
        normalized_zones = self._semantic_validator.normalize_zones(zones, context)
        normalized_layers = self._semantic_validator.normalize_velocity_layers(
            layers, context
        )

        logger.info(
            f"Resolved definition {definition.id!r}: "
            f"{len(normalized_zones)} zones, {len(normalized_layers)} velocity layers"
        )

        return ResolvedTone(
            id=definition.id,
            name=definition.name,
            bank_msb=definition.midi_program.bank_msb,
            bank_lsb=definition.midi_program.bank_lsb,
            program=definition.midi_program.program,
            zones=normalized_zones,
            velocity_layers=normalized_layers,
            note_on=definition.timing.note_on,
            release_capture=definition.timing.release_capture,
            source_path=definition_path,
        )

    def _load_audio_information(self, audio_device_file: Path) -> AudioDeviceInformation:
        try:
            return self._audio_information_loader.load(str(audio_device_file))
        except Exception as e:
            raise DefinitionLoadError(
                f"cannot load audio device information: {audio_device_file}: {e}"
            ) from e

    def _verify_kind(self, file_path: Path, expected_kind: str) -> None:
        data = self._loader.load_raw(file_path)
        actual_kind = data.get("kind")
        if actual_kind != expected_kind:
            raise DefinitionReferenceError(
                f"{file_path}: expected kind {expected_kind!r}, "
                f"got {actual_kind!r}"
            )

    def _resolve_reference(self, base_dir: Path, raw: str, context: str) -> Path:
        if raw == "":
            raise DefinitionReferenceError(f"{context}: file reference must not be empty")
        if "://" in raw:
            raise DefinitionReferenceError(
                f"{context}: URL references are not allowed: {raw!r}"
            )
        if raw.startswith("~"):
            raise DefinitionReferenceError(
                f"{context}: '~' expansion is not allowed: {raw!r}"
            )
        if any(character in raw for character in "*?["):
            raise DefinitionReferenceError(
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
            raise DefinitionReferenceError(
                f"{context}: absolute paths are not allowed: {raw!r}"
            )

        resolved = (base_dir / raw).resolve()
        if not resolved.is_file():
            raise DefinitionReferenceError(
                f"{context}: referenced file not found: {raw!r} "
                f"(resolved to {resolved})"
            )

        logger.debug(f"Resolved reference: {raw!r} -> {resolved}")
        return resolved
