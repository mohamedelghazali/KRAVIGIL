import uuid

import pytest
import subprocess

from backend.database.models.asset import Asset
from backend.database.models.observation import Observation
from backend.database.models.scan import Scan
from backend.database.models.target import Target
from backend.database.models.user import Organization
from backend.services.normalization.adapters.base import (
    BaseEngineAdapter,
    ScanCancelledError,
)
from workers.tasks import (
    _claim_scan,
    _complete_scan_if_running,
    _mark_scan_failed,
    _scan_cancel_requested,
)


class DummyAdapter(BaseEngineAdapter):
    def parse_output(self, raw_output):
        return []


class FakeProcess:
    def __init__(self, output=""):
        self.output = output
        self.returncode = None
        self.calls = 0
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def communicate(self, timeout=None):
        self.calls += 1
        if self.calls == 1 and self.returncode is None:
            raise subprocess.TimeoutExpired(["dummy-engine"], timeout)
        self.returncode = -15 if self.terminated else 0
        return self.output, ""

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True
        self.returncode = -9


def _create_scan(db_session, status="PENDING", task_id=None):
    tenant_id = uuid.uuid4()
    target_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    db_session.add(Organization(id=tenant_id, name=f"scan-lifecycle-{tenant_id}"))
    db_session.flush()
    db_session.add(
        Target(
            id=target_id,
            tenant_id=tenant_id,
            name="Scan lifecycle target",
            ip_address="192.0.2.190",
            is_authorized=True,
        )
    )
    db_session.flush()
    db_session.add(
        Asset(
            id=asset_id,
            tenant_id=tenant_id,
            target_id=target_id,
            ip_address="192.0.2.190",
        )
    )
    db_session.add(
        Scan(
            id=scan_id,
            tenant_id=tenant_id,
            target_id=target_id,
            asset_id=asset_id,
            status=status,
            task_id=task_id,
            scan_type="WEB",
        )
    )
    db_session.commit()
    return tenant_id, scan_id, asset_id


def test_claim_does_not_overwrite_a_cancelled_scan(db_session):
    tenant_id, scan_id, _ = _create_scan(db_session, status="CANCELLED")

    state = _claim_scan(db_session, tenant_id, scan_id, "celery-task-1")

    assert state == "CANCELLED"
    assert db_session.query(Scan).filter(Scan.id == scan_id).one().status == "CANCELLED"


def test_claim_is_idempotent_for_same_task_and_rejects_a_different_task(db_session):
    tenant_id, scan_id, _ = _create_scan(
        db_session, status="RUNNING", task_id="celery-task-1"
    )

    assert _claim_scan(db_session, tenant_id, scan_id, "celery-task-1") == "RUNNING"
    assert _claim_scan(db_session, tenant_id, scan_id, "celery-task-2") == "BUSY"


def test_completion_rolls_back_observations_if_cancellation_won(db_session):
    tenant_id, scan_id, asset_id = _create_scan(db_session, status="CANCELLED")
    db_session.add(
        Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="WEB_FINDING",
            raw_data={"title": "uncommitted finding"},
        )
    )

    completed = _complete_scan_if_running(db_session, tenant_id, scan_id)

    assert completed is False
    assert db_session.query(Observation).filter(Observation.scan_id == scan_id).count() == 0
    assert db_session.query(Scan).filter(Scan.id == scan_id).one().status == "CANCELLED"


def test_completion_commits_observations_and_terminal_state_together(db_session):
    tenant_id, scan_id, asset_id = _create_scan(db_session, status="RUNNING")
    db_session.add(
        Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="WEB_FINDING",
            raw_data={"title": "completed finding"},
        )
    )

    completed = _complete_scan_if_running(db_session, tenant_id, scan_id)

    assert completed is True
    assert db_session.query(Observation).filter(Observation.scan_id == scan_id).count() == 1
    assert db_session.query(Scan).filter(Scan.id == scan_id).one().status == "COMPLETED"


def test_failed_transition_never_overwrites_cancelled_state(db_session):
    tenant_id, scan_id, _ = _create_scan(db_session, status="CANCELLED")

    failed = _mark_scan_failed(
        db_session, tenant_id, scan_id, RuntimeError("late worker error")
    )

    assert failed is False
    assert db_session.query(Scan).filter(Scan.id == scan_id).one().status == "CANCELLED"


def test_cancellation_callback_reads_committed_scan_state(db_session):
    tenant_id, scan_id, _ = _create_scan(db_session, status="RUNNING")
    assert _scan_cancel_requested(db_session, tenant_id, scan_id) is False

    scan = db_session.query(Scan).filter(Scan.id == scan_id).one()
    scan.status = "CANCELLED"
    db_session.commit()

    assert _scan_cancel_requested(db_session, tenant_id, scan_id) is True


def test_engine_process_is_terminated_when_cancellation_is_requested(monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    adapter = DummyAdapter("dummy-engine", timeout_seconds=10)

    with pytest.raises(ScanCancelledError, match="scan was cancelled"):
        adapter.execute(["--long-running"], should_cancel=lambda: True)

    assert process.terminated is True
    assert process.killed is False


def test_engine_returns_stdout_when_process_completes_normally(monkeypatch):
    class CompletedProcess(FakeProcess):
        def communicate(self, timeout=None):
            self.calls += 1
            self.returncode = 0
            return self.output, ""

    process = CompletedProcess(output='{"ok": true}')
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)
    adapter = DummyAdapter("dummy-engine", timeout_seconds=10)

    assert adapter.execute(["--once"]) == '{"ok": true}'
