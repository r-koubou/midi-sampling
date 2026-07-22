import hashlib
from pathlib import Path

from midi_sampling.sampling.audit import AuditService, ToneAuditStatus
from midi_sampling.sampling.exceptions import SamplingError

from conftest import (
    DEFAULT_ZONES_YAML,
    FakeAudioDevice,
    FakeMidiDevice,
    build_plan,
    make_session,
)
from midi_sampling.sampling import SamplingExecutor

service = AuditService()


def run_sampling(plan) -> None:
    executor = SamplingExecutor(
        audio_device=FakeAudioDevice(),
        midi_device=FakeMidiDevice(),
        sleep=lambda seconds: None,
    )
    executor.execute(plan)


def snapshot_tree(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


class TestAuditStatuses:
    def test_missing_when_nothing_recorded(self, plan):
        result = service.audit(plan)
        assert result.tones[0].status is ToneAuditStatus.MISSING
        assert not result.all_up_to_date
        assert result.resampling_required_count == 1

    def test_up_to_date_after_successful_run(self, plan):
        run_sampling(plan)
        result = service.audit(plan)
        tone = result.tones[0]
        assert tone.status is ToneAuditStatus.UP_TO_DATE
        assert tone.planned_sample_count == 4
        assert tone.existing_hash == tone.current_hash
        assert result.all_up_to_date
        assert result.up_to_date_count == 1

    def test_definition_changed(self, tmp_path):
        session_path = make_session(tmp_path)
        run_sampling(build_plan(session_path))

        changed_zones = DEFAULT_ZONES_YAML.replace("high: 40", "high: 39")
        (tmp_path / "presets" / "zones.yaml").write_text(
            changed_zones, encoding="utf-8"
        )
        changed_plan = build_plan(session_path)

        result = service.audit(changed_plan)
        tone = result.tones[0]
        assert tone.status is ToneAuditStatus.DEFINITION_CHANGED
        assert tone.existing_hash is not None
        assert tone.existing_hash != tone.current_hash

    def test_incomplete_when_run_failed(self, plan):
        executor = SamplingExecutor(
            audio_device=FakeAudioDevice(fail_on_export_index=1),
            midi_device=FakeMidiDevice(),
            sleep=lambda seconds: None,
        )
        try:
            executor.execute(plan)
        except SamplingError:
            pass

        result = service.audit(plan)
        assert result.tones[0].status is ToneAuditStatus.INCOMPLETE

    def test_missing_samples(self, plan):
        run_sampling(plan)
        deleted = plan.tones[0].targets[2].output_path
        deleted.unlink()

        result = service.audit(plan)
        tone = result.tones[0]
        assert tone.status is ToneAuditStatus.MISSING_SAMPLES
        assert tone.missing_files == (deleted.name,)

    def test_invalid_manifest(self, plan):
        run_sampling(plan)
        plan.tones[0].manifest_path.write_text(
            "this is not a manifest\n", encoding="utf-8"
        )
        result = service.audit(plan)
        assert result.tones[0].status is ToneAuditStatus.INVALID_MANIFEST


class TestAuditIsReadOnly:
    def test_audit_does_not_modify_files(self, plan, tmp_path):
        run_sampling(plan)
        before = snapshot_tree(tmp_path)
        service.audit(plan)
        after = snapshot_tree(tmp_path)
        assert before == after

    def test_audit_on_missing_output_creates_nothing(self, plan):
        service.audit(plan)
        assert not plan.output_root.exists()
