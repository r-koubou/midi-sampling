from dataclasses import dataclass, field
from enum import Enum


class ToneAuditStatus(Enum):
    """
    Audit status of one tone. Everything except UP_TO_DATE means the
    tone needs to be resampled (INVALID_MANIFEST may also warrant manual
    inspection).
    """
    UP_TO_DATE = "up_to_date"
    MISSING = "missing"
    DEFINITION_CHANGED = "definition_changed"
    INCOMPLETE = "incomplete"
    MISSING_SAMPLES = "missing_samples"
    INVALID_MANIFEST = "invalid_manifest"

    @property
    def needs_resampling(self) -> bool:
        return self is not ToneAuditStatus.UP_TO_DATE


@dataclass(frozen=True)
class ToneAuditResult:
    definition_id: str
    status: ToneAuditStatus
    planned_sample_count: int
    current_hash: str
    existing_hash: str | None = None
    missing_files: tuple[str, ...] = ()
    detail: str | None = None

    @property
    def needs_resampling(self) -> bool:
        return self.status.needs_resampling


@dataclass(frozen=True)
class SessionAuditResult:
    """
    Machine-readable audit result for a whole session. Structured so a
    JSON output format can be added later without reshaping the model.
    """
    tones: tuple[ToneAuditResult, ...] = field(default_factory=tuple)

    @property
    def up_to_date_count(self) -> int:
        return sum(1 for tone in self.tones if not tone.needs_resampling)

    @property
    def resampling_required_count(self) -> int:
        return sum(1 for tone in self.tones if tone.needs_resampling)

    @property
    def all_up_to_date(self) -> bool:
        return self.resampling_required_count == 0
