import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from backend.schemas.report import ReportCreate, ReportRead as ReportResponse
from sqlalchemy.orm import Session
from backend.core.security import get_current_user, require_role
from backend.database.models.report import Report
from backend.database.models.scan import Scan
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from workers.tasks import generate_report
from backend.services.evidence.minio_client import MinIOClient

logger = logging.getLogger(__name__)
router = APIRouter()

def _tenant_id(user: User) -> uuid.UUID:
    value = getattr(user, "organization_id", None) or getattr(user, "tenant_id", None)
    if value is None:
        raise HTTPException(status_code=403, detail="Tenant context is missing")
    return uuid.UUID(str(value))

@router.post("/", response_model=ReportResponse, status_code=202)
def create_report(report_in: ReportCreate,
                  current_user: User = Depends(require_role(["admin", "analyst"])),
                  db: Session = Depends(get_tenant_db)):
    tenant_id = _tenant_id(current_user)
    scan = db.query(Scan).filter(
        Scan.id == report_in.scan_id, Scan.tenant_id == tenant_id
    ).first()
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Cannot generate report for incomplete scan")
    report = Report(tenant_id=tenant_id, scan_id=scan.id, status="QUEUED",
                    requested_by=current_user.id)
    try:
        db.add(report)
        db.commit()
        db.refresh(report)
        generate_report.delay(str(tenant_id), str(report.id))
        return report
    except Exception:
        db.rollback()
        logger.exception("Report creation failed")
        raise HTTPException(status_code=500, detail="Report creation failed")

@router.get("/", response_model=list[ReportResponse])
def list_reports(current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_tenant_db)):
    return db.query(Report).filter(Report.tenant_id == _tenant_id(current_user)).order_by(
        Report.created_at.desc()).limit(200).all()

@router.get("/{report_id}", response_model=ReportResponse)
def get_report_status(report_id: uuid.UUID,
                      current_user: User = Depends(get_current_user),
                      db: Session = Depends(get_tenant_db)):
    report = db.query(Report).filter(
        Report.id == report_id, Report.tenant_id == _tenant_id(current_user)
    ).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@router.get("/{report_id}/download")
def download_report(report_id: uuid.UUID,
                    current_user: User = Depends(get_current_user),
                    db: Session = Depends(get_tenant_db)):
    report = db.query(Report).filter(
        Report.id == report_id, Report.tenant_id == _tenant_id(current_user)
    ).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status != "READY" or not report.object_key:
        raise HTTPException(status_code=400, detail="Report is not ready for download")
    try:
        url = MinIOClient().generate_presigned_url(report.object_key, expires_seconds=300)
        return {"download_url": url, "expires_in_seconds": 300}
    except Exception as exc:
        logger.exception("Report download URL generation failed")
        raise HTTPException(status_code=500, detail="Report download failed") from exc
