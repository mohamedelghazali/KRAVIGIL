import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from backend.database.models.target import Target
from backend.database.models.asset import Asset
from backend.database.models.scan import Scan
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user, require_role
from backend.core.exceptions import KravigilException, ScopeViolationException
from workers.tasks import run_network_scan

router = APIRouter()


class ScanCreate(BaseModel):
    target_id: uuid.UUID
    ports: List[int] = Field(
        default_factory=lambda: [22, 80, 443, 8080],
        min_length=1,
        max_length=1000,
    )

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, ports: List[int]) -> List[int]:
        if any(not isinstance(port, int) or port < 1 or port > 65535 for port in ports):
            raise ValueError("Ports must be integers between 1 and 65535")
        return list(dict.fromkeys(ports))


class ScanResponse(BaseModel):
    scan_id: uuid.UUID
    status: str

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "/start",
    response_model=ScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_scan(
    scan_in: ScanCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db),
):
    tenant_id = current_user.tenant_id

    try:
        target = (
            db.query(Target)
            .filter(
                Target.id == scan_in.target_id,
                Target.tenant_id == tenant_id,
            )
            .first()
        )
        if target is None:
            raise HTTPException(status_code=404, detail="Target not found")

        if not target.is_authorized:
            raise ScopeViolationException("Target is not authorized for scanning")

        asset = (
            db.query(Asset)
            .filter(
                Asset.target_id == target.id,
                Asset.tenant_id == tenant_id,
            )
            .first()
        )

        if asset is None:
            asset = Asset(
                tenant_id=tenant_id,
                target_id=target.id,
                ip_address=target.ip_address or target.domain,
            )
            db.add(asset)
            db.flush()

        if not asset.ip_address:
            raise HTTPException(
                status_code=422,
                detail="Target does not have a resolvable IP address",
            )

        scan = Scan(
            tenant_id=tenant_id,
            target_id=target.id,
            asset_id=asset.id,
            status="PENDING",
            scan_type="NETWORK",
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        try:
            run_network_scan.delay(
                tenant_id=str(tenant_id),
                scan_id=str(scan.id),
                asset_id=str(asset.id),
                target_ip=asset.ip_address,
                ports=scan_in.ports,
            )
        except Exception as queue_error:
            scan.status = "FAILED"
            db.commit()
            raise KravigilException(
                message="Failed to queue network scan",
                status_code=503,
                error_code="SCAN_QUEUE_ERROR",
            ) from queue_error

        return ScanResponse(scan_id=scan.id, status=scan.status)

    except (HTTPException, ScopeViolationException, KravigilException):
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise KravigilException(
            message="Failed to initiate scan",
            status_code=500,
            error_code="SCAN_INIT_ERROR",
        ) from exc


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan_status(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    scan = (
        db.query(Scan)
        .filter(
            Scan.id == scan_id,
            Scan.tenant_id == current_user.tenant_id,
        )
        .first()
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanResponse(scan_id=scan.id, status=scan.status)
