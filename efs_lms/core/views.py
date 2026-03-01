from django.shortcuts import render, redirect
import logging, requests
from django.conf import settings

logger = logging.getLogger(__name__)

# --- helpers for fetching originators from efs_profile ---
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

# --- form handler ---
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
    return redirect("efs_lms:lms_page")

# --- LMS pages ---
def lms_page(request):
    ctx = base_context(request)
    return render(request, "lms.html", ctx)

def invoice_finance_page(request):
    ctx = base_context(request)
    return render(request, "invoice_finance.html", ctx)

def scf_page(request):
    ctx = base_context(request)
    return render(request, "scf.html", ctx)

def trade_finance_page(request):
    ctx = base_context(request)
    return render(request, "trade_finance.html", ctx)

def term_loan_page(request):
    ctx = base_context(request)
    return render(request, "term_loan.html", ctx)

def overdraft_page(request):
    ctx = base_context(request)
    return render(request, "overdraft.html", ctx)

def asset_finance_page(request):
    ctx = base_context(request)
    return render(request, "asset_finance.html", ctx)
