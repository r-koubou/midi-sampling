from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from midi_sampling.postprocess.exceptions import PostprocessStageError

WAV_SUFFIX = ".wav"


@dataclass(frozen=True)
class StageContext:
    """
    Everything one stage needs to process a single sample.

    Both paths are guaranteed to end with `.wav`; see `validate()`.
    """
    input_path: Path
    output_path: Path
    root_note: int
    sample_rate: int
    channels: int

    def validate(self) -> None:
        """
        Guard the invariant that no path handed to an external DSP
        package ever carries a non-`.wav` extension.

        libsndfile infers the output format from the extension when
        writing, so a name like `foo.wav.part` fails to be recognized.
        This already broke the sampling stage once, and the fix there was
        to pass `format="WAV"` explicitly. Here we keep the extension
        correct instead of relying on each library's tolerance.
        """
        for label, path in (
            ("input", self.input_path),
            ("output", self.output_path),
        ):
            if path.suffix.lower() != WAV_SUFFIX:
                raise PostprocessStageError(
                    f"{label} path handed to a stage must end with "
                    f"{WAV_SUFFIX!r}: {path}"
                )


@dataclass(frozen=True)
class StageOutcome:
    """
    Result of applying one stage to one sample.

    `output_written` is False when the stage deliberately produced no new
    file (for example loop detection that found no acceptable loop while
    running with `on_failure: skip`). The executor then carries the input
    forward as this stage's effective output.
    """
    manifest_block: BaseModel
    output_written: bool


@runtime_checkable
class PostprocessStage(Protocol):
    """
    Adapter over one external DSP package.

    Implementations are the only place in this project allowed to import
    `wav_silence_trimmer` or `sample_loop_detector`, and they must do so
    lazily inside functions.
    """

    kind: str

    def settings_payload(self) -> dict:
        """
        Effective settings in canonical form, used for the settings hash.
        Omitted values must already be resolved to the DSP defaults so
        that the hash describes what actually ran.
        """
        ...

    def apply(self, context: StageContext) -> StageOutcome:
        """
        Process one sample. Must not modify `context.input_path`.
        """
        ...
