import hashlib
import logging
import os
import tempfile
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database.models.report import Report
from backend.database.models.scan import Scan
from backend.services.reporting.data_extractor import DataExtractor
from backend.services.reporting.html_renderer import HTMLRenderer
from backend.services.reporting.pdf_renderer import PDFRenderer
from backend.services.evidence.minio_client import MinIOClient

logger = logging.getLogger(__name__)

class ReportOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = DataExtractor(db)
        self.html_renderer = HTMLRenderer()
        self.pdf_renderer = PDFRenderer()
        self.storage = MinIOClient()

    def generate_report(self, report_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        report = self.db.query(Report).filter(
            Report.id == uuid.UUID(str(report_id)),
            Report.tenant_id == uuid.UUID(str(tenant_id))
        ).first()
        if report is None:
            raise ValueError("Report not found")
        tmp_path = None
        uploaded_key = None
        try:
            report.status = "PROCESSING"
            report.error_message = None
            self.db.commit()
            scan = self.db.query(Scan).filter(
                Scan.id == report.scan_id,
                Scan.tenant_id == report.tenant_id
            ).first()
            if scan is None:
                raise ValueError("Scan not found for report tenant")
            findings_data = [{
                "id": str(item.id), "title": item.title, "severity": item.severity,
                "confidence": item.confidence, "cve_id": item.cve_id,
                "remediation": item.remediation
            } for item in self.extractor.iterate_findings(report.tenant_id, report.scan_id)]
            scan_data = {
                "id": str(scan.id),
                "target_ip": scan.asset.ip_address if getattr(scan, "asset", None) else "Unknown",
                "created_at": scan.created_at.strftime("%Y-%m-%d %H:%M:%S") if scan.created_at else "Unknown"
            }
            html = self.html_renderer.render(scan_data, findings_data)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name
            self.pdf_renderer.render_to_file(html, tmp_path)
            digest = hashlib.sha256()
            file_size = os.path.getsize(tmp_path)
            with open(tmp_path, "rb") as pdf_file:
                for chunk in iter(lambda: pdf_file.read(1024 * 1024), b""):
                    digest.update(chunk)
            report.status = "UPLOADING"
            self.db.commit()
            uploaded_key = f"{report.tenant_id}/reports/{report.id}.pdf"
            with open(tmp_path, "rb") as pdf_file:
                self.storage.upload_stream(uploaded_key, pdf_file, "application/pdf", file_size)
            report.object_key = uploaded_key
            report.sha256 = digest.hexdigest()
            report.file_size_bytes = file_size
            report.status = "READY"
            report.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info("Report %s generated", report.id)
        except Exception as exc:
            self.db.rollback()
            if uploaded_key:
                try:
                    self.storage.delete_object(uploaded_key)
                except Exception:
                    logger.exception("Could not clean up failed report object")
            report = self.db.query(Report).filter(
                Report.id == uuid.UUID(str(report_id)),
                Report.tenant_id == uuid.UUID(str(tenant_id))
            ).first()
            if report:
                report.status = "FAILED"
                report.error_message = str(exc)[:2048]
                self.db.commit()
            logger.exception("Report generation failed for %s", report_id)
            raise
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
