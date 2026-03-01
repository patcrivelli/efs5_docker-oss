# efs_risk/core/views.py
import json
import logging
from types import SimpleNamespace

import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)

# ---------------------------
# Service URL helpers
# ---------------------------
def _aggregate_base() -> str:
    # application_aggregate service (default 8016)
    return getattr(settings, "EFS_APPLICATION_AGGREGATE_BASE_URL", "http://localhost:8016").rstrip("/")

def _profile_base() -> str:
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

def _bureau_base() -> str:
    # your credit-bureau/data-bureau service (default 8018)
    return getattr(settings, "EFS_DATA_BUREAU_BASE_URL", "http://localhost:8018").rstrip("/")

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
# Originators (shared pattern)
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

# ---------------------------
# Aggregate → fetch/normalize
# ---------------------------
# ---------------------------
# Risk actions / proxies
# ---------------------------
@csrf_exempt  # your JS sends CSRF if present; keep this for flexibility across services
def approve_transaction(request):
    """
    Body: { "transaction_id": "...", "decision": "approve"|"reject" }
    → application_aggregate: set 'state' to 'approved' or 'rejected'
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body or "{}")
        tx = data.get("transaction_id")
        decision = (data.get("decision") or "").lower()
        if not tx or decision not in {"approve", "reject"}:
            return JsonResponse({"error": "transaction_id and valid decision required"}, status=400)

        new_state = "risk_approved" if decision == "approve" else "rejected"

        # Preferred endpoint
        patch_url = f"{_aggregate_base()}/api/applications/{tx}/state/"
        status_code, body = _post_json(patch_url, {
            "state": new_state,
            "source": "risk",
        })
        if status_code in (404, 405):
            # Fallback generic state endpoint
            status_code, body = _post_json(f"{_aggregate_base()}/api/applications/state/", {
                "transaction_id": tx,
                "state": new_state,
                "source": "risk",
            })

        ok = isinstance(body, dict) and (body.get("status") == "success" or body.get("ok") is True)
        return JsonResponse({"success": bool(ok), "raw": body}, status=200 if ok else max(status_code, 400))
    except Exception as e:
        logger.exception("approve_transaction failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@require_GET
def credit_report(request):
    """
    Proxy the credit report from your bureau service so the Risk UI can call
    /api/credit-report?abn=...
    """
    abn = request.GET.get("abn")
    if not abn:
        return JsonResponse({"error": "abn required"}, status=400)
    # Support either query form or REST path—adjust to your bureau API
    # Common patterns you've used: /api/credit-report?abn=...  OR  /api/credit-report/<abn>/
    # We'll try query first, then path form as fallback.
    data = _get_json(f"{_bureau_base()}/api/credit-report", params={"abn": abn}) \
        or _get_json(f"{_bureau_base()}/api/credit-report/{abn}/") \
        or {}
    return JsonResponse(data)


# ---------------------------
# Aggregate → fetch/normalize (state-aware)
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
    Try to filter at the aggregate via ?states=... (if supported),
    and ALWAYS apply a local filter as a safety net.
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

    # Local safety net filter
    if states:
        apps = _filter_by_state(apps, states)

    try:
        apps.sort(key=lambda a: a.get("application_time") or "", reverse=True)
    except Exception:
        pass
    return apps

# ---------------------------
# Page
# ---------------------------
def risk_view(request):
    ctx = base_context(request)
    org_name = (ctx.get("selected_originator") or {}).get("originator")

    # 🔑 Only show specific states
    live = _fetch_apps(["risk_review"], org_name)
    completed = _fetch_apps(["risk_approved"], org_name)

    ctx["live_risk_review_applications"] = live
    ctx["completed_risk_review_applications"] = completed
    return render(request, "risk.html", ctx)





   # =====================================================================
   # efs_agents service code 
   # =====================================================================



import os
import requests

from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def modal_risk_agents(request):
    """
    BFF proxy: browser calls efs_risk, efs_risk fetches modal HTML from efs_agents.
    """
    base = os.getenv("EFS_AGENTS_URL", "http://localhost:8015").rstrip("/")
    abn = request.GET.get("abn", "") or ""
    tx  = request.GET.get("tx", "") or ""

    upstream_url = f"{base}/modal/risk-agents/"
    try:
        resp = requests.get(
            upstream_url,
            params={"abn": abn, "tx": tx},
            timeout=10,
        )
        # return raw HTML back to browser
        return HttpResponse(resp.text, status=resp.status_code, content_type="text/html")
    except Exception as e:
        return HttpResponse(
            f"<div class='modal-content'><p>Failed to load Risk Agents modal: {e}</p></div>",
            status=502,
            content_type="text/html",
        )
