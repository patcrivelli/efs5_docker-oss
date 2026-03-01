import logging
import requests
from django.conf import settings
from django.shortcuts import render, redirect

logger = logging.getLogger(__name__)

def _profile_base():
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

def _api_key_header():
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def fetch_originators():
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        logger.exception("Failed to fetch originators")
        return []

def base_context(request):
    originators = fetch_originators()
    selected = None
    selected_id = request.GET.get("originators")
    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected = o
                break
    return {"originators": originators, "selected_originator": selected}

def pnl_home(request):
    return render(request, "pnl_home.html", base_context(request))

def pnl_view(request):
    ctx = base_context(request)
    return render(request, "pnl.html", ctx)

def create_originator(request):
    if request.method == "POST":
        payload = {
            "originator": request.POST.get("originator_name"),
            "created_by": request.POST.get("username"),
        }
        try:
            r = requests.post(f"{_profile_base()}/api/originators/create/",
                              json=payload, headers=_api_key_header(), timeout=5)
            if r.status_code not in (200, 201):
                logger.error("Originator create failed: %s %s", r.status_code, r.text)
        except Exception:
            logger.exception("Error calling efs_profile create originator")
    return redirect("pnl_home")
