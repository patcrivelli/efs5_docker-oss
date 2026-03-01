
# efs_sales/core/services.py
import os, logging, requests
from django.db import transaction

logger = logging.getLogger(__name__)

class RiskServiceError(Exception):
    pass

class ApproveApplicationService:
    _model_map = {}
    RISK_URL = os.getenv("EFS_RISK_URL", "http://localhost:8005").rstrip("/") + "/api/applications/ingest/"

    @classmethod
    def configure_models(cls, SalesApp, SalesTFApp, SalesSCFApp, SalesIPFApp):
        cls._model_map = {
            "invoice finance": SalesApp,
            "trade finance": SalesTFApp,
            "supply chain finance": SalesSCFApp,
            "scf": SalesSCFApp,
            "ipf": SalesIPFApp,
            "insurance premium funding": SalesIPFApp,
        }

    @classmethod
    def run(cls, *, transaction_id: str, new_state: str, product_normalized: str):
        Model = cls._model_map.get(product_normalized)
        if not Model:
            raise ValueError(f"Unknown product: {product_normalized}")

        with transaction.atomic():
            app = Model.objects.get(transaction_id=transaction_id)
            app.state = new_state
            app.save()

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
                "state": new_state,
                "amount_requested": str(app.amount_requested) if app.amount_requested else None,
                "product": app.product,
                "insurance_premiums": app.insurance_premiums,
            }

        resp = requests.post(cls.RISK_URL, json=payload, timeout=10)
        if not resp.ok:
            raise RiskServiceError(f"Risk service error {resp.status_code}: {resp.text[:200]}")
        return True




#---------#---------#---------#---------
    #kanban board
#---------#---------#---------#---------


# core/services.py
import os
import requests
from collections.abc import Iterable

def fetch_aggregate_applications(timeout: int = 5) -> list[dict]:
    base = os.getenv("EFS_APPLICATION_AGGREGATE_URL", "http://localhost:8016")
    url = f"{base.rstrip('/')}/api/applications/"

    r = requests.get(url, timeout=timeout)
    r.raise_for_status()

    data = r.json()

    # 🔍 DEBUG ONCE (leave this in until tickets appear)
    print("🧠 RAW AGGREGATE JSON KEYS:", list(data.keys()) if isinstance(data, dict) else type(data))

    apps: list[dict] = []

    def collect_lists(obj):
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    apps.append(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                collect_lists(v)

    collect_lists(data)

    return apps

