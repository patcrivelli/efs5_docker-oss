# efs_sales/core/views.py
import json
import uuid
import logging
from types import SimpleNamespace

import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET  # <-- added for new GET-only endpoints

logger = logging.getLogger(__name__)

# ---------------------------
# Service URL helpers
# ---------------------------
def _profile_base() -> str:
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

def _aggregate_base() -> str:
    # application_aggregate (you said port 8016)
    return getattr(settings, "EFS_APPLICATION_AGGREGATE_BASE_URL", "http://localhost:8016").rstrip("/")

def _apis_base() -> str:
    return getattr(settings, "EFS_APIS_BASE_URL", "http://localhost:8017").rstrip("/")

def _bureau_base() -> str:
    return getattr(settings, "EFS_DATA_BUREAU_BASE_URL", "http://localhost:8018").rstrip("/")

def _financial_base() -> str:
    # point this at your new service (e.g. http://localhost:8019)
    return getattr(settings, "EFS_DATA_FINANCIAL_URL", "http://localhost:8019").rstrip("/")

def _bank_base() -> str:
    return getattr(settings, "EFS_DATA_BANKSTATEMENTS_BASE_URL", "http://localhost:8020").rstrip("/")

def _crosssell_base() -> str:
    return getattr(settings, "EFS_CROSSSELL_BASE_URL", "http://localhost:8021").rstrip("/")


def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def _get_json(url: str, params: dict | None = None, timeout: int = 10):
    try:
        r = requests.get(url, params=params or {}, headers=_api_key_header(), timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        logger.exception("GET %s failed (params=%s)", url, params)
        return None

def _post_json(url: str, payload: dict, timeout: int = 10):
    try:
        r = requests.post(url, json=payload, headers=_api_key_header(), timeout=timeout)
        content_type = r.headers.get("Content-Type", "")
        if "application/json" in content_type:
            body = r.json()
        else:
            body = {"status": "error", "message": r.text}
        return r.status_code, body
    except Exception as e:
        logger.exception("POST %s failed", url)
        return 500, {"status": "error", "message": str(e)}

def _proxy_html(remote_url: str, params: dict | None = None, timeout: int = 10) -> HttpResponse:
    try:
        r = requests.get(remote_url, params=params or {}, headers=_api_key_header(), timeout=timeout)
        r.raise_for_status()
        return HttpResponse(r.text, content_type=r.headers.get("Content-Type", "text/html; charset=utf-8"))
    except Exception:
        logger.exception("Proxy HTML GET %s failed", remote_url)
        return HttpResponse("<p style='color:#b00'>Failed to load modal.</p>", status=502)

# ---------------------------
# left side panel for Originators  
# ---------------------------
def fetch_originators():
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        data = r.json()
        return data.get("originators", data if isinstance(data, list) else [])
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []

def base_context(request):
    originators = fetch_originators()
    selected_originator = None
    selected_id = request.GET.get("originators")
    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected_originator = o
                break
    return {"originators": originators, "selected_originator": selected_originator}



#--------#--------#--------#--------#--------

#Kanban board code 

#--------#--------#--------#--------#--------




# efs_sales/core/views.py


import logging
from django.shortcuts import render

from .services import fetch_aggregate_applications  # core/services.py
# from .context import base_context  # wherever your base_context lives

logger = logging.getLogger(__name__)


def _state_to_column(state: str | None) -> str:
    s = (state or "").lower().strip()

    # Sales stage
    if s == "sales_review":
        return "sales"

    # Operations stage (if you use it)
    if s.startswith("ops") or s.startswith("operations"):
        return "operations"

    # Risk stage
    if s == "risk_review":
        return "risk"

    # ✅ APPROVED BY RISK → FINANCE
    if s == "risk_approved":
        return "finance"

    # Safe default
    return "sales"



# efs_sales/core/views.py

import logging
from django.shortcuts import render

from .services import fetch_aggregate_applications  # core/services.py

logger = logging.getLogger(__name__)


import logging
from django.shortcuts import render

from .services import fetch_aggregate_applications  # core/services.py
# from .context import base_context  # wherever your base_context lives

logger = logging.getLogger(__name__)


def sales_home(request):
    context = base_context(request)

    try:
        applications = fetch_aggregate_applications(timeout=5)
        logger.warning(f"[SALES_HOME] fetched {len(applications)} aggregate apps")
    except Exception:
        logger.exception("[SALES_HOME] aggregate fetch failed")
        applications = []

    # ---------------------------
    # ✅ Filter by selected originator (unless "originators" = All)
    # ---------------------------
    selected = context.get("selected_originator")  # dict or None
    selected_id = str(selected.get("id")) if isinstance(selected, dict) and selected.get("id") is not None else None
    selected_name = (selected.get("originator") or "").strip().lower() if isinstance(selected, dict) else ""

    # Show all only if the dropdown special option is literally "originators"
    show_all = (selected_name == "originators")

    if selected and not show_all:
        def _matches_selected(app: dict) -> bool:
            # --- ID match (only if the app payload has an originator id) ---
            app_originator_id = app.get("originator_id") or app.get("originatorId")

            # If originator is nested dict, safely extract id
            originator_val = app.get("originator")
            if isinstance(originator_val, dict):
                app_originator_id = app_originator_id or originator_val.get("id")

            if app_originator_id is not None and selected_id is not None:
                return str(app_originator_id) == selected_id

            # --- Name match fallback (handles originator being a string) ---
            app_originator_name = originator_val
            if isinstance(app_originator_name, dict):
                app_originator_name = app_originator_name.get("originator") or app_originator_name.get("name")

            app_originator_name = (str(app_originator_name or "")).strip().lower()
            return app_originator_name == selected_name

        applications = [a for a in applications if _matches_selected(a)]
        logger.warning(
            f"[SALES_HOME] after originator filter: {len(applications)} apps "
            f"(selected_id={selected_id}, selected_name={selected_name})"
        )

    # ---------------------------
    # ✅ Updated kanban split (per your rules)
    # ---------------------------
    sales_applications = []
    operations_applications = []
    risk_applications = []
    finance_applications = []

    EXCLUDED = {"closed_funded", "closed_rejected"}

    for app in applications:
        state = (app.get("state") or "").lower().strip()

        # ✅ Do not display closed items at all
        if state in EXCLUDED:
            continue

        # Sales column
        if state in {"sales_review", "sales_just_in"}:
            sales_applications.append(app)

        # Risk column
        elif state == "risk_review":
            risk_applications.append(app)

        # Operations column
        elif state == "risk_approved":
            operations_applications.append(app)

        # Finance column
        elif state == "operations_approved":
            finance_applications.append(app)

        # Safe default: keep visible in Sales if unknown/new state
        else:
            sales_applications.append(app)

    context.update({
        "sales_applications": sales_applications,
        "operations_applications": operations_applications,
        "risk_applications": risk_applications,
        "finance_applications": finance_applications,
    })

    return render(request, "sales_home.html", context)



# ---------------------------
# Aggregate API → rows for template
# ---------------------------
from types import SimpleNamespace
import logging
logger = logging.getLogger(__name__)

def _wrap_for_template(items: list[dict]) -> list[dict]:
    """
    Normalize each aggregate item to the shape expected by the template:
    {
      "id": ...,
      "application": SimpleNamespace(...abn, originator, product, state, transaction_id...),
      "credit_score": "N/A",
      "threshold_score": None,
      "creditData": {}
    }
    Supports either a flat app dict or {"application": {...}}.
    """
    out = []
    for raw in items or []:
        try:
            if isinstance(raw, dict) and isinstance(raw.get("application"), dict):
                base = raw["application"]
            elif isinstance(raw, dict):
                base = raw
            else:
                # Skip non-dicts
                continue

            app = SimpleNamespace(**base)
            out.append({
                "id": base.get("id") or base.get("pk") or base.get("transaction_id"),
                "application": app,
                "credit_score": "N/A",
                "threshold_score": None,
                "creditData": {},
            })
        except Exception:
            logger.exception("Failed to wrap aggregate row: %r", raw)
    return out


def _fetch_apps_any_product(states: list[str], originator_name: str | None):
    """
    Calls application_aggregate and normalizes the payload to a list of app dicts.
    Accepts these shapes:
      - [ {...}, {...} ]
      - { "applications": [ ... ] }
      - { "results": [ ... ] } or { "items": [ ... ] } or { "data": [ ... ] }
      - single object { ... }  (will be wrapped into a list)
      - { "application": { ... } }  (will be wrapped into a list)
    """
    url = f"{_aggregate_base()}/api/applications/"
    params = {"states": ",".join(states)}
    if originator_name:
        params["originator"] = originator_name

    data = _get_json(url, params=params)
    items: list[dict] = []

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # try common list keys
        for key in ("applications", "results", "items", "data"):
            val = data.get(key)
            if isinstance(val, list):
                items = val
                break
        else:
            # single object or {"application": {...}}
            if isinstance(data.get("application"), dict):
                items = [data["application"]]
            else:
                items = [data]
    else:
        logger.warning("Unexpected aggregate payload type: %s", type(data))
        items = []

    return _wrap_for_template(items)


def _filter_by_product(rows: list[dict], keys: set[str]) -> list[dict]:
    """
    Keep a row if its product string contains ANY of the given keys (case-insensitive).
    """
    needles = {k.strip().lower() for k in keys if k}
    out = []
    for row in rows:
        prod = (getattr(row["application"], "product", "") or "").lower()
        if any(n in prod for n in needles):
            out.append(row)
    return out

def _filter_by_state(rows: list[dict], states: list[str]) -> list[dict]:
    allowed = {s.lower() for s in states}
    out = []
    for row in rows:
        st = (getattr(row["application"], "state", "") or "").lower()
        if st in allowed:
            out.append(row)
    return out

# ---------------------------
# Pages
# ---------------------------

def create_originator(request):
    if request.method == "POST":
        payload = {"originator": request.POST.get("originator_name"),
                   "created_by": request.POST.get("username")}
        try:
            r = requests.post(f"{_profile_base()}/api/originators/create/",
                              json=payload, headers=_api_key_header(), timeout=5)
            if r.status_code not in (200, 201):
                logger.error("Originator create failed: %s %s", r.status_code, r.text)
        except Exception:
            logger.exception("Error calling efs_profile create originator")
    return redirect("sales_home")





from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def sales_view(request):
    ctx = base_context(request)
    org_name = (ctx.get("selected_originator") or {}).get("originator")

    # Ask aggregate for “review-ish” and “approved-ish”.
    review = _fetch_apps_any_product(["sales_review", "sales_just_in"], org_name)
    approved = _fetch_apps_any_product(["risk_review", "approved"], org_name)

    # If the aggregate endpoint doesn't implement states filtering, fall back to local filtering
    if review and all(getattr(r["application"], "state", None) for r in review):
        review = _filter_by_state(review, ["sales_review", "sales_just_in"])
    if approved and all(getattr(r["application"], "state", None) for r in approved):
        approved = _filter_by_state(approved, ["risk_review", "approved"])

    IF  = {"invoice finance", "if"}
    TF  = {"trade finance", "tf"}
    SCF = {"supply chain finance", "scf"}
    IPF = {"insurance premium funding", "insurance premiums", "ipf"}

    ctx["review_applications_with_scores"]  = _filter_by_product(review, IF)
    ctx["approved_applications_with_scores"] = _filter_by_product(approved, IF)

    ctx["review_tf_applications_with_scores"]  = _filter_by_product(review, TF)
    ctx["approved_tf_applications_with_scores"] = _filter_by_product(approved, TF)

    ctx["review_scf_applications_with_scores"]  = _filter_by_product(review, SCF)
    ctx["approved_scf_applications_with_scores"] = _filter_by_product(approved, SCF)

    ctx["review_ipf_applications_with_scores"]  = _filter_by_product(review, IPF)
    ctx["approved_ipf_applications_with_scores"] = _filter_by_product(approved, IPF)

    return render(request, "sales.html", ctx)

# ---------------------------
# Ingest from client_app → forward to application_aggregate
# ---------------------------
def _aggregate_ingest_path() -> str:
    # You can expose this as an env var if your aggregate uses a different route
    return f"{_aggregate_base()}/api/applications/ingest/"

def _aggregate_fallback_post_path() -> str:
    return f"{_aggregate_base()}/api/applications/"

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def receive_application_data(request):
    """Receiver endpoint for ApplicationData from client_app → forwards to application_aggregate."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body or "{}")
        logger.debug("📌 Received Invoice Finance application data:\n%s", json.dumps(data, indent=2))

        # Ensure transaction_id and default state
        data.setdefault("transaction_id", str(uuid.uuid4()))
        data.setdefault("state", "sales_just_in")

        # Prefer ingest endpoint; fall back to generic POST if needed
        status, body = _post_json(_aggregate_ingest_path(), data)
        if status in (404, 405):  # not found/not allowed → try fallback
            status, body = _post_json(_aggregate_fallback_post_path(), data)

        # Normalize response to your existing contract
        if not isinstance(body, dict):
            body = {"status": "error", "message": "Unexpected response from aggregate."}

        return JsonResponse(body, status=201 if body.get("status") == "success" else max(status, 400))

    except Exception as e:
        logger.exception("🔥 Exception in receive_application_data")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# ---------------------------
# Proxies for efs credit decision service  (and efs_buruea_data servcice???) 
# ---------------------------
    

def fetch_credit_score_data(request, abn: str):
    """Proxy to efs_data_bureau so the UI can keep calling /fetch_credit_score_data/<abn>/."""
    params = {}
    originator = request.GET.get("originator")
    if originator:
        params["originator"] = originator
    url = f"{_bureau_base()}/api/credit-score/{abn}/"
    data = _get_json(url, params=params) or {}
    return JsonResponse(data)


from django.views.decorators.http import require_GET
from django.http import JsonResponse
import requests

@require_GET
def fetch_credit_report(request, abn: str, tx: str):
    """
    BFF → data_bureau. Try both API and non-API shapes, with/without slash.
    Pass through status and JSON.
    """
    base = _bureau_base()
    candidates = [
        f"{base}/api/fetch_credit_report/{abn}/{tx}",
        f"{base}/api/fetch_credit_report/{abn}/{tx}/",
        f"{base}/fetch_credit_report/{abn}/{tx}",
        f"{base}/fetch_credit_report/{abn}/{tx}/",
    ]
    params = {}
    if request.GET.get("originator"):
        params["originator"] = request.GET.get("originator")

    last_err = None
    for url in candidates:
        try:
            r = requests.get(url, params=params, headers=_api_key_header(), timeout=10)
            # try to return JSON regardless of status
            try:
                payload = r.json()
            except ValueError:
                payload = {"error": "Upstream did not return JSON", "raw": (r.text or "")[:500]}
            return JsonResponse(payload, status=r.status_code, safe=False)
        except requests.RequestException as e:
            last_err = e
            continue
    # nothing worked
    return JsonResponse({"error": "bureau upstream unavailable", "detail": str(last_err)}, status=502)


@require_GET
def fetch_sales_override(request, tx: str):
    """
    BFF → data_bureau: return latest normalized override row for tx.
    """
    base = _bureau_base()
    candidates = [
        f"{base}/api/fetch_sales_override_current/{tx}",
        f"{base}/api/fetch_sales_override_current/{tx}/",
    ]
    params = {}
    if request.GET.get("originator"):
        params["originator"] = request.GET.get("originator")

    last_err = None
    for url in candidates:
        try:
            r = requests.get(url, params=params, headers=_api_key_header(), timeout=10)
            try:
                payload = r.json()
            except ValueError:
                payload = {"error": "Upstream did not return JSON", "raw": (r.text or "")[:500]}
            return JsonResponse(payload, status=r.status_code, safe=False)
        except requests.RequestException as e:
            last_err = e
            continue
    return JsonResponse({"error": "bureau upstream unavailable", "detail": str(last_err)}, status=502)




def modal_apis(request):
    """
    /sales/modal/apis?abn=...&tx=...&originator=...&product=...
    Proxies HTML fragment from efs_apis (:8017).
    """
    upstream = f"{_apis_base()}/modal/apis"
    try:
        r = requests.get(upstream, params=request.GET, timeout=10)
        # Pass through HTML exactly as returned by efs_apis
        ctype = r.headers.get("Content-Type", "text/html; charset=utf-8")
        return HttpResponse(r.text, status=r.status_code, content_type=ctype)
    except requests.RequestException:
        # keep your existing 502 behavior
        return HttpResponse("<p style='color:#b00'>Failed to load modal.</p>", status=502)
    

def modal_abn(request):
    params = {"abn": request.GET.get("abn"), "tx": request.GET.get("tx")}
    return _proxy_html(f"{_bureau_base()}/modal/abn", params)

def modal_credit_score(request):
    params = {"abn": request.GET.get("abn"), "tx": request.GET.get("tx")}
    return _proxy_html(f"{_bureau_base()}/modal/credit-score", params)

from django.http import HttpResponse
import requests
from django.views.decorators.http import require_GET

# Assuming _upstream is defined elsewhere (e.g., in a utility module)
# Assuming _upstream gets the correct base URL

@require_GET
def modal_bank_statements(request):
    """
    Handles a GET request to display a modal with bank statements.
    It proxies the request to an upstream service defined by the EFS_DATA_BANKSTATEMENTS_URL setting.
    This function maintains the functionality of passing 'abn' (or any other GET parameter)
    to the upstream service.
    """
    try:
        # 1. Get the base URL from settings/config using the helper function
        base = _upstream("EFS_DATA_BANKSTATEMENTS_URL")
        
        # 2. Make the GET request, passing ALL parameters from request.GET
        #    This covers the 'abn' parameter from the first function's logic
        #    and the general parameters from the second function's logic.
        r = requests.get(
            f"{base}/modal/bank-statements", 
            params=request.GET, 
            timeout=100
        )
        
        # 3. Return the upstream response directly
        return HttpResponse(
            r.text, 
            status=r.status_code,
            content_type=r.headers.get("content-type", "text/html")
        )
        
    except requests.exceptions.RequestException as e:
        # Handle connection/timeout errors gracefully
        return HttpResponse(f"Error connecting to bank statements service: {e}", status=503)


def modal_financials(request):
    params = {
        "abn": request.GET.get("abn") or "",
        "acn": request.GET.get("acn") or "",
        "tx":  request.GET.get("tx")  or "",
    }
    return _proxy_html(f"{_financial_base()}/modal/financials/", params)
    #                                            ✅ trailing slash



def modal_ppsr(request):
    params = {"tx": request.GET.get("tx")}
    return _proxy_html(f"{_financial_base()}/modal/ppsr", params)

def modal_xsell(request):
    params = {"tx": request.GET.get("tx")}
    return _proxy_html(f"{_crosssell_base()}/modal/x-sell", params)

# core/views.py in efs_sales
import os, requests
from django.http import HttpResponse

def modal_terms(request):
    tx = request.GET.get("tx", "")
    # Point to the other service
    base = os.getenv("EFS_APPLICATION_URL", "http://localhost:8016")
    upstream = f"{base.rstrip('/')}/application/modal/terms?tx={tx}"

    r = requests.get(upstream, timeout=10)
    return HttpResponse(r.text, status=r.status_code,
                        content_type=r.headers.get("content-type", "text/html"))


# --- product lookup by tx id ---
def get_product_by_transaction_id(request):
    tx = request.GET.get("transaction_id")
    if not tx:
        return JsonResponse({"error": "transaction_id is required"}, status=400)

    # Try a direct-by-id endpoint first; fall back to filter
    url_direct = f"{_aggregate_base()}/api/applications/{tx}/"
    res = _get_json(url_direct)
    if not res:
        res = _get_json(f"{_aggregate_base()}/api/applications/", params={"transaction_id": tx})

    if not res:
        return JsonResponse({"error": "not found"}, status=404)

    # Support both raw-object or {"application": {...}} or list
    app = res.get("application", res) if isinstance(res, dict) else res[0]
    return JsonResponse({"product": app.get("product")})


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt  # keep if you're posting from JS without CSRF token; otherwise remove and send csrftoken
def approve_application(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload = json.loads(request.body or "{}")
        tx = payload.get("transaction_id")
        new_state = payload.get("new_state")
        product = payload.get("product")

        if not (tx and new_state and product):
            return JsonResponse({"error": "transaction_id, new_state, and product are required"}, status=400)

        # Optional: save an override/note locally (only if you *really* still need it here)
        # from .models import SalesOverride
        # SalesOverride.objects.create(
        #     transaction_id=tx,
        #     changed_by=getattr(getattr(request, "user", None), "username", "sales-ui"),
        #     new_state=new_state,
        #     product=product,
        # )

        # Forward the state change to the aggregate
        patch_url = f"{_aggregate_base()}/api/applications/{tx}/state/"
        status_code, body = _post_json(patch_url, {
            "state": new_state,
            "product": product,
            "source": "sales",
        })
        if status_code in (404, 405):
            # Fallback shape if your aggregate doesn't support the /{tx}/state path
            status_code, body = _post_json(f"{_aggregate_base()}/api/applications/state/", {
                "transaction_id": tx,
                "state": new_state,
                "product": product,
                "source": "sales",
            })

        success = isinstance(body, dict) and (body.get("status") == "success" or body.get("ok") is True)
        return JsonResponse({"success": bool(success), "raw": body}, status=200 if success else max(status_code, 400))

    except Exception as e:
        logger.exception("approve_application failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# efs_sales/core/views.py  (add near other proxies)
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def apis_orchestrate(request):
    """
    Browser -> BFF -> efs_apis/core/api/orchestrations/run
    Accepts either JSON body or query string. Returns JSON.
    """
    target = f"{_apis_base()}/api/orchestrations/run"
    try:
        if request.method == "POST":
            # forward JSON body as-is
            payload = json.loads(request.body or "{}")
            status, body = _post_json(target, payload)
            return JsonResponse(body or {}, status=max(status, 200))
        else:
            # GET passthrough (rare)
            data = _get_json(target, params=request.GET.dict()) or {}
            return JsonResponse(data, status=200)
    except Exception as e:
        logger.exception("apis_orchestrate failed")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# ======================================================================
# Start Financials modal & data and displays
# ======================

TIMEOUT = getattr(settings, "REQUESTS_DEFAULT_TIMEOUT", 8)

@require_GET
def proxy_modal_financials(request):
    params = {
        "abn": request.GET.get("abn", ""),
        "acn": request.GET.get("acn", ""),
        "tx":  request.GET.get("tx", ""),
    }
    r = requests.get(
        f"{_financial_base()}/modal/financials/",
        params=params,
        headers=_api_key_header(),
        timeout=TIMEOUT
    )
    r.raise_for_status()
    return HttpResponse(
        r.text,
        content_type=r.headers.get("Content-Type", "text/html; charset=utf-8")
    )

from django.views.decorators.http import require_GET
from django.http import JsonResponse
import requests
from urllib.parse import quote

# I’m assuming these already exist in this file, since you’re using them now:
# - _financial_base()  -> base URL for efs_data_financial service, e.g. "http://efs-data-financial"
# - _api_key_header()  -> whatever auth header you attach today
# - TIMEOUT            -> request timeout seconds


def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


@require_GET
def fetch_financial_data(request, abn: str):
    """
    BFF for the Financials modal preload.

    NOTE: `abn` in the URL is actually a generic company identifier.
    It might be:
      - an ABN (11 digits)
      - an ACN (9 digits)
    The frontend just passes whatever ID it has.

    We now forward that ID straight to the data service
    /fetch_financial_data/<company_id>/,
    which already knows how to handle ABN-or-ACN.
    """

    company_raw = (abn or "").strip()
    if not company_raw:
        return JsonResponse({"error": "Company ID is required"}, status=400)

    # normalize just digits (this matches what the downstream view expects)
    company_digits = _digits_only(company_raw)
    if not company_digits:
        return JsonResponse({"error": "Invalid company identifier"}, status=400)

    # Build the upstream URL, path-style, NOT query param,
    # and do NOT force it into ?abn=
    upstream_url = f"{_financial_base()}/fetch_financial_data/{quote(company_digits)}/"

    try:
        r = requests.get(
            upstream_url,
            headers=_api_key_header(),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return JsonResponse(
            {"error": f"data service error: {e}"},
            status=502
        )

    # mirror old behaviour for non-OK
    if r.status_code == 404:
        return JsonResponse({"error": "not found"}, status=404)
    if not r.ok:
        return JsonResponse(
            {"error": f"data service {r.status_code}: {r.text[:200]}"},
            status=502
        )

    # just proxy the JSON blob from data service straight back to the browser
    return JsonResponse(r.json(), status=200)



# ======================================================================
# End Financials modal & data and displays
# =============================




# efs_sales/core/views.py
def _credit_decision_base() -> str:
    return getattr(settings, "EFS_CREDIT_DECISION_BASE_URL", "http://localhost:8022").rstrip("/")








# ======================================================================
# New: BFF proxies for Buruea data 
# ======================================================================

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# uses your existing _apis_base(), _post_json
@csrf_exempt
def apis_fetch_bureau_data(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST required"}, status=405)
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "invalid json"}, status=400)

    status, body = _post_json(f"{_apis_base()}/apis/fetch-bureau-data/", payload)
    return JsonResponse(body or {}, status=max(status, 200))



def modal_application_details(request):
    tx = request.GET.get("tx")
    url = f"{_apis_base()}/application-details"
    data = _get_json(url, params={"tx": tx}) or {}
    return JsonResponse(data)




# ======================================================================
# New: BFF proxies for bankstatements data modal display
# ======================================================================








import os, logging, requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

log = logging.getLogger(__name__)
DEFAULT_TIMEOUT = float(os.getenv("CORE_PROXY_TIMEOUT", "12"))
BANK_BASE_ENV = "EFS_DATA_BANKSTATEMENTS_URL"  # e.g. http://localhost:8018


from django.conf import settings

def _upstream(base_env_var: str) -> str:
    # Look in Django settings first
    configured = getattr(settings, base_env_var, None)
    if configured:
        return configured.rstrip("/")

    # Fallback: environment variable
    base = os.getenv(base_env_var, "").rstrip("/")
    if not base:
        raise RuntimeError(f"Missing upstream base for {base_env_var}")
    return base


def _forward_headers(request):
    h = {
        "Accept": request.headers.get("Accept", "*/*"),
        "User-Agent": request.headers.get("User-Agent", "efs-core-proxy"),
    }
    if "Authorization" in request.headers:
        h["Authorization"] = request.headers["Authorization"]
    return h



@require_GET
def display_bank_account_data(request, abn: str):
    base = _upstream(BANK_BASE_ENV)
    abn = _digits_only(abn)                 # keep this
    url = f"{base}/display_bank_account_data/{abn}/"
    r = requests.get(url, headers=_forward_headers(request), timeout=DEFAULT_TIMEOUT)
    return JsonResponse(r.json(), status=r.status_code, safe=False)

@require_GET
def bankstatements_summary(request, abn: str):
    base = _upstream(BANK_BASE_ENV)
    abn = _digits_only(abn)                 # add this here too
    url = f"{base}/bankstatements/summary/{abn}/"
    r = requests.get(url, params=request.GET, headers=_forward_headers(request), timeout=DEFAULT_TIMEOUT)
    return JsonResponse(r.json(), status=r.status_code, safe=False)





import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Put this in efs_sales settings:
# BANKSTATEMENTS_SERVICE_BASE_URL = "http://localhost:800X"  # the efs_data_bankstatements service

@csrf_exempt
@require_POST
def proxy_bankstatements_analyse_ai(request, abn: str):
    base = getattr(settings, "EFS_DATA_BANKSTATEMENTS_BASE_URL", "").rstrip("/")
    if not base:
        return JsonResponse({"success": False, "message": "Missing BANKSTATEMENTS_SERVICE_BASE_URL"}, status=500)

    upstream_url = f"{base}/bankstatements/analyse-ai/{abn}/"

    # Forward JSON body
    try:
        body = request.body.decode("utf-8") if request.body else "{}"
        json.loads(body)  # validate
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    try:
        r = requests.post(
            upstream_url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=60,
        )
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream request failed: {e}"}, status=502)

    # If upstream didn't return JSON, return a clean error
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/json" not in ctype:
        return JsonResponse(
            {"success": False, "message": f"Upstream error: non-JSON response (status {r.status_code})"},
            status=502,
        )

    try:
        payload = r.json()
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)

    return JsonResponse(payload, status=r.status_code)






# POST BANKSTATEMENTS NOTES TO EFS_DATA_FINANCIAL SERVICE / FINANCIAL STATEMENT NTOES DATA MODEL
import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # if you want, but usually keep CSRF on for same-origin

DEFAULT_TIMEOUT = 20

def _forward_headers(request):
    # keep cookies/session behavior consistent
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    return h

@require_POST
def proxy_save_financial_notes(request):
    base = getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "").rstrip("/")
    if not base:
        return JsonResponse({"success": False, "message": "Upstream base URL not configured"}, status=500)

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    url = f"{base}/api/financial-statement-notes/save/"
    try:
        r = requests.post(
            url,
            json=body,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream request failed: {e}"}, status=502)

    # ensure JSON
    try:
        data = r.json()
    except Exception:
        return JsonResponse({"success": False, "message": "Upstream returned non-JSON"}, status=502)

    return JsonResponse(data, status=r.status_code, safe=False)











# ======================================================================
# New: BFF proxies for PPSR data modal display
# ======================================================================





# efs_sales/core/views.py
import os
import logging
import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

FINANCIALS_BASE = os.getenv("EFS_FINANCIALS_URL", "http://localhost:8019").rstrip("/")

@require_GET
def proxy_ppsr_modal(request):
    """
    /sales/modal/ppsr?tx=...  ->  http://localhost:8019/modal/ppsr/?tx=...
    Proxies the HTML fragment from efs_data_financial.
    """
    upstream = f"{FINANCIALS_BASE}/modal/ppsr/"
    try:
        r = requests.get(upstream, params=request.GET, timeout=10)
        content_type = r.headers.get("Content-Type", "text/html; charset=utf-8")
        return HttpResponse(r.text, status=r.status_code, content_type=content_type)
    except requests.RequestException:
        logger.exception("Proxy HTML GET %s failed", upstream)
        return HttpResponse("Bad Gateway", status=502)

@require_GET
def proxy_ppsr_for_abn(request, abn: str):
    """
    /sales/fetch_ppsr_data/<abn>/  ->  http://localhost:8019/api/ppsr/<abn>/
    Proxies the JSON list from efs_data_financial.
    """
    upstream = f"{FINANCIALS_BASE}/api/ppsr/{abn}/"
    try:
        r = requests.get(upstream, timeout=10)
        # best-effort pass-through of JSON and status
        try:
            payload = r.json()
        except ValueError:
            payload = {"error": "Upstream did not return JSON"}
        return JsonResponse(payload, status=r.status_code, safe=False)
    except requests.RequestException:
        logger.exception("Proxy JSON GET %s failed", upstream)
        return JsonResponse({"error": "Bad Gateway"}, status=502)





# ======================================================================
# New: BFF proxies for Terms data modal display
# ======================================================================




# efs_sales/core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


@require_GET
def terms_fetch_proxy(request):
    """
    /sales/application/terms/fetch/?abn=... (or ?tx=...)
    -> proxies to application_aggregate on 8016
    """
    base = _aggregate_base()
    # prefer abn; fall back to tx (your aggregate view supports both)
    params = {}
    if request.GET.get("abn"): params["abn"] = request.GET.get("abn")
    if request.GET.get("tx"):  params["tx"]  = request.GET.get("tx")

    try:
        r = requests.get(f"{base}/application/terms/fetch/", params=params,
                         headers=_api_key_header(), timeout=10)
        # pass through JSON/status
        try:
            payload = r.json()
        except ValueError:
            payload = {"error": "Upstream did not return JSON", "raw": r.text}
        return JsonResponse(payload, status=r.status_code, safe=False)
    except requests.RequestException:
        logger.exception("terms_fetch_proxy failed")
        return JsonResponse({"error": "Bad Gateway"}, status=502)

@csrf_exempt  # keep if you don't send CSRF token from the fragment
@require_POST
def terms_save_proxy(request):
    """
    /sales/application/terms/save/  (POST JSON body)
    -> proxies to application_aggregate on 8016
    """
    base = _aggregate_base()
    url = f"{base}/application/terms/save/"
    try:
        # forward raw body/headers
        r = requests.post(url, data=request.body,
                          headers={"Content-Type": "application/json", **_api_key_header()},
                          timeout=100)
        # normalize return type
        try:
            payload = r.json()
            return JsonResponse(payload, status=r.status_code, safe=isinstance(payload, (dict, list)))
        except ValueError:
            return HttpResponse(r.text, status=r.status_code,
                                content_type=r.headers.get("content-type", "text/plain"))
    except requests.RequestException:
        logger.exception("terms_save_proxy failed")
        return JsonResponse({"status": "error", "message": "Bad Gateway"}, status=502)
















#--------- Start of Agents service BFF code------------
#--------- Start of Agents service BFF code------------
#--------- Start of Agents service BFF code------------
#--------- Start of Agents service BFF code------------
#--------- Start of Agents service BFF code------------



import os
import json
import requests
from urllib.parse import quote

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_GET


def _upstream(setting_name: str, default_env: str = "") -> str:
    """
    Resolve upstream base URL from Django settings or env vars.
    Falls back to default_env if not set.
    """
    val = (getattr(settings, setting_name, "") or os.getenv(setting_name, default_env) or "").rstrip("/")
    if not val:
        raise RuntimeError(f"Missing upstream base for {setting_name}")
    return val


def _agents_base() -> str:
    """
    Backward-compatible base resolver:
    1) Django setting AGENTS_SERVICE_BASE (existing pattern)
    2) env AGENTS_SERVICE_BASE
    3) env EFS_AGENTS_URL (new pattern)
    4) localhost default
    """
    return (
        getattr(settings, "AGENTS_SERVICE_BASE", None)
        or os.getenv("AGENTS_SERVICE_BASE")
        or os.getenv("EFS_AGENTS_URL", "http://127.0.0.1:8015")
    ).rstrip("/")


def _timeout() -> int:
    try:
        return int(os.getenv("DATA_SERVICE_TIMEOUT", "20"))
    except Exception:
        return 20


# ---------- Modal (GET) ----------
import requests
from django.http import HttpResponse

@ensure_csrf_cookie
@require_GET
def modal_tasks(request):
    AGENTS_BASE = _agents_base()
    tx = request.GET.get("tx", "")
    abn = request.GET.get("abn", "")

    params = {"abn": abn, "tx": tx, "transaction_id": tx}
    upstream = f"{AGENTS_BASE}/modal/sales-agents/"

    try:
        r = requests.get(upstream, params=params, timeout=6)
    except requests.RequestException as e:
        return HttpResponse(
            f"<h3>Agents service unavailable</h3><pre>{e}</pre>",
            status=502,
            content_type="text/html",
        )

    return HttpResponse(
        r.text,
        status=r.status_code,
        content_type=r.headers.get("content-type", "text/html; charset=utf-8"),
    )


# ---------- Agents BFF (POST) ----------
# KEEP NAME: run_agent_analysis
@csrf_exempt
def run_agent_analysis(request):
    AGENTS_BASE = _agents_base()
    TIMEOUT = _timeout()

    # ---- CORS preflight ----
    if request.method == "OPTIONS":
        resp = JsonResponse({"ok": True})
        resp["Access-Control-Allow-Origin"] = "*"
        resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return resp

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed"}, status=405)

    # ---- Parse body ----
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    # New agents endpoint you want to call
    url = f"{AGENTS_BASE}/run-agent-analysis/"

    try:
        r = requests.post(url, json=body, timeout=TIMEOUT)

        try:
            js = r.json()
        except Exception:
            return JsonResponse(
                {"ok": False, "error": r.text or "Invalid JSON from agents"},
                status=502
            )

        return JsonResponse(js, status=r.status_code)

    except requests.RequestException as e:
        return JsonResponse({"ok": False, "error": f"Agents upstream error: {e}"}, status=502)


# ---------- Guard ----------
def _guard_financial_summary_on_sales(request, abn: str):
    return JsonResponse({
        "ok": False,
        "error": "This endpoint belongs to the financials service (8019), "
                 "but was called on sales (8001). Remove any browser fetches "
                 "to /financial_summary/… from the Sales UI."
    }, status=410)








#--------- End of Agents service BFF code------------
#--------- End of Agents service BFF code------------
#--------- End of Agents service BFF code------------
#--------- End of Agents service BFF code------------
#--------- End of Agents service BFF code------------
#--------- End of Agents service BFF code------------








# manually create a deal
# manually create a deal
# manually create a deal
# manually create a deal


import json
import os
import uuid
import requests
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

@require_GET
def create_deal_modal(request):
    """
    Returns the create-deal modal HTML fragment.
    """
    return render(request, "create_deal_modal.html")

@require_POST
@ensure_csrf_cookie
def create_deal(request):
    """
    Receives user input from the modal, enriches it (tx id, timestamps, state, originator),
    and forwards to application_aggregate /api/applications/ingest/.
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        body = request.POST.dict()

    # Required user inputs
    company_name     = body.get("company_name", "").strip()
    abn              = body.get("abn", "").strip()
    acn              = body.get("acn", "").strip()
    contact_email    = body.get("contact_email", "").strip()
    contact_number   = body.get("contact_number", "").strip()
    amount_requested = body.get("amount_requested")  # string/number, let backend coerce
    product          = body.get("product", "").strip()

    # Originator comes from the page (JS passes it); allow query fallback
    originator = body.get("originator") or request.GET.get("originator") or ""

    # Server-side enrichment
    tx_id = str(uuid.uuid4())
    payload = {
        "transaction_id":   tx_id,
        "application_time": timezone.now().isoformat(),
        "company_name":     company_name,
        "abn":              abn,
        "acn":              acn,
        "contact_email":    contact_email,
        "contact_number":   contact_number,
        "amount_requested": amount_requested,
        "product":          product,
        "state":            "sales_review",
        "originator":       originator,
    }

    agg_base = os.getenv("EFS_APPLICATION_AGGREGATE_URL", "http://localhost:8016")
    url = f"{agg_base.rstrip('/')}/api/applications/ingest/"

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            return JsonResponse({"success": True, "transaction_id": tx_id})
        return JsonResponse(
            {"success": False, "error": resp.text or f"HTTP {resp.status_code}"},
            status=resp.status_code or 400,
        )
    except requests.RequestException as e:
        return JsonResponse({"success": False, "error": str(e)}, status=502)




#link entities 
#link entities 
#link entities 
#link entities 

# efs_sales/core/views.py
# ------------------------------------------------------------
# Sales “BFF” proxy endpoints for entity linking + lookup
# ------------------------------------------------------------
import os
import json
import requests

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt


# -----------------------------
# Upstream base (single source)
# -----------------------------
def _upstream(setting_name: str, default_env: str = "") -> str:
    val = (
        getattr(settings, setting_name, "")
        or os.getenv(setting_name, default_env)
        or ""
    ).rstrip("/")
    if not val:
        raise RuntimeError(f"Missing upstream base for {setting_name}")
    return val


def APPLICATION_AGGREGATE_BASE() -> str:
    # e.g. http://127.0.0.1:8016
    return _upstream("APPLICATION_AGGREGATE_BASE", "http://127.0.0.1:8016")


# -----------------------------
# Shared helpers
# -----------------------------
def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _classify_id_type(digits: str) -> str:
    if len(digits) == 11:
        return "abn"
    if len(digits) == 9:
        return "acn"
    return ""


def _json_error(status: int, msg: str, extra: dict | None = None):
    payload = {"ok": False, "error": msg}
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


# -------------------------------------------------------
# 1) GET /sales/abns/ -> proxy to aggregate /application/abns/
# -------------------------------------------------------
@require_GET
def abns_list_proxy(request):
    """
    Browser calls:
        GET /sales/abns/
    We proxy to aggregate:
        GET {AGG_BASE}/application/abns/
    """
    base = APPLICATION_AGGREGATE_BASE()
    url = f"{base}/application/abns/"

    try:
        r = requests.get(url, timeout=8)
    except requests.RequestException as e:
        return _json_error(502, str(e))

    # Aggregate should return JSON {ok: True, abns: [...]}
    try:
        js = r.json() if r.content else {}
    except ValueError:
        return _json_error(502, "Upstream returned non-JSON", {"body": r.text[:500]})

    if not r.ok:
        # bubble upstream message if present
        return _json_error(r.status_code, js.get("error") or r.text or f"HTTP {r.status_code}")

    return JsonResponse({"ok": True, "abns": js.get("abns", [])})


# -------------------------------------------------------
# 2) GET /sales/acns/ -> proxy to aggregate /application/acns/
# -------------------------------------------------------
@require_GET
def acns_list_proxy(request):
    """
    Browser calls:
        GET /sales/acns/
    We proxy to aggregate:
        GET {AGG_BASE}/application/acns/
    """
    base = APPLICATION_AGGREGATE_BASE()
    url = f"{base}/application/acns/"

    try:
        r = requests.get(url, timeout=8)
    except requests.RequestException as e:
        return _json_error(502, str(e))

    try:
        js = r.json() if r.content else {}
    except ValueError:
        return _json_error(502, "Upstream returned non-JSON", {"body": r.text[:500]})

    if not r.ok:
        return _json_error(r.status_code, js.get("error") or r.text or f"HTTP {r.status_code}")

    return JsonResponse({"ok": True, "acns": js.get("acns", [])})


# -------------------------------------------------------
# 3) POST /sales/link-entities/ -> proxy to aggregate /application/links/save/
# -------------------------------------------------------
@require_POST
@csrf_exempt  # keep if browser->sales is not using CSRF enforcement
def link_entities_proxy(request):
    """
    Browser POSTs to:
        /sales/link-entities/

    Body:
        {
          "id_a": "...",
          "id_b": "...",
          "id_type_a": "abn"|"acn",
          "id_type_b": "abn"|"acn",
          "nature_a": "...",
          "nature_b": "..."
        }

    We forward to:
        {AGG_BASE}/application/links/save/
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except ValueError:
        return _json_error(400, "Invalid JSON from browser")

    base = APPLICATION_AGGREGATE_BASE()
    url = f"{base}/application/links/save/"

    try:
        upstream = requests.post(url, json=payload, timeout=10)
    except requests.RequestException as e:
        return _json_error(502, str(e))

    # Return upstream JSON as-is
    try:
        js = upstream.json() if upstream.content else {}
    except ValueError:
        return _json_error(
            502,
            "Upstream returned non-JSON",
            {"status": upstream.status_code, "body": upstream.text[:500]},
        )

    return JsonResponse(js, status=upstream.status_code)


# -------------------------------------------------------
# 4) GET /sales/linked-entities/ -> proxy to aggregate /linked-entities/
# -------------------------------------------------------
@require_GET
def linked_entities_bff(request):
    """
    Browser calls:
        GET /sales/linked-entities/?abn=...   (legacy)
        GET /sales/linked-entities/?id=...    (preferred)

    We proxy to aggregate:
        GET {AGG_BASE}/linked-entities/?id=<digits>&type=<abn|acn>

    And return upstream JSON as-is.
    """
    raw_id = request.GET.get("abn", "") or request.GET.get("id", "")
    digits = _digits_only(raw_id)
    id_type = _classify_id_type(digits)

    if not digits or id_type not in ("abn", "acn"):
        return _json_error(
            400,
            "ID must be a valid 11-digit ABN or 9-digit ACN",
            {"id": digits},
        )

    base = APPLICATION_AGGREGATE_BASE()
    url = f"{base}/linked-entities/"

    try:
        upstream = requests.get(url, params={"id": digits, "type": id_type}, timeout=8)
    except requests.RequestException as e:
        return _json_error(502, f"aggregate call failed: {e}")

    try:
        js = upstream.json() if upstream.content else {}
    except ValueError:
        return _json_error(
            502,
            "Upstream returned non-JSON",
            {"status": upstream.status_code, "body": upstream.text[:500]},
        )

    return JsonResponse(js, status=upstream.status_code)





# end link entity code
# end link entity code
# end link entity code















# efs_sales/core/views.py  (no functional change; this already forwards PDFs)
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST

def _financial_base() -> str:
    return getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "http://127.0.0.1:8019").rstrip("/")

@require_POST
def proxy_upload_financials(request):
    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file provided"}, status=400)

    up_file = request.FILES["file"]
    files = {
        "file": (
            up_file.name,
            up_file,
            getattr(up_file, "content_type", "application/octet-stream")
        )
    }

    data = {
        # now forward BOTH
        "abn":            request.POST.get("abn", "").strip(),
        "acn":            request.POST.get("acn", "").strip(),
        "originator":     request.POST.get("originator", "").strip(),
        "data_type":      request.POST.get("data_type", "").strip(),
        "year":           request.POST.get("year", "").strip(),
        "company_name":   request.POST.get("company_name", "").strip(),
        "transaction_id": request.POST.get("transaction_id", "").strip(),
    }

    try:
        upstream = f"{_financial_base()}/upload-financials/"
        r = requests.post(upstream, files=files, data=data, timeout=60)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)

    return HttpResponse(
        r.content,
        status=r.status_code,
        content_type=r.headers.get("Content-Type", "application/json"),
    )




# efs_sales/core/views.py
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST

def _financial_base() -> str:
    return getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "http://127.0.0.1:8019").rstrip("/")

@require_POST
def proxy_upload_ar_ledger(request):
    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file provided"}, status=400)

    up_file = request.FILES["file"]
    files = {
        "file": (
            up_file.name,
            up_file,
            getattr(up_file, "content_type", "application/octet-stream")
        )
    }

    data = {
        "abn":            request.POST.get("abn", "").strip(),
        "acn":            request.POST.get("acn", "").strip(),   # NEW
        "originator":     request.POST.get("originator", "").strip(),
        "data_type":      request.POST.get("data_type", "").strip(),
        "transaction_id": request.POST.get("transaction_id", "").strip(),
    }

    try:
        upstream = f"{_financial_base()}/upload-ar-ledger/"
        r = requests.post(upstream, files=files, data=data, timeout=60)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)

    return HttpResponse(
        r.content,
        status=r.status_code,
        content_type=r.headers.get("Content-Type","application/json")
    )

@require_POST
def proxy_upload_ap_ledger(request):
    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file provided"}, status=400)

    f = request.FILES["file"]
    files = {
        "file": (
            f.name,
            f,
            getattr(f, "content_type", "application/octet-stream")
        )
    }
    data = {
        "abn":            request.POST.get("abn", "").strip(),
        "acn":            request.POST.get("acn", "").strip(),   # NEW
        "originator":     request.POST.get("originator", "").strip(),
        "data_type":      request.POST.get("data_type", "").strip(),
        "transaction_id": request.POST.get("transaction_id", "").strip(),
    }

    try:
        r = requests.post(f"{_financial_base()}/upload-ap-ledger/", files=files, data=data, timeout=60)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)

    return HttpResponse(
        r.content,
        status=r.status_code,
        content_type=r.headers.get("Content-Type","application/json")
    )


# efs_sales/core/views.py
import json
import uuid
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # if you prefer to keep CSRF, you can remove this and rely on same-origin token


@csrf_exempt
@require_POST
def save_financial_notes(request):
    """
    BFF endpoint: accepts notes from sales UI and forwards to financials service.
    Body now supports { transaction_id, abn, acn, financial_data_type, notes }.
    """
    try:
        try:
            data = json.loads(request.body.decode('utf-8') or "{}")
        except Exception:
            return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

        tx_str = (data.get("transaction_id") or "").strip()
        abn    = (data.get("abn") or "").strip()
        acn    = (data.get("acn") or "").strip()            # NEW
        ftype  = (data.get("financial_data_type") or "").strip()
        notes  = (data.get("notes") or "").strip()

        # ---- validation ----
        if not tx_str:
            return JsonResponse({"success": False, "message": "Missing transaction_id"}, status=400)
        try:
            uuid.UUID(tx_str)
        except Exception:
            return JsonResponse({"success": False, "message": "transaction_id must be a valid UUID"}, status=400)

        if not abn and not acn:
            return JsonResponse({"success": False, "message": "Missing company identifier (need ABN or ACN)"}, status=400)
        if not ftype:
            return JsonResponse({"success": False, "message": "Missing financial_data_type"}, status=400)
        if not notes:
            return JsonResponse({"success": False, "message": "Notes cannot be empty"}, status=400)

        # ---- normalize financial_data_type for downstream ----
        VALID_TYPES = {
            'financials': 'Financials',
            'ar ledger': 'AR Ledger',
            'debtors': 'Debtors',
            'invoices': 'Invoices',
            'accounts payable': 'Accounts Payable',
            'statutory obligations': 'Statutory Obligations',
        }
        ftype_norm = VALID_TYPES.get(ftype.lower())
        if not ftype_norm:
            return JsonResponse({"success": False, "message": "Unknown financial_data_type"}, status=400)

        forward_payload = {
            "transaction_id": tx_str,
            "abn": abn,
            "acn": acn,  # NEW
            "financial_data_type": ftype_norm,
            "notes": notes,
        }

        fin_base = getattr(settings, "EFS_SERVICES", {}).get("financials") or "http://localhost:8019"
        url = f"{fin_base.rstrip('/')}/save-financial-notes/"
        resp = requests.post(url, json=forward_payload, timeout=10)

        try:
            payload = resp.json()
        except Exception:
            payload = {"success": False, "message": f"Upstream error: HTTP {resp.status_code}"}

        return JsonResponse(payload, status=resp.status_code, safe=False)

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

# efs_sales/core/views.py  (BFF for PPSR upload)
# efs_sales/core/views.py
import os
import logging
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

log = logging.getLogger(__name__)
FIN_BASE = os.getenv("EFS_DATA_FINANCIAL_URL", "http://localhost:8019").rstrip("/")

def _bad(msg, code=400):
    return JsonResponse({"success": False, "message": msg}, status=code)

@csrf_exempt
@require_POST
def upload_ppsr_data_bff(request):
    """
    Browser -> /sales/upload-ppsr-data/ (multipart)
      forwards to efs_data_financials:8019/apis/upload-ppsr-data/
    """
    f = request.FILES.get("file")
    abn = (request.POST.get("abn") or "").strip()
    originator = (request.POST.get("originator") or "").strip()
    transaction_id = (request.POST.get("transaction_id") or "").strip()  # <-- include TX

    if not f:
        return _bad("Missing file.")
    if not abn:
        return _bad("Missing ABN.")

    try:
        r = requests.post(
            f"{FIN_BASE}/apis/upload-ppsr-data/",
            files={"file": (f.name, f, f.content_type or "application/pdf")},
            data={
                "abn": abn,
                "originator": originator,
                "transaction_id": transaction_id,  # <-- forward TX
            },
            timeout=60,
        )
    except requests.RequestException as e:
        log.exception("efd_data_financials upload failed")
        return _bad(f"Upstream error: {e}", code=502)

    # Pass-through upstream JSON/status
    try:
        payload = r.json()
    except Exception:
        payload = {"success": False, "message": "Invalid JSON from parser service."}

    status = r.status_code if 200 <= r.status_code < 600 else 502
    return JsonResponse(payload, status=status, safe=False)


# --- Bureau upload BFF (minimal, uses existing helpers) ---
import logging
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

def _passthrough_json_response(resp: requests.Response) -> JsonResponse:
    """
    Relay upstream JSON if present, otherwise synthesize a small payload.
    Never throws.
    """
    try:
        if "application/json" in (resp.headers.get("Content-Type") or ""):
            payload = resp.json()
        else:
            payload = {"success": False, "message": (resp.text or "").strip()[:500]}
    except Exception:
        payload = {"success": False, "message": "Upstream returned an invalid response"}
    # Keep upstream status (your frontend already checks .ok && data.success)
    return JsonResponse(payload, status=resp.status_code, safe=False)

@csrf_exempt   # keep consistent with your other upload proxies
@require_POST
def upload_bureau_data_bff(request):
    """
    Browser -> /sales/upload-bureau-data/ (multipart)
      file        : PDF
      abn         : required
      originator  : optional
      acn         : optional

    BFF -> efs_data_bureau: /api/upload-credit-report-pdf/
    """
    f = request.FILES.get("file")
    abn = (request.POST.get("abn") or "").strip()
    originator = (request.POST.get("originator") or "").strip()
    acn = (request.POST.get("acn") or "").strip()

    if not f:
        return JsonResponse({"success": False, "message": "Missing file."}, status=400)
    if not abn:
        return JsonResponse({"success": False, "message": "Missing ABN."}, status=400)
    if not f.name.lower().endswith(".pdf"):
        return JsonResponse({"success": False, "message": "Only PDF files are accepted."}, status=400)

    # 🔑 Use your existing base-url helper so envs remain consistent
    try:
        base = _bureau_base()  # already defined elsewhere in this module
    except Exception:
        # ultra-safe fallback
        base = "http://localhost:8018"
    url = f"{base}/api/upload-credit-report-pdf/"

    files = {"file": (f.name, f, getattr(f, "content_type", "application/pdf"))}
    data = {"abn": abn}
    if acn:
        data["acn"] = acn
    if originator:
        data["originator"] = originator  # harmless, parser may ignore

    try:
        # Reasonable timeout; uploads can be a bit slow
        resp = requests.post(url, files=files, data=data, timeout=60)
        return _passthrough_json_response(resp)
    except requests.RequestException as e:
        logger.exception("Bureau upload BFF → data_bureau failed")
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)




# efs_sales/core/views.py
import os
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Resolve your data-financial base (same you use elsewhere)
DATA_FINANCIAL_BASE = (
    getattr(settings, "EFS_SERVICES", {})
        .get("financials")
    or os.environ.get("EFS_DATA_FINANCIAL_BASE")
    or "http://localhost:8019"      # fallback for local dev
).rstrip("/")

@csrf_exempt
@require_POST
def upload_asset_schedule_bff(request):
    try:
        if "file" not in request.FILES:
            return JsonResponse({"success": False, "message": "Missing file"}, status=400)

        upstream_url = f"{DATA_FINANCIAL_BASE}/upload-asset-schedule/"

        files = {
            "file": (
                request.FILES["file"].name,
                request.FILES["file"].read(),
                request.FILES["file"].content_type or "application/octet-stream",
            )
        }
        data = {
            "abn":                request.POST.get("abn", "").strip(),
            "acn":                request.POST.get("acn", "").strip(),            # NEW
            "transaction_id":     request.POST.get("transaction_id", "").strip(),
            "data_type":          request.POST.get("data_type", "").strip(),
            "provider_name":      request.POST.get("provider_name", "").strip(),
            "schedule_title":     request.POST.get("schedule_title", "").strip(),
            "as_of_date":         request.POST.get("as_of_date", "").strip(),
            "amounts_include_tax":request.POST.get("amounts_include_tax", "").strip(),
        }

        r = requests.post(upstream_url, files=files, data=data, timeout=60)
        try:
            payload = r.json()
        except Exception:
            payload = {
                "success": False,
                "message": f"Upstream error: HTTP {r.status_code}",
                "raw": r.text[:4000],
            }

        return JsonResponse(payload, status=r.status_code)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"BFF error: {e}"}, status=500)





#-----code to upload debtor creditors reports 
    #-----code to upload debtor creditors reports 
        #-----code to upload debtor creditors reports 
            #-----code to upload debtor creditors reports 
                #-----code to upload debtor creditors reports 




import os
import logging
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

EFS_FINANCIAL_BASE = os.getenv(
    "EFS_DATA_FINANCIAL_BASE_URL",
    "http://127.0.0.1:8019"
).rstrip("/")

@csrf_exempt
@require_POST
def bff_upload_debtor_credit_report(request):
    """
    Browser-facing BFF endpoint.

    Expects multipart/form-data:
      - file
      - abn/acn
      - transaction_id
      - debtor_name
      - debtor_abn/debtor_acn (optional)
    """
    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file provided"}, status=400)

    f = request.FILES["file"]

    # Pass through metadata
    data = {
        "abn": request.POST.get("abn", ""),
        "acn": request.POST.get("acn", ""),
        "transaction_id": request.POST.get("transaction_id", ""),
        "debtor_name": request.POST.get("debtor_name", ""),
        "debtor_abn": request.POST.get("debtor_abn", ""),
        "debtor_acn": request.POST.get("debtor_acn", ""),
    }

    files = {
        "file": (f.name, f.read(), f.content_type or "application/pdf")
    }

    url = f"{EFS_FINANCIAL_BASE}/upload-debtor-credit-report-pdf/"

    try:
        resp = requests.post(url, data=data, files=files, timeout=60)
        try:
            payload = resp.json()
        except Exception:
            payload = {"success": False, "message": resp.text}

        return JsonResponse(payload, status=resp.status_code)

    except Exception as e:
        logger.exception("BFF forward to efs_data_financial failed")
        return JsonResponse({"success": False, "message": str(e)}, status=502)



#-----code to approve or reject debtors   
    #-----code to approve or reject debtors   
        #-----code to approve or reject debtors   

import os
import json
import requests

from django.http import JsonResponse
from django.views.decorators.http import require_POST


# ✅ Base URL for the efs_data_financials service (BFF target)
EFS_FINANCIAL_BASE = os.getenv(
    "EFS_DATA_FINANCIAL_BASE_URL",
    "http://127.0.0.1:8019"
).rstrip("/")

@csrf_exempt
@require_POST
def proxy_update_debtor_credit_report_state(request):
    """
    BFF endpoint in efs_sales.
    Forwards debtor credit report state updates to efs_data_financials.
    """

    if not EFS_FINANCIAL_BASE:
        return JsonResponse(
            {"success": False, "message": "EFS_DATA_FINANCIAL_BASE_URL not set."},
            status=500
        )

    upstream_url = f"{EFS_FINANCIAL_BASE}/api/debtors/credit-report/state/"

    # Parse request JSON
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    # Light validation (optional)
    debtor_name = (payload.get("debtor_name") or "").strip()
    state = (payload.get("state") or "").strip()
    if not debtor_name or not state:
        return JsonResponse(
            {"success": False, "message": "debtor_name and state are required"},
            status=400
        )

    try:
        resp = requests.post(
            upstream_url,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
    except requests.RequestException as e:
        return JsonResponse(
            {"success": False, "message": f"Upstream request failed: {str(e)}"},
            status=502
        )

    try:
        data = resp.json()
    except ValueError:
        data = {"success": False, "message": "Upstream did not return JSON"}

    return JsonResponse(data, status=resp.status_code)




#-----code to upload invoices 
    #-----code to upload invoices 
        #-----code to upload invoices 


import requests

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt


def _financials_base():
    # Use your existing single source of truth
    return getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "").rstrip("/")


@csrf_exempt
@require_POST
def upload_invoices_proxy(request):
    """
    Receive multipart from the browser and forward to financial service.
    """
    base = _financials_base()
    if not base:
        return JsonResponse({"success": False, "message": "Financials service URL not configured."}, status=500)

    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"success": False, "message": "Missing file."}, status=400)

    data = {
        "abn": request.POST.get("abn", ""),
        "acn": request.POST.get("acn", ""),
        "transaction_id": request.POST.get("transaction_id", ""),
        "entity_id": request.POST.get("entity_id", ""),
        "entity_id_type": request.POST.get("entity_id_type", ""),
        "originator": request.POST.get("originator", ""),
        "data_type": request.POST.get("data_type", "invoices"),
    }

    files = {"file": (f.name, f.read(), f.content_type)}

    try:
        r = requests.post(
            f"{base}/api/invoices/upload-csv/",
            data=data,
            files=files,
            timeout=60
        )
        payload = r.json() if r.content else {}
        return JsonResponse(payload, status=r.status_code)
    except requests.RequestException as e:
        return JsonResponse({"success": False, "message": str(e)}, status=502)


@require_GET
def fetch_invoices_proxy(request, company_id):
    """
    Pass-through fetch used by the existing JS path.
    """
    base = _financials_base()
    if not base:
        return JsonResponse({"invoices": []}, status=200)

    try:
        r = requests.get(
            f"{base}/api/invoices/fetch/{company_id}/",
            timeout=30
        )
        payload = r.json() if r.content else {"invoices": []}
        return JsonResponse(payload, status=r.status_code)
    except requests.RequestException:
        return JsonResponse({"invoices": []}, status=200)




import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


def _financials_base():
    return getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "").rstrip("/")


@csrf_exempt
@require_POST
def upload_ap_invoices_proxy(request):
    base = _financials_base()
    if not base:
        return JsonResponse(
            {"success": False, "message": "Financials service URL not configured."},
            status=500
        )

    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"success": False, "message": "Missing file."}, status=400)

    data = {
        "abn": request.POST.get("abn", ""),
        "acn": request.POST.get("acn", ""),
        "transaction_id": request.POST.get("transaction_id", ""),
        "entity_id": request.POST.get("entity_id", ""),
        "entity_id_type": request.POST.get("entity_id_type", ""),
        "originator": request.POST.get("originator", ""),
        "data_type": request.POST.get("data_type", "invoices_accounts_payable"),
    }

    files = {"file": (f.name, f.read(), f.content_type)}

    downstream_url = f"{base}/api/invoices/upload-ap-csv/"  # <- confirm this exists exactly

    try:
        r = requests.post(downstream_url, data=data, files=files, timeout=60)

        # Try JSON first, but don't assume it
        try:
            payload = r.json() if r.content else {}
            return JsonResponse(payload, status=r.status_code)
        except ValueError:
            # Downstream returned HTML/plain text (404/500/etc)
            body_preview = (r.text or "")[:500]
            return JsonResponse(
                {
                    "success": False,
                    "message": f"Financial service returned non-JSON response (HTTP {r.status_code}).",
                    "downstream_url": downstream_url,
                    "downstream_body_preview": body_preview,
                },
                status=502
            )

    except requests.RequestException as e:
        return JsonResponse({"success": False, "message": str(e)}, status=502)

@require_GET
def fetch_ap_invoices_proxy(request, company_id):
    """
    Pass-through fetch for AP invoices (used by Payables sub-tab in Invoices tab).
    """
    base = _financials_base()
    if not base:
        return JsonResponse({"success": False, "invoices": [], "ap_invoices": []}, status=200)

    downstream_url = f"{base}/api/invoices/ap/fetch/{company_id}/"

    try:
        r = requests.get(downstream_url, timeout=30)

        # ✅ if downstream returns 404/500, capture it (don't silently hide it)
        try:
            payload = r.json() if r.content else {}
        except ValueError:
            payload = {
                "success": False,
                "message": f"Downstream returned non-JSON (HTTP {r.status_code})",
                "downstream_url": downstream_url,
            }

        # Normalize keys for frontend
        ap_list = payload.get("ap_invoices")
        if ap_list is None:
            ap_list = payload.get("invoices", [])

        # If downstream is non-200, still return useful debug info
        if not r.ok:
            return JsonResponse({
                "success": False,
                "message": payload.get("message") or f"Downstream HTTP {r.status_code}",
                "downstream_url": downstream_url,
                "invoices": [],
                "ap_invoices": [],
            }, status=200)

        return JsonResponse({
            "success": True,
            "invoices": ap_list,
            "ap_invoices": ap_list,
        }, status=200)

    except requests.RequestException as e:
        return JsonResponse({
            "success": False,
            "message": str(e),
            "downstream_url": downstream_url,
            "invoices": [],
            "ap_invoices": [],
        }, status=200)

#-----code to approve or reject  invoices 
    #-----code to approve or reject  invoices 
        #-----code to approve or reject  invoices 



import json
import requests

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt


def _financials_base():
    # Same single source of truth used elsewhere in efs_sales
    return getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "").rstrip("/")


@csrf_exempt
@require_POST
def invoice_approve_reject_bff(request):
    """
    BFF endpoint in efs_sales.
    Forwards invoice approve/reject updates to efs_data_financials.
    """

    base = _financials_base()
    if not base:
        return JsonResponse(
            {"success": False, "message": "Financials service URL not configured."},
            status=500
        )

    upstream_url = f"{base}/api/invoices/approve-reject/"

    # Parse request JSON
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    # Extract fields
    invoice_number = payload.get("invoice_number")
    debtor = payload.get("debtor")
    approve_reject = payload.get("approve_reject")  # "approved" | "rejected"

    abn = payload.get("abn")
    acn = payload.get("acn")
    transaction_id = payload.get("transaction_id")
    entity_id = payload.get("entity_id")
    entity_id_type = payload.get("entity_id_type")
    originator = payload.get("originator")

    # Light validation
    if approve_reject not in ("approved", "rejected"):
        return JsonResponse(
            {"success": False, "message": "Invalid approve_reject value"},
            status=400
        )

    if not invoice_number:
        return JsonResponse(
            {"success": False, "message": "Missing invoice_number"},
            status=400
        )

    # Build upstream payload (pass-through friendly)
    # Build upstream payload (pass-through friendly)
    upstream_payload = {
        # Keep old key for compatibility
        "invoice_number": invoice_number,

        # ✅ Correct model field name
        "inv_number": invoice_number,

        "approve_reject": approve_reject,
        "debtor": debtor,
        "abn": abn,
        "acn": acn,
        "transaction_id": transaction_id,
        "entity_id": entity_id,
        "entity_id_type": entity_id_type,
        "originator": originator,
    }


    try:
        resp = requests.post(
            upstream_url,
            json=upstream_payload,
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
    except requests.RequestException as e:
        return JsonResponse(
            {"success": False, "message": f"Upstream request failed: {str(e)}"},
            status=502
        )

    try:
        data = resp.json()
    except ValueError:
        data = {"success": False, "message": "Upstream did not return JSON"}

    return JsonResponse(data, status=resp.status_code)


#-----code to upload PPE csv file 
#-----code to upload PPE csv file 
#-----code to upload PPE csv file 
#-----code to upload PPE csv file 



# efs_sales/core/views.py
import os, requests
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

def _financial_base():
    # Prefer settings, then env (support both names you’ve used), then localhost dev
    base = getattr(settings, "EFS_SERVICES", {}).get("financials") \
        or os.environ.get("EFS_DATA_FINANCIAL_BASE") \
        or os.environ.get("EFS_DATA_FINANCIAL_BASE_URL") \
        or "http://localhost:8019"
    return base.rstrip("/")

@csrf_exempt
@require_POST
def upload_plant_machinery_schedule_bff(request):
    upfile = request.FILES.get("file")
    if not upfile:
        return JsonResponse({"success": False, "error": "No file uploaded"}, status=400)

    abn        = (request.POST.get("abn") or "").strip()
    acn        = (request.POST.get("acn") or "").strip()        # NEW
    tx         = (request.POST.get("transaction_id") or "").strip()
    originator = (request.POST.get("originator") or "").strip()

    base = _financial_base()
    try:
        resp = requests.post(
            f"{base}/upload-plant-machinery-schedule/",
            files={
                "file": (
                    upfile.name,
                    upfile.read(),
                    upfile.content_type or "text/csv"
                )
            },
            data={
                "abn":            abn,
                "acn":            acn,           # NEW
                "transaction_id": tx,
                "originator":     originator,
            },
            headers={"X-API-Key": os.environ.get("INTERNAL_API_KEY", "")},
            timeout=30,
        )
    except requests.RequestException as e:
        return JsonResponse({"success": False, "error": f"Upstream connect error: {e}", "financial_base": base}, status=502)

    try:
        payload = resp.json()
    except Exception:
        payload = {"success": False, "error": resp.text[:1000]}

    return JsonResponse(payload, status=resp.status_code)



#-----#-----#-----#-----#-----#-----

#-----BFF code to upload tax documents  

#-----#-----#-----#-----#-----#-----



# efs_sales/core/views.py
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST

def _financial_base() -> str:
    """
    Whatever you already use to reach efs_data_financial.
    Example: return settings.EFS_DATA_FINANCIAL_BASE_URL
    """
    from django.conf import settings
    return getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "").rstrip("/")


def _as_files_dict(uploaded_file):
    return {
        "file": (
            uploaded_file.name,
            uploaded_file,
            getattr(uploaded_file, "content_type", "application/octet-stream"),
        )
    }

@csrf_exempt
@require_POST
def proxy_upload_tax_document(request):
    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file provided"}, status=400)

    up_file = request.FILES["file"]
    files = _as_files_dict(up_file)

    # Pass through the same context your data service expects
    # (Your data service reads doc_type from doc_type OR data_type)
    data = {
        "transaction_id": request.POST.get("transaction_id", ""),
        "originator": request.POST.get("originator", ""),
        "abn": request.POST.get("abn", ""),
        "acn": request.POST.get("acn", ""),
        "company_name": request.POST.get("company_name", ""),

        # keep both for compatibility
        "data_type": request.POST.get("data_type", ""),   # e.g. tax_bas
        "doc_type":  request.POST.get("doc_type", "")     # optional
    }

    # If UI only sends data_type, ensure doc_type is populated too
    if not data["doc_type"]:
        data["doc_type"] = data["data_type"]

    try:
        upstream = f"{_financial_base()}/upload-tax-document/"
        r = requests.post(upstream, files=files, data=data, timeout=90)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)

    # Return upstream response as-is
    return HttpResponse(
        r.content,
        status=r.status_code,
        content_type=r.headers.get("Content-Type", "application/json"),
    )




#-----#-----#-----#-----#-----#-----

#-----BFF code to fetch and display tax documents  

#-----#-----#-----#-----#-----#-----




from django.http import JsonResponse, HttpResponse
import requests

def proxy_fetch_statutory_obligations(request, entity_id):
    upstream = f"{_financial_base()}/fetch_statutory_obligations/{entity_id}/"
    try:
        r = requests.get(upstream, timeout=30)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)

    return HttpResponse(
        r.content,
        status=r.status_code,
        content_type=r.headers.get("Content-Type","application/json"),
    )









#-----code to fetch and display  vehical assets data 
#-----code to fetch and display  vehical assets data 
#-----code to fetch and display  vehical assets data 
#-----code to fetch and display  vehical assets data 

# efs_sales/core/views.py
from django.views.decorators.http import require_GET
from django.http import JsonResponse, HttpResponseBadRequest
import requests
import os

API_KEY = os.environ.get("INTERNAL_API_KEY", "")

@require_GET
def fetch_asset_schedule_rows_bff(request, abn):
    """
    Proxies → {financials}/fetch_asset_schedule_rows/<id>/
    <id> can now be ABN or ACN.
    """
    company_id = (abn or "").strip()
    if not company_id:
        return HttpResponseBadRequest("Company identifier (ABN or ACN) required")

    base = _financial_base()
    url = f"{base}/fetch_asset_schedule_rows/{company_id}/"
    qs = request.GET.urlencode()
    if qs:
        url = f"{url}?{qs}"

    try:
        upstream = requests.get(url, headers={"X-API-Key": API_KEY}, timeout=20)
    except requests.RequestException as e:
        return JsonResponse(
            {"rows": [], "success": False, "error": f"Upstream error: {e}"},
            status=502,
        )

    return _pass_rows(upstream)


#-----code to fetch and display  PPE data 
#-----code to fetch and display  PPE data 
#-----code to fetch and display  PPE data 
#-----code to fetch and display  PPE data 

# efs_sales/core/views.py
import os, requests
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

API_KEY = os.environ.get("INTERNAL_API_KEY", "")

def _financial_base():
    return (
        getattr(settings, "EFS_SERVICES", {}).get("financials")
        or os.environ.get("EFS_DATA_FINANCIAL_BASE")
        or os.environ.get("EFS_DATA_FINANCIAL_BASE_URL")
        or "http://localhost:8019"
    ).rstrip("/")

def _pass_rows(resp):
    try:
        data = resp.json()
    except Exception:
        data = None
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        payload = data
    elif isinstance(data, list):
        payload = {"rows": data}
    else:
        payload = {"rows": []}
    status = 200 if resp.status_code in (200, 201) else (400 if resp.status_code == 400 else 502)
    return JsonResponse(payload, status=status)

@require_GET
def fetch_plant_machinery_schedule_rows_bff(request, abn):
    """
    Proxies → {financials}/fetch_plant_machinery_schedule_rows/<id>/
    <id> can now be ABN or ACN.
    """
    company_id = (abn or "").strip()
    if not company_id:
        return HttpResponseBadRequest("Company identifier (ABN or ACN) required")

    base = _financial_base()
    qs = request.GET.urlencode()
    url = f"{base}/fetch_plant_machinery_schedule_rows/{company_id}/"
    if qs:
        url = f"{url}?{qs}"

    try:
        upstream = requests.get(url, headers={"X-API-Key": API_KEY}, timeout=20)
    except requests.RequestException as e:
        return JsonResponse(
            {"rows": [], "success": False, "error": f"Upstream error: {e}"},
            status=502,
        )

    return _pass_rows(upstream)


#-----NAV code 
#-----NAV code 
#-----NAV code 
#-----NAV code 



# BFF side
import logging, json, requests
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.conf import settings

log = logging.getLogger(__name__)

FINANCIALS_BASE = getattr(settings, "EFS_SERVICES", {}).get("financials", "http://localhost:8019")
SERVICE_KEY = getattr(settings, "INTERNAL_API_KEY", None)

@require_POST
def save_nav_snapshot(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    # require at least one identifier now
    abn = (payload.get("abn") or "").strip()
    acn = (payload.get("acn") or "").strip()
    if not abn and not acn:
        return HttpResponseBadRequest("Missing company identifier (ABN or ACN)")

    # (Optional) still allowed to sanity check tx etc. here if you want

    url = f"{FINANCIALS_BASE.rstrip('/')}/save_nav_snapshot/"
    headers = {"Content-Type": "application/json"}
    if SERVICE_KEY:
        headers["X-API-Key"] = SERVICE_KEY

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return JsonResponse(r.json(), status=r.status_code, safe=False)
    except requests.RequestException as e:
        log.exception("save_nav_snapshot proxy failed")
        return JsonResponse({"success": False, "message": str(e)}, status=502)




# efs_sales/core/views.py  (BFF → financials)
import os, requests, logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET
from django.conf import settings

log = logging.getLogger(__name__)

def _financial_base_for_bff() -> str:
    # keep consistent with your other helpers/ENV
    return (
        getattr(settings, "EFS_DATA_FINANCIAL_URL", None)
        or getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", None)
        or os.getenv("EFS_DATA_FINANCIAL_URL")
        or "http://localhost:8019"
    ).rstrip("/")

def _pass_json(resp: requests.Response) -> JsonResponse:
    try:
        payload = resp.json()
    except Exception:
        payload = {"error": "Upstream did not return JSON", "raw": (resp.text or "")[:1000]}
    return JsonResponse(payload, status=resp.status_code, safe=False)


@require_GET
def assets_summary_bff(request):
    """
    /sales/api/assets/summary/?abn=...&tx=...
    → BFF → {FIN}/api/assets/summary/?abn=...&tx=...
    Returns aggregated AssetScheduleRow totals/breakdowns for the UI.
    """
    base = _financial_base_for_bff()
    try:
        r = requests.get(f"{base}/api/assets/summary/", params=request.GET, timeout=10)
        return _pass_json(r)
    except requests.RequestException as e:
        log.exception("assets_summary_bff failed")
        return JsonResponse({"error": str(e)}, status=502)


@require_GET
def nav_latest_bff(request):
    """
    /sales/api/nav/latest/?abn=...&tx=...
    → BFF → {FIN}/api/nav/latest/?abn=...&tx=...
    Returns the latest NetAssetValueSnapshot and its lines.
    """
    base = _financial_base_for_bff()
    try:
        r = requests.get(f"{base}/api/nav/latest/", params=request.GET, timeout=10)
        return _pass_json(r)
    except requests.RequestException as e:
        log.exception("nav_latest_bff failed")
        return JsonResponse({"error": str(e)}, status=502)


# efs_sales/core/views.py

# efs_sales/core/views.py

import logging, json, requests
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.conf import settings

log = logging.getLogger(__name__)

FINANCIALS_BASE = getattr(settings, "EFS_SERVICES", {}).get("financials", "http://localhost:8019")
SERVICE_KEY = getattr(settings, "INTERNAL_API_KEY", None)

@require_POST
def save_liabilities_nav_bff(request):
    """
    /sales/save_liabilities_nav/

    Browser calls this when user is on the Liabilities tab and clicks "Save NAV".

    We:
      - parse/validate payload
      - forward it to the financials service
      - return upstream JSON straight back to the browser
    """

    # 1. Read JSON from browser
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    # 2. Basic validation BEFORE we burn network calls
    abn = (payload.get("abn") or "").strip()
    acn = (payload.get("acn") or "").strip()
    if not abn and not acn:
        return HttpResponseBadRequest("Missing company identifier (ABN or ACN)")

    lines = payload.get("lines") or []
    if not isinstance(lines, list) or not lines:
        return HttpResponseBadRequest("No liability lines provided.")

    # 3. Build upstream URL to the financials service
    url = f"{FINANCIALS_BASE.rstrip('/')}/save_liabilities_nav/"

    headers = {"Content-Type": "application/json"}
    # optional "internal auth" header for service-to-service trust
    if SERVICE_KEY:
        headers["X-API-Key"] = SERVICE_KEY

    try:
        # 4. Proxy POST to financials service
        upstream_resp = requests.post(
            url,
            headers=headers,
            json=payload,    # send exact same shape the browser gave us
            timeout=10,
        )

        # 5. Pass upstream response straight back
        #    mirror what you do in save_nav_snapshot()
        return JsonResponse(
            upstream_resp.json(),
            status=upstream_resp.status_code,
            safe=False
        )

    except requests.RequestException as e:
        log.exception("save_liabilities_nav_bff proxy failed")
        return JsonResponse(
            {"success": False, "message": str(e)},
            status=502
        )

import logging, requests
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
from django.conf import settings

log = logging.getLogger(__name__)

# You already have something like this in your file:
FINANCIALS_BASE = getattr(settings, "EFS_SERVICES", {}).get("financials", "http://localhost:8019")
SERVICE_KEY = getattr(settings, "INTERNAL_API_KEY", None)

def _pass_json(resp: requests.Response) -> JsonResponse:
    try:
        payload = resp.json()
    except Exception:
        payload = {
            "error": "Upstream did not return JSON",
            "raw": (resp.text or "")[:1000],
        }
    return JsonResponse(payload, status=resp.status_code, safe=False)

@require_GET
def liabilities_latest_bff(request):
    """
    Browser calls:
      /sales/api/liabilities/latest/?abn=...&acn=...&tx=...

    We forward that to the financials service:
      {FINANCIALS_BASE}/api/liabilities/latest/?...

    Then we return whatever it said.
    """

    # Optional local validation before proxying (not mandatory)
    abn = (request.GET.get("abn") or "").strip()
    acn = (request.GET.get("acn") or "").strip()
    if not abn and not acn:
        return HttpResponseBadRequest("Missing identifier (abn or acn).")

    upstream_url = f"{FINANCIALS_BASE.rstrip('/')}/api/liabilities/latest/"

    headers = {}
    if SERVICE_KEY:
        headers["X-API-Key"] = SERVICE_KEY  # if you enforce internal auth upstream

    try:
        upstream_resp = requests.get(
            upstream_url,
            headers=headers,
            params=request.GET,  # pass abn/acn/tx straight through
            timeout=10,
        )
        return _pass_json(upstream_resp)
    except requests.RequestException as e:
        log.exception("liabilities_latest_bff failed")
        return JsonResponse({"error": str(e)}, status=502)






#-----------------#-----------------#-----------------#-----------------

#this is the proxy code for the efs_data_financials service 
    

#handles the auto-generate 'Sales Notes'reports for all the tab

#-----------------#-----------------#-----------------#-----------------


import json, os, logging, requests
from urllib.parse import urljoin
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

log = logging.getLogger(__name__)

def _financial_base():
    return (
        getattr(settings, "FINANCIAL_SVC_BASE", None)
        or os.environ.get("FINANCIAL_SVC_BASE")
        or "http://localhost:8019"
    ).rstrip("/")

# efs_sales/views.py

import os
import json
import logging
import requests
from urllib.parse import urljoin

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

log = logging.getLogger(__name__)


def _get_data_financial_base():
    return os.getenv("EFS_DATA_FINANCIAL_URL", "http://localhost:8019").rstrip("/")


# If you already have _financial_base() elsewhere, keep yours.
# This alias preserves your existing proxy pattern.
def _financial_base():
    return _get_data_financial_base()


def _summaries_to_text(items):
    if not items:
        return "No debtor credit reports found for this transaction."

    lines = ["Debtors credit report summary:"]
    for i, it in enumerate(items, start=1):
        s = it.get("summary") or "—"
        lines.append(f"{i}. {s}")
    return "\n".join(lines)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def run_financial_analysis(request):
    """
    Existing endpoint your modal uses.

    NEW:
      - supports analysis_type == "debtors"
        which calls:
          /api/debtors-credit-reports/by-transaction/?transaction_id=<uuid>

    Everything else:
      - falls back to your existing upstream proxy:
          POST {EFS_DATA_FINANCIAL_URL}/run_financial_analysis/
    """
    if request.method == "OPTIONS":
        return HttpResponse(status=204)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    analysis_type = payload.get("analysis_type") or "financials"
    tx = (payload.get("transaction_id") or "").strip()

    # ---- NEW: Debtors analysis ----
    if analysis_type == "debtors":
        if not tx:
            return JsonResponse(
                {"success": False, "message": "transaction_id is required for debtors analysis."},
                status=400
            )

        base = _get_data_financial_base()
        url = f"{base}/api/debtors-credit-reports/by-transaction/"

        try:
            resp = requests.get(url, params={"transaction_id": tx}, timeout=8)
            data = resp.json() if resp.content else {}
        except Exception as e:
            log.exception("Debtors upstream call failed")
            return JsonResponse(
                {"success": False, "message": f"Failed to reach data_financial service: {e}"},
                status=502
            )

        if resp.status_code != 200 or not data.get("success"):
            return JsonResponse(
                {
                    "success": False,
                    "message": data.get("message") or f"Upstream error HTTP {resp.status_code}"
                },
                status=502
            )

        items = data.get("items", [])
        summary_text = _summaries_to_text(items)

        return JsonResponse({
            "success": True,
            "analysis_type": "debtors",
            "count": data.get("count", len(items)),
            "items": items,
            "summary": summary_text,  # ✅ what your JS can append into notes
        })

    # ---- Existing behaviour unchanged ----
    upstream = urljoin(_financial_base() + "/", "run_financial_analysis/")

    try:
        r = requests.post(upstream, json=payload, timeout=60)
        try:
            data = r.json()
        except Exception:
            data = {"success": False, "message": f"Upstream non-JSON (HTTP {r.status_code})"}
        return JsonResponse(data, status=r.status_code, safe=False)
    except requests.RequestException as e:
        log.exception("Upstream call failed")
        return JsonResponse({"success": False, "message": f"Upstream error: {e}"}, status=502)


#------------------------------------
    
    # this is the proxy for the code to generate the final report for investors

 #------------------------------------
   

# efs_sales/core/views.py
import json
import requests
from typing import Any
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST

@require_POST
def agents_generate_report_proxy(request):
    try:
        payload: dict[str, Any] = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    base = getattr(settings, "AGENTS_BASE_URL", "").rstrip("/")
    if not base:
        return JsonResponse({"error": "AGENTS_BASE_URL is not configured"}, status=500)

    url = f"{base}/api/agents/generate-report/"

    try:
        r = requests.post(url, json=payload, timeout=100)
    except requests.RequestException as e:
        return JsonResponse({"error": f"Proxy error: {e}"}, status=502)

    # Try JSON first, else pass raw text/HTML through so you can see upstream error
    ctype = r.headers.get("Content-Type", "")
    if "application/json" in ctype.lower():
        try:
            data = r.json()
        except ValueError:
            # malformed JSON upstream
            return HttpResponse(r.text, status=r.status_code, content_type=ctype or "text/plain")
        return JsonResponse(data, status=r.status_code, safe=False)
    else:
        # forward non-JSON body as-is (often a Django HTML error page)
        return HttpResponse(r.text, status=r.status_code, content_type=ctype or "text/plain")



####################
    
# delete applcation data 

####################



# BFF proxy: forwards delete-by-transaction to application_aggregate
import os
import json
import requests
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt

AGG_BASE = os.environ.get("AGG_BASE_URL", "http://localhost:8016")

@csrf_exempt
def bff_delete_application(request, tx):
    if request.method not in ("POST", "DELETE"):
        return HttpResponseNotAllowed(["POST", "DELETE"])

    product = request.GET.get("product", "")
    qs = f"?product={product}" if product else ""
    url = f"{AGG_BASE}/api/applications/{tx}/delete/{qs}"

    try:
        # Mirror method; body not required but harmless
        r = requests.request(
            method=request.method,
            url=url,
            headers={"Content-Type": "application/json"},
            data=request.body or b"{}",
            timeout=10,
        )
        return JsonResponse(r.json(), status=r.status_code, safe=False)
    except requests.RequestException as e:
        return JsonResponse(
            {"status": "error", "message": f"BFF delete failed: {e}"},
            status=502,
        )




####################
    
# BFF code to save agents reports in efs_agents service 

####################
    
import os
import json
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

AGENTS_BASE = os.getenv("EFS_AGENTS_URL", "http://localhost:8015").rstrip("/")
TIMEOUT = int(os.getenv("EFS_PROXY_TIMEOUT", "30"))

@require_POST
def sales_save_agent_memory(request):
    """
    BFF endpoint: Browser -> efs_sales -> efs_agents
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    # Forward to Agents
    url = f"{AGENTS_BASE}/api/agents/memory/save/"
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        # pass through status + body
        try:
            return JsonResponse(resp.json(), status=resp.status_code, safe=False)
        except Exception:
            return JsonResponse({"ok": False, "error": resp.text}, status=resp.status_code)
    except requests.RequestException as e:
        return JsonResponse({"ok": False, "error": f"Upstream error: {e}"}, status=502)