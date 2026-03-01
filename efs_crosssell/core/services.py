# efs_finance/core/services.py
import logging
from typing import Dict, Type
from django.db import transaction

from .models import (
    ApplicationData as FinanceApp,
    tf_ApplicationData as FinanceTFApp,
    scf_ApplicationData as FinanceSCFApp,
    IPF_ApplicationData as FinanceIPFApp,
)

logger = logging.getLogger(__name__)

_PRODUCT_MODEL_MAP: Dict[str, Type] = {
    "invoice finance": FinanceApp,
    "trade finance": FinanceTFApp,
    "supply chain finance": FinanceSCFApp,
    "scf": FinanceSCFApp,  # alias
    "insurance premium funding": FinanceIPFApp,
    "ipf": FinanceIPFApp,  # alias
}

def _pick_model(product: str) -> Type:
    key = (product or "invoice finance").strip().lower()
    return _PRODUCT_MODEL_MAP.get(key, FinanceApp)

class FinanceIngestService:
    @staticmethod
    @transaction.atomic
    def upsert(validated: dict) -> dict:
        Model = _pick_model(validated.get("product"))
        obj, created = Model.objects.update_or_create(
            transaction_id=validated["transaction_id"],
            defaults=validated,
        )
        logger.info(
            "Finance upsert: tx=%s product=%s model=%s created=%s",
            validated["transaction_id"],
            validated.get("product"),
            Model.__name__,
            created,
        )
        return {
            "transaction_id": obj.transaction_id,
            "product": validated.get("product"),
            "model_used": Model.__name__,
            "created": created,
        }
