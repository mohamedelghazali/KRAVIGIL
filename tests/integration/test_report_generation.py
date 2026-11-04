import hashlib
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from backend.database.models.asset import Asset
from backend.database.models.finding import Finding
from backend.database.models.observation import Observation
from backend.database.models.report import Report
from backend.database.models.scan import Scan
from backend.database.models.target import Target
from backend.database.models.user import Organization, User
from backend.services.reporting.data_extractor import DataExtractor
import backend.services.reporting.report_orchestrator as report_module


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def upload_stream(self, object_key, stream, content_type, size):
        payload = stream.read()
        assert content_type == "application/pdf"
        assert len(payload) == size
        self.objects[object_key] = payload

    def delete_object(self, object_key):
        self.objects.pop(object_key, None)


class FakeHTMLRenderer:
    captured_findings = []

    def render(self, scan_data, findings_data):
        self.captured_findings = findings_data
        return "<html><body>report</body></html>"


class FakePDFRenderer:
    def render_to_file(self, html, output_path):
        Path(output_path).write_bytes(b"%PDF-1.4\nKRAVIGIL integration test\n%%EOF")


def _create_report_fixture(db_session):
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()
    target_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    other_scan_id = uuid.uuid4()
    now = datetime.utcnow()

    organization = Organization(id=tenant_id, name=f"report-{tenant_id}")
    other_organization = Organization(
        id=other_tenant_id, name=f"report-{other_tenant_id}"
    )
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"reporter-{tenant_id}@example.test",
        hashed_password="test-hash",
        role="analyst",
    )
    target = Target(
        id=target_id,
        tenant_id=tenant_id,
        name="authorized report target",
        ip_address="192.0.2.80",
        is_authorized=True,
    )
    asset = Asset(
        id=asset_id,
        tenant_id=tenant_id,
        target_id=target_id,
        ip_address="192.0.2.80",
    )
    scan = Scan(
        id=scan_id,
        tenant_id=tenant_id,
        target_id=target_id,
        asset_id=asset_id,
        status="COMPLETED",
        scan_type="WEB",
    )
    other_scan = Scan(
        id=other_scan_id,
        tenant_id=tenant_id,
        target_id=target_id,
        asset_id=asset_id,
        status="COMPLETED",
        scan_type="WEB",
    )
    db_session.add_all(
        [organization, other_organization, user, target, asset, scan, other_scan]
    )
    db_session.flush()

    observations = [
        Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "http/test-one"},
        ),
        Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "http/test-two"},
        ),
        Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=other_scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "http/other-scan"},
        ),
    ]
    other_asset = Asset(
        id=uuid.uuid4(),
        tenant_id=other_tenant_id,
        target_id=uuid.uuid4(),
        ip_address="192.0.2.81",
    )
    other_target = Target(
        id=other_asset.target_id,
        tenant_id=other_tenant_id,
        name="other tenant target",
        ip_address="192.0.2.81",
        is_authorized=True,
    )
    other_tenant_scan = Scan(
        id=uuid.uuid4(),
        tenant_id=other_tenant_id,
        target_id=other_target.id,
        asset_id=other_asset.id,
        status="COMPLETED",
        scan_type="WEB",
    )
    db_session.add_all([other_target, other_asset, other_tenant_scan])
    db_session.flush()
    observations.append(
        Observation(
            id=uuid.uuid4(),
            tenant_id=other_tenant_id,
            scan_id=other_tenant_scan.id,
            asset_id=other_asset.id,
            engine_id="nuclei",
            event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "http/other-tenant"},
        )
    )
    db_session.add_all(observations)
    db_session.flush()

    findings = []
    for index, observation in enumerate(observations):
        finding = Finding(
            id=uuid.uuid4(),
            tenant_id=observation.tenant_id,
            asset_id=observation.asset_id,
            engine_id="nuclei",
            engine_version="3.4.0",
            title=f"Finding {index}",
            vulnerability_key=f"test:{uuid.uuid4()}",
            severity="medium",
            confidence="potential",
            validation_status="potential",
            workflow_status="open",
            first_seen=now,
            last_seen=now,
            observations=[observation],
        )
        findings.append(finding)
    db_session.add_all(findings)
    db_session.flush()

    report = Report(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        scan_id=scan_id,
        report_type="PDF",
        status="QUEUED",
        requested_by=user.id,
    )
    db_session.add(report)
    db_session.flush()
    return tenant_id, scan_id, report, findings


def test_report_data_extractor_is_scan_and_tenant_scoped(db_session):
    tenant_id, scan_id, report, findings = _create_report_fixture(db_session)
    extracted = list(DataExtractor(db_session).iterate_findings(tenant_id, scan_id, batch_size=1))
    assert len(extracted) == 2
    assert {item.id for item in extracted} == {findings[0].id, findings[1].id}
    with pytest.raises(ValueError):
        list(DataExtractor(db_session).iterate_findings(tenant_id, scan_id, batch_size=0))


def test_report_orchestrator_generates_pdf_for_only_requested_scan(
    db_session, monkeypatch
):
    tenant_id, scan_id, report, findings = _create_report_fixture(db_session)
    captured_html = FakeHTMLRenderer()
    storage = FakeStorage()
    monkeypatch.setattr(report_module, "MinIOClient", lambda: storage)
    monkeypatch.setattr(report_module, "HTMLRenderer", lambda: captured_html)
    monkeypatch.setattr(report_module, "PDFRenderer", FakePDFRenderer)

    report_module.ReportOrchestrator(db_session).generate_report(report.id, tenant_id)

    db_session.refresh(report)
    expected_key = f"{tenant_id}/reports/{report.id}.pdf"
    assert report.status == "READY"
    assert report.object_key == expected_key
    assert report.file_size_bytes == len(b"%PDF-1.4\nKRAVIGIL integration test\n%%EOF")
    assert report.sha256 == hashlib.sha256(
        b"%PDF-1.4\nKRAVIGIL integration test\n%%EOF"
    ).hexdigest()
    assert report.completed_at is not None
    assert len(captured_html.captured_findings) == 2
    assert len(storage.objects[expected_key]) == report.file_size_bytes


def test_report_orchestrator_does_not_cross_tenant(db_session, monkeypatch):
    tenant_id, _, report, _ = _create_report_fixture(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(report_module, "MinIOClient", lambda: storage)
    with pytest.raises(ValueError, match="Report not found"):
        report_module.ReportOrchestrator(db_session).generate_report(
            report.id, uuid.uuid4()
        )
    db_session.refresh(report)
    assert report.status == "QUEUED"
    assert storage.objects == {}
