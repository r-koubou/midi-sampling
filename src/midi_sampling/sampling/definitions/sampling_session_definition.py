from pydantic import BaseModel, ConfigDict, Field, StrictStr
from typing import Literal

from midi_sampling.sampling.definitions.field_types import MidiChannel, Seconds

DEFAULT_SAMPLE_FILENAME_TEMPLATE = (
    "r{root_note:03d}"
    "__k{key_low:03d}-{key_high:03d}"
    "__v{velocity_low:03d}-{velocity_high:03d}"
    "__s{send_velocity:03d}"
)


class FileReference(BaseModel):
    """
    Reference to an external file, relative to the referencing YAML file.
    """
    model_config = ConfigDict(extra="forbid")

    file: StrictStr


class SessionMidiDefinition(BaseModel):
    """
    Session wide MIDI settings.

    - channel is shared by all tones in the session.
    - initialization_files are sent once, in order, at session start.
    """
    model_config = ConfigDict(extra="forbid")

    channel: MidiChannel
    initialization_files: list[StrictStr] = Field(default_factory=list)


class SessionTimingDefinition(BaseModel):
    """
    Session wide timing in seconds.

    - program_change_settle: wait after Bank Select / Program Change.
    - pre_roll:              recorded seconds before Note On.
    - inter_sample_wait:     non-recorded wait between samples.
    """
    model_config = ConfigDict(extra="forbid")

    program_change_settle: Seconds
    pre_roll: Seconds
    inter_sample_wait: Seconds


class OutputNamingDefinition(BaseModel):
    """
    Optional sample filename template override. The extension is never
    part of the template; `.wav` is appended by the program.
    """
    model_config = ConfigDict(extra="forbid")

    sample_filename: StrictStr | None = None


class OutputDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: StrictStr
    naming: OutputNamingDefinition | None = None


class SamplingSessionDefinition(BaseModel):
    """
    Sampling session definition file. (kind: sampling_session)
    """
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    kind: Literal["sampling_session"]

    audio_device: FileReference
    midi_device: FileReference
    midi: SessionMidiDefinition
    timing: SessionTimingDefinition
    output: OutputDefinition
    definitions: list[FileReference] = Field(min_length=1)

    def sample_filename_template(self) -> str:
        """
        Return the effective sample filename template.
        """
        if self.output.naming is not None and self.output.naming.sample_filename is not None:
            return self.output.naming.sample_filename
        return DEFAULT_SAMPLE_FILENAME_TEMPLATE
