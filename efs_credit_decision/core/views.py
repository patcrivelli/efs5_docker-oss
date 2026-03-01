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
    return redirect("sales_home")







#---------start credit decision modal ----
#---------start credit decision modal ----
#---------start credit decision modal ----
#---------start credit decision modal ----
#---------start credit decision modal ----
#---------start credit decision modal ----




# efs_credit_decision/core/views.py
import logging, os, json
from urllib.parse import urlencode, quote
import requests
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import CreditDecisionParametersGlobalSettings

logger = logging.getLogger(__name__)

EFS_SALES_URL = os.getenv("EFS_SALES_URL", "http://localhost:8001").rstrip("/")
TIMEOUT = float(os.getenv("EFS_HTTP_TIMEOUT", "8.0"))

# ---- helpers ---------------------------------------------------------------

def _http_get(url: str):
    resp = requests.get(url, timeout=TIMEOUT)
    ct = (resp.headers.get("content-type") or "").lower()
    if "json" in ct:
        return resp.status_code, resp.json()
    return resp.status_code, {"error": "Upstream did not return JSON", "status": resp.status_code, "body": resp.text[:500]}

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
    """Try multiple URL shapes until one returns non-404."""
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
    """
    Accepts ANY of these shapes:
      { report: { courtJudgements:[...] ... }, creditEnquiries: ... }
      { courtJudgements:[...] ... }  (already flattened)
    Returns a flattened object with camelCase keys your JS understands.
    """
    r = raw or {}
    rep = r.get("report") or {}
    # prefer top-level first, then nested camel, then nested snake
    insolvencies        = _first(r.get("insolvencies"),        rep.get("insolvencies"),        rep.get("insolvencies"))
    paymentDefaults     = _first(r.get("paymentDefaults"),     rep.get("paymentDefaults"),     rep.get("payment_defaults"))
    mercantileEnquiries = _first(r.get("mercantileEnquiries"), rep.get("mercantileEnquiries"), rep.get("mercantile_enquiries"))
    courtJudgements     = _first(r.get("courtJudgements"),     rep.get("courtJudgements"),     rep.get("court_judgements"))
    atoTaxDefault       = _first(r.get("atoTaxDefault"),       rep.get("atoTaxDefault"),       rep.get("ato_tax_default"))
    loans               = _first(r.get("loans"),               rep.get("loans"),               rep.get("loans"))
    anzsic              = _first(r.get("anzsic"),              rep.get("anzsic"),              rep.get("anzsic"))

    # force lists for array fields (your JS checks length)
    def _as_list(x):
        if x is None: return []
        return x if isinstance(x, list) else [x] if x != "No data available" else []

    return {
        "insolvencies":        _as_list(insolvencies),
        "paymentDefaults":     _as_list(paymentDefaults),
        "mercantileEnquiries": _as_list(mercantileEnquiries),
        "courtJudgements":     _as_list(courtJudgements),
        "atoTaxDefault":       _as_list(atoTaxDefault),
        "loans":               _as_list(loans),
        "anzsic":              anzsic or {},  # object, not list
        # surface some common top-level fields if upstream provided them
        "abn": r.get("abn") or rep.get("organisationNumber"),
        "acn": r.get("acn"),
    }

# ---- fragment --------------------------------------------------------------

def credit_decision_modal(request):
    return render(request, "credit_decision.html")

# ---- SETTINGS: local DB ----------------------------------------------------

def _serialize_settings(obj: CreditDecisionParametersGlobalSettings) -> dict:
    if not obj:
        return {
            "originator": None,
            "credit_score_threshold": None,
            "credit_score_switch": False,
            "credit_enquiries_switch": False,
            "court_actions_current_switch": False,
            "court_actions_resolved_switch": False,
            "payment_defaults_current_switch": False,
            "payment_defaults_resolved_switch": False,
            "insolvencies_switch": False,
            "ato_tax_default_switch": False,
        }
    return {
        "originator": obj.originator,
        "credit_score_threshold": obj.credit_score_threshold,
        "credit_score_switch": bool(obj.credit_score_switch),
        "credit_enquiries_switch": bool(obj.credit_enquiries_switch),
        "court_actions_current_switch": bool(obj.court_actions_current_switch),
        "court_actions_resolved_switch": bool(obj.court_actions_resolved_switch),
        "payment_defaults_current_switch": bool(obj.payment_defaults_current_switch),
        "payment_defaults_resolved_switch": bool(obj.payment_defaults_resolved_switch),
        "insolvencies_switch": bool(obj.insolvencies_switch),
        "ato_tax_default_switch": bool(obj.ato_tax_default_switch),
    }

def fetch_credit_settings(request):
    originator = (request.GET.get("originator") or "").strip()
    obj = None
    if originator:
        obj = (CreditDecisionParametersGlobalSettings.objects
               .filter(originator__iexact=originator)
               .order_by("-timestamp").first())

    if not obj:
        obj = (CreditDecisionParametersGlobalSettings.objects
               .filter(originator__isnull=True).order_by("-timestamp").first()) or \
              (CreditDecisionParametersGlobalSettings.objects
               .filter(originator="").order_by("-timestamp").first())

    return JsonResponse(_serialize_settings(obj), status=200)

# ---- BUREAU / OVERRIDES via BFF (with slash fallbacks + normalization) -----

def fetch_credit_score_data(request, abn: str):
    originator = request.GET.get("originator", "")
    url = f"{EFS_SALES_URL}/fetch_credit_score_data/{quote(abn)}/?{urlencode({'originator': originator})}"
    return _get_json(url)

def fetch_credit_report(request, abn: str, tx: str):
    """Proxy to BFF; try both URL shapes; normalize before returning 200 to the UI."""
    paths = [
        f"{EFS_SALES_URL}/fetch_credit_report/{quote(abn)}/{quote(tx)}",
        f"{EFS_SALES_URL}/fetch_credit_report/{quote(abn)}/{quote(tx)}/",
    ]
    status, data = _try_bff_paths(paths)
    if status == 200:
        return JsonResponse(_norm_report_payload(data), status=200)
    # keep upstream status so you can see 404s during dev
    return JsonResponse(data, status=status, safe=False)






def fetch_sales_override(request, tx: str):
    originator = request.GET.get("originator", "")
    paths = [
        f"{EFS_SALES_URL}/fetch_sales_override/{quote(tx)}/?{urlencode({'originator': originator})}",
        f"{EFS_SALES_URL}/fetch_sales_override/{quote(tx)}?{urlencode({'originator': originator})}",
    ]
    status, data = _try_bff_paths(paths)
    return JsonResponse(data, status=status, safe=False)

# ---- receive (unchanged) ---------------------------------------------------

def _check_token(request):
    expected = os.getenv("EFS_INTERNAL_TOKEN") or getattr(__import__("django.conf").conf.settings, "EFS_INTERNAL_TOKEN", "")
    got = request.headers.get("X-Internal-Token", "")
    return expected and got and (expected == got)

@csrf_exempt
def receive_credit_decision(request):
    if request.method != "POST":
        return JsonResponse({"message": "Invalid method"}, status=405)
    if not _check_token(request):
        return HttpResponseForbidden("Invalid internal token")
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        data = {}
    obj = CreditDecisionParametersGlobalSettings.objects.create(
        originator=data.get("originator"),
        credit_score_threshold=data.get("credit_score_threshold"),
        credit_score_switch=data.get("credit_score_switch", False),
        credit_enquiries_switch=data.get("credit_enquiries_switch", False),
        court_actions_current_switch=data.get("court_actions_current_switch", False),
        court_actions_resolved_switch=data.get("court_actions_resolved_switch", False),
        payment_defaults_current_switch=data.get("payment_defaults_current_switch", False),
        payment_defaults_resolved_switch=data.get("payment_defaults_resolved_switch", False),
        insolvencies_switch=data.get("insolvencies_switch", False),
        ato_tax_default_switch=data.get("ato_tax_default_switch", False),
    )
    return JsonResponse({"ok": True, "id": obj.id})




#-------code for modal (credit_decision.html)


# efs_credit_decision/core/views.py
import logging, os, json
from urllib.parse import urlencode, quote
import requests
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import CreditDecisionParametersGlobalSettings

logger = logging.getLogger(__name__)

# ---------- Upstream selection ----------
# Choose which upstream serves bureau/score:
#   EFS_BUREAU_SOURCE=sales   -> go via efs_sales (default)
#   EFS_BUREAU_SOURCE=bureau  -> call efs_data_bureau directly
BUREAU_SOURCE = (os.getenv("EFS_BUREAU_SOURCE", "sales") or "sales").lower()

EFS_SALES_URL       = os.getenv("EFS_SALES_URL", "http://localhost:8001").rstrip("/")
EFS_DATA_BUREAU_URL = os.getenv("EFS_DATA_BUREAU_URL", "http://localhost:8018").rstrip("/")
TIMEOUT             = float(os.getenv("EFS_HTTP_TIMEOUT", "8.0"))

def _bureau_base() -> str:
    return EFS_SALES_URL if BUREAU_SOURCE == "sales" else EFS_DATA_BUREAU_URL

# ---------- HTTP helpers ----------
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
    """Try multiple URL shapes until one returns non-404."""
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
    """
    Accept ANY of these shapes:
      { report: { courtJudgements:[...] ... }, creditEnquiries: ... }
      { courtJudgements:[...] ... }  (already flattened)
    Return flattened camelCase keys the UI expects.
    """
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

# ---------- Template fragment ----------
def cd_modal(request):
    """Render the Credit Decision HTML partial."""
    return render(request, "credit_decision.html")

# ---------- SETTINGS (local DB) ----------
def _serialize_settings(obj: CreditDecisionParametersGlobalSettings) -> dict:
    if not obj:
        return {
            "originator": None,
            "credit_score_threshold": None,
            "credit_score_switch": False,
            "credit_enquiries_switch": False,
            "court_actions_current_switch": False,
            "court_actions_resolved_switch": False,
            "payment_defaults_current_switch": False,
            "payment_defaults_resolved_switch": False,
            "insolvencies_switch": False,
            "ato_tax_default_switch": False,
        }
    return {
        "originator": obj.originator,
        "credit_score_threshold": obj.credit_score_threshold,
        "credit_score_switch": bool(obj.credit_score_switch),
        "credit_enquiries_switch": bool(obj.credit_enquiries_switch),
        "court_actions_current_switch": bool(obj.court_actions_current_switch),
        "court_actions_resolved_switch": bool(obj.court_actions_resolved_switch),
        "payment_defaults_current_switch": bool(obj.payment_defaults_current_switch),
        "payment_defaults_resolved_switch": bool(obj.payment_defaults_resolved_switch),
        "insolvencies_switch": bool(obj.insolvencies_switch),
        "ato_tax_default_switch": bool(obj.ato_tax_default_switch),
    }

def cd_fetch_settings(request):
    """
    Return the latest switches/threshold scoped by originator (fallback to global/default).
    """
    originator = (request.GET.get("originator") or "").strip()
    obj = None
    if originator:
        obj = (CreditDecisionParametersGlobalSettings.objects
               .filter(originator__iexact=originator)
               .order_by("-timestamp").first())

    if not obj:
        obj = (CreditDecisionParametersGlobalSettings.objects
               .filter(originator__isnull=True).order_by("-timestamp").first()) or \
              (CreditDecisionParametersGlobalSettings.objects
               .filter(originator="").order_by("-timestamp").first())

    return JsonResponse(_serialize_settings(obj), status=200)

# ---------- Bureau / Score / Overrides (proxy) ----------
def cd_fetch_score(request, abn: str):
    """
    Proxy to upstream for current score for ABN.
    Adds ?originator= passthrough (harmless if upstream ignores it).
    """
    base = _bureau_base()
    originator = request.GET.get("originator", "")
    url = f"{base}/fetch_credit_score_data/{quote(abn)}/"
    if originator:
        url += f"?{urlencode({'originator': originator})}"
    return _get_json(url)

def cd_fetch_bureau_report(request, abn: str, tx: str):
    """
    Proxy → normalize shape to UI contract.
    Tries both /no-slash and /slash upstream shapes.
    """
    base = _bureau_base()
    paths = [
        f"{base}/fetch_credit_report/{quote(abn)}/{quote(tx)}",
        f"{base}/fetch_credit_report/{quote(abn)}/{quote(tx)}/",
    ]
    status, data = _try_bff_paths(paths)
    if status == 200:
        return JsonResponse(_norm_report_payload(data), status=200)
    return JsonResponse(data, status=status, safe=False)

def cd_fetch_sales_override(request, tx: str):
    """
    Sales overrides live in efs_sales; fetch and pass through.
    """
    originator = request.GET.get("originator", "")
    paths = [
        f"{EFS_SALES_URL}/fetch_sales_override/{quote(tx)}/?{urlencode({'originator': originator})}",
        f"{EFS_SALES_URL}/fetch_sales_override/{quote(tx)}?{urlencode({'originator': originator})}",
    ]
    status, data = _try_bff_paths(paths)
    return JsonResponse(data, status=status, safe=False)

# ---------- receive settings (POST from efs_settings) ----------
def _check_token(request):
    expected = os.getenv("EFS_INTERNAL_TOKEN") or getattr(__import__("django.conf").conf.settings, "EFS_INTERNAL_TOKEN", "")
    got = request.headers.get("X-Internal-Token", "")
    return expected and got and (expected == got)

@csrf_exempt
def cd_receive_settings(request):
    if request.method != "POST":
        return JsonResponse({"message": "Invalid method"}, status=405)
    if not _check_token(request):
        return HttpResponseForbidden("Invalid internal token")
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        data = {}
    obj = CreditDecisionParametersGlobalSettings.objects.create(
        originator=data.get("originator"),
        credit_score_threshold=data.get("credit_score_threshold"),
        credit_score_switch=data.get("credit_score_switch", False),
        credit_enquiries_switch=data.get("credit_enquiries_switch", False),
        court_actions_current_switch=data.get("court_actions_current_switch", False),
        court_actions_resolved_switch=data.get("court_actions_resolved_switch", False),
        payment_defaults_current_switch=data.get("payment_defaults_current_switch", False),
        payment_defaults_resolved_switch=data.get("payment_defaults_resolved_switch", False),
        insolvencies_switch=data.get("insolvencies_switch", False),
        ato_tax_default_switch=data.get("ato_tax_default_switch", False),
    )
    return JsonResponse({"ok": True, "id": obj.id})

