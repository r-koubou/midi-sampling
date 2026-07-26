from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

from midi_sampling.postprocess.definitions.loop_stage_definition import (
    LoopStageDefinition,
)
from midi_sampling.postprocess.definitions.trim_stage_definition import (
    TrimStageDefinition,
)

StageDefinition = Annotated[
    TrimStageDefinition | LoopStageDefinition,
    Field(discriminator="kind"),
]


class SourceDefinition(BaseModel):
    """
    Location of the sampling output used as input. Read only: nothing
    below this directory is ever modified.
    """
    model_config = ConfigDict(extra="forbid")

    directory: StrictStr


class OutputDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: StrictStr


class PostprocessSessionDefinition(BaseModel):
    """
    Postprocess session definition file. (kind: postprocess_session)

    This is the only file a user writes by hand; the derived manifest is
    generated entirely by the program.
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["postprocess_session"]

    source: SourceDefinition
    output: OutputDefinition
    stages: list[StageDefinition] = Field(min_length=1)
    tones: list[StrictStr] | None = None

    @model_validator(mode="after")
    def _reject_duplicate_stage_kinds(self) -> "PostprocessSessionDefinition":
        seen: set[str] = set()
        for stage in self.stages:
            if stage.kind in seen:
                raise ValueError(f"duplicate stage kind: {stage.kind!r}")
            seen.add(stage.kind)
        return self

    @model_validator(mode="after")
    def _reject_duplicate_tones(self) -> "PostprocessSessionDefinition":
        if self.tones is None:
            return self
        if len(self.tones) == 0:
            raise ValueError("tones must not be an empty list; omit it to select all")
        seen: set[str] = set()
        for tone_id in self.tones:
            if tone_id in seen:
                raise ValueError(f"duplicate tone id: {tone_id!r}")
            seen.add(tone_id)
        return self
