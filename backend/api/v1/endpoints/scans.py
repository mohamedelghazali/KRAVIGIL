from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.models.target import Target
from backend.database.models.asset import Asset
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user
from workers.tasks import run_network_scan
from pydantic import BaseModel
import uuid

router = APIRouter()

class ScanCreate(BaseModel):
    target_id: uuid.UUID
    ports: list[int] = [22, 80, 443, 8080]

@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
def start_scan(
    scan_in: ScanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    target = db.query(Target).filter(Target.id == scan_in.target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    
    if not target.is_authorized:
        raise HTTPException(status_code=403, detail="Target is not authorized for scanning")

    scan_id = str(uuid.uuid4())
    asset = db.query(Asset).filter(Asset.target_id == target.id).first()
    
    if not asset:
        asset = Asset(
            tenant_id=current_user.tenant_id,
            target_id=target.id,
            ip_address=target.ip_address or target.domain
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

    run_network_scan.delay(
        tenant_id=str(current_user.tenant_id),
        scan_id=scan_id,
        asset_id=str(asset.id),
        target_ip=asset.ip_address,
        ports=scan_in.ports
    )

    return {"scan_id": scan_id, "status": "PENDING"}
