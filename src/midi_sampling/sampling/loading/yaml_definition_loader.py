from logging import getLogger
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from midi_sampling.sampling.exceptions import (
    DefinitionLoadError,
    DefinitionValidationError,
)

logger = getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)


class YamlDefinitionLoader:
    """
    Load a YAML definition file and validate it against a pydantic model.

    - Reads the file as UTF-8.
    - Uses yaml.safe_load only. Custom YAML tags are rejected.
    - Converts syntax errors into DefinitionLoadError with file path and
      position information.
    - Converts pydantic validation errors into DefinitionValidationError.
    """

    def load(self, file_path: Path, model_type: type[TModel]) -> TModel:
        data = self.load_raw(file_path)
        return self.validate(file_path, data, model_type)

    def load_raw(self, file_path: Path) -> dict:
        """
        Load a YAML file and return its top-level mapping without model
        validation.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except OSError as e:
            raise DefinitionLoadError(f"{file_path}: cannot read file: {e}") from e
        except UnicodeDecodeError as e:
            raise DefinitionLoadError(f"{file_path}: file is not valid UTF-8: {e}") from e
        except yaml.YAMLError as e:
            location = ""
            mark = getattr(e, "problem_mark", None)
            if mark is not None:
                location = f" (line {mark.line + 1}, column {mark.column + 1})"
            raise DefinitionLoadError(
                f"{file_path}: YAML syntax error{location}: {e}"
            ) from e

        if not isinstance(data, dict):
            raise DefinitionLoadError(
                f"{file_path}: top-level YAML structure must be a mapping, "
                f"got {type(data).__name__}"
            )

        return data

    def validate(
        self, file_path: Path, data: dict, model_type: type[TModel]
    ) -> TModel:
        """
        Validate an already loaded YAML mapping against a pydantic model.
        """
        try:
            model = model_type.model_validate(data)
        except ValidationError as e:
            raise DefinitionValidationError(
                f"{file_path}: definition validation failed:\n{e}"
            ) from e

        logger.debug(f"Loaded definition: {file_path} as {model_type.__name__}")
        return model
