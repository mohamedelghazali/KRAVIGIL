import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from tests.conftest import client, auth_headers

@pytest.mark.integration
def test_network_scan_pipeline(client, auth_headers):
    target_response = client.post(
        "/api/v1/targets/",
        json={"name": "Integration Target", "ip_address": "1.1.1.1", "is_authorized": True},
        headers=auth_headers
    )
    assert target_response.status_code == 201
    target_id = target_response.json()["id"]

    with patch("workers.tasks.run_network_scan.delay") as mock_scan:
        scan_response = client.post(
            "/api/v1/scans/network",
            json={"target_id": target_id, "ports": [80, 443]},
            headers=auth_headers
        )
        assert scan_response.status_code == 202
        assert mock_scan.called

    scan_id = scan_response.json()["scan_id"]
    status_response = client.get(f"/api/v1/scans/{scan_id}", headers=auth_headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "PENDING"
