from midi_sampling.postprocess.definitions import (
    LoopStageDefinition,
    StageDefinition,
    TrimStageDefinition,
)
from midi_sampling.postprocess.exceptions import PostprocessDefinitionError

from .stage import PostprocessStage, StageContext, StageOutcome
from .trim_stage import TrimStage
from .loop_stage import LoopStage


def create_stage(definition: StageDefinition) -> PostprocessStage:
    """
    Build one stage adapter from its definition.

    This resolves every omitted setting against the DSP package default,
    so it is also the point where a missing optional dependency is
    detected: pre-flight validation calls it before any file is touched.
    """
    if isinstance(definition, TrimStageDefinition):
        return TrimStage.create(definition.settings)
    if isinstance(definition, LoopStageDefinition):
        return LoopStage.create(definition.settings, definition.on_failure)
    raise PostprocessDefinitionError(f"unknown stage kind: {definition.kind!r}")


def create_stages(definitions: list[StageDefinition]) -> tuple[PostprocessStage, ...]:
    return tuple(create_stage(definition) for definition in definitions)


__all__ = [
    "LoopStage",
    "PostprocessStage",
    "StageContext",
    "StageOutcome",
    "TrimStage",
    "create_stage",
    "create_stages",
]
