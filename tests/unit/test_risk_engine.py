import pytest
from unittest.mock import MagicMock
from backend.services.risk.risk_engine import RiskEngine
from backend.database.models.finding import Finding

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_intel(mocker):
    intel = mocker.patch("backend.services.risk.risk_engine.VulnerabilityIntelligence")
    instance = intel.return_value
    instance.get_cve_details.return_value = {"cvss_score": 9.8}
    instance.get_epss_score.return_value = 0.9
    instance.is_in_kev.return_value = True
    return instance

def test_calculate_risk_critical(mock_db, mock_intel):
    engine = RiskEngine(mock_db)

    finding = Finding(
        id="test-id",
        tenant_id="tenant-id",
        cve_id="CVE-2023-1234",
        severity="HIGH"
    )
    mock_db.query.return_value.filter.return_value.first.return_value = finding

    result = engine.calculate_risk(
        tenant_id="tenant-id",
        finding_id="test-id",
        asset_criticality="critical",
        exposure="internet"
    )

    assert result.calculated_risk_score > 80.0
    assert result.risk_level == "CRITICAL"
    assert result.kev_status is True
    assert result.cvss_score == 9.8
    assert result.epss_score == 0.9

def test_calculate_risk_heuristic(mock_db, mock_intel):
    engine = RiskEngine(mock_db)

    finding = Finding(
        id="test-id-2",
        tenant_id="tenant-id",
        cve_id=None,
        severity="MEDIUM"
    )
    mock_db.query.return_value.filter.return_value.first.return_value = finding

    result = engine.calculate_risk(
        tenant_id="tenant-id",
        finding_id="test-id-2",
        asset_criticality="low",
        exposure="internal"
    )

    assert result.calculated_risk_score < 60.0
    assert result.risk_level == "LOW"
    assert result.kev_status is False
    assert result.cvss_score == 5.5
