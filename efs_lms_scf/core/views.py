import logging
import os
import requests

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)

# ---------------------------
# Service URL helper
# ---------------------------
def _profile_base() -> str:
    return (
        getattr(settings, "EFS_PROFILE_BASE_URL", None)
        or os.getenv("EFS_PROFILE_URL", "http://localhost:8002")
    ).rstrip("/")

# ---------------------------
# Originators (shared pattern)
# ---------------------------
def fetch_originators(timeout: int = 5):
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("originators", data if isinstance(data, list) else [])
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []

def build_base_context(request):
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
# Page view
# ---------------------------
def scf_page(request):
    """
    Renders the Supply Chain Finance page and supplies `originators`
    so the left-hand dropdown in the shared base works.
    """
    ctx = build_base_context(request)
    return render(request, "scf.html", ctx)

# ---------------------------
# Healthcheck
# ---------------------------
def ping(request):
    return JsonResponse({"service": "efs_lms_scf", "status": "ok"})
