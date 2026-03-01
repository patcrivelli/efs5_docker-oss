
# efs_data_bureau/core/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def abn_modal(request):
    return render(request, "abn.html", {
        "abn": request.GET.get("abn"),
        "transaction_id": request.GET.get("tx"),
    })


@require_GET
def credit_report(request):
    # TODO: integrate real data. Match the shape your BFF expects.
    abn = request.GET.get("abn")
    return JsonResponse({
        "report": {
            "insolvencies": [],
            "payment_defaults": [],
            "mercantile_enquiries": [],
            "court_judgements": [],
            "ato_tax_default": None,
            "loans": [],
            "anzsic": {},
        }
    })


# efs_data_bureau/core/views.py
import json
import logging
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import CreditScore, CreditScoreHistory, CreditReport

log = logging.getLogger(__name__)

def _extract_credit_report(report_payload):
    """
    Accepts either:
      - {"creditReport": {...}}  (raw CW)
      - {...}                    (already the inner block)
    Returns a dict with normalized keys for our model.
    """
    if not report_payload:
        return None
    cr = report_payload.get("creditReport") or report_payload
    return {
        "description": cr.get("description", "") or "Credit Report",
        "item_code": cr.get("itemCode", "") or "REPORT",
        "acn": cr.get("acn") or "",
        "credit_enquiries": cr.get("creditEnquiries") or 0,
        # store the whole creditReport block as JSON
        "report_json": cr,
    }

def _extract_credit_score(score_payload):
    """
    Accepts either:
      - {"creditScore": {...}}  (raw CW)
      - {...}                    (already the inner block)
    Returns:
      current_credit_score, description, item_code, history[]
    """
    if not score_payload:
        return None
    cs = score_payload.get("creditScore") or score_payload
    scores = cs.get("scores") or {}
    return {
        "current_credit_score": scores.get("currentCreditScore"),
        "description": cs.get("description", ""),
        "item_code": cs.get("itemCode", ""),
        "history": scores.get("creditScoreHistory") or [],
    }

@csrf_exempt
@require_http_methods(["POST"])
def store_credit_report_data(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
        print("DEBUG store_credit_report_data:", json.dumps(body, indent=2))  # 👈 See payload in console
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Invalid JSON: {e}"}, status=400)

    abn = body.get("abn")
    acn = body.get("acn") or ""
    if not abn:
        return JsonResponse({"success": False, "message": "ABN required"}, status=400)

    # Normalize both snake_case and camelCase
    cr_payload = body.get("credit_report") or body.get("creditReport")
    cs_payload = body.get("credit_score") or body.get("creditScore")

    cr_map = _extract_credit_report(cr_payload)
    cs_map = _extract_credit_score(cs_payload)

    # Save CreditScore
    if cs_map:
        cs_obj = CreditScore.objects.create(
            abn=abn,
            acn=acn,
            current_credit_score=cs_map["current_credit_score"],
            description=cs_map["description"],
            item_code=cs_map["item_code"],
        )
        for h in cs_map["history"]:
            CreditScoreHistory.objects.create(
                abn=abn,
                date=_safe_parse_date(h.get("date")),
                score=h.get("score"),
            )

    # Save CreditReport
    if cr_map:
        CreditReport.objects.create(
            abn=abn,
            acn=acn or cr_map["acn"],
            description=cr_map["description"],
            item_code=cr_map["item_code"],
            credit_enquiries=cr_map["credit_enquiries"],
            report=cr_map["report_json"],
        )

    return JsonResponse({"success": True, "message": "Stored successfully"})


def _safe_parse_date(date_str):
    from datetime import datetime
    if not date_str:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None

# efs_data_bureau/core/views.py
import os
import json
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from .models import ProductsGlobalSettings  # identical model lives here

def _check_token(request):
    expected = os.getenv("EFS_INTERNAL_TOKEN") or getattr(__import__("django.conf").conf.settings, "EFS_INTERNAL_TOKEN", "")
    got = request.headers.get("X-Internal-Token", "")
    return expected and got and (expected == got)

@csrf_exempt
def receive_products(request):
    if request.method != "POST":
        return JsonResponse({"message": "Invalid method"}, status=405)

    if not _check_token(request):
        return HttpResponseForbidden("Invalid internal token")

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        data = {}

    obj = ProductsGlobalSettings.objects.create(
        originator=data.get("originator"),
        term_loan_switch=data.get("term_loan_switch", False),
        term_loan_duration_years=data.get("term_loan_duration_years"),
        term_loan_duration_months=data.get("term_loan_duration_months"),
        overdraft_switch=data.get("overdraft_switch", False),
        overdraft_duration_years=data.get("overdraft_duration_years"),
        overdraft_duration_months=data.get("overdraft_duration_months"),
        credit_card_switch=data.get("credit_card_switch", False),
        credit_card_duration_years=data.get("credit_card_duration_years"),
        credit_card_duration_months=data.get("credit_card_duration_months"),
        bulk_invoice_finance_switch=data.get("bulk_invoice_finance_switch", False),
        single_invoice_finance_switch=data.get("single_invoice_finance_switch", False),
        trade_finance_switch=data.get("trade_finance_switch", False),
        trade_finance_installments=data.get("trade_finance_installments"),
        trade_finance_installment_frequency=data.get("trade_finance_installment_frequency"),
        insurance_premium_funding_switch=data.get("insurance_premium_funding_switch", False),
        insurance_premium_funding_installments=data.get("insurance_premium_funding_installments"),
        insurance_premium_funding_installment_frequency=data.get("insurance_premium_funding_installment_frequency"),
        # timestamp auto add handles itself
    )
    return JsonResponse({"ok": True, "id": obj.id})







# efs_data_bureau/core/views.py

import json
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from .models import CreditDecisionParametersGlobalSettings, ProductsGlobalSettings  # relative imports!


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
        credit_score_threshold=data.get("credit_score_threshold") or 500,
        credit_score_switch=bool(data.get("credit_score_switch")),
        credit_enquiries_switch=bool(data.get("credit_enquiries_switch")),
        court_actions_current_switch=bool(data.get("court_actions_current_switch")),
        court_actions_resolved_switch=bool(data.get("court_actions_resolved_switch")),
        payment_defaults_current_switch=bool(data.get("payment_defaults_current_switch")),
        payment_defaults_resolved_switch=bool(data.get("payment_defaults_resolved_switch")),
        insolvencies_switch=bool(data.get("insolvencies_switch")),
        ato_tax_default_switch=bool(data.get("ato_tax_default_switch")),
        # timestamp auto add handles itself
    )
    return JsonResponse({"ok": True, "id": obj.id})

# efs_data_bureau/core/views.py
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
from .models import CreditReport, CreditDecisionParametersGlobalSettings

def _corsify(resp: HttpResponse) -> HttpResponse:
    # dev-only; tighten for prod (e.g., specific origin, credentials, etc.)
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
    return resp

def abn_modal(request):
    from django.shortcuts import render
    return _corsify(render(request, "abn.html", {}))




# ------------------------------------------------------------
# fetch_credit_report for ABN.html modal  
# ------------------------------------------------------------
from django.views.decorators.http import require_GET
from .models import SalesOverride  # <-- your model
from datetime import datetime, timezone as dt_timezone
# (you probably already have this) 
from django.utils import timezone 


@require_GET
def fetch_credit_report(request, abn, tx):
    abn = _digits(abn)

    try:
        rep = CreditReport.objects.filter(abn=abn).latest("created_at")
    except CreditReport.DoesNotExist:
        return _corsify(JsonResponse({"error": "No credit report found for this ABN"}, status=404))

    raw = rep.report or {}
    # Some sources store at root; others under "report"
    inner = raw.get("report") if isinstance(raw.get("report"), dict) else raw

    # --- normalizers to match the UI's expected keys ---
    def norm_payment_defaults(arr):
        out = []
        for x in (arr or []):
            out.append({
                "posterName": x.get("posterName") or x.get("poster") or x.get("creditor"),
                "amountOutstanding": x.get("amountOutstanding") or x.get("amount") or x.get("value"),
            })
        return out

    def norm_mercantile(arr):
        out = []
        for x in (arr or []):
            out.append({
                "agent": x.get("agent") or x.get("provider") or x.get("status"),
                "phone": x.get("phone"),
                "enquiryDate": x.get("enquiryDate") or x.get("date"),
                "status": x.get("status"),
            })
        return out

    def norm_courts(arr):
        out = []
        for x in (arr or []):
            out.append({
                "action": x.get("action"),
                "location": x.get("location"),
                "plaintiff": x.get("plaintiff"),
                "actionDate": x.get("actionDate") or x.get("date"),
                "judgementAmount": x.get("judgementAmount") or x.get("amount"),
                "proceedingNumber": x.get("proceedingNumber") or x.get("proceedingNo"),
                "natureOfClaimDesc": x.get("natureOfClaimDesc") or x.get("natureOfClaim"),
            })
        return out

    data = {
        "insolvencies":         inner.get("insolvencies", []),
        "paymentDefaults":      norm_payment_defaults(inner.get("paymentDefaults")),
        "mercantileEnquiries":  norm_mercantile(inner.get("mercantileEnquiries")),
        "courtJudgements":      norm_courts(inner.get("courtJudgements")),
        "atoTaxDefault":        inner.get("atoTaxDefault"),
        "loans":                inner.get("loans", []),
        "anzsic":               inner.get("anzsic", {}),
    }
    return _corsify(JsonResponse(data))


from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods

from .models import CreditDecisionParametersGlobalSettings


def _corsify(resp: HttpResponse) -> HttpResponse:
    # Keep this aligned with whatever you had before (origins, credentials, etc.)
    resp["Access-Control-Allow-Origin"] = "*"
    resp["Access-Control-Allow-Credentials"] = "true"
    resp["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
    resp["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return resp


@require_http_methods(["GET", "OPTIONS"])
def fetch_credit_settings(request):
    # Handle preflight nicely
    if request.method == "OPTIONS":
        return _corsify(HttpResponse())

    originator = (request.GET.get("originator") or "").strip()

    # Order newest first; if your model can get same timestamp, break ties by id
    qs = CreditDecisionParametersGlobalSettings.objects.all().order_by("-timestamp", "-id")

    # Tolerant selection:
    # 1) exact originator if provided
    # 2) a row where originator is NULL (global defaults)
    # 3) otherwise just the newest record
    obj = (qs.filter(originator=originator).first() if originator else None) \
          or qs.filter(originator__isnull=True).first() \
          or qs.first()

    if not obj:
        # Sane defaults when table is empty—keeps UI working instead of 404/400
        return _corsify(JsonResponse({
            "originator": originator or "",
            "credit_score_threshold": 500,
            "credit_score_switch": False,
            "credit_enquiries_switch": False,
            "court_actions_current_switch": False,
            "court_actions_resolved_switch": False,
            "payment_defaults_current_switch": False,
            "payment_defaults_resolved_switch": False,
            "insolvencies_switch": False,
            "ato_tax_default_switch": False,
        }))

    data = {
        "originator": obj.originator or "",
        "credit_score_threshold": obj.credit_score_threshold,
        "credit_score_switch": bool(obj.credit_score_switch),
        "credit_enquiries_switch": bool(obj.credit_enquiries_switch),
        "court_actions_current_switch": bool(obj.court_actions_current_switch),
        "court_actions_resolved_switch": bool(obj.court_actions_resolved_switch),
        "payment_defaults_current_switch": bool(obj.payment_defaults_current_switch),
        "payment_defaults_resolved_switch": bool(obj.payment_defaults_resolved_switch),
        "insolvencies_switch": bool(obj.insolvencies_switch),
        "ato_tax_default_switch": bool(obj.ato_tax_default_switch),
        "timestamp": obj.timestamp.isoformat() if obj.timestamp else None,
    }
    return _corsify(JsonResponse(data))





def _now_iso() -> str:
    """
    Return timezone-aware ISO timestamp.
    Prefer Django's timezone.now(); fall back to stdlib UTC if unavailable.
    """
    try:
        return timezone.now().isoformat()
    except Exception:
        return datetime.now(dt_timezone.utc).isoformat()

# Visible label -> model field base name
LABEL_TO_FIELD = {
    "Insolvencies":           "Insolvencies",
    "Payment Defaults":       "Payment_Defaults",
    "Mercantile Enquiries":   "Mercantile_Enquiries",
    "Court Judgements":       "Court_Judgements",
    "ATO Tax Default":        "ATO_Tax_Default",
    "Loans":                  "Loans",
    "ANZSIC":                 "ANZSIC",
}

# ---------- save (only ON→OFF overrides + notes) ----------
@csrf_exempt
@require_POST
def save_abn_modal(request):
    import json, uuid
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return _corsify(JsonResponse({"ok": False, "error": "invalid JSON"}, status=400))

    abn_raw = (body.get("abn") or "").strip()
    tx_raw  = (body.get("transaction_id") or "").strip()
    notes   = (body.get("Sales_notes") or "").strip()
    overrides = body.get("overrides") or []
    credit_score_state = body.get("Credit_score_threshold_state")

    abn = _digits(abn_raw)
    if not abn:
        return _corsify(JsonResponse({"ok": False, "error": "ABN required"}, status=400))

    # try to parse UUID; if bad, just ignore it (store NULL)
    tx = None
    if tx_raw:
        try:
            tx = uuid.UUID(tx_raw)
        except Exception:
            # optional: log a warning instead of breaking the UX
            # logger.warning("save_abn_modal: non-UUID transaction_id=%r", tx_raw)
            tx = None

    if not notes and not overrides and credit_score_state not in ("below", "above"):
        return _corsify(JsonResponse({"ok": True, "saved": False, "reason": "no changes"}))

    fields = {
        "ABN": abn,
        "Sales_notes": notes or None,
    }
    if tx:
        fields["transactionID"] = tx
    if credit_score_state in ("below", "above"):
        fields["Credit_score_threshold_state"] = credit_score_state

    for label in overrides:
        base = LABEL_TO_FIELD.get(label)
        if not base:
            continue
        exists_flag = body.get(base)
        if exists_flag is None:
            exists_flag = True
        fields[base] = bool(exists_flag)
        fields[f"{base}_state"] = "closed"

    obj = SalesOverride.objects.create(**fields)
    return _corsify(JsonResponse({"ok": True, "id": obj.id, "saved_at": _now_iso()}, status=201))

# ---------- simple history for the modal ----------
@require_GET
def fetch_override_history(request, abn, tx):
    """
    Return prior SalesOverride rows for this ABN (and optional tx),
    newest first. The modal uses this to render the History tab.
    """
    abn = _digits(abn)
    rows = SalesOverride.objects.filter(ABN=abn).order_by("-created_at")
    if tx:
        try:
            tx_uuid = uuid.UUID(str(tx))
            rows = rows.filter(transactionID=tx_uuid)
        except Exception:
            pass

    out = []
    for r in rows:
        out.append({
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "Sales_notes": r.Sales_notes or "",
            # expose each field (NULLs mean “not part of this override”)
            "Insolvencies_state": r.Insolvencies_state,
            "Payment_Defaults_state": r.Payment_Defaults_state,
            "Mercantile_Enquiries_state": r.Mercantile_Enquiries_state,
            "Court_Judgements_state": r.Court_Judgements_state,
            "ATO_Tax_Default_state": r.ATO_Tax_Default_state,
            "Loans_state": r.Loans_state,
            "ANZSIC_state": r.ANZSIC_state,
            "Credit_score_threshold_state": r.Credit_score_threshold_state,
        })
    return _corsify(JsonResponse(out, safe=False))





# ------------------------------------------------------------
# fetch_credit_scrore for credit_score.html modal
# ------------------------------------------------------------

# efs_data_bureau/core/views.py (additions / replacements)

from django.http import JsonResponse, HttpResponse  # (you already import these elsewhere)
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .models import CreditScore, CreditScoreHistory, CreditReport  # make sure these exist


# --- helpers ---
def _digits(s: str) -> str:
    """Keep digits only (strips bidi controls, spaces, etc.)."""
    return "".join(ch for ch in (s or "") if ch.isdigit())


@require_GET
def credit_score_modal(request):
    """
    Returns the credit score modal HTML (template lives beside abn.html).
    Sales service proxies to this via /sales/modal/credit-score.
    """
    # Pass through raw values to the template; client JS will also sanitize before calling APIs.
    abn = (request.GET.get("abn") or "").strip()
    tx  = (request.GET.get("tx") or "").strip()
    html = render(request, "credit_score.html", {"abn": abn, "tx": tx}).content
    return _corsify(HttpResponse(html))


@require_GET
def credit_score_history(request, abn: str):
    """
    JSON time series for the chart. Returns:
      {"history": [{"date":"YYYY-MM-DD","score":123}, ...]}
    """
    abn = _digits(abn)

    rows = (
        CreditScoreHistory.objects
        .filter(abn=abn)
        .order_by("date", "created_at")
    )
    history = [
        {"date": r.date.isoformat(), "score": int(r.score)}
        for r in rows
        if r.date and r.score is not None
    ]
    return _corsify(JsonResponse({"history": history}))


# efs_data_bureau/core/views.py
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from .models import CreditScore, CreditReport  # add CreditReport only if you want the fallback


@require_GET
def credit_score(request, abn: str):
    """
    Return the most recent credit score for an ABN.
    Shape expected by efs_sales is: {"current_credit_score": <int|null>}
    Optional extras ("threshold", "threshold_switch") are added if a settings model exists,
    but absence must not break this endpoint.
    """
    abn = _digits(abn)
    originator = (request.GET.get("originator") or "").strip() or None

    score_val = None

    # 1) Primary: CreditScore row
    cs = (
        CreditScore.objects
        .filter(abn=abn)
        .order_by("-created_at", "-updated_at")
        .first()
    )
    if cs and cs.current_credit_score is not None:
        score_val = int(cs.current_credit_score)

    # 2) Fallback: CreditReport JSON (supports multiple shapes)
    if score_val is None:
        try:
            rep = CreditReport.objects.filter(abn=abn).latest("created_at")
            rpt = rep.report or {}

            # try several shapes
            candidates = [
                rpt.get("creditEnquiries"),
                (rpt.get("report") or {}).get("creditEnquiries") if isinstance(rpt.get("report"), dict) else None,
                (rpt.get("summary") or {}).get("creditEnquiries"),
                (rpt.get("report", {}).get("summary", {}) if isinstance(rpt.get("report"), dict) else {}).get("creditEnquiries"),
            ]
            score_val = next((int(x) for x in candidates if isinstance(x, (int, float, str)) and str(x).isdigit()), None)
        except CreditReport.DoesNotExist:
            pass
        except Exception:
            score_val = score_val or None  # never crash

    payload = {"current_credit_score": score_val}

    # 3) OPTIONAL: attach threshold/switch (defensive)
    try:
        from .models import CreditSettings  # adjust to your actual settings model name
        if originator:
            s = (
                CreditSettings.objects
                .filter(originator__iexact=originator)
                .order_by("-updated_at", "-created_at")
                .first()
            )
            if s:
                payload["threshold"] = getattr(s, "credit_score_threshold", None)
                payload["threshold_switch"] = bool(getattr(s, "credit_score_switch", False))
    except Exception:
        pass

    return _corsify(JsonResponse(payload))






from django.http import JsonResponse
from django.apps import apps

def list_models(request):
    # Limit to models in this app only
    app_models = apps.get_app_config("core").get_models()
    model_names = [m.__name__ for m in app_models]
    return JsonResponse({"models": model_names})






# ---- -----------------------------------------------

# Credit Bureau end points for the efs_agents service 
# ---------------------------------------------------

# efs_data_bureau/core/views.py
from django.http import JsonResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from .models import CreditReport

def _digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

@require_GET
def bureau_summary(request, abn: str):
    abn = _digits(abn)
    try:
        row = (CreditReport.objects
               .filter(abn=abn)
               .order_by("-created_at", "-updated_at")
               .first())
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

    if not row:
        return HttpResponseNotFound("No credit report for that ABN")

    # Return the raw record as-is; Agents will normalize.
    payload = {
        "abn": row.abn,
        "acn": row.acn,
        "creditEnquiries": row.credit_enquiries,
        "itemCode": row.item_code,
        "description": row.description,
        "report": row.report,   # ← your big JSON (anzsic, courtJudgements, defaults, etc.)
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return JsonResponse(payload)



# efs_data_bureau/core/views.py
from django.http import JsonResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from .models import CreditReport, CreditScore, CreditScoreHistory

def _digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

@require_GET
def bureau_score(request, abn: str):
    abn = _digits(abn)
    row = (CreditScore.objects
           .filter(abn=abn)
           .order_by("-updated_at", "-created_at")
           .first())
    if not row:
        return HttpResponseNotFound("No credit score for that ABN")
    payload = {
        "abn": row.abn,
        "acn": row.acn,
        "current_credit_score": row.current_credit_score,
        "description": row.description,
        "item_code": row.item_code,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    return JsonResponse(payload)

@require_GET
def bureau_score_history(request, abn: str):
    abn = _digits(abn)
    qs = (CreditScoreHistory.objects
          .filter(abn=abn)
          .order_by("-date", "-updated_at", "-created_at"))
    if not qs.exists():
        return HttpResponseNotFound("No credit score history for that ABN")
    items = [{
        "abn": h.abn,
        "date": h.date.isoformat() if h.date else None,
        "score": h.score,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
    } for h in qs]
    return JsonResponse(items, safe=False)




 #---- -----------------------------------------------

# file upload endpoint for efs_apis service

# ---------------------------------------------------


# efs_data_bureau/core/views.py
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

try:
    # PyPDF2 >= 3.x
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from bs4 import BeautifulSoup  # for XML parsing path
except Exception:
    BeautifulSoup = None

from .models import CreditReport, CreditScore  # <-- your models in this service

logger = logging.getLogger(__name__)

# ------------ regex helpers ------------

ABN_RE = re.compile(r"\bABN[:\s]+(\d{2}\s?\d{3}\s?\d{3}\s?\d{3}|\d{11})\b", re.IGNORECASE)
ACN_RE = re.compile(r"\bACN[:\s]+(\d{3}\s?\d{3}\s?\d{3}|\d{9})\b", re.IGNORECASE)

# Score appears as "A3 / 692", "RiskScore 692 / 850", etc.
SCORE_BLOCK_RE = re.compile(
    r"\b(Risk\s*Score|RiskScore|Credit\s*Score)\b.*?(?:^|\b)([A-Z]\d)?\s*[/\-:,]*\s*(\d{2,3})\s*/\s*850",
    re.IGNORECASE | re.DOTALL,
)

# More tolerant: handle the "A3 / 692" that precedes "Very Low Risk"
A3_692_RE = re.compile(r"\b([A-Z]\d)\s*[/\-:,]*\s*(\d{2,3})\b", re.IGNORECASE)

TOTAL_ENQUIRIES_12M_RE = re.compile(
    r"(Total\s+Enquiries\s*\(.*?last\s*12\s*months.*?\)|Last\s*12\s*Months)\D+(\d{1,4})",
    re.IGNORECASE | re.DOTALL,
)

ANZSIC_HEADER_RE = re.compile(r"^\s*ANZSIC\s*Classification\s*$", re.IGNORECASE)

def _tidy_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def _find_first_text(regex: re.Pattern, text: str, default: str | None = None) -> str | None:
    m = regex.search(text or "")
    if not m:
        return default
    return (m.group(1) if m.lastindex else m.group(0)) or default

# ------------ PDF → XML (preferred) / text (fallback) ------------

def _pdf_to_xml_text_lines(pdf_path: str) -> list[str]:
    """
    Preferred path: uses `pdftohtml -xml` to keep layout order stable.
    Returns a flat list of lines (page order).
    """
    if shutil.which("pdftohtml") is None:
        return []

    if BeautifulSoup is None:
        logger.warning("bs4 is not installed; cannot use XML parsing path.")
        return []

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as xml_tmp:
        xml_path = xml_tmp.name

    try:
        # -c preserve layout, -hidden include hidden text, -xml XML output
        subprocess.run(
            ["pdftohtml", "-c", "-hidden", "-xml", pdf_path, xml_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "lxml-xml")

        lines: list[str] = []
        for page in soup.find_all("page"):
            for t in page.find_all("text"):
                txt = (t.get_text() or "").strip("\r\n")
                if txt:
                    lines.append(txt)
        return lines
    except Exception as e:
        logger.exception("pdftohtml XML parse failed")
        return []
    finally:
        try:
            os.remove(xml_path)
        except Exception:
            pass

def _pdf_to_plain_text_lines(pdf_path: str) -> list[str]:
    """
    Fallback path: PyPDF2 to plain text.
    """
    if PdfReader is None:
        return []
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages) or ""
        return [ln for ln in text.splitlines()]
    except Exception:
        logger.exception("PyPDF2 text extraction failed")
        return []

def _load_pdf_lines_from_uploaded_file(django_file) -> list[str]:
    """
    Copy uploaded file to temp path, then attempt XML route; fallback to plain text.
    """
    with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp:
        for chunk in django_file.chunks():
            tmp.write(chunk)
        tmp.flush()

        # Try XML-first
        lines = _pdf_to_xml_text_lines(tmp.name)
        if lines:
            return lines

        # Fallback
        return _pdf_to_plain_text_lines(tmp.name)

# ------------ domain parsing ------------

def _extract_score(lines: list[str]) -> tuple[int | None, str | None]:
    """
    Finds the first risk/credit score occurrence.
    Tries structured pattern first, then tolerant pattern like 'A3 / 692'.
    Returns (numeric_score, band) e.g., (692, "A3")
    """
    blob = "\n".join(lines)

    m = SCORE_BLOCK_RE.search(blob)
    if m:
        band = (m.group(2) or "").strip() or None
        try:
            score = int(m.group(3))
        except Exception:
            score = None
        return score, band

    # Tolerant: scan windows around RiskScore blocks or the A3/692 near "Very Low Risk"
    for i, ln in enumerate(lines):
        if "Very Low Risk" in ln or "RiskScore" in ln or "Credit Score" in ln:
            window = "\n".join(lines[max(0, i - 6): i + 6])
            mm = A3_692_RE.search(window)
            if mm:
                band = mm.group(1).strip().upper()
                try:
                    score = int(mm.group(2))
                except Exception:
                    score = None
                return score, band

    # absolute fallback: first "nnn / 850"
    m2 = re.search(r"\b(\d{2,3})\s*/\s*850\b", blob)
    if m2:
        try:
            return int(m2.group(1)), None
        except Exception:
            pass

    return None, None

def _extract_ids(lines: list[str]) -> tuple[str, str]:
    blob = "\n".join(lines)
    abn_raw = _find_first_text(ABN_RE, blob, "") or ""
    acn_raw = _find_first_text(ACN_RE, blob, "") or ""
    return _tidy_digits(abn_raw), _tidy_digits(acn_raw)

def _extract_credit_enquiries_12m(lines: list[str]) -> int:
    """
    Pulls 'Total Enquiries (within the last 12 months)' or a nearby
    'Last 12 Months' number. Your sample shows `42`.
    """
    blob = "\n".join(lines)
    m = TOTAL_ENQUIRIES_12M_RE.search(blob)
    if m:
        try:
            return int(m.group(2))
        except Exception:
            pass

    # Secondary heuristic: scan a page that contains 'Credit Enquiries' header
    # and look for a standalone integer on/near a line 'Last 12 Months'
    for i, ln in enumerate(lines):
        if re.search(r"Credit\s+Enquiries", ln, re.I):
            win = lines[i:i+80]
            # try to find "Total Enquiries" then a number
            for j, w in enumerate(win):
                mt = re.search(r"Total\s+Enquiries.*?(\d{1,4})", w, re.I)
                if mt:
                    try:
                        return int(mt.group(1))
                    except Exception:
                        pass
            # otherwise, look for 'Last 12 Months' followed by a number line
            for j in range(len(win) - 1):
                if re.search(r"Last\s+12\s+Months", win[j], re.I):
                    nxt = re.sub(r"[^\d]", "", win[j+1])
                    if nxt.isdigit():
                        return int(nxt)
    return 0

def _extract_anzsic_descriptions(lines: list[str]) -> dict | None:
    """
    From the 'ANZSIC Classification' block:
      Information Media and Telecommunications
      Publishing (except Internet and Music Publishing)
      Newspaper, Periodical, Book and Directory Publishing
      Magazine and Other Periodical Publishing
    We’ll store these as descriptive fields; codes are unknown in the sample.
    """
    # Find the header line index
    idx = None
    for i, ln in enumerate(lines):
        if ANZSIC_HEADER_RE.match(ln.strip()):
            idx = i
            break
    if idx is None:
        return None

    # Collect next non-empty lines until we hit an obvious next section
    collected: list[str] = []
    for ln in lines[idx + 1: idx + 10]:  # look ahead a few lines only
        t = ln.strip()
        if not t:
            break
        # stop if we hit another big section heading
        if re.match(r"^(Report Generated|ASIC Extract|RiskScore|Payment Rating|Credit Enquiries|Risk Data|Registered Addresses)\b", t):
            break
        collected.append(t)

    if not collected:
        return None

    # Map the 1..4 lines into hierarchical descriptions (best-effort)
    return {
        "divisionDescription": collected[0] if len(collected) >= 1 else None,
        "subdivisionDescription": collected[1] if len(collected) >= 2 else None,
        "groupDescription": collected[2] if len(collected) >= 3 else None,
        "anzsicDescription": collected[3] if len(collected) >= 4 else None,
        # Codes unknown in sample; leave them None
        "divisionCode": None,
        "subdivisionCode": None,
        "groupCode": None,
        "anzsicCode": None,
    }

def _has_text(blob: str, *phrases: str) -> bool:
    blob_low = blob.lower()
    return any(p.lower() in blob_low for p in phrases)

def _extract_court_judgements(lines: list[str]) -> list[dict]:
    """
    Your sample explicitly says 'No Court Actions' under Risk Data.
    We'll detect that and return [].
    """
    blob = "\n".join(lines)
    if _has_text(blob, "No Court Actions"):
        return []
    # (If later reports include rows, extend parser here.)
    return []

def _extract_payment_defaults(lines: list[str]) -> list[dict]:
    blob = "\n".join(lines)
    if _has_text(blob, "No Payment Defaults Lodged"):
        return []
    return []

def _extract_insolvencies(lines: list[str]) -> list[dict]:
    """
    Map from 'Bankruptcy Search Result Summary ... No bankruptcy matches found'
    to empty list.
    """
    blob = "\n".join(lines)
    if _has_text(blob, "Bankruptcy Search Result Summary") and _has_text(blob, "No bankruptcy matches found"):
        return []
    # If you want to also zero out when 'No ASIC Published Notices' appears, you can:
    # if _has_text(blob, "No ASIC Published Notices"):
    #     return []
    return []

def _extract_mercantile_enquiries(lines: list[str]) -> list[dict]:
    """
    Sample shows a single past 'Mercantile Enquiry Lodged' with a date.
    We'll capture the date and short description if present.
    """
    out: list[dict] = []
    # simple sweep to find date lines followed by 'Mercantile Enquiry Lodged'
    date_re = re.compile(r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b")
    for i, ln in enumerate(lines):
        if "Mercantile Enquiry Lodged" in ln:
            # look back a few lines for a date
            for j in range(max(0, i - 3), i + 1):
                m = date_re.search(lines[j])
                if m:
                    out.append({
                        "enquiryDate": m.group(1),
                        "status": "Mercantile Enquiry Lodged",
                        "agent": None,
                    })
                    break
    return out

def _build_report_json(abn: str, acn: str, score_val: int | None, lines: list[str]) -> tuple[dict, int]:
    """
    Build the JSON object for CreditReport.report and return (report_json, credit_enquiries_int).
    """
    anzsic = _extract_anzsic_descriptions(lines)
    credit_enquiries_12m = _extract_credit_enquiries_12m(lines)
    court_judgements = _extract_court_judgements(lines)
    payment_defaults = _extract_payment_defaults(lines)
    insolvencies = _extract_insolvencies(lines)
    mercantile = _extract_mercantile_enquiries(lines)

    report = {
        "summary": {
            "abn": abn or "",
            "acn": acn or "",
            "score": {"band": None, "value": score_val, "outOf": 850},
            "creditEnquiries": credit_enquiries_12m,
        },
        "anzsic": anzsic,
        "loans": [],  # no loans section in sample pages provided
        "insolvencies": insolvencies,
        "courtJudgements": court_judgements,
        "paymentDefaults": payment_defaults,
        "mercantileEnquiries": mercantile,
    }
    return report, int(credit_enquiries_12m or 0)

# ------------ the upload view ------------

@csrf_exempt
def upload_credit_report_pdf(request):
    """
    POST multipart/form-data:
      - file: PDF credit report
      - abn (optional; will try to read from PDF if missing)
      - acn (optional; will try to read from PDF if missing)

    Creates/updates:
      - CreditReport (item_code='credit_report_pdf', description='Credit Report Extract for ABN#/ACN#')
      - CreditScore   (item_code='credit_score_pdf', description='RiskScore <band>')

    Response:
      { success: true, credit_report_id, credit_score_id, abn, acn }
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST required"}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file provided"}, status=400)

    f = request.FILES["file"]
    if not f.name.lower().endswith(".pdf"):
        return JsonResponse({"success": False, "message": "Only PDF files are accepted"}, status=400)

    # Optional hints from the client
    abn_hint = (request.POST.get("abn") or "").strip()
    acn_hint = (request.POST.get("acn") or "").strip()

    try:
        # 1) Load lines (XML-first → PyPDF2 fallback)
        lines = _load_pdf_lines_from_uploaded_file(f)
        if not lines:
            return JsonResponse({"success": False, "message": "Unable to extract text from PDF (check pdftohtml/bs4/PyPDF2 installation)."}, status=500)

        # 2) Extract IDs and score
        abn_auto, acn_auto = _extract_ids(lines)
        abn = _tidy_digits(abn_hint) or abn_auto
        acn = _tidy_digits(acn_hint) or acn_auto

        score_value, score_band = _extract_score(lines)

        # 3) Build report JSON (only the sections you need)
        report_json, credit_enquiries_int = _build_report_json(abn, acn, score_value, lines)

        # 4) Persist CreditReport
        description = f"Credit Report Extract for ABN# {abn or '—'} / ACN# {acn or '—'}"
        cr = CreditReport.objects.create(
            description=description[:255],
            item_code="credit_report_pdf",
            abn=abn or "",
            acn=acn or "",
            credit_enquiries=credit_enquiries_int,
            report=report_json,
        )

        # 5) Upsert CreditScore for this ABN/ACN
        score_desc = f"RiskScore {score_band or ''}".strip() if (score_band or score_value is not None) else None
        cs, _created = CreditScore.objects.update_or_create(
            abn=abn or None,
            acn=acn or None,
            defaults={
                "current_credit_score": score_value,
                "description": (score_desc[:255] if score_desc else None),
                "item_code": "credit_score_pdf",
            },
        )

        return JsonResponse({
            "success": True,
            "abn": abn,
            "acn": acn,
            "credit_report_id": cr.id,
            "credit_score_id": cs.id,
            "message": "Credit report parsed and stored (XML-first parser).",
        })

    except Exception as e:
        logger.exception("Failed to parse credit report PDF")
        return JsonResponse({"success": False, "message": str(e)}, status=500)




#-------endpoint  code for efs_credit_decision service 
    #-------endpoint  code for efs_credit_decision service 
    #-------endpoint  code for efs_credit_decision service 
    #-------endpoint  code for efs_credit_decision service 
    #-------endpoint  code for efs_credit_decision service 
    #-------endpoint  code for efs_credit_decision service 
    
    # efs_data_bureau/core/views.py
import re
from django.http import JsonResponse, HttpResponseNotFound
from .models import CreditReport, CreditScore

# ---------- helpers (unchanged) ----------
def _digits(s: str) -> str:
    return re.sub(r"\D", "", (s or ""))

def _as_list(x):
    if x is None: return []
    if x == "No data available": return []
    return x if isinstance(x, list) else [x]

def _norm_report_payload(raw: dict) -> dict:
    """
    Normalizes raw/DB credit report JSON into the camelCase keys
    that the Credit Decision UI expects. This endpoint is used by
    the efs_credit_decision feature (via BFF or direct).
    """
    r = raw or {}
    rep = r.get("report") or {}

    def first(*vals):
        for v in vals:
            if v is not None:
                return v
        return None

    return {
        "insolvencies":        _as_list(first(r.get("insolvencies"),        rep.get("insolvencies"))),
        "paymentDefaults":     _as_list(first(r.get("paymentDefaults"),     rep.get("paymentDefaults"),     rep.get("payment_defaults"))),
        "mercantileEnquiries": _as_list(first(r.get("mercantileEnquiries"), rep.get("mercantileEnquiries"), rep.get("mercantile_enquiries"))),
        "courtJudgements":     _as_list(first(r.get("courtJudgements"),     rep.get("courtJudgements"),     rep.get("court_judgements"))),
        "atoTaxDefault":             first(r.get("atoTaxDefault"),          rep.get("atoTaxDefault"),       rep.get("ato_tax_default")),
        "loans":               _as_list(first(r.get("loans"),               rep.get("loans"))),
        "anzsic":                    first(r.get("anzsic"),                  rep.get("anzsic")) or {},
        "abn": r.get("abn") or rep.get("organisationNumber"),
        "acn": r.get("acn"),
    }

# ---------- explicit, credit-decision-namespaced views ----------
# ---------- explicit, credit-decision-namespaced views ----------
# ---------- explicit, credit-decision-namespaced views ----------
# ---------- explicit, credit-decision-namespaced views ----------
# ---------- explicit, credit-decision-namespaced views ----------
# ---------- explicit, credit-decision-namespaced views ----------


def cd_bureau_fetch_credit_report(request, abn: str, tx: str):
    """
    [efs_credit_decision] Get normalized bureau report for an ABN.
    URL is kept the same; only the view func name is explicit.
    """
    abn_clean = _digits(abn)
    q = CreditReport.objects.filter(abn=abn_clean).order_by("-updated_at", "-created_at")
    if not q.exists():
        return HttpResponseNotFound(JsonResponse({"error": "not found"}).content)
    doc = q.first()
    payload = {
        "abn": doc.abn,
        "acn": doc.acn,
        "creditEnquiries": doc.credit_enquiries,
        **_norm_report_payload(doc.report),
    }
    return JsonResponse(payload, status=200)

def cd_bureau_fetch_credit_score(request, abn: str):
    """
    [efs_credit_decision] Get latest credit score for an ABN.
    URL is kept the same; only the view func name is explicit.
    """
    abn_clean = _digits(abn)
    score = CreditScore.objects.filter(abn=abn_clean).order_by("-timestamp").first()
    return JsonResponse({"current_credit_score": getattr(score, "current_credit_score", None)}, status=200)

# ---------- thin wrappers for backward compatibility ----------
# (Keep old function names alive in case anything imports them.)
def fetch_credit_report(request, abn: str, tx: str):
    return cd_bureau_fetch_credit_report(request, abn, tx)

def fetch_credit_score_data(request, abn: str):
    return cd_bureau_fetch_credit_score(request, abn)

# efs_data_bureau/core/views.py
from django.http import JsonResponse, HttpResponseNotFound
from .models import SalesOverride  # ← import your model

def _normalize_override_row(row: SalesOverride) -> dict:
    """
    Turn a SalesOverride row (open/closed + existence booleans) into the shape
    the UI can easily consume. We also expose 'raw' for debugging.
    'Override Yes' means: user closed a check that actually exists.
    """
    def ov_yes(exists_bool, state_val):
        return bool(exists_bool) and str(state_val or '').lower() == 'closed'

    data = {
        # short booleans the UI could use if wanted
        "flags": {
            "Insolvencies":         ov_yes(row.Insolvencies,         row.Insolvencies_state),
            "Payment_Defaults":     ov_yes(row.Payment_Defaults,     row.Payment_Defaults_state),
            "Mercantile_Enquiries": ov_yes(row.Mercantile_Enquiries, row.Mercantile_Enquiries_state),
            "Court_Judgements":     ov_yes(row.Court_Judgements,     row.Court_Judgements_state),
            "ATO_Tax_Default":      ov_yes(row.ATO_Tax_Default,      row.ATO_Tax_Default_state),
            "Loans":                ov_yes(row.Loans,                row.Loans_state),
            "ANZSIC":               ov_yes(row.ANZSIC,               row.ANZSIC_state),
            "Credit_Score_Threshold": str(row.Credit_score_threshold_state or '').lower() == 'below',
        },
        # human strings used by the table
        "Insolvencies_state":         "Override Yes" if ov_yes(row.Insolvencies,         row.Insolvencies_state) else "Override No",
        "Payment_Defaults_state":     "Override Yes" if ov_yes(row.Payment_Defaults,     row.Payment_Defaults_state) else "Override No",
        "Mercantile_Enquiries_state": "Override Yes" if ov_yes(row.Mercantile_Enquiries, row.Mercantile_Enquiries_state) else "Override No",
        "Court_Judgements_state":     "Override Yes" if ov_yes(row.Court_Judgements,     row.Court_Judgements_state) else "Override No",
        "ATO_Tax_Default_state":      "Override Yes" if ov_yes(row.ATO_Tax_Default,      row.ATO_Tax_Default_state) else "Override No",
        "Loans_state":                "Override Yes" if ov_yes(row.Loans,                row.Loans_state) else "Override No",
        "ANZSIC_state":               "Override Yes" if ov_yes(row.ANZSIC,               row.ANZSIC_state) else "Override No",
        "Credit_Score_Threshold_state": "Override Yes" if str(row.Credit_score_threshold_state or '').lower() == 'below' else "Override No",
        "Sales_notes": row.Sales_notes or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "ABN": row.ABN, "transactionID": str(row.transactionID) if row.transactionID else None,
        # raw echoes for debugging (optional)
        "raw": {
            "Insolvencies": row.Insolvencies, "Insolvencies_state": row.Insolvencies_state,
            "Payment_Defaults": row.Payment_Defaults, "Payment_Defaults_state": row.Payment_Defaults_state,
            "Mercantile_Enquiries": row.Mercantile_Enquiries, "Mercantile_Enquiries_state": row.Mercantile_Enquiries_state,
            "Court_Judgements": row.Court_Judgements, "Court_Judgements_state": row.Court_Judgements_state,
            "ATO_Tax_Default": row.ATO_Tax_Default, "ATO_Tax_Default_state": row.ATO_Tax_Default_state,
            "Loans": row.Loans, "Loans_state": row.Loans_state,
            "ANZSIC": row.ANZSIC, "ANZSIC_state": row.ANZSIC_state,
            "Credit_score_threshold_state": row.Credit_score_threshold_state,
        }
    }
    return data

@require_GET
def fetch_sales_override_current(request, tx: str):
    """
    Return the latest SalesOverride for this transaction, normalized to show
    'Override Yes/No' for each item.
    """
    try:
        row = (SalesOverride.objects
               .filter(transactionID=tx)
               .order_by("-created_at", "-id").first())
        if not row:
            return HttpResponseNotFound(JsonResponse({"error": "not found"}).content)
        return JsonResponse(_normalize_override_row(row), status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
