# efs_operations/core/views.py
import json
import logging
import requests

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

import os
from django.http import HttpResponse
from django.views.decorators.http import require_GET


# ---------------------------
# Service URL helpers (same pattern as efs_risk)
# ---------------------------
def _aggregate_base() -> str:
    return getattr(settings, "EFS_APPLICATION_AGGREGATE_BASE_URL", "http://localhost:8016").rstrip("/")

def _profile_base() -> str:
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

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
        if "application/json" in (r.headers.get("Content-Type") or ""):
            body = r.json()
        else:
            body = {"status": "error", "message": r.text}
        return r.status_code, body
    except Exception as e:
        logger.exception("POST %s failed", url)
        return 500, {"status": "error", "message": str(e)}

# ---------------------------
# Originators (same as risk)
# ---------------------------
def fetch_originators():
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        data = r.json()
        # accept either {"originators":[...]} or list [...]
        if isinstance(data, dict):
            return data.get("originators", []) or data.get("results", [])
        if isinstance(data, list):
            return data
        return []
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
                selected_originator = {"id": o.get("id"), "originator": o.get("originator")}
                break
    return {"originators": originators, "selected_originator": selected_originator}

# ---------------------------
# Aggregate → fetch/normalize (borrowed from risk)
# ---------------------------
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
    """
    GET {aggregate}/api/applications/?states=a,b&originator=<name>
    Then ALWAYS local-filter by state as safety net (same as risk service).
    """
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

def _split_by_product(apps: list[dict]):
    inv, tf, scf, ipf = [], [], [], []
    for a in apps or []:
        p = (a.get("product") or "").strip().upper()
        if p in ("IF", "INVOICE FINANCE", "INVOICE_FINANCE", "INVOICE"):
            inv.append(a)
        elif p in ("TF", "TRADE FINANCE", "TRADE_FINANCE", "TRADE"):
            tf.append(a)
        elif p in ("SCF", "SUPPLY CHAIN FINANCE", "SUPPLY_CHAIN_FINANCE"):
            scf.append(a)
        elif p in ("IPF", "INSURANCE PREMIUM FUNDING", "INSURANCE_PREMIUM_FUNDING"):
            ipf.append(a)
        else:
            inv.append(a)
    return inv, tf, scf, ipf

# ---------------------------
# Pages (KEEP)
# ---------------------------
def operations_home(request):
    return render(request, "operations_home.html", base_context(request))

def operations_view(request):
    ctx = base_context(request)
    org_name = (ctx.get("selected_originator") or {}).get("originator")

    # Your rule:
    # Review tab: risk_approved
    review_all = _fetch_apps(["risk_approved"], org_name)

    # Status tab: operations_approved OR closed OR funded
    status_all = _fetch_apps(["operations_approved", "closed", "funded"], org_name)

    review_if, review_tf, review_scf, review_ipf = _split_by_product(review_all)
    status_if, status_tf, status_scf, status_ipf = _split_by_product(status_all)

    ctx.update({
        "review_applications": review_if,
        "review_tf_applications": review_tf,
        "review_scf_applications": review_scf,
        "review_ipf_applications": review_ipf,

        "status_applications": status_if,
        "status_tf_applications": status_tf,
        "status_scf_applications": status_scf,
        "status_ipf_applications": status_ipf,
    })

    return render(request, "operations.html", ctx)

# ---------------------------
# Submit -> update aggregate state to operations_approved
# ---------------------------
@csrf_exempt  # keep consistent with your risk service style across microservices
@require_POST
def operations_submit(request):
    """
    Accepts either JSON or form POST:
      - transaction_id
      - product (optional)
    Updates application_aggregate state to 'operations_approved'
    """
    try:
        # Support JSON and form-encoded
        if request.content_type and "application/json" in request.content_type:
            payload_in = json.loads(request.body or "{}")
            tx = (payload_in.get("transaction_id") or "").strip()
            product = (payload_in.get("product") or "").strip()
        else:
            tx = (request.POST.get("transaction_id") or "").strip()
            product = (request.POST.get("product") or "").strip()

        if not tx:
            # if form POST, just go back
            return redirect("operations")

        new_state = "operations_approved"

        # Preferred endpoint
        url = f"{_aggregate_base()}/api/applications/{tx}/state/"
        status_code, body = _post_json(url, {
            "state": new_state,
            "product": product,   # harmless if aggregate ignores it
            "source": "operations",
        })

        if status_code in (404, 405):
            # Fallback generic state endpoint (same pattern as risk)
            status_code, body = _post_json(f"{_aggregate_base()}/api/applications/state/", {
                "transaction_id": tx,
                "state": new_state,
                "product": product,
                "source": "operations",
            })

        ok = isinstance(body, dict) and (body.get("status") == "success" or body.get("ok") is True)

        # If JSON request, respond JSON
        if request.content_type and "application/json" in (request.content_type or ""):
            return JsonResponse({"success": bool(ok), "raw": body}, status=200 if ok else max(status_code, 400))

        # If form request, redirect back and preserve originator selection
        originator_id = request.GET.get("originators") or request.POST.get("originators")
        if originator_id:
            return redirect(f"/operations/?originators={originator_id}")
        return redirect("operations")

    except Exception as e:
        logger.exception("operations_submit failed")
        if request.content_type and "application/json" in (request.content_type or ""):
            return JsonResponse({"success": False, "error": str(e)}, status=500)
        return redirect("operations")

# ----------------------------
# Form handler (KEEP)
# ----------------------------
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

    return redirect("operations")


def _agents_base() -> str:
    # Prefer Django settings; fallback to env; then localhost
    return getattr(
        settings,
        "EFS_AGENTS_BASE_URL",
        os.getenv("EFS_AGENTS_URL", "http://localhost:8015")
    ).rstrip("/")


# efs_operations/core/views.py
import os
import requests
from django.http import HttpResponse
from django.views.decorators.http import require_GET

@require_GET
def modal_operations_agents(request):
    """
    BFF proxy: browser calls efs_operations, efs_operations fetches modal HTML from efs_agents.
    """
    base = os.getenv("EFS_AGENTS_URL", "http://localhost:8015").rstrip("/")
    abn = request.GET.get("abn", "") or ""
    tx  = request.GET.get("tx", "") or ""

    upstream_url = f"{base}/modal/operations-agents/"
    try:
        resp = requests.get(
            upstream_url,
            params={"abn": abn, "tx": tx},
            timeout=10,
        )
        return HttpResponse(resp.text, status=resp.status_code, content_type="text/html")
    except Exception as e:
        return HttpResponse(
            f"<div class='modal-content'><p>Failed to load Operations Agents modal: {e}</p></div>",
            status=502,
            content_type="text/html",
        )
