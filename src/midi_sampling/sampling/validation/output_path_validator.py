import os
import re
import sys
from pathlib import Path

from midi_sampling.sampling.exceptions import InvalidOutputPathError

WINDOWS_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

# Reject the Windows-invalid character set on every OS so that generated
# sample libraries stay portable across file systems.
_INVALID_CHARACTERS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

MAX_COMPONENT_LENGTH = 255
MAX_FULL_PATH_LENGTH = 259 if sys.platform == "win32" else 4095


class OutputPathValidator:
    """
    Fail-safe validation of generated output names and paths. All checks
    run before any MIDI message is sent or any device is opened.
    """

    def validate_component(self, name: str, context: str) -> None:
        """
        Validate a single path component (a directory name or a file name).
        """
        if name == "":
            raise InvalidOutputPathError(f"{context}: name must not be empty")

        match = _INVALID_CHARACTERS_PATTERN.search(name)
        if match is not None:
            raise InvalidOutputPathError(
                f"{context}: name contains invalid character "
                f"{match.group()!r}: {name!r}"
            )

        if name.endswith(" ") or name.endswith("."):
            raise InvalidOutputPathError(
                f"{context}: name must not end with a space or a period: {name!r}"
            )

        first_segment = name.split(".", 1)[0]
        if first_segment.upper() in WINDOWS_RESERVED_DEVICE_NAMES:
            raise InvalidOutputPathError(
                f"{context}: name collides with a Windows reserved device "
                f"name: {name!r}"
            )

        if len(name) > MAX_COMPONENT_LENGTH:
            raise InvalidOutputPathError(
                f"{context}: name is longer than {MAX_COMPONENT_LENGTH} "
                f"characters: {name!r}"
            )

    def validate_full_path(self, path: Path, context: str) -> None:
        """
        Validate the total length of an absolute output path.
        """
        text = str(path)
        if len(text) > MAX_FULL_PATH_LENGTH:
            raise InvalidOutputPathError(
                f"{context}: full path is longer than {MAX_FULL_PATH_LENGTH} "
                f"characters ({len(text)}): {text}"
            )

    def validate_output_root_creatable(self, output_root: Path) -> None:
        """
        Check that the output root either exists as a directory or can be
        created under its nearest existing ancestor.
        """
        current = output_root
        while not current.exists():
            parent = current.parent
            if parent == current:
                break
            current = parent

        if current.exists() and not current.is_dir():
            raise InvalidOutputPathError(
                f"output root is not creatable: {current} is not a directory"
            )

        if current.exists() and not os.access(current, os.W_OK):
            raise InvalidOutputPathError(
                f"output root is not creatable: no write permission on {current}"
            )
