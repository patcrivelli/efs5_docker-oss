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
from django.shortcuts import render

from .models import (
    ApplicationData,
    tf_ApplicationData,
    scf_ApplicationData,
    IPF_ApplicationData,
)

logger = logging.getLogger(__name__)



# -------------------------------
# Helpers for numeric conversions
# -------------------------------
def _to_decimal(x):
    if x in (None, "", "null"):
        return None
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None

# -------------------
# Finance list (UI)
# -------------------
def finance_view(request):
    ctx = base_context(request)  # originators + selected_originator

    live_states = ["risk_approved", "docs_requested", "pending_funding"]
    done_states = ["closed_funded", "closed_rejected", "funded", "paid_out", "archived"]

    live = (
        list(ApplicationData.objects.filter(state__in=live_states)) +
        list(tf_ApplicationData.objects.filter(state__in=live_states)) +
        list(scf_ApplicationData.objects.filter(state__in=live_states)) +
        list(IPF_ApplicationData.objects.filter(state__in=live_states))
    )
    done = (
        list(ApplicationData.objects.filter(state__in=done_states)) +
        list(tf_ApplicationData.objects.filter(state__in=done_states)) +
        list(scf_ApplicationData.objects.filter(state__in=done_states)) +
        list(IPF_ApplicationData.objects.filter(state__in=done_states))
    )

    # Optional filter by selected originator
    sel = ctx.get("selected_originator")
    if sel:
        sel_name = (sel.get("originator") or "").strip()
        if sel_name:
            live = [x for x in live if (x.originator or "").strip() == sel_name]
            done = [x for x in done if (x.originator or "").strip() == sel_name]

    ctx.update({
        "live_finance_applications": live,
        "completed_finance_applications": done,
    })
    return render(request, "finance.html", ctx)

# -------------------------------------------------------------
# POST /api/update-transaction-state/
# - decision: "pay" | "reject"
# - updates finance app state
# - on "pay": fetch invoices from efs_data and post ledger+invoices to LMS
# -------------------------------------------------------------
@csrf_exempt
def update_transaction_state(request):
    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body or "{}")
        transaction_id = data.get("transaction_id")
        decision = data.get("decision")

        if not transaction_id or decision not in {"pay", "reject"}:
            return JsonResponse({"success": False, "error": "Missing/invalid transaction_id or decision"}, status=400)

        # locate app in any of the four tables
        application, finance_type = None, None
        for model, ftype in [
            (ApplicationData, "standard"),
            (tf_ApplicationData, "tf"),
            (scf_ApplicationData, "scf"),
            (IPF_ApplicationData, "ipf"),
        ]:
            obj = model.objects.filter(transaction_id=transaction_id).first()
            if obj:
                application, finance_type = obj, ftype
                break

        if not application:
            return JsonResponse({"success": False, "error": "Application not found"}, status=404)

        # update state locally
        if decision == "pay":
            application.state = "closed_funded"
        else:
            application.state = "closed_rejected"
        application.save(update_fields=["state"])

        pushed = False

        if decision == "pay":
            # 1) fetch invoices from efs_data
            data_base = getattr(settings, "EFS_DATA_BASE_URL", "http://localhost:8003").rstrip("/")
            inv_url = f"{data_base}/api/financial/invoices/?transaction_id={transaction_id}"
            invoices = []
            try:
                r = requests.get(inv_url, timeout=8)
                if not r.ok:
                    logger.error("efs_data invoices failed %s: %s", r.status_code, r.text[:800])
                r.raise_for_status()
                invoices = r.json()  # expected list
            except Exception as e:
                logger.error("Failed to fetch invoices for %s: %s", transaction_id, e)
                invoices = []

            # 2) optional prorata for invoice finance
            product = (application.product or "").strip().lower()
            amt_req = _to_decimal(application.amount_requested)
            if product in {"invoice finance"} and amt_req and invoices:
                total_face = sum((_to_decimal(i.get("face_value")) or Decimal("0")) for i in invoices)
                if total_face and total_face > 0:
                    for i in invoices:
                        face = _to_decimal(i.get("face_value")) or Decimal("0")
                        ratio = (face / total_face) if face else Decimal("0")
                        prorata = (amt_req * ratio).quantize(Decimal("0.01"))
                        i["amount_funded"] = str(prorata)
                        i["amount_due"]    = str(prorata)
                else:
                    # equal split if face values missing
                    each = (amt_req / Decimal(len(invoices))).quantize(Decimal("0.01")) if invoices else Decimal("0")
                    for i in invoices:
                        i["amount_funded"] = str(each)
                        i["amount_due"]    = str(each)

            # 3) build payload to LMS (accepts this shape)
            lms_payload = {
                "ledger": {
                    "trans_id": transaction_id,
                    "abn": application.abn,
                    "name": application.contact_name,
                    "amount_funded": str(amt_req or 0),
                    "amount_repaid": "0.00",
                    "amount_due":    str(amt_req or 0),
                    "state": "closed_funded",
                    "product": application.product,
                },
                "invoices": [
                    {
                        "trans_id": transaction_id,
                        "debtor": i.get("debtor"),
                        "due": i.get("due_date"),                  # LMS view handles 'due' or 'due_date'
                        "amount_funded": i.get("amount_funded"),
                        "amount_repaid": "0.00",
                        "amount_due": i.get("amount_due"),
                        "face_value": i.get("face_value"),
                        "date_funded": i.get("date_funded"),
                        "invoice_number": i.get("inv_number"),     # LMS view handles invoice_number or inv_number
                        "abn": i.get("abn"),
                        "product": application.product,
                    } for i in invoices
                ],
            }

            # 4) POST to LMS; log error body if not ok
            lms_url = getattr(settings, "EFS_LMS_URL", "http://localhost:8008/api/ingest_transaction/")
            try:
                lr = requests.post(lms_url, json=lms_payload, timeout=10)
                if not lr.ok:
                    logger.error("LMS 400/500: %s", lr.text[:1000])
                lr.raise_for_status()
                pushed = True
                logger.info("Posted transaction %s to LMS with %d invoices", transaction_id, len(invoices))
            except Exception as e:
                logger.error("Failed to notify LMS: %s", e)

        return JsonResponse({
            "success": True,
            "transaction_id": transaction_id,
            "state": application.state,
            "pushed_to_lms": pushed,
        })

    except Exception as e:
        logger.exception("update_transaction_state failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
