import string
from collections.abc import Mapping

from midi_sampling.sampling.exceptions import InvalidFilenameTemplateError

ALLOWED_PLACEHOLDERS = frozenset(
    {
        "definition_id",
        "bank_msb",
        "bank_lsb",
        "program",
        "root_note",
        "key_low",
        "key_high",
        "velocity_low",
        "velocity_high",
        "send_velocity",
        "sample_index",
    }
)


class SampleFilenameFormatter:
    """
    Safe, restricted filename formatter.

    Only a fixed set of placeholders is allowed. Attribute access, index
    access, conversions (`!r` etc.), nested placeholders and therefore any
    arbitrary code execution are rejected. Untrusted templates are never
    passed to a bare str.format.
    """

    def __init__(self, template: str) -> None:
        self._template = template
        self._parsed = self._parse(template)

    @property
    def template(self) -> str:
        return self._template

    def _parse(self, template: str) -> list[tuple[str, str | None, str]]:
        if template == "":
            raise InvalidFilenameTemplateError("filename template must not be empty")

        parsed: list[tuple[str, str | None, str]] = []
        try:
            fields = list(string.Formatter().parse(template))
        except ValueError as e:
            raise InvalidFilenameTemplateError(
                f"malformed filename template {template!r}: {e}"
            ) from e

        for literal, field_name, format_spec, conversion in fields:
            if field_name is None:
                parsed.append((literal, None, ""))
                continue

            if conversion is not None:
                raise InvalidFilenameTemplateError(
                    f"conversion {'!' + conversion!r} is not allowed "
                    f"in filename template {template!r}"
                )
            if field_name == "":
                raise InvalidFilenameTemplateError(
                    f"positional placeholders are not allowed "
                    f"in filename template {template!r}"
                )
            if "." in field_name or "[" in field_name:
                raise InvalidFilenameTemplateError(
                    f"attribute or index access is not allowed "
                    f"in filename template {template!r}: {field_name!r}"
                )
            if field_name not in ALLOWED_PLACEHOLDERS:
                raise InvalidFilenameTemplateError(
                    f"unknown placeholder {field_name!r} "
                    f"in filename template {template!r}"
                )
            if format_spec is not None and "{" in format_spec:
                raise InvalidFilenameTemplateError(
                    f"nested placeholders are not allowed "
                    f"in filename template {template!r}"
                )

            parsed.append((literal, field_name, format_spec or ""))

        return parsed

    def format(self, values: Mapping[str, int | str]) -> str:
        """
        Format the template with the given placeholder values.
        The result does not include a file extension.
        """
        parts: list[str] = []
        for literal, field_name, format_spec in self._parsed:
            parts.append(literal)
            if field_name is None:
                continue
            try:
                parts.append(format(values[field_name], format_spec))
            except KeyError as e:
                raise InvalidFilenameTemplateError(
                    f"no value provided for placeholder {field_name!r}"
                ) from e
            except ValueError as e:
                raise InvalidFilenameTemplateError(
                    f"invalid format spec {format_spec!r} for placeholder "
                    f"{field_name!r}: {e}"
                ) from e

        return "".join(parts)
