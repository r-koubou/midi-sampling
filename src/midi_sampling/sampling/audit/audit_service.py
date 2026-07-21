from logging import getLogger

from midi_sampling.sampling.audit.audit_result import (
    SessionAuditResult,
    ToneAuditResult,
    ToneAuditStatus,
)
from midi_sampling.sampling.exceptions import ManifestReadError
from midi_sampling.sampling.manifest import SampleManifestRepository
from midi_sampling.sampling.planning import SamplingPlan, TonePlan

logger = getLogger(__name__)


class AuditService:
    """
    Compare the current resolved definitions against existing manifests
    and WAV files.

    Strictly read-only: never opens MIDI or audio devices and never
    creates, updates or deletes any file.
    """

    def __init__(
        self, manifest_repository: SampleManifestRepository | None = None
    ) -> None:
        self._manifest_repository = (
            manifest_repository
            if manifest_repository is not None
            else SampleManifestRepository()
        )

    def audit(self, plan: SamplingPlan) -> SessionAuditResult:
        results = tuple(self._audit_tone(tone) for tone in plan.tones)
        return SessionAuditResult(tones=results)

    def _audit_tone(self, tone: TonePlan) -> ToneAuditResult:
        planned_sample_count = len(tone.targets)

        def result(
            status: ToneAuditStatus,
            existing_hash: str | None = None,
            missing_files: tuple[str, ...] = (),
            detail: str | None = None,
        ) -> ToneAuditResult:
            logger.info(f"Audit: {tone.definition_id}: {status.value}")
            return ToneAuditResult(
                definition_id=tone.definition_id,
                status=status,
                planned_sample_count=planned_sample_count,
                current_hash=tone.resolved_definition_sha256,
                existing_hash=existing_hash,
                missing_files=missing_files,
                detail=detail,
            )

        if not tone.directory.is_dir() or not tone.manifest_path.is_file():
            return result(ToneAuditStatus.MISSING)

        try:
            manifest = self._manifest_repository.read(tone.manifest_path)
        except ManifestReadError as e:
            return result(ToneAuditStatus.INVALID_MANIFEST, detail=str(e))

        existing_hash = manifest.provenance.resolved_definition_sha256

        if existing_hash != tone.resolved_definition_sha256:
            return result(
                ToneAuditStatus.DEFINITION_CHANGED, existing_hash=existing_hash
            )

        if manifest.status != "completed":
            return result(
                ToneAuditStatus.INCOMPLETE,
                existing_hash=existing_hash,
                detail=f"manifest status is {manifest.status!r}",
            )

        missing_files = tuple(
            sample.file
            for sample in manifest.samples
            if not (tone.directory / sample.file).is_file()
        )
        if missing_files:
            return result(
                ToneAuditStatus.MISSING_SAMPLES,
                existing_hash=existing_hash,
                missing_files=missing_files,
            )

        return result(ToneAuditStatus.UP_TO_DATE, existing_hash=existing_hash)
