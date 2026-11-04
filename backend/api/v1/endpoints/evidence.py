import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from backend.core.security import get_current_user, require_role
from backend.database.models.evidence import Evidence
from backend.database.models.finding import Finding
from backend.database.models.scan import Scan
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.services.evidence.evidence_manager import EvidenceManager

logger = logging.getLogger(__name__)
router = APIRouter()
MAX_EVIDENCE_SIZE = 50 * 1024 * 1024


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    scan_id: uuid.UUID
    finding_id: uuid.UUID | None
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


def _tenant_id(user: User):
    value = getattr(user, "organization_id", None) or getattr(user, "tenant_id", None)
    if value is None:
        raise HTTPException(status_code=403, detail="Tenant context is missing")
    return uuid.UUID(str(value))


@router.post("/upload", response_model=EvidenceResponse, status_code=201)
async def upload_evidence(scan_id: uuid.UUID = Form(...),
                          finding_id: uuid.UUID | None = Form(None),
                          file: UploadFile = File(...),
                          current_user: User = Depends(require_role(["admin", "analyst"])),
                          db: Session = Depends(get_tenant_db)):
    tenant_id = _tenant_id(current_user)
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.tenant_id == tenant_id).first()
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if finding_id:
        finding = db.query(Finding).filter(Finding.id == finding_id,
            Finding.tenant_id == tenant_id, Finding.asset_id == scan.asset_id).first()
        if finding is None:
            raise HTTPException(status_code=404, detail="Finding not found")
    try:
        content = await file.read(MAX_EVIDENCE_SIZE + 1)
        if len(content) > MAX_EVIDENCE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds 50MB limit")
        if not content:
            raise HTTPException(status_code=400, detail="Empty evidence files are not allowed")
        from io import BytesIO
        filename = (file.filename or "evidence.bin").replace("\\", "/").split("/")[-1]
        extension = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        record = EvidenceManager(db).store_evidence(
            tenant_id=tenant_id, scan_id=scan_id, finding_id=finding_id,
            stream=BytesIO(content), content_type=file.content_type or "application/octet-stream",
            extension=extension, metadata={"original_filename": filename})
        return record
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Evidence upload failed")
        raise HTTPException(status_code=500, detail="Evidence upload failed") from exc
    finally:
        await file.close()


@router.get("/{evidence_id}/download-url")
def get_download_url(evidence_id: uuid.UUID,
                     current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_tenant_db)):
    try:
        url = EvidenceManager(db).get_download_url(evidence_id, _tenant_id(current_user), 300)
        return {"download_url": url, "expires_in_seconds": 300}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc


@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence_metadata(evidence_id: uuid.UUID,
                          current_user: User = Depends(get_current_user),
                          db: Session = Depends(get_tenant_db)):
    record = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.tenant_id == _tenant_id(current_user),
        Evidence.deletion_status == "ACTIVE",
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return record


@router.delete("/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: uuid.UUID,
                    current_user: User = Depends(require_role(["admin"])),
                    db: Session = Depends(get_tenant_db)):
    try:
        EvidenceManager(db).delete_evidence(evidence_id, _tenant_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    except Exception as exc:
        logger.exception("Evidence deletion remains pending for %s", evidence_id)
        raise HTTPException(
            status_code=503,
            detail="Evidence deletion is pending; retry the request to complete it",
        ) from exc
    return Response(status_code=204)
