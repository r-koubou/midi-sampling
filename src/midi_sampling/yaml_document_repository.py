import os
from logging import getLogger
from pathlib import Path
from typing import Generic, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from midi_sampling.exceptions import MidiSamplingError

logger = getLogger(__name__)

TEMP_SUFFIX = ".tmp"

TDocument = TypeVar("TDocument", bound=BaseModel)


class YamlDocumentRepository(Generic[TDocument]):
    """
    Read and write a single kind of generated YAML document.

    Writes always go through a temporary file in the same directory and
    are finalized with an atomic replace, so an existing document is
    never left half-written.

    Subclasses bind the document type and the error types to raise.
    """

    document_type: type[TDocument]
    read_error: type[MidiSamplingError]
    write_error: type[MidiSamplingError]
    description: str = "document"

    def read(self, path: Path) -> TDocument:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except OSError as e:
            raise self.read_error(
                f"{path}: cannot read {self.description}: {e}"
            ) from e
        except UnicodeDecodeError as e:
            raise self.read_error(
                f"{path}: {self.description} is not valid UTF-8: {e}"
            ) from e
        except yaml.YAMLError as e:
            raise self.read_error(
                f"{path}: {self.description} is not valid YAML: {e}"
            ) from e

        if not isinstance(data, dict):
            raise self.read_error(
                f"{path}: {self.description} must be a YAML mapping, "
                f"got {type(data).__name__}"
            )

        try:
            return self.document_type.model_validate(data)
        except ValidationError as e:
            raise self.read_error(
                f"{path}: {self.description} schema validation failed:\n{e}"
            ) from e

    def write(self, path: Path, document: TDocument) -> None:
        temporary_path = path.with_name(path.name + TEMP_SUFFIX)
        data = document.model_dump(mode="python", exclude_none=True)

        try:
            with open(temporary_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                )
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, path)
        except (OSError, yaml.YAMLError) as e:
            raise self.write_error(
                f"{path}: cannot write {self.description}: {e}"
            ) from e

        status = getattr(document, "status", None)
        logger.debug(
            f"Updated {self.description}: {path}"
            + (f" (status={status})" if status is not None else "")
        )
