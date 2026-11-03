import logging
import uuid
from typing import Any, Dict

from ai.gateway.output_validator import OutputValidator
from ai.gateway.security_guard import SecurityGuard
from ai.providers.gemini_provider import GeminiProvider
from backend.database.models.ai_record import AIAnalysisRecord
from backend.database.models.finding import Finding
from backend.database.session import SessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)


class AIGateway:
    def __init__(self):
        self.guard = SecurityGuard()
        self.provider = GeminiProvider()
        self.validator = OutputValidator()

    async def process_finding_analysis(
        self,
        tenant_id: str,
        finding_id: str,
        finding_data: Dict[str, Any],
        raw_evidence: str,
    ) -> Dict[str, Any]:
        tenant_uuid = uuid.UUID(str(tenant_id))
        finding_uuid = uuid.UUID(str(finding_id))
        if not self.guard.validate_data_policy(finding_data):
            raise ValueError("Data policy violation: sensitive data detected")

        clean_evidence = self.guard.sanitize_evidence(raw_evidence)
        db = SessionLocal()
        try:
            db.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_uuid)},
            )
            db.commit()
            finding = db.query(Finding).filter(
                Finding.id == finding_uuid,
                Finding.tenant_id == tenant_uuid,
            ).first()
            if finding is None:
                raise ValueError("Finding not found for the requested tenant")

            ai_response = await self.provider.analyze_finding(
                finding_data, clean_evidence
            )
            validated = self.validator.validate_ai_response(ai_response)
            db.add(AIAnalysisRecord(
                id=uuid.uuid4(),
                tenant_id=tenant_uuid,
                finding_id=finding_uuid,
                provider="gemini",
                model_name=self.provider.model_name,
                status="success",
                response_raw=validated,
            ))

            if validated["is_true_positive"]:
                finding.confidence = (
                    "high" if validated["confidence_score"] >= 0.8 else "medium"
                )
            else:
                finding.confidence = "low"
            finding.remediation = validated["remediation"]
            db.commit()
            return validated
        except Exception as exc:
            db.rollback()
            logger.error(
                "AI Gateway processing failed for finding %s: %s",
                finding_uuid, exc, exc_info=True,
            )
            try:
                db.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                    {"tenant_id": str(tenant_uuid)},
                )
                db.commit()
                db.add(AIAnalysisRecord(
                    id=uuid.uuid4(),
                    tenant_id=tenant_uuid,
                    finding_id=finding_uuid,
                    provider="gemini",
                    model_name=self.provider.model_name,
                    status="failed",
                    error_message=str(exc)[:4000],
                ))
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("Failed to persist AI analysis failure record")
            raise
        finally:
            self.provider.close()
            try:
                db.rollback()
                db.execute(
                    text("SELECT set_config('app.tenant_id', '', false), set_config('app.auth_lookup', 'false', false)")
                )
                db.commit()
            except Exception:
                db.rollback()
            db.close()
