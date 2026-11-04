from backend.services.correlation.deduplication import merge_duplicate_findings


def test_repeated_scan_does_not_reopen_rejected_false_positive():
    merged = merge_duplicate_findings(
        [
            {
                "vulnerability_key": "scanner:known-false-positive",
                "severity": "medium",
                "validation_status": "potential",
                "workflow_status": "open",
                "evidence_refs": ["evidence://first"],
            },
            {
                "vulnerability_key": " SCANNER:KNOWN-FALSE-POSITIVE ",
                "severity": "high",
                "validation_status": "rejected",
                "workflow_status": "open",
                "evidence_refs": ["evidence://second"],
            },
        ]
    )

    assert len(merged) == 1
    assert merged[0]["validation_status"] == "rejected"
    assert merged[0]["severity"] == "high"
    assert merged[0]["evidence_refs"] == [
        "evidence://first",
        "evidence://second",
    ]



def test_correlation_engine_keeps_rejected_finding_rejected_on_repeat_scan():
    import os
    import uuid

    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.database.models.asset import Asset
    from backend.database.models.observation import Observation
    from backend.database.models.scan import Scan
    from backend.database.models.target import Target
    from backend.database.models.user import Organization
    from backend.services.correlation.correlation_engine import CorrelationEngine

    database_url = os.getenv("DATABASE_URL")
    if not database_url or not database_url.startswith(("postgresql://", "postgresql+")):
        pytest.skip("requires the PostgreSQL integration database")

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        tenant_id = uuid.uuid4()
        target_id, asset_id, scan_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        organization = Organization(id=tenant_id, name=f"false-positive-{tenant_id}")
        target = Target(
            id=target_id,
            tenant_id=tenant_id,
            name="false-positive regression target",
            ip_address="192.0.2.111",
            is_authorized=True,
        )
        asset = Asset(
            id=asset_id,
            tenant_id=tenant_id,
            target_id=target_id,
            ip_address="192.0.2.111",
        )
        scan = Scan(
            id=scan_id,
            tenant_id=tenant_id,
            target_id=target_id,
            asset_id=asset_id,
            status="COMPLETED",
            scan_type="WEB",
        )
        first_observation = Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "http/known-false-positive"},
        )
        db.add_all([organization, target, asset, scan, first_observation])
        db.commit()

        correlation = CorrelationEngine(db)
        finding_id = correlation.process_observation(
            first_observation,
            vulnerability_key="scanner:known-false-positive",
            severity="medium",
        )
        finding = db.query(Finding).filter(
            Finding.id == finding_id,
            Finding.tenant_id == tenant_id,
        ).one()
        finding.validation_status = "rejected"
        finding.workflow_status = "resolved"
        db.commit()

        second_observation = Observation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            scan_id=scan_id,
            asset_id=asset_id,
            engine_id="nuclei",
            event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "http/known-false-positive"},
        )
        db.add(second_observation)
        db.commit()
        repeated_id = correlation.process_observation(
            second_observation,
            vulnerability_key=" SCANNER:KNOWN-FALSE-POSITIVE ",
            severity="high",
        )
        assert repeated_id == finding_id
        db.refresh(finding)
        assert finding.validation_status == "rejected"
        assert finding.workflow_status == "resolved"
        assert len(finding.observations) == 2
    finally:
        db.rollback()
        db.close()
        engine.dispose()
