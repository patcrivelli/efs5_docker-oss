# efs_drawdowns/core/views.py
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
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        return r.json().get("originators", [])
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []

# ---- context used in templates ----
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
def drawdowns_home(request):
    return render(request, "drawdowns_home.html", base_context(request))

def drawdowns_view(request):
    return render(request, "drawdowns.html", base_context(request))

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

    return redirect("drawdowns_home")



import json
from decimal import Decimal, InvalidOperation
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone

from .models import if_DrawdownData

def _to_decimal(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None

@csrf_exempt  # since you’re posting cross-origin / cross-service
def receive_drawdown(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    # Required/expected inputs
    tx  = (payload.get("transaction_id") or "").strip()
    abn = (payload.get("abn") or "19155437620").strip()  # default to the hard-coded ABN if omitted
    product = (payload.get("product") or "Invoice Finance").strip()
    originator = (payload.get("originator") or "").strip()
    state = (payload.get("state") or "sales").strip()
    amount = _to_decimal(payload.get("amount_requested"))

    if not tx:
        # Generate server-side if client didn't provide
        try:
            import uuid
            tx = str(uuid.uuid4())
        except Exception:
            tx = str(int(timezone.now().timestamp()))

    if not amount or amount <= 0:
        return JsonResponse({"success": False, "error": "amount_requested must be > 0"}, status=400)

    # Upsert by transaction_id (unique)
    defaults = {
        "drawdown_time": timezone.now(),
        "contact_name": payload.get("contact_name"),
        "abn": abn,
        "acn": payload.get("acn"),
        "bankstatements_token": payload.get("bankstatements_token"),
        "bureau_token": payload.get("bureau_token"),
        "accounting_token": payload.get("accounting_token"),
        "ppsr_token": payload.get("ppsr_token"),
        "contact_email": payload.get("contact_email"),
        "contact_number": payload.get("contact_number"),
        "originator": originator,
        "state": state,
        "amount_requested": amount,
        "product": product,
        "insurance_premiums": payload.get("insurance_premiums"),
    }

    obj, created = if_DrawdownData.objects.update_or_create(
        transaction_id=tx,
        defaults=defaults,
    )

    return JsonResponse({
        "success": True,
        "transaction_id": obj.transaction_id,
        "created": created,
    }, status=200)



from django.shortcuts import render
from .models import if_DrawdownData, tf_DrawdownData, scf_DrawdownData, IPF_DrawdownData

def drawdowns_board(request):
    rows = []
    for Model in (if_DrawdownData, tf_DrawdownData, scf_DrawdownData, IPF_DrawdownData):
        rows.extend(list(Model.objects.values(
            "transaction_id", "abn", "originator", "product", "amount_requested", "state"
        )))

    columns = {"sales": [], "operations": [], "risk": [], "finance": []}
    active = set(columns.keys())  # only show these

    for r in rows:
        key = (r.get("state") or "").strip().lower()
        if key in active:
            columns[key].append(r)
        # else: skip it (e.g., 'sales_approved' won't show)

    ctx = base_context(request)
    ctx["columns"] = columns
    return render(request, "drawdowns.html", ctx)





# ------Drawdown fetch compliance checks ------
# ------Drawdown fetch compliance checks ------
# ------Drawdown fetch compliance checks ------
# ------Drawdown fetch compliance checks ------

# efs_drawdowns/core/views.py
import os, logging
from urllib.parse import urlencode, quote
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

BUREAU_SOURCE        = (os.getenv("EFS_BUREAU_SOURCE", "sales") or "sales").lower()
EFS_SALES_URL        = os.getenv("EFS_SALES_URL", "http://localhost:8001").rstrip("/")
EFS_DATA_BUREAU_URL  = os.getenv("EFS_DATA_BUREAU_URL", "http://localhost:8018").rstrip("/")
TIMEOUT              = float(os.getenv("EFS_HTTP_TIMEOUT", "8.0"))

def _bureau_base() -> str:
    return EFS_SALES_URL if BUREAU_SOURCE == "sales" else EFS_DATA_BUREAU_URL

def _http_get(url: str):
    resp = requests.get(url, timeout=TIMEOUT)
    ct = (resp.headers.get("content-type") or "").lower()
    if "json" in ct:
        return resp.status_code, resp.json()
    return resp.status_code, {
        "error": "Upstream did not return JSON",
        "status": resp.status_code,
        "body": resp.text[:500],
    }

def _get_json(url: str):
    try:
        status, data = _http_get(url)
        return JsonResponse(data, status=status, safe=False)
    except requests.Timeout:
        logger.exception("Timeout calling %s", url)
        return JsonResponse({"error": "Upstream timeout"}, status=504)
    except Exception as e:
        logger.exception("Upstream error calling %s", url)
        return JsonResponse({"error": str(e)}, status=502)

def _try_bff_paths(paths):
    last = (404, {"error": "not found"})
    for p in paths:
        try:
            status, data = _http_get(p)
            if status != 404:
                return status, data
            last = (status, data)
        except Exception as e:
            last = (502, {"error": str(e)})
    return last

def _first(*vals):
    for v in vals:
        if v is not None:
            return v
    return None

def _norm_report_payload(raw):
    r = raw or {}
    rep = r.get("report") or {}

    insolvencies        = _first(r.get("insolvencies"),        rep.get("insolvencies"))
    paymentDefaults     = _first(r.get("paymentDefaults"),     rep.get("paymentDefaults"),     rep.get("payment_defaults"))
    mercantileEnquiries = _first(r.get("mercantileEnquiries"), rep.get("mercantileEnquiries"), rep.get("mercantile_enquiries"))
    courtJudgements     = _first(r.get("courtJudgements"),     rep.get("courtJudgements"),     rep.get("court_judgements"))
    atoTaxDefault       = _first(r.get("atoTaxDefault"),       rep.get("atoTaxDefault"),       rep.get("ato_tax_default"))
    loans               = _first(r.get("loans"),               rep.get("loans"))
    anzsic              = _first(r.get("anzsic"),              rep.get("anzsic"))

    def _as_list(x):
        if x is None: return []
        return x if isinstance(x, list) else ([x] if x != "No data available" else [])

    return {
        "insolvencies":        _as_list(insolvencies),
        "paymentDefaults":     _as_list(paymentDefaults),
        "mercantileEnquiries": _as_list(mercantileEnquiries),
        "courtJudgements":     _as_list(courtJudgements),
        "atoTaxDefault":       _as_list(atoTaxDefault),
        "loans":               _as_list(loans),
        "anzsic":              anzsic or {},
        "abn": r.get("abn") or rep.get("organisationNumber"),
        "acn": r.get("acn"),
    }

# ---------- Public proxy endpoints (under /drawdown-decision/...) ----------

def dd_fetch_settings(request):
    """
    Pull latest credit decision switches/thresholds from efs_credit_decision (or your DB later).
    For now we call the same upstream your credit_decision service calls: efs_settings -> posted here.
    If you want to duplicate local DB reads, swap this to your own ORM as needed.
    """
    # Reuse the credit decision service if you prefer (set via EFS_CREDIT_DECISION_URL)
    base = os.getenv("EFS_CREDIT_DECISION_URL")
    originator = (request.GET.get("originator") or "").strip()
    if base:
        url = f"{base.rstrip('/')}/credit-decision/fetch_credit_settings/"
        if originator:
            url += f"?{urlencode({'originator': originator})}"
        return _get_json(url)

    # (Optional) If you DON'T want to hop to efs_credit_decision, just return defaults:
    return JsonResponse({
        "originator": originator or None,
        "credit_score_threshold": None,
        "credit_score_switch": False,
        "credit_enquiries_switch": False,
        "court_actions_current_switch": False,
        "court_actions_resolved_switch": False,
        "payment_defaults_current_switch": False,
        "payment_defaults_resolved_switch": False,
        "insolvencies_switch": False,
        "ato_tax_default_switch": False,
    }, status=200)

def dd_fetch_score(request, abn: str):
    base = _bureau_base()
    originator = request.GET.get("originator", "")
    url = f"{base}/fetch_credit_score_data/{quote(abn)}/"
    if originator:
        url += f"?{urlencode({'originator': originator})}"
    return _get_json(url)

def dd_fetch_bureau_report(request, abn: str, tx: str):
    base = _bureau_base()
    paths = [
        f"{base}/fetch_credit_report/{quote(abn)}/{quote(tx)}",
        f"{base}/fetch_credit_report/{quote(abn)}/{quote(tx)}/",
    ]
    status, data = _try_bff_paths(paths)
    if status == 200:
        return JsonResponse(_norm_report_payload(data), status=200)
    return JsonResponse(data, status=status, safe=False)

def dd_fetch_sales_override(request, tx: str):
    originator = request.GET.get("originator", "")
    paths = [
        f"{EFS_SALES_URL}/fetch_sales_override/{quote(tx)}/?{urlencode({'originator': originator})}",
        f"{EFS_SALES_URL}/fetch_sales_override/{quote(tx)}?{urlencode({'originator': originator})}",
    ]
    status, data = _try_bff_paths(paths)
    return JsonResponse(data, status=status, safe=False)






# --- Approve a drawdown (sets state='sales_approved') ---
# --- Approve a drawdown (sets state='sales_approved') ---
# --- Approve a drawdown (sets state='sales_approved') ---
# --- Approve a drawdown (sets state='sales_approved') ---

# --- Approve a drawdown (sets state='sales_approved' AND routes to the right LMS /pay_drawdown/) ---
import json, os
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import requests

from .models import if_DrawdownData, tf_DrawdownData, scf_DrawdownData, IPF_DrawdownData

TIMEOUT = float(os.getenv("EFS_HTTP_TIMEOUT", "8.0"))

# LMS service bases (override via env as needed)
EFS_LMS_INVOICE_FINANCE_URL = os.getenv("EFS_LMS_INVOICE_FINANCE_URL", "http://localhost:8024").rstrip("/")
EFS_LMS_TRADE_FINANCE_URL   = os.getenv("EFS_LMS_TRADE_FINANCE_URL",   "http://localhost:8028").rstrip("/")
EFS_LMS_SCF_URL             = os.getenv("EFS_LMS_SCF_URL",             "http://localhost:8026").rstrip("/")
EFS_LMS_ASSET_FINANCE_URL   = os.getenv("EFS_LMS_ASSET_FINANCE_URL",   "http://localhost:8023").rstrip("/")
EFS_LMS_OVERDRAFT_URL       = os.getenv("EFS_LMS_OVERDRAFT_URL",       "http://localhost:8025").rstrip("/")
EFS_LMS_TERM_LOAN_URL       = os.getenv("EFS_LMS_TERM_LOAN_URL",       "http://localhost:8027").rstrip("/")
# (No explicit IPF service given; we’ll fallback for IPF)

def _http_post_json(url: str, payload: dict):
    r = requests.post(url, json=payload, timeout=TIMEOUT)
    try:
        data = r.json()
    except Exception:
        data = {"body": r.text[:500]}
    return r.status_code, data

def _lms_base_for_model(model_cls):
    """
    Route by the model class the drawdown was found in.
    - if_DrawdownData    -> Invoice Finance LMS (8024)
    - tf_DrawdownData    -> Trade Finance LMS   (8028)
    - scf_DrawdownData   -> SCF LMS             (8026)
    - IPF_DrawdownData   -> (no dedicated service listed) fallback to Invoice Finance LMS (or change here)
    """
    if model_cls is if_DrawdownData:
        return EFS_LMS_INVOICE_FINANCE_URL
    if model_cls is tf_DrawdownData:
        return EFS_LMS_TRADE_FINANCE_URL
    if model_cls is scf_DrawdownData:
        return EFS_LMS_SCF_URL
    if model_cls is IPF_DrawdownData:
        # Adjust if you spin up a dedicated IPF LMS service; for now, fallback:
        return EFS_LMS_INVOICE_FINANCE_URL
    return None

@csrf_exempt
def dd_approve(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        data = {}

    tx = (data.get("transaction_id") or request.POST.get("transaction_id") or "").strip()
    if not tx:
        return JsonResponse({"success": False, "error": "transaction_id required"}, status=400)

    # locate record across product tables
    obj = None
    model_cls = None
    for Model in (if_DrawdownData, tf_DrawdownData, scf_DrawdownData, IPF_DrawdownData):
        found = Model.objects.filter(transaction_id=tx).first()
        if found:
            obj = found
            model_cls = Model
            break

    if not obj:
        return JsonResponse({"success": False, "error": "transaction not found"}, status=404)

    # 1) Update local state
    obj.state = "sales_approved"
    obj.save(update_fields=["state"])

    # 2) Route to the correct LMS service
    lms_base = _lms_base_for_model(model_cls)
    if not lms_base:
        return JsonResponse({
            "success": True,
            "updated": {"model": model_cls.__name__, "transaction_id": tx, "new_state": "sales_approved"},
            "lms_post": {"ok": False, "status": 501, "data": {"error": "No LMS mapping for this model"}}
        }, status=207)

    lms_payload = {
        "abn": obj.abn,  # legacy pay_drawdown requires at least ABN
        # harmless extras (LMS can ignore if it doesn't use them)
        "transaction_id": obj.transaction_id,
        "originator": obj.originator,
        "product": obj.product,
        "amount_requested": (str(obj.amount_requested) if obj.amount_requested is not None else None),
    }
    lms_status, lms_data = _http_post_json(f"{lms_base}/pay_drawdown/", lms_payload)

    ok = (200 <= lms_status < 300)
    return JsonResponse({
        "success": True,
        "updated": {"model": model_cls.__name__, "transaction_id": tx, "new_state": "sales_approved"},
        "lms_post": {"ok": ok, "status": lms_status, "data": lms_data},
    }, status=200 if ok else 207)
