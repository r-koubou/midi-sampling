from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SamplingTarget:
    """
    One WAV to record. Fully resolved: no YAML structures and no external
    references are held here.
    """
    definition_id: str
    sample_index: int
    root_note: int
    key_low: int
    key_high: int
    velocity_low: int
    velocity_high: int
    send_velocity: int
    note_on: float
    release_capture: float
    file_name: str
    output_path: Path
