# efs_risk/core/services.py
import logging
import requests
from django.conf import settings

from .models import (
    ApplicationData as RiskApp,
    tf_ApplicationData as RiskTFApp,
    scf_ApplicationData as RiskSCFApp,
    IPF_ApplicationData as RiskIPFApp,
)

logger = logging.getLogger(__name__)

# Map product names to the right Risk model
_PRODUCT_MODEL_MAP = {
    "invoice finance": RiskApp,
    "trade finance": RiskTFApp,
    "supply chain finance": RiskSCFApp,
    "scf": RiskSCFApp,  # alias
    "ipf": RiskIPFApp,
    "insurance premium funding": RiskIPFApp,
}

def _pick_model(product: str):
    """Return the correct model class based on product name."""
    if not product:
        return RiskApp
    return _PRODUCT_MODEL_MAP.get(product.strip().lower(), RiskApp)


class ApplicationIngestService:
    """
    Upsert an application into the appropriate risk table.
    Called when new application data arrives in Risk.
    """
    @staticmethod
    def upsert(data: dict) -> dict:
        product = (data.get("product") or "").strip().lower()
        Model = _pick_model(product)

        obj, created = Model.objects.update_or_create(
            transaction_id=data.get("transaction_id"),
            defaults=data,
        )
        return {"created": created, "transaction_id": obj.transaction_id}


class ApprovalService:
    """
    Approve/Reject an application and (if approved) push to Finance.
    """
    FINANCE_URL = getattr(
        settings,
        "EFS_FINANCE_INGEST_URL",
        "http://localhost:8006/api/ingest_from_risk/",
    )

    @classmethod
    def approve_or_reject(cls, transaction_id: str, decision: str) -> dict:
        # Find the application in any of the Risk models
        app = None
        model_used = None
        for Model in (RiskApp, RiskTFApp, RiskSCFApp, RiskIPFApp):
            app = Model.objects.filter(transaction_id=transaction_id).first()
            if app:
                model_used = Model
                break
        if not app:
            return {"success": False, "error": "Application not found"}

        if decision not in {"approve", "reject"}:
            return {"success": False, "error": "Invalid decision"}

        # Update local state
        app.state = "risk_approved" if decision == "approve" else "risk_rejected"
        app.save(update_fields=["state"])

        pushed = False
        if decision == "approve":
            payload = {
                "transaction_id": app.transaction_id,
                "application_time": app.application_time.isoformat() if app.application_time else None,
                "contact_name": app.contact_name,
                "abn": app.abn,
                "acn": app.acn,
                "bankstatements_token": app.bankstatements_token,
                "bureau_token": app.bureau_token,
                "accounting_token": app.accounting_token,
                "ppsr_token": app.ppsr_token,
                "contact_email": app.contact_email,
                "contact_number": app.contact_number,
                "originator": app.originator,
                "state": app.state,
                "amount_requested": str(app.amount_requested) if app.amount_requested is not None else None,
                "product": app.product,
                "insurance_premiums": app.insurance_premiums,
            }
            try:
                r = requests.post(cls.FINANCE_URL, json=payload, timeout=8)
                if not r.ok:
                    logger.error("Finance ingest failed %s: %s", r.status_code, r.text[:400])
                else:
                    pushed = True
            except Exception:
                logger.exception("Failed to push to Finance service")

        return {
            "success": True,
            "state": app.state,
            "pushed_to_finance": pushed,
            "model": getattr(model_used, "__name__", None),
        }
