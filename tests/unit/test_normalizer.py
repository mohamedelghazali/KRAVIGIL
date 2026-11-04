import uuid

from backend.services.normalization.normalizer import Normalizer
from shared.protocols import network_engine_pb2


def test_network_port_open_event_becomes_observation() -> None:
    tenant_id, scan_id, asset_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    event = network_engine_pb2.ScanEvent(
        event_type="PORT_OPEN",
        target_ip="192.0.2.10",
        port=443,
        status="OPEN",
        engine_version="1.2.3",
    )

    observation = Normalizer.from_network_event(tenant_id, scan_id, asset_id, event)

    assert observation is not None
    assert observation.tenant_id == tenant_id
    assert observation.scan_id == scan_id
    assert observation.asset_id == asset_id
    assert observation.engine_id == "network_cpp"
    assert observation.raw_data == {
        "target_ip": "192.0.2.10",
        "port": 443,
        "status": "OPEN",
        "engine_version": "1.2.3",
    }


def test_network_non_open_or_invalid_port_events_are_ignored() -> None:
    base = {
        "event_type": "PORT_CLOSED",
        "target_ip": "192.0.2.10",
        "port": 443,
        "status": "CLOSED",
    }
    assert Normalizer.from_network_event(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        network_engine_pb2.ScanEvent(**base),
    ) is None

    base["event_type"] = "PORT_OPEN"
    base["port"] = 0
    assert Normalizer.from_network_event(
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        network_engine_pb2.ScanEvent(**base),
    ) is None


def test_nuclei_result_preserves_scanner_identifiers() -> None:
    observation = Normalizer.from_nuclei_result(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        {
            "name": "Exposed admin panel",
            "severity": "high",
            "template_id": "http/exposed-panel",
            "cve_id": "CVE-2025-1234",
            "engine_version": "3.4.0",
        },
    )
    assert observation.engine_id == "nuclei"
    assert observation.raw_data["template_id"] == "http/exposed-panel"
    assert observation.raw_data["cve_id"] == "CVE-2025-1234"


def test_cloud_result_with_null_raw_payload_is_safe() -> None:
    observation = Normalizer.from_cloud_result(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        {"title": "Public bucket", "severity": "critical", "raw": None},
    )
    assert observation.engine_id == "cloud_scanner"
    assert observation.raw_data["resource_arn"] is None
