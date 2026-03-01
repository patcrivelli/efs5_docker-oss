# efs_finance/core/views.py
import logging
import requests
from django.conf import settings
from django.shortcuts import render, redirect

logger = logging.getLogger(__name__)

# ---- helpers to talk to efs_profile ----
def _profile_base() -> str:
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def fetch_originators():
    """Return a list of originators from efs_profile as [{id, originator, ...}, ...]."""
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        data = r.json()
        return data.get("originators", [])
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []

# ---- view context used by templates ----
def base_context(request):
    originators = fetch_originators()

    selected_originator = None
    selected_id = request.GET.get("originators")
    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected_originator = o
                break

    return {
        "originators": originators,
        "selected_originator": selected_originator,
    }

# ---- pages ----
def finance_home(request):
    return render(request, "finance_home.html", base_context(request))


# ---- form handler ----
def create_originator(request):
    if request.method == "POST":
        payload = {
            "originator": request.POST.get("originator_name"),
            "created_by": request.POST.get("username"),
        }
        try:
            r = requests.post(
                f"{_profile_base()}/api/originators/create/",
                json=payload,
                headers=_api_key_header(),
                timeout=5,
            )
            if r.status_code not in (200, 201):
                logger.error("Originator create failed: %s %s", r.status_code, r.text)
        except Exception:
            logger.exception("Error calling efs_profile create originator")

    # redirect back so dropdown refreshes
    return redirect("finance_home")

# efs_finance/core/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json, logging

from .serializers import IngestFromRiskSerializer
from .services import FinanceIngestService

logger = logging.getLogger(__name__)

@csrf_exempt
def ingest_from_risk(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=400)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    ser = IngestFromRiskSerializer(data=payload)
    if not ser.is_valid():
        logger.warning("Finance ingest validation error: %s", ser.errors)
        return JsonResponse({"success": False, "error": ser.errors}, status=400)

    out = FinanceIngestService.upsert(ser.validated_data)
    return JsonResponse({"success": True, **out})



# efs_finance/core/views.py
import json
import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

# -------------------------------
# Helpers
# -------------------------------
def _to_decimal(x):
    if x in (None, "", "null"):
        return None
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None

def _aggregate_base() -> str:
    # central application_aggregate service
    return getattr(settings, "EFS_APPLICATION_AGGREGATE_BASE_URL", "http://localhost:8016").rstrip("/")

def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def _get_json(url: str, params: dict | None = None, timeout: int = 10):
    try:
        r = requests.get(url, params=params or {}, headers=_api_key_header(), timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("GET %s failed: %s", url, e)
        return None

def _wrap_list(maybe_data) -> list[dict]:
    if isinstance(maybe_data, list):
        return [x for x in maybe_data if isinstance(x, dict)]
    if isinstance(maybe_data, dict):
        for key in ("applications", "results", "items", "data"):
            val = maybe_data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        if isinstance(maybe_data.get("application"), dict):
            return [maybe_data["application"]]
        return [maybe_data]
    return []

def _filter_by_state(apps: list[dict], states: list[str]) -> list[dict]:
    allowed = {s.lower() for s in states}
    return [a for a in apps if (a.get("state") or "").lower() in allowed]

def _fetch_apps(states: list[str], originator_name: str | None) -> list[dict]:
    params = {}
    if originator_name:
        params["originator"] = originator_name
    if states:
        params["states"] = ",".join(states)

    data = _get_json(f"{_aggregate_base()}/api/applications/", params=params) or []
    items = _wrap_list(data)

    apps = []
    for raw in items:
        app = raw.get("application") if isinstance(raw.get("application"), dict) else raw
        if isinstance(app, dict):
            apps.append(app)

    if states:
        apps = _filter_by_state(apps, states)

    try:
        apps.sort(key=lambda a: a.get("application_time") or "", reverse=True)
    except Exception:
        pass
    return apps

# ---- Finance view ----
def finance_view(request):
    ctx = base_context(request)  # originators + selected_originator
    org_name = (ctx.get("selected_originator") or {}).get("originator")

    # Finance should only see risk_approved → live
    live = _fetch_apps(["operations_approved"], org_name)

    # And only closed ones → completed
    completed = _fetch_apps(["closed_funded", "closed_rejected"], org_name)

    ctx["live_finance_applications"] = live
    ctx["completed_finance_applications"] = completed
    return render(request, "finance.html", ctx)


# -------------------------------------------------------------
# POST /api/update-transaction-state/
# - decision: "pay" | "reject"
# - updates finance app state
# - on "pay": fetch invoices from efs_data and post ledger+invoices to LMS
# -------------------------------------------------------------
# efs_finance/core/views.py
import json
import logging
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

# -------------------------------
# Helpers
# -------------------------------
def _to_decimal(x):
    if x in (None, "", "null"):
        return None
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None

def _aggregate_base() -> str:
    # central application_aggregate service
    return getattr(settings, "EFS_APPLICATION_AGGREGATE_BASE_URL", "http://localhost:8016").rstrip("/")

def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def _get_json(url: str, params: dict | None = None, timeout: int = 10):
    try:
        r = requests.get(url, params=params or {}, headers=_api_key_header(), timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("GET %s failed: %s", url, e)
        return None


# -------------------------------
# Update transaction state
# -------------------------------
@csrf_exempt
def update_transaction_state(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body or "{}")
        transaction_id = data.get("transaction_id")
        decision = data.get("decision")

        if not transaction_id or decision not in {"pay", "reject"}:
            return JsonResponse({"success": False, "error": "Missing/invalid transaction_id or decision"}, status=400)

        # -----------------------------
        # 1) Fetch application from aggregate
        # -----------------------------
        app_url = f"{_aggregate_base()}/api/applications/{transaction_id}/"
        application = _get_json(app_url)

        if not application or not isinstance(application, dict):
            return JsonResponse({"success": False, "error": "Application not found"}, status=404)

        # normalize shape (in case wrapped under "application")
        if "application" in application and isinstance(application["application"], dict):
            application = application["application"]


        originator = (application.get("originator") or "").strip() or None


        # -----------------------------
        # 2) Update state in aggregate
        # -----------------------------
        new_state = "closed_funded" if decision == "pay" else "closed_rejected"
        patch_url = f"{_aggregate_base()}/api/applications/{transaction_id}/state/"
        try:
            r = requests.post(
                patch_url,
                json={"state": new_state, "source": "finance"},
                headers=_api_key_header(),
                timeout=8,
            )
            if not r.ok:
                logger.error("Failed to update state in aggregate %s: %s", r.status_code, r.text)
            r.raise_for_status()
        except Exception as e:
            logger.error("Error patching aggregate for %s: %s", transaction_id, e)

        pushed = False


        # -----------------------------
        # 3) If "pay": fetch invoices + push to LMS (Invoice Finance service)
        # -----------------------------

        if decision == "pay":
            # IMPORTANT: point to efs_data_financial (8019), not generic efs_data
            data_fin_base = getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "http://localhost:8019").rstrip("/")
            inv_url = f"{data_fin_base}/api/financial/invoices/"
            invoices = []
            try:
                r = requests.get(inv_url, params={"transaction_id": transaction_id}, timeout=8, headers=_api_key_header())
                r.raise_for_status()
                raw = r.json() or []
                raw_list = raw.get("results", raw) if isinstance(raw, dict) else raw

                invoices = []
                for i in raw_list:
                    if not isinstance(i, dict):
                        continue
                    inv_number = i.get("inv_number") or i.get("invoice_number") or ""
                    if not inv_number:
                        continue
                    invoices.append({
                        "trans_id": transaction_id,
                        "originator": originator,  # ✅ NEW
                        "debtor": i.get("debtor"),
                        "due": i.get("due_date"),
                        "amount_funded": i.get("amount_funded"),
                        "amount_repaid": "0.00",
                        "amount_due": i.get("amount_due"),
                        "face_value": i.get("face_value"),
                        "date_funded": i.get("date_funded"),
                        "invoice_number": inv_number,
                        "abn": i.get("abn"),
                        "product": application.get("product") or "Invoice Finance",
                    })
            except Exception as e:
                logger.error("Failed to fetch invoices for %s from efs_data_financial: %s", transaction_id, e)
                invoices = []

            product = (application.get("product") or "").strip().lower()
            amt_req = _to_decimal(application.get("amount_requested"))

            # Optional prorata allocation for invoice finance
            if product in {"invoice finance"} and amt_req and invoices:
                from decimal import Decimal
                total_face = sum((_to_decimal(i.get("face_value")) or Decimal("0")) for i in invoices)
                if total_face and total_face > 0:
                    for i in invoices:
                        face = _to_decimal(i.get("face_value")) or Decimal("0")
                        ratio = (face / total_face) if face else Decimal("0")
                        prorata = (amt_req * ratio).quantize(Decimal("0.01"))
                        i["amount_funded"] = str(prorata)
                        i["amount_due"] = str(prorata)
                else:
                    each = (amt_req / Decimal(len(invoices))).quantize(Decimal("0.01")) if invoices else Decimal("0")
                    for i in invoices:
                        i["amount_funded"] = str(each)
                        i["amount_due"] = str(each)


            # pick a company name (prefer company_name, fallback to contact_name)
            company_name = (
                (application.get("company_name") or "").strip()
                or (application.get("contact_name") or "").strip()
                or None
            )



            lms_payload = {
                "ledger": {
                    "trans_id": transaction_id,
                    "abn": application.get("abn"),
                    "acn": application.get("acn"),          # ✅ optional but recommended since LMS ledger has acn
                    "originator": originator,  # ✅ NEW
                    "name": company_name,                   # ✅ CHANGED HERE
                    "amount_funded": str(amt_req or 0),
                    "amount_repaid": "0.00",
                    "amount_due": str(amt_req or 0),
                    "state": "closed_funded",
                    "product": application.get("product") or "Invoice Finance",
                },
                "invoices": invoices,
            }

            lms_base = getattr(settings, "EFS_LMS_INVOICE_FINANCE_URL", "http://localhost:8024").rstrip("/")
            lms_url = f"{lms_base}/api/ingest_transaction/"

            try:
                lr = requests.post(lms_url, json=lms_payload, timeout=10)
                if not lr.ok:
                    logger.error("LMS Invoice Finance 400/500: %s", lr.text[:1000])
                lr.raise_for_status()
                pushed = True
                logger.info("Posted %s to LMS Invoice Finance with %d invoices", transaction_id, len(invoices))
            except Exception as e:
                logger.error("Failed to notify LMS Invoice Finance: %s", e)

        return JsonResponse(
            {
                "success": True,
                "transaction_id": transaction_id,
                "state": new_state,
                "pushed_to_lms": pushed,
            }
        )

    except Exception as e:
        logger.exception("update_transaction_state failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)




# efs_finance/core/views.py
import os
import requests
import logging
from django.http import HttpResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

def _agents_base() -> str:
    # Prefer Django settings; fallback to env; then localhost
    return getattr(
        settings,
        "EFS_AGENTS_BASE_URL",
        os.getenv("EFS_AGENTS_URL", "http://localhost:8015"),
    ).rstrip("/")


@require_GET
def modal_finance_agents(request):
    """
    BFF proxy:
      Browser -> efs_finance -> efs_agents -> returns HTML
    """
    abn = request.GET.get("abn", "") or ""
    tx  = request.GET.get("tx", "") or ""

    upstream_url = f"{_agents_base()}/modal/finance-agents/"
    try:
        resp = requests.get(
            upstream_url,
            params={"abn": abn, "tx": tx},
            timeout=10,
        )
        return HttpResponse(resp.text, status=resp.status_code, content_type="text/html")
    except Exception as e:
        logger.exception("Failed to load finance agents modal")
        return HttpResponse(
            f"<div class='modal-content'><p>Failed to load Finance Agents modal: {e}</p></div>",
            status=502,
            content_type="text/html",
        )
