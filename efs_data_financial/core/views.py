# efs_finance/core/views.py
import logging
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from .models import Registration  # keep this high in the file
from django.db.models import Q, Sum, F
from django.db.models.functions import Coalesce
from django.db.models import DecimalField
from django.utils.timezone import localtime
from django.http import JsonResponse, HttpResponseBadRequest
from decimal import Decimal
logger = logging.getLogger(__name__)

# efs_data_financial/core/views.py
from django.http import JsonResponse

def ping(request):
    return JsonResponse({"status": "ok", "service": "efs_data_financial"})


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





#--------#--------#--------#--------#--------
    
#   Invoice finance 


#--------#--------#--------#--------#--------



import json, logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import LoanApplicationService

logger = logging.getLogger(__name__)

@csrf_exempt
def receive_invoice_data(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)
    payload = json.loads(request.body or "{}")
    result = LoanApplicationService.process_invoice_data(payload)
    return JsonResponse(result, status=201 if result.get("status") == "success" else 400)

@csrf_exempt
def receive_ledger_data(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)
    payload = json.loads(request.body or "{}")
    entries = payload.get("ledger_data", [])
    result = LoanApplicationService.process_ledger_data(entries)
    return JsonResponse(result, status=201 if result.get("status") == "success" else 400)





#--------#--------#--------#--------#--------
    
#   trade finance 


#--------#--------#--------#--------#--------



import logging
import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import TradeFinanceService

logger = logging.getLogger(__name__)


@csrf_exempt
def receive_tf_invoice_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            logger.debug(f"📌 Received TF invoice data: {json.dumps(data, indent=4)}")

            invoices = data.get('invoices', [])

            if not invoices:
                logger.error("❌ No TF invoices found in request")
                return JsonResponse({'status': 'error', 'message': 'Invoice list is empty.'}, status=400)

            for invoice in invoices:
                transaction_id = invoice.get('transaction_id')
                if not transaction_id:
                    logger.error("❌ Missing Transaction ID in one of the TF invoices")
                    return JsonResponse({'status': 'error', 'message': 'Each invoice must include a transaction_id.'}, status=400)

            result = TradeFinanceService.process_invoice_data({"invoices": invoices})

            if result['status'] == 'success':
                logger.debug(f"✅ TF invoice data processed successfully for {len(invoices)} invoices.")
            else:
                logger.error(f"❌ Failed to process TF invoice data: {result['message']}")

            return JsonResponse(result, status=201 if result['status'] == 'success' else 400)

        except Exception as e:
            logger.error(f"🔥 Exception in receive_tf_invoice_data: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)






#--------#--------#--------#--------#--------
    
#   supply chain finance 


#--------#--------#--------#--------#--------






# efs_data_financial/financial/views.py
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import SCFFundingService

logger = logging.getLogger(__name__)

@csrf_exempt
def receive_scf_invoice_data(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        payload = json.loads(request.body or "{}")
        logger.debug("📌 Received SCF invoice data: %s", json.dumps(payload, indent=2))

        invoices = payload.get("invoices", [])
        if not invoices:
            return JsonResponse({"status": "error", "message": "Invoice list is empty."}, status=400)

        # Validate each invoice has transaction_id (your requirement)
        for inv in invoices:
            if not inv.get("transaction_id"):
                return JsonResponse(
                    {"status": "error", "message": "Each invoice must include a transaction_id."},
                    status=400
                )

        result = SCFFundingService.process_invoice_data({"invoices": invoices})
        return JsonResponse(result, status=201 if result.get("status") == "success" else 400)

    except Exception as e:
        logger.exception("🔥 Exception in receive_scf_invoice_data")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)





from django.views.decorators.http import require_GET
from django.shortcuts import render

@require_GET
def financials_modal(request):
    raw_abn = (request.GET.get("abn") or "").strip()
    raw_acn = (request.GET.get("acn") or "").strip()
    tx      = (request.GET.get("tx")  or "").strip()

    # Fallback logic:
    # - If we have an ABN, use it.
    # - Else if we have an ACN, use that everywhere the template expects `abn`.
    #   (so you don't have to refactor the template right now)
    abn_or_acn = raw_abn or raw_acn
    id_type = "ABN" if raw_abn else ("ACN" if raw_acn else "TX")

    ctx = {
        # keep backwards compatibility – template still references {{ abn }}
        "abn": abn_or_acn,

        # expose extra info for future use / debugging / header labels
        "acn": raw_acn,
        "tx": tx,
        "id_type": id_type,
    }
    return render(request, "financials.html", ctx)



def _norm_company_id(val: str) -> str:
    """
    Normalizes an ABN or ACN-ish identifier from the URL.
    Strips spaces, dashes, etc. You can make this smarter later
    (like zero-padding ACNs if you want).
    """
    if not val:
        return ""
    return "".join(ch for ch in val.strip() if ch.isalnum())

def _norm_company_id_pair(abn_raw: str, acn_raw: str):
    """
    Return a tuple (clean_abn, clean_acn).

    - Cleans each (strip, basic normalisation if you have _norm_abn/_norm_acn).
    - Either may be '' if missing.
    """
    abn_val = _norm_abn(abn_raw or "") if ' ' in (abn_raw or "") or '-' in (abn_raw or "") else _norm_abn(abn_raw or "")
    # If you already have an _norm_acn() util, call that. Otherwise just strip.
    acn_val = (acn_raw or "").strip()
    return (abn_val, acn_val)




# efs_data_financial/core/views.py
from django.views.decorators.http import require_GET
from django.shortcuts import render


@require_GET
def ppsr_modal(request):
    """
    Returns the PPSR modal fragment. The template must contain a root
    element with id="ppsrModal" and the script that defines window.openPPSRModal.
    """
    tx = request.GET.get("tx", "")
    return render(request, "ppsr.html", {"tx": tx})



import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from .serializers import FinancialStoreSerializer
from .services import upsert_financial_record, FinancialData  # upsert + model

log = logging.getLogger(__name__)

def _authorized(request) -> bool:
    expected = getattr(settings, "INTERNAL_API_KEY", "dev-key")
    got = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY")
    return bool(expected) and (got == expected)

@csrf_exempt
@require_POST
def store_financials(request):
    """
    Accepts either:
      { "record":  {abn, year?, financials?, profit_loss?, balance_sheet?, ...} }
    or
      { "records": [ {...}, {...} ] }
    Validates with FinancialStoreSerializer and upserts each item using upsert_financial_record().
    """
    if not _authorized(request):
        return JsonResponse({"success": False, "message": "unauthorized"}, status=401)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "invalid json"}, status=400)

    s = FinancialStoreSerializer(data=body)
    if not s.is_valid():
        return JsonResponse({"success": False, "message": s.errors}, status=400)

    saved, created_ids, updated_ids = 0, [], []
    for rec in s.validated_data["as_list"]:
        obj, created = upsert_financial_record(rec)
        saved += 1
        (created_ids if created else updated_ids).append(str(obj.id))

    return JsonResponse({
        "success": True,
        "saved": saved,
        "created_ids": created_ids,
        "updated_ids": updated_ids,
    }, status=200)







# efs_data_financial/core/views.py
# efs_data_financials/core/views.py
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .services import StorePPSRDataService

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def store_ppsr_data(request):  # <- keep original name
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "invalid json"}, status=400)

    abn = (body.get("abn") or "").strip()
    data = body.get("data") or {}
    transaction_id = body.get("transaction_id")  # <- pick up TX

    if not abn or not data:
        return JsonResponse({"success": False, "message": "Missing ABN or data"}, status=400)

    StorePPSRDataService.store_ppsr_data(
        data=data,
        abn=abn,
        transaction_id=transaction_id,  # <- pass TX to service
    )
    return JsonResponse({"success": True, "message": "PPSR data stored"})






#---------start display data in financials.html-----------
#---------start display data in financials.html-----------
#---------start display data in financials.html-----------
#---------start display data in financials.html-----------



# efs_data_financial/core/views.py
from django.conf import settings
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from decimal import Decimal, InvalidOperation
from django.db.models import Q, Sum


from .models import (
    UploadAPLedgerData,
    FinancialData,
    LedgerData,
    InvoiceData,
    UploadedLedgerData,
    InvoiceDataUploaded,
    
)

DB_ALIAS = "default"  # ✅ matches your settings


def _get_invoice_source_qs(company_id: str):
    """
    Mutually exclusive sources rule:
    - If any Uploaded invoices exist for this company_id, use that set.
    - Else use API invoices.
    """
    uploaded_qs = InvoiceDataUploaded.objects.using(DB_ALIAS).filter(
        Q(abn=company_id) | Q(acn=company_id)
    )

    if uploaded_qs.exists():
        return uploaded_qs.order_by("-date_funded", "-due_date"), "uploaded"

    api_qs = InvoiceData.objects.using(DB_ALIAS).filter(
        Q(abn=company_id) | Q(acn=company_id)
    )
    return api_qs.order_by("-date_funded", "-due_date"), "api"


def _map_row_to_ui(row):
    return {
        "company_name": row.company_name,
        "profit_loss": row.profit_loss or {},
        "balance_sheet": row.balance_sheet or {},
    }


def _num(v):
    """
    Parse amounts from UploadedLedgerData (strings like '1,234.56', '$2,000', '(123.45)').
    Returns Decimal, or Decimal('0') on failure/blank.
    """
    if v is None:
        return Decimal("0")
    s = str(v).strip()
    if not s:
        return Decimal("0")
    # handle parentheses negatives
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    # strip currency/thousand separators
    s = s.replace("$", "").replace(",", "")
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return -d if negative else d


import re

YEAR_RE = re.compile(r"^\d{4}$")
SECTION_WORDS = {
    "income","expenses","cogs","cogs:","depreciation","gp %","gp%", "normalised profit reconciliation:",
    "total", "summary"
}

def _clean_key(k: str) -> str:
    return (k or "").replace("\ufeff", "").strip()

def _to_num_str(s):
    """Return normalized numeric string or '' if not numeric."""
    if s is None:
        return ""
    t = str(s).strip()
    if not t:
        return ""
    # convert accounting negatives e.g. (73,964.00)
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    t = t.replace(",", "").replace("$", "")
    # percentages? keep as number if you want, else drop
    if t.endswith("%"):
        try:
            val = float(t[:-1]) / 100.0
            t = str(val)
        except:
            return ""
    # numeric?
    try:
        val = float(t)
        if neg:
            val = -val
        # compact string
        s = f"{val}"
        # strip trailing .0
        if s.endswith(".0"):
            s = s[:-2]
        return s
    except:
        return ""

def _looks_like_section(label: str) -> bool:
    if not label:
        return True
    low = label.lower().strip().strip(":")
    if low in SECTION_WORDS:
        return True
    # skip very short separators
    if low in {"-", "—"}:
        return True
    return False

def normalize_fin_rows(rows, fallback_year: int | None = None):
    """
    Normalize a list[dict] into rows shaped like:
      {"Line Item": "...", "<YYYY>": "<number string>"}
    - Drops blank/section rows.
    - Uses fallback_year if row has only one numeric value and no explicit year key.
    """
    out = []
    if not isinstance(rows, list):
        return out

    for r in rows:
        if not isinstance(r, dict):
            continue
        # Clean keys
        rr = { _clean_key(k): v for k, v in r.items() }

        # Detect label from common keys
        label = (
            rr.get("Line Item") or rr.get("Item") or rr.get("Description") or
            rr.get("PVS") or rr.get("PVs") or rr.get("PV") or rr.get("Account") or
            rr.get("Name") or rr.get("Title") or rr.get("") or ""
        )
        label = str(label or "").strip()
        # If label is actually a year header row like {"": "2021", "PVS":"Description"}, skip
        if YEAR_RE.match(label) and (rr.get("PVS") == "Description" or rr.get("Description") == "Description"):
            continue
        # Skip section/blank rows
        if _looks_like_section(label):
            continue

        # Gather year->value pairs
        year_values = {}
        for k, v in rr.items():
            k_clean = _clean_key(k)
            if YEAR_RE.match(k_clean):
                num = _to_num_str(v)
                if num != "":
                    year_values[k_clean] = num

        # If no explicit year keys, try single numeric cell path (2-col dumps)
        if not year_values:
            # candidate numeric values are cells not equal to the label itself
            numeric_candidates = []
            for k, v in rr.items():
                if str(v).strip() == label:
                    continue
                num = _to_num_str(v)
                if num != "":
                    numeric_candidates.append(num)
            if len(numeric_candidates) == 1 and fallback_year:
                year_values[str(fallback_year)] = numeric_candidates[0]

        # If still nothing numeric, skip the row
        if not year_values:
            continue

        # Build one row per label, merging years
        row = {"Line Item": label}
        row.update(year_values)
        out.append(row)

    return out






from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.db.models import Q, Sum
from decimal import Decimal
from django.utils.timezone import localtime

@require_GET
def fetch_financial_data(request, abn):
    """
    NOTE: 'abn' in the URL is now a generic company_id.
    We will try to match either abn OR acn in the DB.
    """
    company_id = (abn or "").strip()
    if not company_id:
        return JsonResponse({"success": False, "error": "Company identifier (ABN or ACN) is required"}, status=400)

    try:
        # ---------- Financials (top + comparison) ----------
        rows = list(
            FinancialData.objects.using(DB_ALIAS)
            .filter(Q(abn=company_id) | Q(acn=company_id))
            .order_by("-timestamp", "-year")
        )

        by_year = {}
        for r in rows:
            if r.year is None:
                continue
            if r.year not in by_year:
                by_year[r.year] = _map_row_to_ui(r)

        f2021 = by_year.get(2021)
        f2022 = by_year.get(2022)
        if not f2021 or not f2022:
            yrs = sorted(by_year.keys(), reverse=True)
            if yrs:
                newest = yrs[0]
                second = yrs[1] if len(yrs) > 1 else None
                f2022 = f2022 or by_year.get(newest)
                if second is not None:
                    f2021 = f2021 or by_year.get(second)

        # ---------- AR Ledger (group by debtor) - PRIMARY SOURCE ----------
        ledger_qs = (
            LedgerData.objects.using(DB_ALIAS)
            .filter(Q(abn=company_id) | Q(acn=company_id))
            .values("debtor")
            .annotate(total_due=Sum("amount_due"))
            .order_by("debtor")
        )
        ar_ledger = [
            {
                "name": r["debtor"] or "—",
                "total_due": float(r["total_due"] or 0),
                # no aged buckets in primary source
            }
            for r in ledger_qs
        ]

        # ---------- Debtors list (PRIMARY) ----------
        debtors_list = list(
            LedgerData.objects.using(DB_ALIAS)
            .filter(Q(abn=company_id) | Q(acn=company_id))
            .order_by()
            .values_list("debtor", flat=True)
            .distinct()
        )

        # ---------- FALLBACK to UploadedLedgerData IF primary AR is empty ----------
        if not ar_ledger:  # only if no rows from primary source
            uploaded = list(
                UploadedLedgerData.objects.using(DB_ALIAS)
                .filter(Q(abn=company_id) | Q(acn=company_id))
                .order_by("debtor")
            )
            ar_ledger = []
            seen = set()
            for u in uploaded:
                debtor_name = (u.debtor or "—").strip()
                if debtor_name in seen:
                    continue
                seen.add(debtor_name)

                aged_current = _num(u.aged_receivables)
                d0_30 = _num(u.days_0_30)
                d31_60 = _num(u.days_31_60)
                d61_90 = _num(u.days_61_90)
                d90_plus = _num(u.days_90_plus)

                ar_ledger.append({
                    "name": debtor_name,
                    "total_due": float(aged_current),
                    "aged_current": float(aged_current),
                    "d0_30": float(d0_30),
                    "d31_60": float(d31_60),
                    "d61_90": float(d61_90),
                    "d90_plus": float(d90_plus),
                })

            debtors_list = [r["name"] for r in ar_ledger]

        # ---------- Invoices (basic mapping; unchanged shape) ----------
        # ---------- Invoices (prefer Uploaded, else API) ----------
# ---------- Invoices (prefer Uploaded, else API) ----------
        inv_qs, inv_source = _get_invoice_source_qs(company_id)

        invoices = []
        for i in inv_qs:
            ar = (getattr(i, "approve_reject", None) or "").strip()
            invoices.append({
                "debtor": i.debtor or "—",
                "invoice_number": getattr(i, "inv_number", None) or "—",
                "amount_due": float(i.amount_due or 0),
                "repayment_date": i.due_date.isoformat() if i.due_date else None,

                # ✅ make approve/reject first-class
                "approve_reject": ar or None,

                # ✅ ensure UI status matches approve/reject
                "status": ar or getattr(i, "status", "") or getattr(i, "invoice_state", "") or "",

                "created_at": i.date_funded.isoformat() if i.date_funded else None,
                "source": inv_source,
                "invoice_state": getattr(i, "invoice_state", None),
                "date_paid": getattr(i, "date_paid", None).isoformat() if getattr(i, "date_paid", None) else None,
            })



        return JsonResponse({
            "success": True,
            "financials_2021": [f2021] if f2021 else [],
            "financials_2022": [f2022] if f2022 else [],
            "ar_ledger": ar_ledger,
            "debtors_list": debtors_list,
            "invoices": invoices,
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)




# views.py (where fetch_invoices lives)

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q
from .models import InvoiceDataUploaded

from .services import fetch_invoices_combined_for_company


@require_GET
def fetch_invoices(request, company_id):
    """
    company_id can be ABN or ACN.
    Ensures a stable front-end contract:
      - includes approve_reject
      - includes status (mirrors approve_reject)
      - supports both invoice_number and inv_number fallbacks
    """
    data = fetch_invoices_combined_for_company(company_id)
    invoices = data.get("invoices", []) or []

    normalized = []
    for inv in invoices:
        ar = (inv.get("approve_reject") or "").strip()

        # normalize keys your UI expects
        invoice_number = inv.get("invoice_number") or inv.get("inv_number") or "—"

        normalized.append({
            **inv,
            "invoice_number": invoice_number,  # keep UI-friendly key
            "status": ar,                      # ✅ UI status always from approve_reject
            "approve_reject": ar,              # ✅ always present for pill logic
        })

    return JsonResponse({"invoices": normalized})


from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_GET

def _num_strict(val):
    """
    Take a string like "$1,234.56", "1,234", "(700.00)", None, "-" etc.
    Return Decimal('0') if it's not parseable.
    Negative parentheses become negative.
    """
    if val is None:
        return Decimal("0")

    s = str(val).strip()

    if s in ("", "-", "—"):
        return Decimal("0")

    # Handle "(1,234.00)" -> -1234.00
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()

    # Strip $ and commas
    s = s.replace("$", "").replace(",", "")

    try:
        num = Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal("0")

    return -num if neg else num



@require_GET
def fetch_accounts_payable(request, abn):
    """
    'abn' path param is now a generic company_id.
    We look up AP ledger rows by abn OR acn.
    """
    company_id = (abn or "").strip()
    if not company_id:
        return JsonResponse({"success": False, "error": "Company identifier (ABN or ACN) is required"}, status=400)

    try:
        # Uploaded AP is already aggregated per creditor -> one row per creditor.
        rows = (
            UploadAPLedgerData.objects.using("default")  # or DB_ALIAS if that's correct for AP
            .filter(Q(abn=company_id) | Q(acn=company_id))
            .order_by("creditor")
        )

        accounts_payable = []
        seen = set()
        for r in rows:
            supplier = (r.creditor or "—").strip()
            if supplier in seen:
                continue
            seen.add(supplier)

            aged_current = _num_strict(r.aged_payables)
            d0_30    = _num_strict(r.days_0_30)
            d31_60   = _num_strict(r.days_31_60)
            d61_90   = _num_strict(r.days_61_90)
            d90_plus = _num_strict(r.days_90_plus)

            accounts_payable.append({
                "name": supplier,
                "supplier": supplier,
                "vendor": supplier,

                "aged_current": float(aged_current),
                "ap_current": float(aged_current),

                "d0_30": float(d0_30),
                "d30_plus": float(d31_60),
                "d60_plus": float(d61_90),
                "d90_plus": float(d90_plus),

                "older": float(Decimal("0")),
                "ap_older": float(Decimal("0")),
            })

        return JsonResponse({"success": True, "accounts_payable": accounts_payable})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# efs_data_financial/core/views.py
from django.views.decorators.http import require_GET
from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models.functions import Coalesce
from django.db.models import F, DecimalField, Q  # ← Q added
from .models import AssetScheduleRow

@require_GET
def fetch_asset_schedule_rows(request, abn):
    """
    'abn' path param is a generic company_id (ABN or ACN).
    We match AssetScheduleRow by abn OR acn.
    """
    company_id = (abn or "").strip()
    if not company_id:
        return HttpResponseBadRequest("Company identifier (ABN or ACN) required")

    # fields requested by the client
    fields_qs = (request.GET.get("fields") or "").strip()
    allowed = {
        "make", "model", "type", "year_of_manufacture",
        "fmv_amount", "fsv_amount", "olv_amount",
        # ▼ NEW amounts
        "bv_amount", "lease_os_amount", "nbv_amount",
    }
    use_fields = [f for f in fields_qs.split(",") if f in allowed] or list(allowed)

    clazz = (request.GET.get("class") or "").strip().lower()

    qs = AssetScheduleRow.objects.filter(
        Q(abn=company_id) | Q(acn=company_id)
    )

    vehicle_rx = r"(vehicle|truck|ute|car|van|trailer|prime\s*mover|tractor|rigid|bus|coach)"
    if clazz == "vehicles":
        qs = qs.filter(type__iregex=vehicle_rx)
    elif clazz == "plant":
        qs = qs.exclude(type__iregex=vehicle_rx)

    # Fallback: use fsv_amount if present, else olv_amount
    qs = qs.annotate(
        fsv_amount_fallback=Coalesce(
            F("fsv_amount"),
            F("olv_amount"),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )
    )

    # If client asked for fsv_amount, return fallback under that key
    select_fields = []
    replace_key = False
    for f in use_fields:
        if f == "fsv_amount":
            select_fields.append("fsv_amount_fallback")
            replace_key = True
        else:
            select_fields.append(f)

    rows = list(
        qs.values(*select_fields).order_by("-created_at", "make", "model")[:2000]
    )

    if replace_key:
        for r in rows:
            r["fsv_amount"] = r.pop("fsv_amount_fallback", None)

    return JsonResponse({"rows": rows})

# efs_data_financial/core/views.py
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
from django.db.models import Q  # ← ensure Q is imported
from .models import PPEAsset
from decimal import Decimal

def _dec(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None

def _trim_fields(rows, fields_qs):
    if not fields_qs:
        return rows
    allowed = set(f.strip() for f in fields_qs.split(",") if f.strip())
    out = []
    for r in rows:
        out.append({k: v for k, v in r.items() if k in allowed})
    return out

@require_GET
def fetch_plant_machinery_schedule_rows(request, abn: str):
    """
    GET /fetch_plant_machinery_schedule_rows/<company_id>/
      ?fields=...
      [&transaction_id=<tx>][&originator=<name>][&limit=500]
      [&class=vehicles|plant]

    company_id can be ABN OR ACN.
    Source of truth: PPEAsset ONLY.
    """
    company_id = (abn or "").strip()
    if not company_id:
        return HttpResponseBadRequest("Company identifier (ABN or ACN) required")

    tx         = (request.GET.get("transaction_id") or "").strip()
    originator = (request.GET.get("originator") or "").strip()
    clazz      = (request.GET.get("class") or "").strip().lower()

    try:
        limit = int(request.GET.get("limit", "0"))
    except Exception:
        limit = 0

    qs = PPEAsset.objects.filter(
        Q(abn=company_id) | Q(acn=company_id)
    )
    if tx:
        qs = qs.filter(transaction_id=tx)
    if originator:
        qs = qs.filter(originator=originator)

    # Optional split by type
    vehicle_rx = r"(vehicle|truck|ute|car|van|trailer)"
    if clazz == "vehicles":
        qs = qs.filter(type__iregex=vehicle_rx)
    elif clazz == "plant":
        qs = qs.exclude(type__iregex=vehicle_rx)

    qs = qs.order_by("-uploaded_at", "asset_number", "make")
    if limit and limit > 0:
        qs = qs[:limit]

    rows = [{
        "make":  a.make,
        "model": a.asset,  # PPEAsset stores the asset name in `asset`
        "type":  a.type,
        "year_of_manufacture": a.year_of_manufacture,
        "fmv_amount": _dec(a.fair_market_value_ex_gst),
        # Keep using OLV-equivalent from PPEAsset for FSV column in UI:
        "fsv_amount": _dec(a.orderly_liquidation_value_ex_gst),

        # ▼ NEW amounts straight from model
        "bv_amount": _dec(a.bv_amount),
        "lease_os_amount": _dec(a.lease_os_amount),
        "nbv_amount": _dec(a.nbv_amount),
    } for a in qs]

    rows = _trim_fields(rows, request.GET.get("fields", ""))
    return JsonResponse({"rows": rows})

import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
from .models import NetAssetValueSnapshot, NAVLiabilityLine


@require_GET
def liabilities_latest(request):
    """
    GET /api/liabilities/latest/?abn=...&acn=...&tx=...

    Returns the most recent LIABILITIES snapshot for that entity
    and all the NAVLiabilityLine rows under it.
    {
      "success": true,
      "snapshot_id": 123,
      "lines": [
        {
          "facility_limit_amount": "100000.00",
          "lender": "Westpac",
          "product": "Overdraft",
          "current_balance_amount": "55000.00",
          "due_date": "2025-03-01"
        },
        ...
      ]
    }
    """

    abn = (request.GET.get("abn") or "").strip()
    acn = (request.GET.get("acn") or "").strip()
    tx  = (request.GET.get("tx")  or "").strip()

    if not abn and not acn:
        return HttpResponseBadRequest("Missing identifier (abn or acn).")

    qs = NetAssetValueSnapshot.objects.filter(
        source_tab=NetAssetValueSnapshot.TAB_LIABILITIES,
    )

    if abn:
        qs = qs.filter(abn=abn)
    if acn:
        qs = qs.filter(acn=acn)
    if tx:
        qs = qs.filter(transaction_id=tx)

    snap = qs.order_by("-created_at").first()
    if not snap:
        return JsonResponse({
            "success": True,
            "snapshot_id": None,
            "lines": []
        })

    lines_qs = NAVLiabilityLine.objects.filter(snapshot=snap)
    lines_payload = []
    for ln in lines_qs:
        lines_payload.append({
            "facility_limit_amount": str(ln.facility_limit_amount),
            "lender": ln.lender,
            "product": ln.product,
            "current_balance_amount": str(ln.current_balance_amount),
            "due_date": ln.due_date,
        })

    return JsonResponse({
        "success": True,
        "snapshot_id": snap.id,
        "lines": lines_payload,
    })















#---------end display data in financials.html-----------
#---------end display data in financials.html-----------
#---------end display data in financials.html-----------
#---------end display data in financials.html-----------







#-----------------------------


#---end-point for efs_data_bankstatements  sales notes -> financial_statements notes data model 


#-----------------------------



# efs_data_financial/.../views.py
import json
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import FinancialStatementNotes

def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

@csrf_exempt
@require_POST
def save_financial_statement_notes(request):
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    abn = _digits_only(body.get("abn"))
    if not abn:
        return JsonResponse({"success": False, "message": "abn required"}, status=400)

    notes = (body.get("notes") or "").strip()
    if not notes:
        return JsonResponse({"success": False, "message": "notes required"}, status=400)

    financial_data_type = (body.get("financial_data_type") or "").strip()
    if not financial_data_type:
        return JsonResponse({"success": False, "message": "financial_data_type required"}, status=400)

    acn = _digits_only(body.get("acn")) or None

    tx_raw = (body.get("transaction_id") or "").strip()
    tx_id = None
    if tx_raw:
        try:
            tx_id = uuid.UUID(tx_raw)
        except Exception:
            return JsonResponse({"success": False, "message": "transaction_id must be a UUID"}, status=400)

    # If transaction_id wasn’t provided, let the model default generate it
    if tx_id:
        # ✅ update-or-create “latest notes for this transaction + type”
        obj, created = FinancialStatementNotes.objects.update_or_create(
            transaction_id=tx_id,
            abn=abn,
            financial_data_type=financial_data_type,
            defaults={
                "acn": acn,
                "notes": notes,
            }
        )
    else:
        obj = FinancialStatementNotes.objects.create(
            abn=abn,
            acn=acn,
            financial_data_type=financial_data_type,
            notes=notes,
        )
        created = True

    return JsonResponse({
        "success": True,
        "created": created,
        "id": obj.id,
        "transaction_id": str(obj.transaction_id),
        "abn": obj.abn,
        "acn": obj.acn,
        "financial_data_type": obj.financial_data_type,
        "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
    }, status=200)








#-----------------------------


#---end-point for PPSR modal  -> registration  data model 


#-----------------------------

# efs_data_financial/core/views.py
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .models import Registration  # <-- from THIS service/app
from django.db.models import Q

# ------- PPSR: helpers, serializer, endpoints -------

from django.views.decorators.http import require_GET
from django.shortcuts import render
from django.http import JsonResponse

def _iso(dt):
    return dt.isoformat() if dt else None

def _abn_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _serialize_registration(reg: Registration) -> dict:
    return {
        "id": str(reg.id),
        "abn": reg.abn,
        "search_date": reg.search_date.isoformat() if reg.search_date else None,
        "registration_number": reg.registration_number,
        "start_time": _iso(reg.start_time),
        "end_time": _iso(reg.end_time),
        "change_number": reg.change_number,
        "change_time": _iso(reg.change_time),
        "registration_kind": reg.registration_kind,
        "is_migrated": reg.is_migrated,
        "is_transitional": reg.is_transitional,
        "grantor_organisation_identifier": reg.grantor_organisation_identifier,
        "grantor_organisation_identifier_type": reg.grantor_organisation_identifier_type,
        "grantor_organisation_name": reg.grantor_organisation_name,
        "collateral_class_type": reg.collateral_class_type,
        "collateral_type": reg.collateral_type,
        "collateral_class_description": reg.collateral_class_description,
        "are_proceeds_claimed": reg.are_proceeds_claimed,
        "proceeds_claimed_description": reg.proceeds_claimed_description,
        "is_security_interest_registration_kind": reg.is_security_interest_registration_kind,
        "are_assets_subject_to_control": reg.are_assets_subject_to_control,
        "is_inventory": reg.is_inventory,
        "is_pmsi": reg.is_pmsi,
        "is_subordinate": reg.is_subordinate,
        "giving_of_notice_identifier": reg.giving_of_notice_identifier,
        "security_party_groups": reg.security_party_groups,
        "grantors": reg.grantors,
        "address_for_service": reg.address_for_service,
        "created_at": _iso(reg.created_at),
    }


@require_GET
def ppsr_modal(request):
    """
    Returns the PPSR modal HTML fragment.
    Sales proxies this endpoint at /sales/modal/ppsr?tx=...
    """
    tx = request.GET.get("tx", "")
    return render(request, "ppsr.html", {"tx": tx})

@require_GET
def ppsr_api_for_abn(request, abn: str):
    """
    KEPT ROUTE the UI/BFF already uses.
    Accepts ABN but queries primarily by ACN (last 9 digits), and also
    falls back to legacy rows saved with full ABN.
    """
    abn_digits = _digits(abn)
    acn = _abn_to_acn(abn_digits)

    qs = (
        Registration.objects
        .filter(Q(abn=acn) | Q(abn=abn_digits))
        .order_by("-start_time", "-created_at")
    )
    data = [_serialize_registration(r) for r in qs]
    return JsonResponse({"registrations": data})

@require_GET
def ppsr_for_abn(request, abn: str):
    # legacy route kept in sync with the same behavior
    abn_digits = _digits(abn)
    acn = _abn_to_acn(abn_digits)

    qs = (
        Registration.objects
        .filter(Q(abn=acn) | Q(abn=abn_digits))
        .order_by("-start_time", "-created_at")
    )
    data = [_serialize_registration(r) for r in qs]
    return JsonResponse({"registrations": data})



#-----------------------------
#-----------------------------
#-----------------------------
#-----------------------------

#-----------------------------save NAV data#-----------------------------
#-----------------------------save NAV data#-----------------------------
#-----------------------------save NAV data#-----------------------------
#-----------------------------save NAV data#-----------------------------

import json
import time
from decimal import Decimal
from django.db import transaction
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import NetAssetValueSnapshot, NAVAssetLine, NAVARLine, NAVPlantandequipmentLine
import logging

logger = logging.getLogger("efs.nav")

_BIDI_ZW_RE = r"[\u200E\u200F\u202A-\u202E\u2066-\u2069\uFEFF]"
def _clean_abn(s: str) -> str:
    try:
        import re
        return re.sub(_BIDI_ZW_RE, "", (s or "").strip())
    except Exception:
        return (s or "").strip()

def _to_decimal(v):
    if v is None or v == "":
        return Decimal("0")
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v))
    s = str(v).replace("$", "").replace(",", "").strip()
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except Exception as e:
        logger.warning("to_decimal_failed", extra={"value": v, "err": str(e)})
        return Decimal("0")

# views.py
from .models import (
    NetAssetValueSnapshot,
    NAVAssetLine,
    NAVARLine,
    NAVPlantandequipmentLine,  # ← NEW import
)

def _sum_fsv(lines):
    from decimal import Decimal
    total = Decimal("0")
    for r in (lines or []):
        # handle non-dict rows or missing key safely
        val = None
        if isinstance(r, dict):
            val = r.get("fsv", 0)
        total += _to_decimal(val if val is not None else 0)
    return total

@csrf_exempt
@require_POST
def save_nav_snapshot(request):
    import json, time
    from django.db import transaction
    from django.http import JsonResponse, HttpResponseBadRequest

    t0 = time.time()
    ctx = {
        "path": request.path,
        "method": request.method,
        "content_type": request.headers.get("Content-Type", ""),
        "origin": request.headers.get("Origin", ""),
        "referer": request.headers.get("Referer", ""),
        "remote_addr": request.META.get("REMOTE_ADDR"),
    }

    raw_body = request.body or b""
    ctx["body_len"] = len(raw_body)

    # -------- Parse JSON --------
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except Exception as e:
        logger.error(
            "nav_parse_json_failed",
            extra={**ctx, "err": str(e), "body_excerpt": raw_body[:200].decode("utf-8", "ignore")},
        )
        return HttpResponseBadRequest("Invalid JSON")

    # -------- Core fields --------
    raw_abn = (payload.get("abn") or "")
    raw_acn = (payload.get("acn") or "")
    abn, acn = _norm_company_id_pair(raw_abn, raw_acn)

    tx = (payload.get("transaction_id") or "").strip()
    source_tab = ((payload.get("source_tab") or "")).upper()

    # Selections from client
    lines = payload.get("lines") or []
    plant_lines = payload.get("plant_lines") or []

    # Totals/advance (top-level)
    meta = payload.get("meta") or {}
    advance_pct_top     = _to_decimal(payload.get("advance_rate_pct"))
    selected_total_top  = _to_decimal(payload.get("selected_total_amount"))
    available_funds_top = _to_decimal(payload.get("available_funds_amount"))

    logger.info(
        "nav_request_received",
        extra={
            **ctx,
            "abn": abn,
            "acn": acn,
            "tx": tx,
            "source_tab": source_tab,
            "lines_count": len(lines),
            "plant_lines_count": len(plant_lines),
            "advance_pct_top": str(advance_pct_top),
            "selected_total_top": str(selected_total_top),
            "available_funds_top": str(available_funds_top),
        },
    )

    # -------- Validation --------
    if source_tab not in ("ASSETS", "AR"):
        logger.warning("nav_invalid_source_tab", extra={**ctx, "source_tab": source_tab})
        return HttpResponseBadRequest("source_tab must be 'ASSETS' or 'AR'")

    if not abn and not acn:
        logger.warning("nav_missing_identifier", extra=ctx)
        return HttpResponseBadRequest("Missing company identifier (ABN or ACN)")

    if not tx:
        logger.warning("nav_missing_tx", extra=ctx)
        return HttpResponseBadRequest("Missing transaction_id")

    if source_tab == "ASSETS" and not lines and not plant_lines:
        logger.info("nav_no_lines_to_save_assets", extra={**ctx, "abn": abn, "acn": acn})
        return JsonResponse({"success": True, "message": "No selected rows; nothing saved.", "rows_saved": 0})

    if source_tab == "AR" and not lines:
        logger.info("nav_no_lines_to_save_ar", extra={**ctx, "abn": abn, "acn": acn})
        return JsonResponse({"success": True, "message": "No selected rows; nothing saved.", "rows_saved": 0})

    # -------- Per-section computation (only for ASSETS) --------
    veh_adv = veh_sel = veh_avl = None
    pm_adv  = pm_sel  = pm_avl  = None

    if source_tab == "ASSETS":
        veh_meta = (meta.get("vehicles") or {})
        pm_meta  = (meta.get("plant_equipment") or {})

        veh_adv = _to_decimal(veh_meta.get("advance_rate_pct") or advance_pct_top)
        veh_sel = _to_decimal(veh_meta.get("selected_total_amount") or _sum_fsv(lines))
        veh_avl = _to_decimal(veh_meta.get("available_funds_amount") or (veh_sel * veh_adv / _to_decimal(100)))

        pm_adv = _to_decimal(pm_meta.get("advance_rate_pct") or advance_pct_top)
        pm_sel = _to_decimal(pm_meta.get("selected_total_amount") or _sum_fsv(plant_lines))
        pm_avl = _to_decimal(pm_meta.get("available_funds_amount") or (pm_sel * pm_adv / _to_decimal(100)))

    # -------- Persist --------
    try:
        with transaction.atomic():
            snapshot_ids = []
            rows_saved = 0

            if source_tab == "ASSETS":
                # Vehicles snapshot (if any)
                if lines:
                    snap_kwargs = dict(
                        abn=abn or None,
                        transaction_id=tx,
                        source_tab="ASSETS",
                        advance_rate_pct=veh_adv,
                        selected_total_amount=veh_sel,
                        available_funds_amount=veh_avl,
                        meta={**meta, "section": "vehicles"},
                    )
                    if acn and "acn" in [f.name for f in NetAssetValueSnapshot._meta.fields]:
                        snap_kwargs["acn"] = acn

                    snap_veh = NetAssetValueSnapshot.objects.create(**snap_kwargs)
                    snapshot_ids.append(snap_veh.id)

                    NAVAssetLine.objects.bulk_create(
                        [
                            NAVAssetLine(
                                snapshot=snap_veh,
                                make=(r.get("make", "") or "")[:128],
                                model=(r.get("model", "") or "")[:128],
                                type=(r.get("type", "") or "")[:128],
                                year_of_manufacture=str(r.get("year") or ""),
                                fmv_amount=_to_decimal(r.get("fmv")),
                                fsv_amount=_to_decimal(r.get("fsv")),
                                # ▼▼ NEW fields persisted
                                bv_amount=_to_decimal(r.get("bv")),
                                lease_os_amount=_to_decimal(r.get("lease_os")),
                                nbv_amount=_to_decimal(r.get("nbv")),
                            )
                            for r in lines
                        ],
                        batch_size=500,
                    )
                    rows_saved += len(lines)

                # Plant & Machinery snapshot (if any)
                if plant_lines:
                    snap_kwargs_pm = dict(
                        abn=abn or None,
                        transaction_id=tx,
                        source_tab="ASSETS",
                        advance_rate_pct=pm_adv,
                        selected_total_amount=pm_sel,
                        available_funds_amount=pm_avl,
                        meta={**meta, "section": "plant_equipment"},
                    )
                    if acn and "acn" in [f.name for f in NetAssetValueSnapshot._meta.fields]:
                        snap_kwargs_pm["acn"] = acn

                    snap_pm = NetAssetValueSnapshot.objects.create(**snap_kwargs_pm)
                    snapshot_ids.append(snap_pm.id)

                    NAVPlantandequipmentLine.objects.bulk_create(
                        [
                            NAVPlantandequipmentLine(
                                snapshot=snap_pm,
                                make=(r.get("make", "") or "")[:128],
                                model=(r.get("model", "") or "")[:128],
                                type=(r.get("type", "") or "")[:128],
                                year_of_manufacture=str(r.get("year") or ""),
                                fmv_amount=_to_decimal(r.get("fmv")),
                                fsv_amount=_to_decimal(r.get("fsv")),
                                # ▼▼ NEW fields persisted
                                bv_amount=_to_decimal(r.get("bv")),
                                lease_os_amount=_to_decimal(r.get("lease_os")),
                                nbv_amount=_to_decimal(r.get("nbv")),
                            )
                            for r in plant_lines
                        ],
                        batch_size=500,
                    )
                    rows_saved += len(plant_lines)


            elif source_tab == "AR":
                # Ensure meta is a dict
                meta_dict = meta if isinstance(meta, dict) else {}

                # Pull AR-specific meta safely (what your front-end sends)
                ar_meta = meta_dict.get("ar") if isinstance(meta_dict.get("ar"), dict) else {}

                snap_kwargs_ar = dict(
                    abn=abn or None,
                    transaction_id=tx,
                    source_tab="AR",
                    advance_rate_pct=advance_pct_top,
                    selected_total_amount=selected_total_top,
                    available_funds_amount=available_funds_top,
                    # Persist full meta, but guarantee "ar" exists as a dict
                    meta={**meta_dict, "ar": ar_meta},
                )
                if acn and "acn" in [f.name for f in NetAssetValueSnapshot._meta.fields]:
                    snap_kwargs_ar["acn"] = acn

                snap_ar = NetAssetValueSnapshot.objects.create(**snap_kwargs_ar)
                snapshot_ids.append(snap_ar.id)

                ar_rows = []
                for r in (lines or []):
                    if not isinstance(r, dict):
                        continue

                    nominated = bool(r.get("nominated", True))
                    if not nominated:
                        continue

                    # trace must be a dict for JSONField
                    trace = r.get("trace")
                    if not isinstance(trace, dict):
                        trace = {}

                    ar_rows.append(
                        NAVARLine(
                            snapshot=snap_ar,
                            debtor_name=(r.get("debtor", "") or "")[:256],

                            # raw buckets
                            aged_current=_to_decimal(r.get("aged_current")),
                            d0_30=_to_decimal(r.get("d0_30")),
                            d31_60=_to_decimal(r.get("d31_60")),
                            d61_90=_to_decimal(r.get("d61_90")),
                            d90_plus=_to_decimal(r.get("d90_plus")),
                            older=_to_decimal(r.get("older")),

                            nominated=True,

                            # exclusions impact
                            base_due=_to_decimal(r.get("base_due")),
                            excluded_amount=_to_decimal(r.get("excluded_amount")),
                            due_adjusted=_to_decimal(r.get("due_adjusted")),

                            # concentration settings + outputs
                            concentration_limit_pct=_to_decimal(r.get("concentration_limit_pct")),
                            conc_adj_manual=bool(r.get("conc_adj_manual", False)),
                            concentration_pct=_to_decimal(r.get("concentration_pct")),

                            # EC trace
                            advance_rate_pct=_to_decimal(r.get("advance_rate_pct", advance_pct_top)),
                            base_ec=_to_decimal(r.get("base_ec")),
                            adj_ec=_to_decimal(r.get("adj_ec")),

                            # escape hatch
                            trace=trace,
                        )
                    )

                if ar_rows:
                    NAVARLine.objects.bulk_create(ar_rows, batch_size=500)
                    rows_saved += len(ar_rows)


    except Exception as e:
        logger.exception(
            "nav_persist_failed",
            extra={
                **ctx,
                "abn": abn,
                "acn": acn,
                "tx": tx,
                "source_tab": source_tab,
                "lines_count": len(lines),
                "plant_lines_count": len(plant_lines),
                "err": str(e),
            },
        )
        return JsonResponse({"success": False, "message": "Server error persisting NAV."}, status=500)

    dt_ms = int((time.time() - t0) * 1000)
    logger.info(
        "nav_saved",
        extra={
            **ctx,
            "abn": abn,
            "acn": acn,
            "tx": tx,
            "source_tab": source_tab,
            "snapshot_ids": snapshot_ids,
            "rows_saved": rows_saved,
            "duration_ms": dt_ms,
        },
    )

    return JsonResponse(
        {
            "success": True,
            "snapshot_ids": snapshot_ids,
            "snapshot_id": snapshot_ids[0] if snapshot_ids else None,
            "rows_saved": rows_saved,
        }
    )



import json
from decimal import Decimal
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt  # you MAY NOT need this if you're already sending csrf

from .models import (
    NetAssetValueSnapshot,
    NAVLiabilityLine,
)

@require_POST
@csrf_exempt  # drop this if you're already passing CSRF like the other save_nav_snapshot flow
def save_liabilities_nav(request):
    """
    Create a NetAssetValueSnapshot(source_tab='LIABILITIES') and
    attach NAVLiabilityLine rows for each liability row the user entered.

    ALSO:
    - snapshot.selected_total_amount        = sum of current_balance_amount (loan balance outstanding)
    - snapshot.available_funds_amount       = sum of (facility_limit_amount - current_balance_amount)
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # pull top-level fields
    abn  = (payload.get("abn") or "").strip()
    acn  = (payload.get("acn") or "").strip()
    txid = (payload.get("transaction_id") or "").strip()

    # require at least one identifier if that's your rule
    if not abn and not acn:
        return JsonResponse(
            {"success": False, "message": "Missing ABN/ACN."},
            status=400
        )

    lines = payload.get("lines") or []
    if not isinstance(lines, list) or not lines:
        return JsonResponse(
            {"success": False, "message": "No liability lines provided."},
            status=400
        )

    # helper to coerce to Decimal safely
    def _dec(val, default="0"):
        try:
            return Decimal(str(val if val not in [None, ""] else default))
        except Exception:
            return Decimal(default)

    # advance_rate_pct doesn't have meaning for liabilities,
    # but the model requires it. Keep whatever caller sent or 0.
    advance_rate_pct = _dec(payload.get("advance_rate_pct"), "0")

    # ------------------------------------------------------------------
    # NEW LOGIC:
    # We derive:
    #   total_balance_outstanding      = sum(current_balance_amount)
    #   total_available_funds          = sum(facility_limit_amount - current_balance_amount)
    # and store them in the snapshot fields:
    #   selected_total_amount          <- total_balance_outstanding
    #   available_funds_amount         <- total_available_funds
    # ------------------------------------------------------------------
    total_balance_outstanding = Decimal("0")
    total_available_funds     = Decimal("0")

    # We'll also stage the NAVLiabilityLine objects for bulk_create
    liab_objs = []

    for row in lines:
        facility_limit_amount  = _dec(row.get("facility_limit_amount"), "0")
        lender                 = (row.get("lender") or "").strip()
        product                = (row.get("product") or "").strip()
        current_balance_amount = _dec(row.get("current_balance_amount"), "0")
        due_date               = (row.get("due_date") or "").strip()

        # accumulate totals
        total_balance_outstanding += current_balance_amount
        headroom = facility_limit_amount - current_balance_amount
        total_available_funds += headroom

        # stage object (snapshot gets attached after we create it)
        liab_objs.append(
            NAVLiabilityLine(
                snapshot=None,  # temp, we'll set after snapshot is created
                facility_limit_amount=facility_limit_amount,
                lender=lender,
                product=product,
                current_balance_amount=current_balance_amount,
                due_date=due_date,
            )
        )

    # Create the snapshot row using our computed totals
    snap = NetAssetValueSnapshot.objects.create(
        abn=abn or None,
        acn=acn or None,
        transaction_id=txid,
        source_tab=NetAssetValueSnapshot.TAB_LIABILITIES,
        advance_rate_pct=advance_rate_pct,
        selected_total_amount=total_balance_outstanding,   # <-- loan balance outstanding
        available_funds_amount=total_available_funds,      # <-- facility limit minus balance
        meta={},  # you can stash "Sales Notes" for Liabilities here later
    )

    # now attach the FK for each staged liability row and bulk insert
    for obj in liab_objs:
        obj.snapshot = snap
    NAVLiabilityLine.objects.bulk_create(liab_objs)

    return JsonResponse({
        "success": True,
        "snapshot_id": snap.id,
        "rows_created": len(liab_objs),
    })





#-----------------------------
    
    
    
    
    # Start of code for financial data view code that sends data to  efs_agents service
    # Start of code for financial data view code that sends data to  efs_agents service
    # Start of code for financial data view code that sends data to  efs_agents service
    # Start of code for financial data view code that sends data to  efs_agents service
    # Start of code for financial data view code that sends data to  efs_agents service





#-----------------------------





import uuid
from decimal import Decimal, InvalidOperation

from django.apps import apps
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import (
    FinancialData,
    LedgerData,
    InvoiceData,
    UploadedLedgerData,
    UploadAPLedgerData,
    FinancialStatementNotes,
)

# ---------------------------
# Helpers
# ---------------------------

def _digits(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _parse_uuid(val):
    try:
        return uuid.UUID(str(val))
    except Exception:
        return None


def _dnum(v):
    if v is None:
        return Decimal("0")
    s = str(v).strip()
    if not s:
        return Decimal("0")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "")
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return -d if neg else d


def _uld_to_ar_rows(uploaded_qs):
    """
    Convert UploadedLedgerData rows to:
    [{"name","total_due"/"aged_current","d0_30","d31_60","d61_90","d90_plus"}]
    De-dupe by debtor.
    """
    out, seen = [], set()
    for u in uploaded_qs:
        name = (u.debtor or "—").strip()
        if name in seen:
            continue
        seen.add(name)
        aged_current = _dnum(u.aged_receivables)
        d0_30 = _dnum(u.days_0_30)
        d31_60 = _dnum(u.days_31_60)
        d61_90 = _dnum(u.days_61_90)
        d90_plus = _dnum(u.days_90_plus)
        out.append(
            {
                "name": name,
                "total_due": float(aged_current),
                "aged_current": float(aged_current),
                "d0_30": float(d0_30),
                "d31_60": float(d31_60),
                "d61_90": float(d61_90),
                "d90_plus": float(d90_plus),
            }
        )
    return out


def _uap_to_ap_rows(uploaded_qs):
    """UploadAPLedgerData -> same ledger row shape (creditor->name, aged_payables->aged_current)."""
    out, seen = [], set()
    for u in uploaded_qs:
        name = (u.creditor or "—").strip()
        if name in seen:
            continue
        seen.add(name)
        aged_current = _dnum(u.aged_payables)
        d0_30 = _dnum(u.days_0_30)
        d31_60 = _dnum(u.days_31_60)
        d61_90 = _dnum(u.days_61_90)
        d90_plus = _dnum(u.days_90_plus)
        out.append(
            {
                "name": name,
                "total_due": float(aged_current),
                "aged_current": float(aged_current),
                "d0_30": float(d0_30),
                "d31_60": float(d31_60),
                "d61_90": float(d61_90),
                "d90_plus": float(d90_plus),
            }
        )
    return out


def _model_has_field(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields())


# ---------------------------
# View: list_models  ✅ REQUIRED BY urls.py
# ---------------------------

@require_GET
def list_models(request):
    """Return a JSON list of all models in this service (efs_data_financial)."""
    app_models = apps.get_app_config("core").get_models()
    model_names = [m.__name__ for m in app_models]
    return JsonResponse({"models": model_names})


# ---------------------------
# View: financial_full (ABN)
# ---------------------------

@require_GET
def financial_full(request, abn: str):
    """
    Return ALL stored data for a company ABN, without summarising, and include:
      - FinancialData rows (items)
      - AR Ledger (primary LedgerData grouped; fallback UploadedLedgerData)
      - debtors list
      - invoices
      - fs_notes: LATEST per financial_data_type for this ABN
    """
    abn_digits = _digits(abn)
    if not abn_digits:
        return JsonResponse({"ok": False, "error": "Missing ABN"}, status=400)

    pattern = rf'^(?:[^0-9]*{"[^0-9]*".join(list(abn_digits))}[^0-9]*)$'

    rows = (
        FinancialData.objects.filter(Q(abn=abn_digits) | Q(abn__regex=pattern))
        .order_by("year", "timestamp")
    )

    company = rows.first().company_name if rows.exists() else "—"

    items = []
    for r in rows:
        items.append(
            {
                "id": str(r.id),
                "timestamp": (r.timestamp.isoformat() if r.timestamp else None),
                "abn": r.abn,
                "acn": r.acn,
                "company_name": r.company_name,
                "year": r.year,
                "financials": r.financials,
                "profit_loss": r.profit_loss,
                "balance_sheet": r.balance_sheet,
                "cash_flow": r.cash_flow,
                "financial_statement_notes": r.financial_statement_notes,
                "subsidiaries": r.subsidiaries,
                "raw": r.raw,
            }
        )

    # ---- User-entered notes (LATEST per financial_data_type for this ABN) ----
    # Postgres DISTINCT ON: latest per (abn, financial_data_type)
    notes_qs = (
        FinancialStatementNotes.objects.filter(Q(abn=abn_digits) | Q(abn__regex=pattern))
        .order_by("abn", "financial_data_type", "-created_at")
        .distinct("abn", "financial_data_type")
    )

    fs_notes = [
        {
            "id": str(n.pk),
            "transaction_id": str(n.transaction_id),
            "abn": n.abn,
            "acn": n.acn,
            "financial_data_type": n.financial_data_type,
            "notes": n.notes,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }
        for n in notes_qs
    ]

    # ---- AR Ledger primary (LedgerData), fallback to UploadedLedgerData ----
    primary_qs = (
        LedgerData.objects.filter(abn=abn_digits)
        .values("debtor")
        .annotate(total_due=Sum("amount_due"))
        .order_by("debtor")
    )

    if primary_qs.exists():
        ar_ledger = [
            {"name": r["debtor"] or "—", "total_due": float(r["total_due"] or 0.0)}
            for r in primary_qs
        ]
        debtors_list = [r["name"] for r in ar_ledger]
    else:
        uploaded = UploadedLedgerData.objects.filter(abn=abn_digits).order_by("debtor")
        ar_ledger = _uld_to_ar_rows(uploaded)
        debtors_list = [r["name"] for r in ar_ledger]

    inv_qs = InvoiceData.objects.filter(abn=abn_digits).order_by("-date_funded", "-due_date")
    invoices = [
        {
            "debtor": i.debtor or "—",
            "invoice_number": getattr(i, "inv_number", None) or "—",
            "amount_due": float(i.amount_due or 0),
            "repayment_date": i.due_date,
            "status": getattr(i, "status", "") or "",
            "created_at": i.date_funded,
        }
        for i in inv_qs
    ]

    return JsonResponse(
        {
            "ok": True,
            "abn": abn_digits,
            "company": company or "—",
            "items": items,
            "ar_ledger": ar_ledger,
            "debtors_list": debtors_list,
            "invoices": invoices,
            "fs_notes": fs_notes,
        },
        status=200,
    )


# ---------------------------
# View: financial_full_tx (TX)
# ---------------------------

@require_GET
def financial_full_tx(request, tx: str):
    """
    Return ALL stored data for a transaction_id, without summarising.
    Includes fs_notes as LATEST per financial_data_type for this tx (UUID),
    with optional ABN fallback.
    """
    tx = (tx or "").strip()
    if not tx:
        return JsonResponse({"ok": False, "error": "Missing transaction_id"}, status=400)

    # ABN fallback inference
    abn_param = _digits(request.GET.get("abn") or "")
    inferred_abn = ""

    try:
        if not abn_param:
            abns_for_tx = (
                UploadedLedgerData.objects.filter(transaction_id=tx)
                .values_list("abn", flat=True)
                .distinct()
            )
            for a in abns_for_tx:
                digits = _digits(a)
                if len(digits) == 11:
                    inferred_abn = digits
                    break
    except Exception:
        pass

    abn_for_fallback = abn_param or inferred_abn

    # Financial rows
    if _model_has_field(FinancialData, "transaction_id"):
        fin_rows = FinancialData.objects.filter(transaction_id=tx).order_by("year", "timestamp")
    else:
        if not abn_for_fallback:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "FinancialData has no 'transaction_id' column; pass ?abn=<11 digits> "
                             "or load UploadedLedgerData for this tx so ABN can be inferred.",
                },
                status=400,
            )
        pattern = rf'^(?:[^0-9]*{"[^0-9]*".join(list(abn_for_fallback))}[^0-9]*)$'
        fin_rows = (
            FinancialData.objects.filter(Q(abn=abn_for_fallback) | Q(abn__regex=pattern))
            .order_by("year", "timestamp")
        )

    company = fin_rows.first().company_name if fin_rows.exists() else "—"

    items = [
        {
            "id": str(r.id),
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "transaction_id": getattr(r, "transaction_id", None),
            "abn": r.abn,
            "acn": r.acn,
            "company_name": r.company_name,
            "year": r.year,
            "financials": r.financials,
            "profit_loss": r.profit_loss,
            "balance_sheet": r.balance_sheet,
            "cash_flow": r.cash_flow,
            "financial_statement_notes": r.financial_statement_notes,
            "subsidiaries": r.subsidiaries,
            "raw": r.raw,
        }
        for r in fin_rows
    ]

    # AR Ledger (LedgerData grouped; fallback UploadedLedgerData)
    if _model_has_field(LedgerData, "transaction_id"):
        primary_qs = (
            LedgerData.objects.filter(transaction_id=tx)
            .values("debtor")
            .annotate(total_due=Sum("amount_due"))
            .order_by("debtor")
        )
    else:
        base_qs = LedgerData.objects.filter(abn=abn_for_fallback) if abn_for_fallback else LedgerData.objects.none()
        primary_qs = (
            base_qs.values("debtor")
            .annotate(total_due=Sum("amount_due"))
            .order_by("debtor")
        )

    if primary_qs.exists():
        ar_ledger = [
            {"name": r["debtor"] or "—", "total_due": float(r["total_due"] or 0.0)}
            for r in primary_qs
        ]
        debtors_list = [r["name"] for r in ar_ledger]
    else:
        uld_qs = UploadedLedgerData.objects.filter(transaction_id=tx)
        if not uld_qs.exists() and abn_for_fallback:
            uld_qs = UploadedLedgerData.objects.filter(abn=abn_for_fallback)
        ar_ledger = _uld_to_ar_rows(uld_qs)
        debtors_list = [r["name"] for r in ar_ledger]

    # AP Ledger
    uap_qs = UploadAPLedgerData.objects.filter(transaction_id=tx)
    if not uap_qs.exists() and abn_for_fallback:
        uap_qs = UploadAPLedgerData.objects.filter(abn=abn_for_fallback)
    ap_ledger = _uap_to_ap_rows(uap_qs)

    # Invoices
    if _model_has_field(InvoiceData, "transaction_id"):
        inv_qs = InvoiceData.objects.filter(transaction_id=tx)
    else:
        inv_qs = InvoiceData.objects.filter(abn=abn_for_fallback) if abn_for_fallback else InvoiceData.objects.none()
    invoices = list(inv_qs.values())

    # ---- fs_notes: LATEST per financial_data_type for this tx ----
    tx_uuid = _parse_uuid(tx)
    notes_qs = FinancialStatementNotes.objects.none()

    if tx_uuid:
        notes_qs = (
            FinancialStatementNotes.objects.filter(transaction_id=tx_uuid)
            .order_by("transaction_id", "financial_data_type", "-created_at")
            .distinct("transaction_id", "financial_data_type")
        )

    # Optional ABN fallback if tx_uuid invalid OR there are no tx notes
    if (not notes_qs.exists()) and abn_for_fallback:
        notes_qs = (
            FinancialStatementNotes.objects.filter(abn=abn_for_fallback)
            .order_by("abn", "financial_data_type", "-created_at")
            .distinct("abn", "financial_data_type")
        )

    fs_notes = [
        {
            "id": str(n.pk),
            "transaction_id": str(n.transaction_id),
            "abn": n.abn,
            "acn": n.acn,
            "financial_data_type": n.financial_data_type,
            "notes": n.notes,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }
        for n in notes_qs
    ]

    return JsonResponse(
        {
            "ok": True,
            "transaction_id": tx,
            "company": company,
            "items": items,
            "ar_ledger": ar_ledger,
            "ap_ledger": ap_ledger,
            "debtors_list": debtors_list,
            "invoices": invoices,
            "fs_notes": fs_notes,
        },
        status=200,
    )



#-----------------------------Net asset value code-----


# efs_data_financial/core/views.py
# efs_data_financial/core/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Sum, Count
from django.db.models import Q

from .models import (
    NetAssetValueSnapshot,
    NAVAssetLine,
    NAVPlantandequipmentLine,
    NAVARLine,
)

# ---------------------------
# Helpers
# ---------------------------

def _digits_only(val: str) -> str:
    """Keep only digits so it works for ABN, ACN, whatever."""
    return "".join(ch for ch in str(val or "") if ch.isdigit())


def _find_latest_snapshot(abn: str | None, tx: str | None):
    """
    Prefer a snapshot by transaction_id when provided; if not found, fall back to ABN.
    Returns the latest (by created_at, id) or None.
    """
    qs = NetAssetValueSnapshot.objects.all()

    snap = None
    if tx:
        snap = qs.filter(transaction_id=tx).order_by("-created_at", "-id").first()
    if not snap and abn:
        snap = qs.filter(abn__icontains=abn).order_by("-created_at", "-id").first()
    return snap

def _find_snapshots_ordered(abn: str | None, tx: str | None):
    qs = NetAssetValueSnapshot.objects.all()
    if tx:
        qs = qs.filter(transaction_id=tx)
    elif abn:
        qs = qs.filter(abn__icontains=abn)
    return qs.order_by("-created_at", "-id")

def _pick_snapshot_with_lines(snaps, model_cls):
    from django.db.models import Count as _Count
    snap_ids = list(snaps.values_list("id", flat=True)[:200])
    if not snap_ids:
        return None, 0

    counts = (model_cls.objects
              .filter(snapshot_id__in=snap_ids)
              .values("snapshot_id")
              .annotate(n=_Count("id")))
    count_map = {row["snapshot_id"]: int(row["n"] or 0) for row in counts}

    for s in snaps:
        n = count_map.get(s.id, 0)
        if n > 0:
            return s, n
    return None, 0

# ---------------------------
# Endpoints
# ---------------------------

@require_GET
def assets_summary_api(request):
    """
    GET /api/assets/summary/?abn=...&tx=...

    Summarise ALL nominated assets (NAVAssetLine + NAVPlantandequipmentLine)
    across EVERY NetAssetValueSnapshot with source_tab == "ASSETS" that matches
    this transaction_id (or ABN fallback).
    """
    abn = _digits_only(request.GET.get("abn"))
    tx  = (request.GET.get("tx") or request.GET.get("transaction_id") or "").strip()

    if not abn and not tx:
        return JsonResponse({"ok": False, "error": "Provide abn or tx"}, status=400)

    # 1) Find matching snapshots (prefer tx; fallback to abn if none)
    snaps = NetAssetValueSnapshot.objects.all()
    snaps_tx = snaps.filter(transaction_id=tx) if tx else NetAssetValueSnapshot.objects.none()
    if tx and not snaps_tx.exists() and abn:
        # tx produced nothing – allow fallback to abn
        snaps_scoped = snaps.filter(abn__icontains=abn)
    else:
        snaps_scoped = snaps_tx if tx else snaps.filter(abn__icontains=abn)

    assets_snaps = snaps_scoped.filter(source_tab=NetAssetValueSnapshot.TAB_ASSETS).order_by("-created_at", "-id")
    asset_snap_ids = list(assets_snaps.values_list("id", flat=True))

    # If still nothing, return empty but with identifiers
    if not asset_snap_ids:
        return JsonResponse({
            "ok": True,
            "abn": abn or None,
            "transaction_id": tx or None,
            "total_rows": 0,
            "fmv_total": 0.0,
            "fsv_total": 0.0,
            "olv_total": 0.0,      # OLV not tracked
            "latest_as_of": None,  # no explicit 'as of' field
            "by_type": [],
            "by_make_model": [],
        }, status=200)

    # 2) Build the two base querysets across ALL ASSETS snapshots
    aset_qs = NAVAssetLine.objects.filter(snapshot_id__in=asset_snap_ids)
    pe_qs   = NAVPlantandequipmentLine.objects.filter(snapshot_id__in=asset_snap_ids)

    # 3) Aggregates
    total_rows = aset_qs.count() + pe_qs.count()

    fmv_total = (
        (aset_qs.aggregate(x=Sum("fmv_amount")).get("x") or 0) +
        (pe_qs.aggregate(x=Sum("fmv_amount")).get("x") or 0)
    )
    fsv_total = (
        (aset_qs.aggregate(x=Sum("fsv_amount")).get("x") or 0) +
        (pe_qs.aggregate(x=Sum("fsv_amount")).get("x") or 0)
    )

    # By type (merge assets + plant)
    by_type_assets = (
        aset_qs.values("type")
               .annotate(count=Count("id"),
                         fsv_total=Sum("fsv_amount"),
                         fmv_total=Sum("fmv_amount"))
    )
    by_type_pe = (
        pe_qs.values("type")
             .annotate(count=Count("id"),
                       fsv_total=Sum("fsv_amount"),
                       fmv_total=Sum("fmv_amount"))
    )
    by_type_map = {}
    for row in list(by_type_assets) + list(by_type_pe):
        key = row.get("type") or "Unknown"
        cur = by_type_map.get(key, {"type": key, "count": 0, "fsv_total": 0.0, "fmv_total": 0.0})
        cur["count"]     += int(row.get("count") or 0)
        cur["fsv_total"] += float(row.get("fsv_total") or 0)
        cur["fmv_total"] += float(row.get("fmv_total") or 0)
        by_type_map[key]  = cur
    by_type = sorted(by_type_map.values(), key=lambda r: (r["count"], r["fsv_total"]), reverse=True)[:25]

    # By make+model (FSV focus)
    by_mm_assets = (
        aset_qs.values("make", "model")
               .annotate(count=Count("id"), fsv_total=Sum("fsv_amount"))
    )
    by_mm_pe = (
        pe_qs.values("make", "model")
             .annotate(count=Count("id"), fsv_total=Sum("fsv_amount"))
    )
    by_mm_map = {}
    for row in list(by_mm_assets) + list(by_mm_pe):
        make  = row.get("make") or ""
        model = row.get("model") or ""
        key = (make, model)
        cur = by_mm_map.get(key, {"make": make, "model": model, "count": 0, "fsv_total": 0.0})
        cur["count"]     += int(row.get("count") or 0)
        cur["fsv_total"] += float(row.get("fsv_total") or 0)
        by_mm_map[key]    = cur
    by_make_model = sorted(by_mm_map.values(), key=lambda r: (r["count"], r["fsv_total"]), reverse=True)[:25]

    # 4) Payload (no `meta`, as requested)
    return JsonResponse({
        "ok": True,
        "abn": abn or None,
        "transaction_id": tx or None,
        "total_rows": int(total_rows or 0),
        "fmv_total": float(fmv_total or 0.0),
        "fsv_total": float(fsv_total or 0.0),
        "olv_total": 0.0,
        "latest_as_of": None,
        "by_type": by_type,
        "by_make_model": by_make_model,
    }, status=200)


from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import (
    NetAssetValueSnapshot,
    NAVAssetLine,
    NAVPlantandequipmentLine,
    NAVARLine,
)

def _digits_only(val: str) -> str:
    """Keep only digits so it works for ABN, ACN, whatever."""
    return "".join(ch for ch in str(val or "") if ch.isdigit())

def _find_snapshots_ordered(abn: str | None, tx: str | None):
    qs = NetAssetValueSnapshot.objects.all()
    if tx:
        qs = qs.filter(transaction_id=tx)
    elif abn:
        qs = qs.filter(abn__icontains=abn)
    return qs.order_by("-created_at", "-id")

@require_GET
def nav_latest_api(request):
    """
    GET /api/nav/latest/?abn=...&tx=...&debug=1

    Returns:
      - snapshot: newest matching snapshot (minimal fields; no `meta`)
      - asset_lines: ALL NAVAssetLine rows across ALL ASSETS snapshots for this tx/abn
      - plant_equipment_lines: ALL NAVPlantandequipmentLine rows across ALL ASSETS snapshots
      - ar_lines: ALL NAVARLine rows across ALL AR snapshots
      - snapshots_all: every matching snapshot (minimal fields; newest→oldest)
    """
    abn = _digits_only(request.GET.get("abn"))
    tx  = (request.GET.get("tx") or request.GET.get("transaction_id") or "").strip()
    want_debug = (request.GET.get("debug") in ("1", "true", "yes"))

    if not abn and not tx:
        return JsonResponse({"ok": False, "error": "Provide abn or tx"}, status=400)

    snaps = _find_snapshots_ordered(abn, tx)
    header_snap = snaps.first()
    if not header_snap:
        payload = {
            "ok": True,
            "snapshot": None,
            "asset_lines": [],
            "plant_equipment_lines": [],
            "ar_lines": [],
            "snapshots_all": [],
        }
        if want_debug:
            payload["debug"] = {"reason": "no snapshots found", "abn": abn or None, "tx": tx or None}
        return JsonResponse(payload, status=200)

    # Split by tab and collect ALL lines across ALL matching snapshots
    assets_snaps = snaps.filter(source_tab=NetAssetValueSnapshot.TAB_ASSETS)
    ar_snaps     = snaps.filter(source_tab=NetAssetValueSnapshot.TAB_AR)

    asset_snap_ids = list(assets_snaps.values_list("id", flat=True))
    ar_snap_ids    = list(ar_snaps.values_list("id", flat=True))

    # ---- Header snapshot (minimal fields; NO meta) ----
    snapshot = {
        "id": header_snap.id,
        "created_at": header_snap.created_at.isoformat() if header_snap.created_at else None,
        "abn": header_snap.abn,
        "transaction_id": header_snap.transaction_id,
        "source_tab": header_snap.source_tab,
        "advance_rate_pct": float(header_snap.advance_rate_pct),
        "selected_total_amount": float(header_snap.selected_total_amount),
        "available_funds_amount": float(header_snap.available_funds_amount),
    }

    # ---- Lines aggregated across ALL matching snapshots (by tab) ----
    asset_lines = []
    if asset_snap_ids:
        for r in NAVAssetLine.objects.filter(snapshot_id__in=asset_snap_ids).iterator():
            def _flt_or_none(v):
                return float(v) if v is not None else None

            asset_lines.append({
                "make": r.make,
                "model": r.model,
                "type": r.type,
                "year_of_manufacture": r.year_of_manufacture,
                "fmv_amount": float(r.fmv_amount or 0),
                "fsv_amount": float(r.fsv_amount or 0),
                # NEW ↓ preserve None so optional columns only show when present
                "bv_amount": _flt_or_none(r.bv_amount),
                "lease_os_amount": _flt_or_none(r.lease_os_amount),
                "nbv_amount": _flt_or_none(r.nbv_amount),
            })

    plant_equipment_lines = []
    if asset_snap_ids:
        for r in NAVPlantandequipmentLine.objects.filter(snapshot_id__in=asset_snap_ids).iterator():
            def _flt_or_none(v):
                return float(v) if v is not None else None

            plant_equipment_lines.append({
                "make": r.make,
                "model": r.model,
                "type": r.type,
                "year_of_manufacture": r.year_of_manufacture,
                "fmv_amount": float(r.fmv_amount or 0),
                "fsv_amount": float(r.fsv_amount or 0),
                # NEW ↓
                "bv_amount": _flt_or_none(r.bv_amount),
                "lease_os_amount": _flt_or_none(r.lease_os_amount),
                "nbv_amount": _flt_or_none(r.nbv_amount),
            })

    ar_lines = []
    if ar_snap_ids:
        for r in NAVARLine.objects.filter(snapshot_id__in=ar_snap_ids).iterator():
            ar_lines.append({
                "debtor_name": r.debtor_name,
                "aged_current": float(r.aged_current or 0),
                "d0_30": float(r.d0_30 or 0),
                "d31_60": float(r.d31_60 or 0),
                "d61_90": float(r.d61_90 or 0),
                "d90_plus": float(r.d90_plus or 0),
                "nominated": bool(r.nominated),
            })

    # ---- All snapshots (minimal fields; NO meta) ----
    snapshots_all = [{
        "id": s.id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "abn": s.abn,
        "transaction_id": s.transaction_id,
        "source_tab": s.source_tab,
        "advance_rate_pct": float(s.advance_rate_pct),
        "selected_total_amount": float(s.selected_total_amount),
        "available_funds_amount": float(s.available_funds_amount),
    } for s in snaps]

    payload = {
        "ok": True,
        "snapshot": snapshot,
        "asset_lines": asset_lines,
        "plant_equipment_lines": plant_equipment_lines,
        "ar_lines": ar_lines,
        "snapshots_all": snapshots_all,
    }

    if want_debug:
        payload["debug"] = {
            "abn": abn or None,
            "tx": tx or None,
            "header_snapshot_id": header_snap.id,
            "counts": {
                "snapshots_total": snaps.count(),
                "asset_snapshots": len(asset_snap_ids),
                "ar_snapshots": len(ar_snap_ids),
                "asset_lines": len(asset_lines),
                "plant_equipment_lines": len(plant_equipment_lines),
                "ar_lines": len(ar_lines),
            }
        }

    return JsonResponse(payload, status=200)






# efs_data_financial/core/views.py
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from django.db.models import Q
import json
import uuid

from .models import (
    FinancialData,
    AssetScheduleRow,
    PPEAsset,
    FinancialStatementNotes,
    UploadedLedgerData,
    UploadAPLedgerData,
)

def _parse_uuid(val):
    try:
        return uuid.UUID(str(val))
    except Exception:
        return None

@csrf_exempt
def data_checklist_status(request):
    """
    POST JSON: { "transaction_id": "...", "abn": "..." }
    Returns yes/no + counts for each model.
    - FinancialData: match on id == transaction_id (UUID primary key)
    - AssetScheduleRow: transaction_id is CharField, compare string
    - PPEAsset: transaction_id is CharField, compare string
    - FinancialStatementNotes: transaction_id is UUIDField
    - UploadedLedgerData: transaction_id is UUIDField
    - UploadAPLedgerData: transaction_id is UUIDField
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    tx = payload.get("transaction_id") or ""
    abn = (payload.get("abn") or "").strip()
    tx_uuid = _parse_uuid(tx)
    tx_str = str(tx).strip()

    # FinancialData: id is the primary key (UUID)
    fd_match_count = FinancialData.objects.filter(id=tx_uuid).count() if tx_uuid else 0
    fd_total_count = FinancialData.objects.count()

    # AssetScheduleRow: transaction_id is CharField
    asr_match_count = AssetScheduleRow.objects.filter(transaction_id=tx_str).count() if tx_str else 0
    asr_total_count = AssetScheduleRow.objects.count()

    # PPEAsset: transaction_id is CharField
    ppe_match_count = PPEAsset.objects.filter(transaction_id=tx_str).count() if tx_str else 0
    ppe_total_count = PPEAsset.objects.count()

    # FinancialStatementNotes: transaction_id is UUIDField
    fsn_match_count = FinancialStatementNotes.objects.filter(transaction_id=tx_uuid).count() if tx_uuid else 0
    fsn_total_count = FinancialStatementNotes.objects.count()

    # UploadedLedgerData (AR): transaction_id is UUIDField
    uld_match_count = UploadedLedgerData.objects.filter(transaction_id=tx_uuid).count() if tx_uuid else 0
    uld_total_count = UploadedLedgerData.objects.count()

    # UploadAPLedgerData (AP): transaction_id is UUIDField
    ap_match_count = UploadAPLedgerData.objects.filter(transaction_id=tx_uuid).count() if tx_uuid else 0
    ap_total_count = UploadAPLedgerData.objects.count()

    data = {
        "transaction_id": tx_str,
        "abn": abn or None,
        "models": {
            "FinancialData": {
                "exists": fd_match_count > 0,
                "match_count": fd_match_count,
                "total_count": fd_total_count,
                "match_rule": "id == transaction_id (UUID)",
            },
            "AssetScheduleRow": {
                "exists": asr_match_count > 0,
                "match_count": asr_match_count,
                "total_count": asr_total_count,
                "match_rule": "transaction_id (CharField) == transaction_id",
            },
            "PPEAsset": {
                "exists": ppe_match_count > 0,
                "match_count": ppe_match_count,
                "total_count": ppe_total_count,
                "match_rule": "transaction_id (CharField) == transaction_id",
            },
            "FinancialStatementNotes": {
                "exists": fsn_match_count > 0,
                "match_count": fsn_match_count,
                "total_count": fsn_total_count,
                "match_rule": "transaction_id (UUIDField) == transaction_id",
            },
            "UploadedLedgerData": {
                "exists": uld_match_count > 0,
                "match_count": uld_match_count,
                "total_count": uld_total_count,
                "match_rule": "transaction_id (UUIDField) == transaction_id",
            },
            "UploadAPLedgerData": {
                "exists": ap_match_count > 0,
                "match_count": ap_match_count,
                "total_count": ap_total_count,
                "match_rule": "transaction_id (UUIDField) == transaction_id",
            },
        },
    }
    return JsonResponse(data)




# efs_data_financial/core/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import NetAssetValueSnapshot


@require_GET
def nav_ar_latest_by_tx(request, tx: str):
   tx = (tx or "").strip()
   if not tx:
       return JsonResponse({"ok": False, "error": "transaction_id required"}, status=400)


   snap = (
       NetAssetValueSnapshot.objects
       .filter(transaction_id=tx, source_tab=NetAssetValueSnapshot.TAB_AR)
       .order_by("-created_at", "-id")
       .first()
   )


   if not snap:
       return JsonResponse({
           "ok": True,
           "found": False,
           "transaction_id": tx,
           "source_tab": NetAssetValueSnapshot.TAB_AR,
       }, status=200)


   return JsonResponse({
       "ok": True,
       "found": True,
       "transaction_id": tx,
       "source_tab": snap.source_tab,
       "created_at": snap.created_at.isoformat() if snap.created_at else None,
       "advance_rate_pct": str(snap.advance_rate_pct),
       "selected_total_amount": str(snap.selected_total_amount),
       "available_funds_amount": str(snap.available_funds_amount),
   }, status=200)




#-------#-------#-------#-------#-------#-------

#-------Invoice endpoints for efs_agents service

#-------#-------#-------#-------#-------#-------


from django.http import JsonResponse
from django.views.decorators.http import require_GET
from decimal import Decimal

from .models import InvoiceData, InvoiceDataUploaded, DebtorsCreditReport


def _norm(s: str | None) -> str:
    return (str(s or "").strip().lower())


def _is_rejected(obj) -> bool:
    """
    Rejected can come from:
      - approve_reject == "rejected"
      - invoice_state == "rejected" (uploaded workflow)
      - status == "rejected" (future-proofing)
    """
    if _norm(getattr(obj, "approve_reject", None)) == "rejected":
        return True
    if _norm(getattr(obj, "invoice_state", None)) == "rejected":
        return True
    if _norm(getattr(obj, "status", None)) == "rejected":
        return True
    return False


def _is_approved(obj) -> bool:
    """
    Approved can come from:
      - approve_reject == "approved"
      - invoice_state == "approved" (if you ever use it)
      - status == "approved" (future-proofing)
    """
    if _norm(getattr(obj, "approve_reject", None)) == "approved":
        return True
    if _norm(getattr(obj, "invoice_state", None)) == "approved":
        return True
    if _norm(getattr(obj, "status", None)) == "approved":
        return True
    return False


def _d(v) -> Decimal:
    try:
        if v is None or v == "":
            return Decimal("0")
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


@require_GET
def rejected_invoices_face_value_sum(request, tx: str):
    """
    GET /api/invoices/rejected-face-sum/<tx>/

    Now returns BOTH:
      - rejected invoice totals
      - approved invoice totals

    Data sources:
      - InvoiceData (API)
      - InvoiceDataUploaded (Uploaded overrides API by inv_number for same tx)
    """
    tx = (tx or "").strip()
    if not tx:
        return JsonResponse({"ok": False, "error": "transaction_id required"}, status=400)

    # 1) Fetch both tables for the same transaction_id
    api_qs = InvoiceData.objects.filter(transaction_id=tx)
    upl_qs = InvoiceDataUploaded.objects.filter(transaction_id=tx)

    # 2) Merge rule:
    #    Uploaded overrides API for the same inv_number (same tx).
    merged = {}

    for r in api_qs.iterator():
        inv = (getattr(r, "inv_number", None) or "").strip()
        key = (tx, inv) if inv else ("api", str(getattr(r, "pk", "")))
        merged[key] = r

    for r in upl_qs.iterator():
        inv = (getattr(r, "inv_number", None) or "").strip()
        key = (tx, inv) if inv else ("upl", str(getattr(r, "pk", "")))
        merged[key] = r  # overwrite / take uploaded

    merged_rows = list(merged.values())

    # 3) Partition: rejected vs approved (based on approve_reject / invoice_state / status)
    rejected_rows = [r for r in merged_rows if _is_rejected(r)]
    approved_rows = [r for r in merged_rows if _is_approved(r)]

    # 4) Sum face_value
    rejected_face_total = Decimal("0")
    for r in rejected_rows:
        rejected_face_total += _d(getattr(r, "face_value", None))

    approved_face_total = Decimal("0")
    for r in approved_rows:
        approved_face_total += _d(getattr(r, "face_value", None))

    # 5) Existing “Rejected debtors” output (unchanged)
    debtor_qs = DebtorsCreditReport.objects.filter(
        transaction_id=tx,
        state__iexact="rejected",
    )

    rejected_debtors = [
        {
            "id": d.id,
            "transaction_id": str(d.transaction_id),
            "debtor_name": d.debtor_name,
            "debtor_abn": d.debtor_abn,
            "debtor_acn": d.debtor_acn,
            "description": d.description,
            "item_code": d.item_code,
            "state": d.state,
            "debtor_start_date": (d.debtor_start_date.isoformat() if d.debtor_start_date else None),
        }
        for d in debtor_qs
    ]

    return JsonResponse(
        {
            "ok": True,
            "transaction_id": tx,

            # rejected totals (from BOTH models after merge)
            "rejected_count": len(rejected_rows),
            "rejected_face_value_total": str(rejected_face_total),

            # NEW: approved totals (from BOTH models after merge)
            "approved_count": len(approved_rows),
            "approved_face_value_total": str(approved_face_total),

            # optional debug counters
            "counts": {
                "api_invoices": api_qs.count(),
                "uploaded_invoices": upl_qs.count(),
                "merged_invoices": len(merged_rows),
            },

            # rejected debtors (unchanged)
            "rejected_debtors_count": debtor_qs.count(),
            "rejected_debtors": rejected_debtors,
        },
        status=200,
    )





#-----------------------------
    
    
    
    
    # End of code for financial data view code that sends data to  efs_agents service
    # End of code for financial data view code that sends data to  efs_agents service
    # End of code for financial data view code that sends data to  efs_agents service
    # End of code for financial data view code that sends data to  efs_agents service
    # End of code for financial data view code that sends data to  efs_agents service





#-----------------------------











#-----------------------------



    # Start of PPSR data view code that sends data to efs_agents service
    # Start of PPSR data view code that sends data to efs_agents service
    # Start of PPSR data view code that sends data to efs_agents service
    # Start of PPSR data view code that sends data to efs_agents service




#-----------------------------



#----------------------------- New PPSR fetching code based on ABN query----------

# efs_data_financials/core/views.py  (append near other TX endpoints)
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from django.db.models import Q
from .models import Registration
from collections import Counter
from django.utils import timezone

def _digits_only(val: str) -> str:
    """Keep only digits so it works for ABN, ACN, whatever."""
    return "".join(ch for ch in str(val or "") if ch.isdigit())

def _aware(dt):
    if not dt: return None
    if timezone.is_aware(dt): return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())

def _ppsr_norm_row(r: Registration) -> dict:
    st = _aware(r.start_time)
    et = _aware(r.end_time)
    return {
        "id": str(r.id),
        "transaction_id": str(r.transaction_id) if r.transaction_id else None,
        "abn": r.abn,
        "registration_number": r.registration_number,
        "registration_kind": r.registration_kind,
        "start_time": st.isoformat() if st else None,
        "end_time": et.isoformat() if et else None,
        "change_number": r.change_number,
        "change_time": r.change_time.isoformat() if r.change_time else None,
        "collateral_class_type": r.collateral_class_type,
        "collateral_type": r.collateral_type,
        "collateral_class_description": r.collateral_class_description,
        "are_proceeds_claimed": bool(r.are_proceeds_claimed),
        "is_security_interest_registration_kind": bool(r.is_security_interest_registration_kind),
        "are_assets_subject_to_control": bool(r.are_assets_subject_to_control),
        "is_inventory": bool(r.is_inventory),
        "is_pmsi": bool(r.is_pmsi),
        "is_subordinate": bool(r.is_subordinate),
        "grantor_organisation_identifier": r.grantor_organisation_identifier,
        "grantor_organisation_identifier_type": r.grantor_organisation_identifier_type,
        "grantor_organisation_name": r.grantor_organisation_name,
        "security_party_groups": r.security_party_groups,
        "grantors": r.grantors,
        "address_for_service": r.address_for_service,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

@require_GET
def ppsr_full_tx(request, tx: str):
    """
    TX-first PPSR: GET /ppsr/full_tx/<tx>/?abn=<11>
    - Filter Registration by transaction_id == tx
    - If no rows and ?abn given, fallback to ABN filter
    Response: {"ok": True, "transaction_id": ..., "abn": "...", "counts": {...}, "registrations": [...]}
    """
    tx = (tx or "").strip()
    if not tx:
        return JsonResponse({"ok": False, "error": "Missing transaction_id"}, status=400)

    abn_param = _digits_only(request.GET.get("abn") or "")

    qs = Registration.objects.filter(transaction_id=tx).order_by("-start_time", "-created_at")
    if not qs.exists() and abn_param:
        qs = Registration.objects.filter(abn=abn_param).order_by("-start_time", "-created_at")

    regs = list(qs[:200])  # sane cap
    now = timezone.now()

    total = len(regs)
    active = expired = pmsi = subordinate = 0
    collateral_counter = Counter()

    for r in regs:
        st = _aware(r.start_time)
        et = _aware(r.end_time)
        if et and et <= now: expired += 1
        else: active += 1
        if r.is_pmsi: pmsi += 1
        if r.is_subordinate: subordinate += 1
        collateral_counter[(r.collateral_class_type or r.collateral_type or "Unknown")] += 1

    return JsonResponse({
        "ok": True,
        "transaction_id": tx,
        "abn": abn_param or (regs[0].abn if regs else None),
        "counts": {
            "total": total, "active": active, "expired": expired,
            "pmsi": pmsi, "subordinate": subordinate
        },
        "collateral_breakdown": [
            {"collateral_class_type": k, "count": v}
            for k, v in collateral_counter.most_common()
        ],
        "registrations": [_ppsr_norm_row(r) for r in regs],
    }, status=200)







from django.http import JsonResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET
from django.utils import timezone
from .models import Registration
from collections import Counter
from datetime import datetime

def _as_bool(v):
    return bool(v) if v is not None else False

def _iso(dt):
    return dt.isoformat() if dt else None

def _safe(d, k, default=None):
    try:
        return (d or {}).get(k, default)
    except Exception:
        return default

def _top(items, n=5):
    return items[:n] if items else []

def _normalize_reg(r: Registration) -> dict:
    return {
        "id": str(r.id),
        "abn": r.abn,
        "registration_number": r.registration_number,
        "registration_kind": r.registration_kind,
        "start_time": _iso(r.start_time),
        "end_time": _iso(r.end_time),
        "is_migrated": _as_bool(r.is_migrated),
        "is_transitional": _as_bool(r.is_transitional),
        "collateral_class_type": r.collateral_class_type,
        "collateral_type": r.collateral_type,
        "collateral_class_description": r.collateral_class_description,
        "are_proceeds_claimed": _as_bool(r.are_proceeds_claimed),
        "is_security_interest_registration_kind": _as_bool(r.is_security_interest_registration_kind),
        "are_assets_subject_to_control": _as_bool(r.are_assets_subject_to_control),
        "is_inventory": _as_bool(r.is_inventory),
        "is_pmsi": _as_bool(r.is_pmsi),
        "is_subordinate": _as_bool(r.is_subordinate),
        "grantor": {
            "identifier": r.grantor_organisation_identifier,
            "identifier_type": r.grantor_organisation_identifier_type,
            "name": r.grantor_organisation_name,
        },
        "security_party_groups": r.security_party_groups,  # JSON blob as-is
        "grantors": r.grantors,                            # JSON blob as-is
        "address_for_service": r.address_for_service,      # JSON blob as-is
    }

# efs_data_financial/core/views.py

from collections import Counter
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.http import JsonResponse
from .models import Registration


# ---- PPSR helpers (self-contained) -----------------------------------

def _aware(dt):
    """Return a timezone-aware datetime (or None)."""
    if not dt:
        return None
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt, timezone.get_current_timezone())

def _ppsr_norm(r: Registration) -> dict:
    """Compact representation of a registration row."""
    st = _aware(r.start_time)
    et = _aware(r.end_time)
    return {
        "registration_number": r.registration_number,
        "registration_kind": r.registration_kind,
        "start_time": st.isoformat() if st else None,
        "end_time": et.isoformat() if et else None,
        "collateral_class_type": r.collateral_class_type,
        "collateral_type": r.collateral_type,
        "is_pmsi": bool(r.is_pmsi),
        "is_subordinate": bool(r.is_subordinate),
        "grantor_name": r.grantor_organisation_name,
    }

def _ppsr_top(items, n=10):
    """items is a list of ((name, role), count)."""
    return sorted(items, key=lambda x: x[1], reverse=True)[:n]


def _abn_to_acn(s: str) -> str:
    """
    ABN = 11 digits (first 2 are the checksum); ACN = last 9 digits.
    If already 9 digits, return as-is. Otherwise best-effort: take last 9.
    """
    d = _digits(s)
    if len(d) == 9:
        return d
    if len(d) >= 9:
        return d[-9:]
    return d  

# ---- Aware-safe summary endpoint -------------------------------------

@require_GET
def ppsr_for_abn_summary(request, abn: str):
    """
    JSON: Compact PPSR summary for agents.
    GET /ppsr/<abn>/

    Returns:
    {
      "abn": "...",
      "counts": { "total": 0, "active": 0, "expired": 0, "pmsi": 0, "subordinate": 0 },
      "collateral_breakdown": [{"collateral_class_type": "...", "count": 2}, ...],
      "secured_parties_top": [{"name":"...", "role":"Secured Party", "count": 3}, ...],
      "samples": { "recent_registrations": [ ... up to 5 ... ] },
      "registrations": [ ... up to 50 ... ]
    }
    """
    abn_digits = "".join(ch for ch in (abn or "") if ch.isdigit())
    if not abn_digits:
        return JsonResponse({"success": False, "error": "Invalid ABN"}, status=400)

    qs = (
        Registration.objects
        .filter(abn=abn_digits)
        .order_by("-start_time", "-created_at")
    )

    if not qs.exists():
        # Return valid empty shape
        return JsonResponse({
            "abn": abn_digits,
            "counts": {"total": 0, "active": 0, "expired": 0, "pmsi": 0, "subordinate": 0},
            "collateral_breakdown": [],
            "secured_parties_top": [],
            "samples": {"recent_registrations": []},
            "registrations": [],
        })

    now = timezone.now()

    total = qs.count()
    active = 0
    expired = 0
    pmsi_count = 0
    subordinate_count = 0

    collateral_counter = Counter()
    secured_counter = Counter()

    recent = []
    regs_out = []

    for r in qs:
        # --- normalize to aware before comparing/serializing ---
        start_aware = _aware(r.start_time)
        end_aware   = _aware(r.end_time)

        # active vs expired
        if end_aware and end_aware <= now:
            expired += 1
        else:
            active += 1

        if r.is_pmsi:
            pmsi_count += 1
        if r.is_subordinate:
            subordinate_count += 1

        # collateral breakdown
        key = r.collateral_class_type or r.collateral_type or "Unknown"
        collateral_counter[key] += 1

        # secured parties (if present in JSON)
        spg = r.security_party_groups or []
        for grp in spg:
            parties = (grp or {}).get("securityParties") or (grp or {}).get("parties") or []
            for p in parties:
                nm = (p or {}).get("name") or (p or {}).get("organisationName") or (p or {}).get("partyName")
                role = (p or {}).get("role") or (p or {}).get("partyRole") or "Secured Party"
                if nm:
                    secured_counter[(nm, role)] += 1

        # recent list (cap 5)
        if len(recent) < 5:
            recent.append({
                "registration_number": r.registration_number,
                "registration_kind": r.registration_kind,
                "start_time": start_aware.isoformat() if start_aware else None,
                "end_time": end_aware.isoformat() if end_aware else None,
                "collateral_class_type": r.collateral_class_type,
                "is_pmsi": bool(r.is_pmsi),
                "is_subordinate": bool(r.is_subordinate),
            })

        # full list (cap 50)
        if len(regs_out) < 50:
            regs_out.append(_ppsr_norm(r))

    collateral_breakdown = [
        {"collateral_class_type": k, "count": v}
        for k, v in collateral_counter.most_common()
    ]

    secured_items = list(secured_counter.items())
    secured_parties_top = [
        {"name": nm, "role": role, "count": cnt}
        for (nm, role), cnt in _ppsr_top(secured_items, n=10)
    ]

    return JsonResponse({
        "abn": abn_digits,
        "counts": {
            "total": total,
            "active": active,
            "expired": expired,
            "pmsi": pmsi_count,
            "subordinate": subordinate_count,
        },
        "collateral_breakdown": collateral_breakdown,
        "secured_parties_top": secured_parties_top,
        "samples": {"recent_registrations": recent},
        "registrations": regs_out,
    })


# ----------------- invoice data for invoice finance lms -----------------


# this code exposese end point when user presses the pay button in efs_finance application


# ----------------- invoice data for invoice finance lms -----------------



from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import InvoiceData, InvoiceDataUploaded


def _serialize_invoice(r, source: str):
    return {
        "source": source,  # optional but handy for debugging
        "abn": r.abn,
        "acn": r.acn,
        "name": r.name,
        "transaction_id": r.transaction_id,
        "debtor": r.debtor,
        "date_funded": r.date_funded.strftime("%Y-%m-%d") if r.date_funded else None,
        "due_date": r.due_date.strftime("%Y-%m-%d") if r.due_date else None,
        "amount_funded": str(r.amount_funded) if r.amount_funded is not None else None,
        "amount_due": str(r.amount_due) if r.amount_due is not None else None,
        "discount_percentage": str(r.discount_percentage) if r.discount_percentage is not None else None,
        "face_value": str(r.face_value) if r.face_value is not None else None,
        "sif_batch": r.sif_batch,
        "inv_number": r.inv_number,
        # Fields that exist only on uploaded model (safe on InvoiceData using getattr)
        "invoice_state": getattr(r, "invoice_state", None),
        "date_paid": getattr(r, "date_paid", None).strftime("%Y-%m-%d") if getattr(r, "date_paid", None) else None,
        "approve_reject": getattr(r, "approve_reject", None),
    }




@require_GET
def invoices_by_transaction(request):
    tx = request.GET.get("transaction_id")
    if not tx:
        return JsonResponse({"results": []})

    # Pull both sets
    api_rows = InvoiceData.objects.filter(transaction_id=tx).order_by("inv_number")
    uploaded_rows = InvoiceDataUploaded.objects.filter(transaction_id=tx).order_by("inv_number")

    # Merge key: inv_number is your natural identifier per transaction.
    # If inv_number can repeat across debtors within the same tx (rare), change key to (inv_number, debtor).
    merged = {}

    # 1) Put API rows in first
    for r in api_rows:
        if not r.inv_number:
            continue
        key = (tx, r.inv_number)
        merged[key] = _serialize_invoice(r, source="api")

    # 2) Overlay uploaded rows (override)
    for r in uploaded_rows:
        if not r.inv_number:
            continue
        key = (tx, r.inv_number)
        merged[key] = _serialize_invoice(r, source="uploaded")

    # Return in invoice order
    out = sorted(merged.values(), key=lambda x: (x.get("inv_number") or ""))

    return JsonResponse({"results": out})




# ----------------- Helpers -----------------


# Financial Statements file upload logic 


# ----------------- Helpers -----------------





# -------- helpers --------
# efs_data_financial/core/views.py
# efs_data_financial/core/views.py
import csv, io, json, logging
from typing import Any, Tuple, List, Dict, Optional

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import FinancialData

log = logging.getLogger(__name__)

# ---------- helpers ----------
def _norm_abn(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _guess_year(payload: Any) -> Optional[int]:
    def _one(obj):
        if isinstance(obj, dict):
            for k in ("year", "financialYear", "fy", "financial_year"):
                v = obj.get(k)
                try:
                    if v is not None:
                        y = int(str(v)[:4])
                        if 1900 <= y <= 2100:
                            return y
                except Exception:
                    pass
        return None
    if isinstance(payload, list) and payload:
        return _one(payload[0])
    return _one(payload)

def _try_parse_json(file_bytes: bytes) -> Any:
    return json.loads(file_bytes.decode("utf-8"))

def _try_parse_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    text = file_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]

def _try_parse_xlsx(file_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        import pandas as pd
    except Exception as e:
        raise ValueError("XLSX upload requires pandas to be installed") from e
    bio = io.BytesIO(file_bytes)
    df = pd.read_excel(bio)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")

def _parse_upload_to_json(uploaded) -> Tuple[Any, int]:
    """
    For PL/BS/CF uploads: CSV/JSON/XLSX → Python (list/dict), with row count for UI.
    """
    name = (uploaded.name or "").lower()
    raw = uploaded.read()

    if name.endswith(".json"):
        payload = _try_parse_json(raw)
        return payload, (len(payload) if isinstance(payload, list) else 1)

    if name.endswith(".csv"):
        rows = _try_parse_csv(raw)
        return rows, len(rows)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        rows = _try_parse_xlsx(raw)
        return rows, len(rows)

    # Try JSON as a last-ditch
    try:
        payload = _try_parse_json(raw)
        return payload, (len(payload) if isinstance(payload, list) else 1)
    except Exception:
        pass

    raise ValueError("Unsupported file type. Please upload CSV, JSON, or XLSX.")

def _pdf_bytes_to_text(file_bytes: bytes) -> str:
    """
    Extract text from PDF bytes.
    1) Try pdfminer.six with tuned LAParams (best at avoiding word-per-line).
    2) Fall back to PyPDF2.
    3) Final fallback: empty string.
    """
    # 1) pdfminer.six with layout tuning
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.layout import LAParams
        laparams = LAParams(
            # smaller margins -> less eager to break lines
            line_margin=0.15,   # default ~0.5
            word_margin=0.05,   # default ~0.1
            char_margin=2.0     # default ~2.0 (fine)
        )
        txt = (extract_text(io.BytesIO(file_bytes), laparams=laparams) or "").strip()
        if txt:
            return txt
    except Exception:
        pass

    # 2) PyPDF2 fallback
    try:
        import PyPDF2
        text_parts = []
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t:
                text_parts.append(t)
        txt = "\n".join(text_parts).strip()
        if txt:
            return txt
    except Exception:
        pass

    # 3) Give up
    return ""



# efs_data_financial/core/views.py

import csv, io, json, logging, re, uuid
from decimal import Decimal
from typing import Any, Tuple, List, Dict, Optional

import pandas as pd
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import FinancialData

log = logging.getLogger(__name__)

# -------------------- helpers --------------------

YEAR_RE = re.compile(r"^\d{4}$")

def _strip_bom(s: str) -> str:
    return (s or "").replace("\ufeff", "").strip()

def _to_amount(x) -> str:
    """Normalise numeric-like strings -> plain number string; keep '' for missing."""
    if x is None or x == "":
        return ""
    s = str(x).strip()
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    s = s.replace(",", "")
    try:
        d = Decimal(s)
        if neg:
            d = -d
        return f"{d.normalize()}"
    except Exception:
        return ""

def _clean_headers_and_values(rows: list[dict]) -> list[dict]:
    """Trim BOMs, unify 'description/item/line item' -> 'Line Item'."""
    cleaned = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        new = {}
        for k, v in r.items():
            k2 = _strip_bom(k)
            if k2.lower() in {"description", "item", "line item"}:
                k2 = "Line Item"
            if k2 in {"PVS", "\ufeffPVS"}:
                k2 = "Line Item"
            new[k2] = (str(v).strip() if isinstance(v, str) else v)
        cleaned.append(new)
    return cleaned



def _looks_like_pvs_two_column(rows: list[dict]) -> bool:
    """
    Heuristic for PVS 'stacked' CSVs where the left column is either a year
    (YYYY) or an amount, and the right column is the description.
    We consider it a match if among the first 25 rows we see a line where:
       left == YYYY  and right is non-empty.
    """
    if not rows:
        return False
    rows = _clean_headers_and_values(rows)
    probe = rows[:25]
    for r in probe:
        # choose the first non "Line Item" header as the LEFT column
        left_keys = [k for k in r.keys() if _strip_bom(k) != "Line Item"]
        if not left_keys:
            continue
        left = _strip_bom(str(r.get(left_keys[0]) or ""))
        right = (r.get("Line Item") or "").strip()
        if YEAR_RE.match(left) and right:
            return True
    return False


def _normalise_pvs_two_column(rows: list[dict]) -> list[dict]:
    """
    Convert stacked two-column PVS CSV into wide, multi-year JSON rows like:
      {"Line Item": "...", "2021": "…", "2022": "…", ...}

    Behaviour:
      • Any row whose LEFT cell is exactly YYYY starts a new year block.
      • Following rows in that block: LEFT = amount, RIGHT = line item name.
      • Values are merged by 'Line Item' across all years found.
      • Every output row is padded with all years encountered (missing -> "").
    """
    rows = _clean_headers_and_values(rows)

    # Figure out the left column key (first non "Line Item" header)
    def _left_key(r: dict) -> str | None:
        for k in r.keys():
            if _strip_bom(k) != "Line Item":
                return k
        return None

    merged: dict[str, dict] = {}     # name -> row dict
    order: list[str] = []            # preserve first-seen order
    years_seen: list[int] = []
    current_year: int | None = None

    SECTION_NAMES = {
        "income", "expenses", "cogs", "cogs:", "gross profit", "gross profit (%)",
        "gp %", "profit & loss", "balance sheet",
        "normalised profit reconciliation:",
    }

    for r in rows:
        lk = _left_key(r)
        if lk is None:
            continue

        left_raw = r.get(lk)
        right_raw = r.get("Line Item")

        left = _strip_bom("" if left_raw is None else str(left_raw))
        name = (right_raw or "").strip()

        # YEAR header row?
        if YEAR_RE.match(left):
            y = int(left)
            if 1900 <= y <= 2100:
                current_year = y
                if y not in years_seen:
                    years_seen.append(y)
                # nothing else to do for a header row
                continue

        # skip until we have a current year and a line item
        if current_year is None or not name:
            continue

        amt = _to_amount(left)  # handles commas, (negatives), sci-notation, blanks

        # Skip obvious section headers without numbers
        if amt == "" and name.strip().lower() in SECTION_NAMES:
            continue

        # Merge
        row = merged.get(name)
        if row is None:
            row = merged[name] = {"Line Item": name}
            order.append(name)
        row[str(current_year)] = amt

    # Pad every line with every year that appeared, so all rows have all columns
    for row in merged.values():
        for y in years_seen:
            row.setdefault(str(y), "")

    return [merged[n] for n in order]




def _norm_abn(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _norm_acn(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isalnum())

def _norm_company_id_pair(raw_abn: str, raw_acn: str) -> tuple[Optional[str], Optional[str]]:
    abn = _norm_abn(raw_abn) or None
    acn = _norm_acn(raw_acn) or None
    return abn, acn

def _guess_year(payload: Any) -> Optional[int]:
    def _one(obj):
        if isinstance(obj, dict):
            for k in ("year", "financialYear", "fy", "financial_year"):
                v = obj.get(k)
                try:
                    if v is not None:
                        y = int(str(v)[:4])
                        if 1900 <= y <= 2100:
                            return y
                except Exception:
                    pass
        return None
    if isinstance(payload, list) and payload:
        return _one(payload[0])
    return _one(payload)

def _try_parse_json(file_bytes: bytes) -> Any:
    return json.loads(file_bytes.decode("utf-8"))

def _try_parse_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    text = file_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]

def _try_parse_xlsx(file_bytes: bytes) -> List[Dict[str, Any]]:
    bio = io.BytesIO(file_bytes)
    df = pd.read_excel(bio)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")

def _parse_upload_to_json(uploaded) -> Tuple[Any, int]:
    """
    CSV/JSON/XLSX -> Python + row count (for UI).
    """
    name = (uploaded.name or "").lower()
    raw = uploaded.read()

    if name.endswith(".json"):
        payload = _try_parse_json(raw)
        return payload, (len(payload) if isinstance(payload, list) else 1)

    if name.endswith(".csv"):
        rows = _try_parse_csv(raw)
        return rows, len(rows)

    if name.endswith(".xlsx") or name.endswith(".xls"):
        rows = _try_parse_xlsx(raw)
        return rows, len(rows)

    # last-ditch: try json
    try:
        payload = _try_parse_json(raw)
        return payload, (len(payload) if isinstance(payload, list) else 1)
    except Exception:
        pass

    raise ValueError("Unsupported file type. Please upload CSV, JSON, or XLSX.")

def _pdf_bytes_to_text(file_bytes: bytes) -> str:
    """PDF -> text (best-effort)."""
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.layout import LAParams
        laparams = LAParams(line_margin=0.15, word_margin=0.05, char_margin=2.0)
        txt = (extract_text(io.BytesIO(file_bytes), laparams=laparams) or "").strip()
        if txt:
            return txt
    except Exception:
        pass
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        parts = []
        for p in reader.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            if t:
                parts.append(t)
        txt = "\n".join(parts).strip()
        if txt:
            return txt
    except Exception:
        pass
    return ""

def _clean_wrapped_text(txt: str) -> str:
    # light normalisation; keep simple to avoid side effects
    return txt.strip()

# -------------------- main endpoint --------------------

@csrf_exempt
@require_POST
def upload_financials(request):
    """
    Expects multipart/form-data:
      - file (file)                         REQUIRED
      - abn (str)                           OPTIONAL
      - acn (str)                           OPTIONAL
      - data_type in {financials_pl, financials_bs, financials_cf, financials_notes} REQUIRED
      - (optional) year (int-like)
      - (optional) company_name
      - (optional) transaction_id (UUID)    preferred PK if provided

    Behaviour:
      * Auto-detect and normalise the “PVS two-column” CSV into wide rows
        that match your target structure (Line Item + YYYY columns).
      * Store payload as-is on the appropriate field.
    """

    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"success": False, "message": "Missing file"}, status=400)

    data_type = (request.POST.get("data_type") or "").strip()
    if data_type not in {"financials_pl", "financials_bs", "financials_cf", "financials_notes"}:
        return JsonResponse({"success": False, "message": "Invalid data_type"}, status=400)

    # company identifiers
    raw_abn = request.POST.get("abn", "")
    raw_acn = request.POST.get("acn", "")
    abn, acn = _norm_company_id_pair(raw_abn, raw_acn)
    if not abn and not acn:
        return JsonResponse({"success": False, "message": "Missing or invalid company identifier (need ABN or ACN)"}, status=400)

    company_name = (request.POST.get("company_name") or "").strip() or None

    # ---- Parse content depending on data_type ----
    try:
        if data_type == "financials_notes":
            # NOTES are PDFs → text (no rows count concept)
            file_bytes = f.read()
            notes_text = _pdf_bytes_to_text(file_bytes)
            if not notes_text:
                return JsonResponse({"success": False, "message": "Could not extract text from PDF"}, status=400)
            payload = _clean_wrapped_text(notes_text)
            rows_count = 1
        else:
            # PL/BS/CF: CSV/JSON/XLSX parse
            payload, rows_count = _parse_upload_to_json(f)

            # NORMALISE: if it's the PVS two-column layout, convert to wide
            if isinstance(payload, list) and _looks_like_pvs_two_column(payload):
                payload = _normalise_pvs_two_column(payload)

                # if the normalisation produced nothing, bail with a helpful error
                if not payload:
                    return JsonResponse(
                        {"success": False, "message": "Unable to normalise the PVS two-column file."},
                        status=400,
                    )
    except Exception as e:
        log.exception("Failed to parse upload")
        return JsonResponse({"success": False, "message": f"Parse error: {e}"}, status=400)

    # ---- Year inference (best-effort) ----
    year = request.POST.get("year")
    try:
        year = int(year) if year else None
    except Exception:
        year = None
    if year is None and data_type != "financials_notes":
        year = _guess_year(payload) or None

    # ---- Persist (TX-as-PK when provided) ----
    try:
        tx_str = (request.POST.get("transaction_id") or "").strip()
        tx_uuid = None
        if tx_str:
            try:
                tx_uuid = uuid.UUID(tx_str)
            except Exception:
                return JsonResponse({"success": False, "message": "transaction_id must be a valid UUID"}, status=400)

        with transaction.atomic():
            if tx_uuid:
                defaults = {"year": year, "company_name": company_name}
                if abn: defaults["abn"] = abn
                if acn: defaults["acn"] = acn

                obj, _created = FinancialData.objects.get_or_create(id=tx_uuid, defaults=defaults)

                # sync metadata on subsequent uploads
                if abn and not getattr(obj, "abn", None): obj.abn = abn
                if acn and not getattr(obj, "acn", None): obj.acn = acn
                if year is not None and not obj.year: obj.year = year
                if company_name and not obj.company_name: obj.company_name = company_name

            else:
                # legacy: try to reuse identifier+year row, else create
                qs = FinancialData.objects.all()
                if abn:
                    qs = qs.filter(abn=abn)
                elif acn:
                    qs = qs.filter(acn=acn)
                if year is not None:
                    qs = qs.filter(year=year)

                obj = qs.first()
                if not obj:
                    create_kwargs = {"year": year, "company_name": company_name}
                    if abn: create_kwargs["abn"] = abn
                    if acn: create_kwargs["acn"] = acn
                    obj = FinancialData.objects.create(**create_kwargs)

                # sync missing metadata
                if company_name and not obj.company_name: obj.company_name = company_name
                if abn and not getattr(obj, "abn", None): obj.abn = abn
                if acn and not getattr(obj, "acn", None): obj.acn = acn
                if year is not None and not obj.year: obj.year = year

            # Attach the uploaded (possibly normalised) payload
            if data_type == "financials_pl":
                obj.profit_loss = payload
            elif data_type == "financials_bs":
                obj.balance_sheet = payload
            elif data_type == "financials_cf":
                obj.cash_flow = payload
            elif data_type == "financials_notes":
                max_len = FinancialData._meta.get_field("financial_statement_notes").max_length or 5000
                obj.financial_statement_notes = (payload or "")[:max_len]

            obj.save()

        return JsonResponse({
            "success": True,
            "rows_created": (len(payload) if isinstance(payload, list) else 1),
            "year": year,
            "id": str(obj.id),
        })
    except Exception as e:
        log.exception("Failed to persist financials")
        return JsonResponse({"success": False, "message": f"Save error: {e}"}, status=500)



















import uuid
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import UploadedLedgerData


def _norm(s):
    return "".join(str(s or "").strip().lower().replace("_", "").replace(" ", ""))

def _is_nan(v):
    try:
        return pd.isna(v)
    except Exception:
        return False

def _pick_col(df, *aliases):
    """
    Flexible column matcher. We'll try exact-normalised headers first,
    then fuzzy 'starts with / contains'.
    """
    norm_cols = {_norm(c): c for c in df.columns}
    for a in aliases:
        want = _norm(a)
        if want in norm_cols:
            return norm_cols[want]
    # fallback fuzzy
    for a in aliases:
        want = _norm(a)
        for raw_norm, raw_col in norm_cols.items():
            if raw_norm.startswith(want) or want in raw_norm:
                return raw_col
    return None

def _to_float(v):
    """
    Best-effort numeric parse:
    - handles commas: "1,234.56"
    - handles parentheses: "(123.45)" => -123.45
    Returns float or None.
    """
    if v is None or _is_nan(v):
        return None
    try:
        s = str(v).strip()
        if s == "" or s.lower() in {"nan", "none", "null"}:
            return None
        s = s.replace(",", "")
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        return float(s)
    except Exception:
        return None

def _only_digits(val):
    """Strip everything except 0-9."""
    return "".join(ch for ch in str(val or "") if ch.isdigit()).strip() or None


@csrf_exempt
@require_POST
def upload_ar_ledger(request):
    try:
        # --- 1) transaction_id (required UUID for this upload batch) ---
        tx_str = (request.POST.get("transaction_id") or "").strip()
        try:
            tx_shared = uuid.UUID(tx_str)
        except Exception:
            return JsonResponse(
                {"success": False, "message": "Invalid or missing transaction_id"},
                status=400,
            )

        # --- 2) fallback ABN / ACN from the form (optional) ---
        form_abn = _only_digits(request.POST.get("abn", ""))
        form_acn = _only_digits(request.POST.get("acn", ""))

        # --- 3) file load ---
        up = request.FILES.get("file")
        if not up:
            return JsonResponse({"success": False, "message": "No file uploaded"}, status=400)

        if up.name.lower().endswith(".csv"):
            df = pd.read_csv(up)
        else:
            df = pd.read_excel(up)

        if df is None or df.empty:
            return JsonResponse({"success": False, "message": "Empty file"}, status=400)

        # --- 4) map headers (flexible) ---
        # debtor / customer name
        c_name = _pick_col(df,
            "Debtor", "Debtors", "Debtor Name",
            "Customer", "Customer Name"
        )

        # per-row ABN/ACN columns if provided
        c_abn  = _pick_col(df, "ABN")
        c_acn  = _pick_col(df, "ACN")

        # ageing buckets
        c_aged = _pick_col(df, "Aged Receivables", "AgedReceivables", "Current", "Aged Receivable")
        c_030  = _pick_col(df, "0-30 days", "0-30days", "0_30days", "0-30", "0–30 days", "0 to 30 days")
        c_3160 = _pick_col(df, "31-60 days", "31-60days", "31_60days", "31-60", "31–60 days", "31 to 60 days")
        c_6190 = _pick_col(df, "61-90 days", "61-90days", "61_90days", "61-90", "61–90 days", "61 to 90 days")
        c_90p  = _pick_col(df, "90+ days", "90+days", "90plus", "90plusdays",
                           "90", "90+ days overdue", "90+")

        missing = [
            label for (label, col) in {
                "Debtor/Debtors": c_name,
                "Aged Receivables": c_aged,
                "0-30 days": c_030,
                "31-60 days": c_3160,
                "61-90 days": c_6190,
                "90+ days": c_90p,
            }.items() if not col
        ]
        if missing:
            return JsonResponse(
                {"success": False, "message": f"Missing columns: {', '.join(missing)}"},
                status=400,
            )

        # --- 5) zero-fill policy: only fill "0" if that bucket appears to be used in file ---
        aging_cols = [c_aged, c_030, c_3160, c_6190, c_90p]
        col_has_nonzero = {}
        for col in aging_cols:
            nums = df[col].map(_to_float)
            # if ANY non-zero exists in that column, treat missing values as 0 for real debtors
            col_has_nonzero[col] = bool(nums.fillna(0).abs().gt(0).any())

        rows_saved = 0

        # --- 6) iterate each row in the upload and persist to UploadedLedgerData ---
        for _, r in df.iterrows():
            # debtor / customer name
            debtor_raw = r.get(c_name)
            debtor_txt = "" if (debtor_raw is None or _is_nan(debtor_raw)) else str(debtor_raw)
            debtor = debtor_txt.strip()
            if debtor.lower() in {"nan", "none", "null"}:
                debtor = ""

            if not debtor:
                continue  # skip blank debtor rows

            # skip subtotal / "total" lines etc. (still your existing behaviour)
            is_real_debtor = not debtor.lower().startswith(("total", "other", "balance", "summary"))

            # per-row abn/acn override if present, else fallback from form
            row_abn_val = None
            row_acn_val = None

            if c_abn:
                raw_abn_cell = r.get(c_abn)
                if raw_abn_cell is not None and not _is_nan(raw_abn_cell):
                    row_abn_val = _only_digits(raw_abn_cell)

            if c_acn:
                raw_acn_cell = r.get(c_acn)
                if raw_acn_cell is not None and not _is_nan(raw_acn_cell):
                    row_acn_val = _only_digits(raw_acn_cell)

            use_abn = row_abn_val or form_abn
            use_acn = row_acn_val or form_acn

            # helper to normalise each bucket cell to a string number
            def cell(col_name):
                raw_val = r.get(col_name)
                parsed = _to_float(raw_val)
                if parsed is not None:
                    return str(parsed)
                if is_real_debtor and col_has_nonzero.get(col_name, False):
                    return "0"
                return None

            UploadedLedgerData.objects.create(
                transaction_id   = tx_shared,            # SAME tx for all rows in this upload
                abn              = use_abn,
                acn              = use_acn,
                debtor           = debtor,
                aged_receivables = cell(c_aged),
                days_0_30        = cell(c_030),
                days_31_60       = cell(c_3160),
                days_61_90       = cell(c_6190),
                days_90_plus     = cell(c_90p),
            )

            rows_saved += 1

        return JsonResponse({
            "success": True,
            "rows_saved": rows_saved,
            "tx_used": str(tx_shared),
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


# efs_data_financial/core/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import pandas as pd
import uuid  # <-- added

from .models import UploadAPLedgerData  # updated model

# assumes _pick_col, _to_float, _is_nan helpers already exist in this module

@csrf_exempt
@require_POST
def upload_ap_ledger(request):
    """
    Upload Accounts Payable aging (CSV/XLSX).
    Stores rows into UploadAPLedgerData (creditor = supplier/vendor).
    Now supports ABN or ACN or both.
    """
    try:
        # --- transaction id from the page (shared across all rows for this upload) ---
        tx_str = (request.POST.get("transaction_id") or "").strip()
        try:
            tx_shared = uuid.UUID(tx_str) if tx_str else uuid.uuid4()
        except (ValueError, AttributeError):
            tx_shared = uuid.uuid4()

        # company IDs from form
        raw_abn = request.POST.get("abn", "")
        raw_acn = request.POST.get("acn", "")
        form_abn, form_acn = _norm_company_id_pair(raw_abn, raw_acn)

        up = request.FILES.get("file")
        if not up:
            return JsonResponse({"success": False, "message": "No file uploaded"}, status=400)

        # CSV/XLSX load
        df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
        if df is None or df.empty:
            return JsonResponse({"success": False, "message": "Empty file"}, status=400)

        # --- map headers (flexible) ---
        c_abn   = _pick_col(df, "ABN")
        c_acn   = _pick_col(df, "ACN")  # NEW
        c_name  = _pick_col(df, "Supplier/Vendor", "Supplier", "Vendor", "Supplier Name", "Vendor Name")
        c_aged  = _pick_col(df, "Aged Payables", "AgedPayables", "Aged Payables Current", "Current")
        c_030   = _pick_col(df, "0-30 days", "0-30days", "0_30days", "0-30", "0–30 days")
        c_3160  = _pick_col(df, "31-60 days", "31-60days", "31_60days", "31-60", "31–60 days")
        c_6190  = _pick_col(df, "61-90 days", "61-90days", "61_90days", "61-90", "61–90 days")
        c_90p   = _pick_col(df, "90+ days", "90+days", "90plus", "90plusdays", "90")

        missing = [n for n, c in {
            "Supplier/Vendor": c_name,
            "Aged Payables":   c_aged,
            "0-30 days":       c_030,
            "31-60 days":      c_3160,
            "61-90 days":      c_6190,
            "90+ days":        c_90p,
        }.items() if not c]
        if missing:
            return JsonResponse({"success": False, "message": f"Missing columns: {', '.join(missing)}"}, status=400)

        # Only zero-fill columns that contain any non-zero values in the file
        aging_cols = [c_aged, c_030, c_3160, c_6190, c_90p]
        col_has_nonzero = {}
        for col in aging_cols:
            nums = df[col].map(_to_float)
            col_has_nonzero[col] = bool((nums.fillna(0).abs() > 0).any())

        rows = 0
        for _, r in df.iterrows():
            # Supplier/Vendor -> model.creditor
            raw = r.get(c_name)
            name_str = "" if (raw is None or _is_nan(raw)) else str(raw)
            creditor = name_str.strip()
            if creditor.lower() in {"nan", "none", "null"}:
                creditor = ""
            if not creditor:
                continue

            is_real_row = not creditor.lower().startswith(("total", "other"))

            # Pull row-level ABN/ACN if present
            row_abn = None
            if c_abn:
                abn_raw_val = r.get(c_abn)
                if abn_raw_val is not None and not _is_nan(abn_raw_val):
                    row_abn = str(abn_raw_val).strip() or None

            row_acn = None
            if c_acn:
                acn_raw_val = r.get(c_acn)
                if acn_raw_val is not None and not _is_nan(acn_raw_val):
                    row_acn = str(acn_raw_val).strip() or None

            use_abn = row_abn or form_abn or None
            use_acn = row_acn or form_acn or None

            def cell(col):
                v = r.get(col)
                num = _to_float(v)
                if num is not None:
                    return str(num)
                if is_real_row and col_has_nonzero.get(col, False):
                    return "0"
                return None

            kwargs = dict(
                transaction_id = tx_shared,      # shared TX per upload
                creditor       = creditor,
                aged_payables  = cell(c_aged),
                days_0_30      = cell(c_030),
                days_31_60     = cell(c_3160),
                days_61_90     = cell(c_6190),
                days_90_plus   = cell(c_90p),
            )
            if use_abn:
                kwargs["abn"] = use_abn
            if use_acn and "acn" in [f.name for f in UploadAPLedgerData._meta.fields]:
                kwargs["acn"] = use_acn

            UploadAPLedgerData.objects.create(**kwargs)
            rows += 1

        return JsonResponse({"success": True, "rows_saved": rows})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


#--------start upload vehicle data -----------
#--------start upload vehicle data -----------
#--------start upload vehicle data -----------
#--------start upload vehicle data -----------



# --- VEHICLE ASSET SCHEDULE UPLOAD ------------------------------------------




import io
import uuid
import pandas as pd
from datetime import datetime
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse

# core/views.py
from .models import AssetScheduleRow



_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y"]

def _parse_date_flex(s):
    """Return a python date or None from strings/excel serials/pandas Timestamp/NaT."""
    if s is None:
        return None
    try:
        import numpy as np
        if s is pd.NaT or (isinstance(s, float) and pd.isna(s)) or (hasattr(pd, 'isna') and pd.isna(s)):
            return None
        if isinstance(s, pd.Timestamp):
            # strip tz to keep DateField happy
            return s.tz_localize(None) if s.tz is not None else s
    except Exception:
        pass

    if isinstance(s, datetime):
        return s.date()

    # excel serial-ish
    try:
        txt = str(s).strip()
        if txt.isdigit() and len(txt) <= 5:
            dt = pd.to_datetime(float(txt), unit="D", origin="1899-12-30", errors="coerce")
            return None if (dt is pd.NaT) else dt.date()
    except Exception:
        pass

    txt = str(s).strip()
    if not txt:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(txt, fmt).date()
        except Exception:
            continue
    try:
        dt = pd.to_datetime(txt, errors="coerce")
        return None if (dt is pd.NaT) else dt.date()
    except Exception:
        return None

def _date_or_none(v):
    """Absolute safe date normalizer."""
    d = _parse_date_flex(v)
    return d if d else None

def _str(v):
    return "" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v).strip()

def _int_or_none(v):
    try:
        f = float(v); i = int(f)
        return i if 1900 <= i <= 2100 else None
    except Exception:
        try:
            i = int(str(v).strip()[:4])
            return i if 1900 <= i <= 2100 else None
        except Exception:
            return None

def _decimal_or_none(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip().replace(",", "")
        if not s:
            return None
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        return Decimal(s)
    except Exception:
        return None

def _read_table(file_obj):
    """CSV/XLSX → DataFrame. Decode CSV to text before pandas to avoid bytes iterator errors."""
    name = (getattr(file_obj, "name", "") or "").lower()
    if name.endswith(".csv"):
        raw = file_obj.read()
        if isinstance(raw, bytes):
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin1")
        else:
            text = raw
        return pd.read_csv(io.StringIO(text))
    return pd.read_excel(file_obj)

def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower().strip() if ch.isalnum())

def _pick_col(df: pd.DataFrame, *candidates: str) -> str | None:
    if df is None or df.empty or not len(df.columns):
        return None
    cols = list(df.columns)
    norm_map = {_norm(c): c for c in cols}

    expanded = []
    for c in candidates:
        c = c or ""
        expanded += [
            c,
            c.replace(" No", "").replace(" no", "").replace("#", "").strip(),
            c.replace(" Number", "").replace(" number", "").strip(),
        ]
    for cand in expanded:
        key = _norm(cand)
        if key in norm_map:
            return norm_map[key]
    for cand in expanded:
        k = _norm(cand)
        for col in cols:
            if _norm(col).startswith(k) or k in _norm(col):
                return col
    return None


# ... keep all your imports and helper fns exactly as-is ...

@csrf_exempt
@require_POST
def upload_asset_schedule(request):
    # (unchanged preamble)
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"success": False, "message": "Missing file"}, status=400)

    raw_abn = request.POST.get("abn", "")
    raw_acn = request.POST.get("acn", "")
    abn, acn = _norm_company_id_pair(raw_abn, raw_acn)

    if not abn and not acn:
        return JsonResponse({"success": False, "message": "Missing company identifier (ABN or ACN)"}, status=400)

    data_type = _str(request.POST.get("data_type")).lower()
    if data_type not in {"assets_vehicles", "assets_plant", "assets_property"}:
        return JsonResponse({"success": False, "message": "Unsupported data_type"}, status=400)

    tx = _str(request.POST.get("transaction_id")) or None
    try:
        if tx:
            tx = str(uuid.UUID(tx))
    except Exception:
        pass

    provider_name  = _str(request.POST.get("provider_name")) or "Schedule Upload"
    schedule_title = _str(request.POST.get("schedule_title")) or (getattr(f, "name", None))
    amounts_include_tax = _str(request.POST.get("amounts_include_tax")).lower() in {"1", "true", "yes"}
    as_of_date = _date_or_none(request.POST.get("as_of_date"))

    try:
        df = _read_table(f)
    except Exception as e:
        return JsonResponse({"success": False, "message": f"Load error: {e}"}, status=400)
    if df is None or df.empty:
        return JsonResponse({"success": False, "message": "Empty file"}, status=400)

    # ---- fuzzy column mapping (existing) ----
    c_make   = _pick_col(df, "Make")
    c_model  = _pick_col(df, "Model")
    c_type   = _pick_col(df, "Type", "Category", "Asset Type", "Class")
    c_year   = _pick_col(df, "Year", "Year of Manufacture", "Build Year")
    c_serial = _pick_col(df, "Serial Number", "Serial", "Chassis No", "Chassis", "Serial #")
    c_vin    = _pick_col(df, "VIN", "Vehicle Identification Number")
    c_rego   = _pick_col(df, "Registration", "Registration No", "Rego", "Registration #")
    c_desc   = _pick_col(df, "Description", "Notes")
    c_qty    = _pick_col(df, "Quantity", "Qty")
    c_loc    = _pick_col(df, "Location", "Site")
    c_cond   = _pick_col(df, "Condition", "Condition Note")

    c_fmv    = _pick_col(df, "FMV", "Fair Market Value")
    c_fsv    = _pick_col(df, "FSV", "Forced Sale Value")
    c_olv    = _pick_col(df, "OLV", "Orderly Liquidation Value")
    c_vdate  = _pick_col(df, "Valuation Date", "As Of", "As of", "Valued On")

    # ---- NEW fuzzy picks for BV / Lease Outstanding / NBV ----
    # We try precise names first, then common variants/abbreviations.
    c_bv     = _pick_col(
        df,
        "Book Value", "BV", "Book Value (BV)", "Carrying Value", "Carrying Amount"
    )
    c_lease  = _pick_col(
        df,
        "Lease Outstanding", "Lease OS", "Lease O/S", "Lease Balance",
        "Lease Liability", "Outstanding Lease"
    )
    c_nbv    = _pick_col(
        df,
        "Net Book Value", "NBV", "Net Carrying Value", "Net Carrying Amount"
    )

    rows_saved = 0
    for idx, row in df.iterrows():
        make  = _str(row.get(c_make))   if c_make   else ""
        model = _str(row.get(c_model))  if c_model  else ""
        typ   = _str(row.get(c_type))   if c_type   else (
            "Vehicle" if data_type == "assets_vehicles"
            else (data_type.replace("assets_", "").title() or "Asset")
        )
        year  = _int_or_none(row.get(c_year)) if c_year else None
        serial= _str(row.get(c_serial)) if c_serial else ""
        vin   = _str(row.get(c_vin)).upper() if c_vin else ""
        rego  = _str(row.get(c_rego))  if c_rego  else ""
        desc  = _str(row.get(c_desc))  if c_desc  else ""
        qty   = _decimal_or_none(row.get(c_qty)) if c_qty else Decimal("1")
        loc   = _str(row.get(c_loc))   if c_loc   else ""
        cond  = _str(row.get(c_cond))  if c_cond  else ""

        if not any([make, model, vin, serial, desc]):
            continue

        vdate = _date_or_none(row.get(c_vdate)) if c_vdate else as_of_date
        fmv   = _decimal_or_none(row.get(c_fmv))   if c_fmv   else None
        fsv   = _decimal_or_none(row.get(c_fsv))   if c_fsv   else None
        olv   = _decimal_or_none(row.get(c_olv))   if c_olv   else None

        # ---- NEW: parse the three optional amounts ----
        bv_amount       = _decimal_or_none(row.get(c_bv))    if c_bv    else None
        lease_os_amount = _decimal_or_none(row.get(c_lease)) if c_lease else None
        nbv_amount      = _decimal_or_none(row.get(c_nbv))   if c_nbv   else None

        raw_map = {c: _str(row.get(c)) for c in df.columns}

        create_kwargs = dict(
            provider_name=provider_name,
            schedule_title=schedule_title,
            source_as_of_date=_date_or_none(as_of_date),
            original_filename=getattr(f, "name", None),
            currency="AUD",
            tax_label=("GST" if amounts_include_tax else None),
            amounts_include_tax=amounts_include_tax,

            abn=abn or None,
            transaction_id=tx,

            make=make or "Unknown",
            model=model or "Unknown",
            type=typ or "Asset",
            year_of_manufacture=year,
            serial_no=serial or None,
            vin=(vin or None),
            registration_no=rego or None,
            description=desc or None,
            attributes={},  # extend later

            line_number=int(idx) + 1,
            quantity=qty if qty is not None else Decimal("1"),
            location=loc or None,
            condition_note=cond or None,
            row_raw=raw_map,
            extras={"data_type": data_type},

            valuation_as_of_date=_date_or_none(vdate),
            fmv_amount=fmv,
            fsv_amount=fsv,
            olv_amount=olv,
            valuation_notes=None,

            # ---- NEW fields wired in ----
            bv_amount=bv_amount,
            lease_os_amount=lease_os_amount,
            nbv_amount=nbv_amount,
        )

        # set acn if the model has it
        if acn and "acn" in [f.name for f in AssetScheduleRow._meta.fields]:
            create_kwargs["acn"] = acn

        AssetScheduleRow.objects.create(**create_kwargs)
        rows_saved += 1

    return JsonResponse({
        "success": True,
        "message": f"Schedule processed. Rows saved: {rows_saved}",
        "rows_saved": rows_saved,
    })


#--------end  upload vehicle data -----------
#--------end  upload vehicle data -----------
#--------end  upload vehicle data -----------
#--------end  upload vehicle data -----------
#--------end  upload vehicle data -----------





#--------start upload Plant and machinert data -----------
#--------start upload Plant and machinert data -----------
#--------start upload Plant and machinert data -----------
#--------start upload Plant and machinert data -----------
#--------start upload Plant and machinert data -----------

import io
import uuid
import pandas as pd
from datetime import datetime
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction, router

from .models import PPEAsset

# --- fallback if project helper isn't present ---
try:
    _norm_company_id_pair  # type: ignore
except NameError:
    import re
    def _norm_company_id_pair(abn: str, acn: str):
        abn_digits = re.sub(r"\D", "", abn or "")
        acn_digits = re.sub(r"\D", "", acn or "")
        return (abn_digits or None, acn_digits or None)

# ---------- shared helpers (same style as the working vehicles code) ----------

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y"]

def _parse_date_flex(s):
    if s is None:
        return None
    try:
        if s is pd.NaT or pd.isna(s):
            return None
        if isinstance(s, pd.Timestamp):
            return s.tz_localize(None) if getattr(s, "tz", None) is not None else s
    except Exception:
        pass
    if isinstance(s, datetime):
        return s.date()
    # excel serial-ish
    try:
        txt = str(s).strip()
        if txt.isdigit() and len(txt) <= 5:
            dt = pd.to_datetime(float(txt), unit="D", origin="1899-12-30", errors="coerce")
            return None if (dt is pd.NaT) else dt.date()
    except Exception:
        pass
    txt = str(s).strip()
    if not txt:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(txt, fmt).date()
        except Exception:
            continue
    try:
        dt = pd.to_datetime(txt, errors="coerce")
        return None if (dt is pd.NaT) else dt.date()
    except Exception:
        return None

def _date_or_none(v):
    d = _parse_date_flex(v)
    return d if d else None

def _str(v):
    return "" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v).strip()

def _int_or_none(v):
    try:
        f = float(v); i = int(f)
        return i if 1900 <= i <= 2100 else None
    except Exception:
        try:
            i = int(str(v).strip()[:4])
            return i if 1900 <= i <= 2100 else None
        except Exception:
            return None

def _decimal_or_none(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip().replace(",", "")
        if not s:
            return None
        # accounting negative
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        # strip currency symbols while keeping digits/dot/minus
        s = "".join(ch for ch in s if (ch.isdigit() or ch in ".-"))
        return Decimal(s) if s not in {"", "-", "."} else None
    except Exception:
        return None

def _read_table(file_obj):
    """CSV/XLSX → DataFrame."""
    name = (getattr(file_obj, "name", "") or "").lower()
    if name.endswith(".csv"):
        raw = file_obj.read()
        if isinstance(raw, bytes):
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("latin1")
        else:
            text = raw
        return pd.read_csv(io.StringIO(text))
    return pd.read_excel(file_obj)

def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower().strip() if ch.isalnum())

def _pick_col(df: pd.DataFrame, *candidates: str) -> str | None:
    if df is None or df.empty or not len(df.columns):
        return None
    cols = list(df.columns)
    norm_map = {_norm(c): c for c in cols}

    expanded = []
    for c in candidates:
        c = c or ""
        expanded += [
            c,
            c.replace(" No", "").replace(" no", "").replace("#", "").strip(),
            c.replace(" Number", "").replace(" number", "").strip(),
            c.replace(" (ex gst)", "").replace(" ex gst", "").replace("ex gst", "").strip(),
        ]
    for cand in expanded:
        key = _norm(cand)
        if key in norm_map:
            return norm_map[key]
    for cand in expanded:
        k = _norm(cand)
        for col in cols:
            if _norm(col).startswith(k) or k in _norm(col):
                return col
    return None

# ------------------------------ main view -------------------------------------

@csrf_exempt
@require_POST
def upload_ppe_assets(request):
    """
    Accept CSV or XLSX and write one row per asset into PPEAsset.
    multipart/form-data:
      - file (CSV/XLSX) REQUIRED
      - abn / acn       OPTIONAL
      - transaction_id  OPTIONAL
      - originator      OPTIONAL
    """
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"success": False, "error": "No file uploaded"}, status=400)

    raw_abn = request.POST.get("abn", "")
    raw_acn = request.POST.get("acn", "")
    abn, acn = _norm_company_id_pair(raw_abn, raw_acn)

    if not abn and not acn:
        return JsonResponse({"success": False, "error": "Missing company identifier (ABN or ACN)"}, status=400)

    tx = _str(request.POST.get("transaction_id")) or None
    try:
        if tx:
            tx = str(uuid.UUID(tx))
    except Exception:
        pass
    originator = _str(request.POST.get("originator")) or None

    # persist file (used on each row)
    saved_path = default_storage.save(f"uploads/asset_lists/{f.name}", ContentFile(f.read()))
    fobj = default_storage.open(saved_path, "rb")

    # DB alias via router (avoids 'connection doesn't exist')
    db_alias = router.db_for_write(PPEAsset) or "default"
    upload_group = uuid.uuid4()

    try:
        df = _read_table(fobj)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Load error: {e}"}, status=400)
    if df is None or df.empty:
        return JsonResponse({"success": False, "error": "Empty file"}, status=400)

    # ---- fuzzy column picks (aligned to your UI) ----
    c_asset_no = _pick_col(df, "Asset Number", "Asset No", "Asset #", "Asset Num")
    c_asset    = _pick_col(df, "Asset", "Asset Description", "Item", "Model", "Description")
    c_make     = _pick_col(df, "Make")
    c_type     = _pick_col(df, "Type", "Asset Type", "Category", "Class")
    c_serial   = _pick_col(df, "Serial Number", "Serial", "VIN", "Chassis", "Serial #")
    c_rego     = _pick_col(df, "Registration", "Registration No", "Rego", "Rego No", "Registration #")
    c_year     = _pick_col(df, "Year", "Year of Manufacture", "Build Year")

    # valuation columns
    c_fmv = _pick_col(df, "FMV", "Fair Market Value", "Fair Market Value (ex GST)", "FMV ex GST")
    c_olv = _pick_col(df, "OLV", "Orderly Liquidation Value", "Orderly Liquidation Value (ex GST)", "OLV ex GST")

    # the three you care about
    c_bv    = _pick_col(df, "Book Value", "BV", "Book Value (BV)", "Carrying Value", "Carrying Amount")
    c_lease = _pick_col(df, "Lease Outstanding", "Lease OS", "Lease O/S", "Lease Balance", "Lease Liability", "Outstanding Lease")
    c_nbv   = _pick_col(df, "Net Book Value", "NBV", "Net Carrying Value", "Net Carrying Amount")

    rows = []
    for _, r in df.iterrows():
        # treat as blank unless we have at least one identifier/value
        make  = _str(r.get(c_make))   if c_make   else ""
        asset = _str(r.get(c_asset))  if c_asset  else ""
        if not any([make, asset, _str(r.get(c_serial)) if c_serial else "", _str(r.get(c_rego)) if c_rego else ""]):
            continue

        rec = PPEAsset(
            upload_group=upload_group,
            file=saved_path,
            original_filename=getattr(f, "name", None),
            abn=abn or None,
            acn=(acn or None) if ("acn" in [f.name for f in PPEAsset._meta.fields]) else None,
            transaction_id=tx,
            originator=originator,

            asset_number=_str(r.get(c_asset_no)) or None if c_asset_no else None,
            asset=asset or None,
            make=make or None,
            type=_str(r.get(c_type)) or None if c_type else None,
            serial_no=_str(r.get(c_serial)) or None if c_serial else None,
            rego_no=_str(r.get(c_rego)) or None if c_rego else None,
            year_of_manufacture=_int_or_none(r.get(c_year)) if c_year else None,

            fair_market_value_ex_gst=_decimal_or_none(r.get(c_fmv)) if c_fmv else None,
            orderly_liquidation_value_ex_gst=_decimal_or_none(r.get(c_olv)) if c_olv else None,

            # <<< THESE WILL NOW POPULATE >>>
            bv_amount=_decimal_or_none(r.get(c_bv)) if c_bv else None,
            lease_os_amount=_decimal_or_none(r.get(c_lease)) if c_lease else None,
            nbv_amount=_decimal_or_none(r.get(c_nbv)) if c_nbv else None,
        )

        # push through if *anything* meaningful is present
        if any(getattr(rec, f) for f in (
            "asset_number","asset","make","type","serial_no","rego_no",
            "year_of_manufacture","fair_market_value_ex_gst","orderly_liquidation_value_ex_gst",
            "bv_amount","lease_os_amount","nbv_amount"
        )):
            rows.append(rec)

    if not rows:
        return JsonResponse({"success": False, "error": "No usable rows found"}, status=400)

    with transaction.atomic(using=db_alias):
        PPEAsset.objects.using(db_alias).bulk_create(rows, batch_size=1000)

    return JsonResponse({
        "success": True,
        "rows_created": len(rows),
        "upload_group": str(upload_group),
    })

# Alias used elsewhere
upload_plant_machinery_schedule = upload_ppe_assets


#--------end upload Plant and machinert data -----------
#--------end upload Plant and machinert data -----------
#--------end upload Plant and machinert data -----------
#--------end upload Plant and machinert data -----------
#--------end upload Plant and machinert data -----------







# -----------------------------------


        #debtor Creditor reports 


#-----------------------------------




import logging
import uuid

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import DebtorsCreditReport
from .pdf_parsers.debtors_credit_report import (
    load_pdf_lines_from_uploaded_file,
    extract_ids,
    extract_score,
    build_report_json,
    _tidy_digits,
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def upload_debtor_credit_report_pdf(request):
    """
    POST multipart/form-data:
      - file: PDF
      - abn (optional)
      - acn (optional)
      - transaction_id (optional UUID string)
      - debtor_name (optional)
      - debtor_abn (optional)
      - debtor_acn (optional)

    Creates:
      - DebtorsCreditReport
    """
    if "file" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file provided"}, status=400)

    f = request.FILES["file"]
    if not f.name.lower().endswith(".pdf"):
        return JsonResponse({"success": False, "message": "Only PDF files are accepted"}, status=400)

    abn_hint = (request.POST.get("abn") or "").strip()
    acn_hint = (request.POST.get("acn") or "").strip()

    debtor_name = (request.POST.get("debtor_name") or "").strip() or None
    debtor_abn = (request.POST.get("debtor_abn") or "").strip() or None
    debtor_acn = (request.POST.get("debtor_acn") or "").strip() or None

    tx_raw = (request.POST.get("transaction_id") or "").strip()
    try:
        tx_val = uuid.UUID(tx_raw) if tx_raw else uuid.uuid4()
    except Exception:
        tx_val = uuid.uuid4()

    try:
        lines = load_pdf_lines_from_uploaded_file(f)
        if not lines:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Unable to extract text from PDF (check pdftohtml/bs4/PyPDF2 installation).",
                },
                status=500,
            )

        abn_auto, acn_auto = extract_ids(lines)

        # Indexing identifiers (only from hints)
        abn = _tidy_digits(abn_hint)
        acn = _tidy_digits(acn_hint)

        # Debtor identifiers (PDF-derived unless explicitly overridden)
        debtor_abn = debtor_abn or abn_auto
        debtor_acn = debtor_acn or acn_auto

        score_value, score_band = extract_score(lines)
        report_json, credit_enquiries_int = build_report_json(abn, acn, score_value, lines)

        description = f"Debtor Credit Report for ABN# {abn or '—'} / ACN# {acn or '—'}"
        item_code = "debtor_credit_report_pdf"

        rec = DebtorsCreditReport.objects.create(
            transaction_id=tx_val,
            description=description[:255],
            item_code=item_code,
            abn=abn or "",
            acn=acn or "",
            credit_enquiries=int(credit_enquiries_int or 0),
            report=report_json,
            debtor_name=debtor_name,
            debtor_abn=debtor_abn,
            debtor_acn=debtor_acn,
        )

        return JsonResponse(
            {
                "success": True,
                "id": rec.id,
                "transaction_id": str(rec.transaction_id),
                "abn": abn,
                "acn": acn,
                "debtor_name": debtor_name,
                "message": "Debtor credit report parsed and stored.",
            }
        )

    except Exception as e:
        logger.exception("Failed to parse debtor credit report PDF")
        return JsonResponse({"success": False, "message": str(e)}, status=500)




#------ approve or reject debtor code (and all invoices associated with debtor)
#------ approve or reject debtor code (and all invoices associated with debtor)
#------ approve or reject debtor code (and all invoices associated with debtor)
#------ approve or reject debtor code (and all invoices associated with debtor)


import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from .models import DebtorsCreditReport, InvoiceDataUploaded, InvoiceData


@csrf_exempt
@require_POST
def update_debtor_credit_report_state(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")

        abn = (payload.get("abn") or "").strip()
        acn = (payload.get("acn") or "").strip()
        tx  = (payload.get("transaction_id") or "").strip()
        debtor_name = (payload.get("debtor_name") or "").strip()
        state = (payload.get("state") or "").strip().lower()

        if state not in {"approved", "rejected"}:
            return JsonResponse({"success": False, "message": "Invalid state."}, status=400)

        if not debtor_name:
            return JsonResponse({"success": False, "message": "Missing debtor_name."}, status=400)

        if not abn and not acn:
            return JsonResponse({"success": False, "message": "Missing ABN/ACN."}, status=400)

        # Required for correct deal scoping
        if not tx:
            return JsonResponse(
                {"success": False, "message": "Missing transaction_id (required to update invoices)."},
                status=400
            )

        with transaction.atomic():
            # ---- 1) Update DebtorsCreditReport (unchanged logic) ----
            qs = DebtorsCreditReport.objects.all()

            # keep your tx filter
            qs = qs.filter(transaction_id=tx)

            if abn:
                qs = qs.filter(abn=abn)
            if acn:
                qs = qs.filter(acn=acn)

            qs = qs.filter(debtor_name=debtor_name).order_by("-updated_at")
            obj = qs.first()

            if not obj:
                return JsonResponse({"success": False, "message": "Not found."}, status=404)

            obj.state = state
            obj.save(update_fields=["state", "updated_at"])

            # ---- 2) Update InvoiceDataUploaded.approve_reject (existing) ----
            uploaded_qs = InvoiceDataUploaded.objects.filter(
                transaction_id=tx,
                debtor__iexact=debtor_name,
            )
            if abn:
                uploaded_qs = uploaded_qs.filter(abn=abn)
            if acn:
                uploaded_qs = uploaded_qs.filter(acn=acn)

            uploaded_updated = uploaded_qs.update(approve_reject=state)

            # ---- 3) Update InvoiceData.approve_reject (new) ----
            invoice_qs = InvoiceData.objects.filter(
                transaction_id=tx,
                debtor__iexact=debtor_name,
            )
            if abn:
                invoice_qs = invoice_qs.filter(abn=abn)
            if acn:
                invoice_qs = invoice_qs.filter(acn=acn)

            invoice_updated = invoice_qs.update(approve_reject=state)

        return JsonResponse({
            "success": True,
            "state": obj.state,
            "invoices_uploaded_updated": uploaded_updated,
            "invoices_api_updated": invoice_updated,
            "invoices_updated": uploaded_updated + invoice_updated,
        })

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)

#------ ------ ------ ------ ------ ------ 
    
    #   upload invoices  code 

#------ ------ ------ ------ ------ 
    


from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from .services import (
    process_invoices_csv_upload,
    fetch_invoices_combined_for_company,

    # ✅ NEW (AP)
    process_ap_invoices_csv_upload,
    fetch_ap_invoices_combined_for_company,
)



@csrf_exempt
@require_POST
def upload_invoices_csv(request):
    """
    Multipart form:
      file: CSV
      abn/acn/transaction_id optional metadata
    """
    f = request.FILES.get("file")

    form_abn = request.POST.get("abn", "")
    form_acn = request.POST.get("acn", "")
    form_tx = request.POST.get("transaction_id", "")

    try:
        rows_processed, rows_created = process_invoices_csv_upload(
            uploaded_file=f,
            form_abn=form_abn,
            form_acn=form_acn,
            form_tx=form_tx,
        )
    except ValueError as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)
    except Exception:
        return JsonResponse(
            {"success": False, "message": "Upload failed due to an unexpected error."},
            status=500
        )

    return JsonResponse({
        "success": True,
        "rows_processed": rows_processed,
        "rows_created": rows_created
    })


@require_GET
def fetch_invoices_combined(request, company_id):
    data = fetch_invoices_combined_for_company(company_id)
    return JsonResponse(data)





from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .services import process_ap_invoices_csv_upload


@csrf_exempt
@require_POST
def upload_ap_invoices_csv(request):
    """
    Multipart form:
      file: CSV
      abn/acn/transaction_id optional metadata
    """
    f = request.FILES.get("file")

    form_abn = request.POST.get("abn", "")
    form_acn = request.POST.get("acn", "")
    form_tx = request.POST.get("transaction_id", "")

    try:
        rows_processed, rows_created = process_ap_invoices_csv_upload(
            uploaded_file=f,
            form_abn=form_abn,
            form_acn=form_acn,
            form_tx=form_tx,
        )
    except ValueError as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)
    except Exception as e:
        # TEMP: expose real error while debugging
        return JsonResponse(
            {"success": False, "message": f"AP invoice upload failed due to an unexpected error: {str(e)}"},
            status=500
        )

    return JsonResponse({
        "success": True,
        "rows_processed": rows_processed,
        "rows_created": rows_created
    })

# ✅ NEW: AP invoices fetch
@require_GET
def fetch_ap_invoices_combined(request, company_id):
    """
    AP uploaded invoices for invoices Payables sub-tab.
    Returns {"ap_invoices": [...]}
    """
    data = fetch_ap_invoices_combined_for_company(company_id)
    return JsonResponse(data)




#------ ------ ------ ------ ------ ------ 
    
    #   Approve or reject  invoices  code 

#------ ------ ------ ------ ------ 
    

import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from .models import InvoiceDataUploaded, InvoiceData


def _has_field(model_cls, field_name: str) -> bool:
    return any(f.name == field_name for f in model_cls._meta.get_fields())


def _build_invoice_qs(model_cls, payload):
    invoice_id = payload.get("invoice_id")
    invoice_number = (payload.get("invoice_number") or payload.get("inv_number") or "").strip()
    debtor_name = (payload.get("debtor_name") or payload.get("debtor") or "").strip()

    abn = (payload.get("abn") or "").strip()
    acn = (payload.get("acn") or "").strip()
    tx = (payload.get("transaction_id") or "").strip()

    qs = model_cls.objects.all()

    # Prefer ID match if present
    if invoice_id:
        qs = qs.filter(id=invoice_id)
    elif invoice_number:
        qs = qs.filter(inv_number=invoice_number)
    else:
        return model_cls.objects.none()

    # Optional narrowing
    if tx:
        qs = qs.filter(transaction_id=tx)

    if debtor_name:
        qs = qs.filter(debtor__iexact=debtor_name)

    if abn:
        qs = qs.filter(abn=abn)
    elif acn:
        qs = qs.filter(acn=acn)

    return qs


@csrf_exempt
@require_POST
def update_invoice_approve_reject(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    state = (payload.get("approve_reject") or payload.get("state") or "").strip().lower()
    if state not in {"approved", "rejected"}:
        return JsonResponse(
            {"success": False, "error": "approve_reject must be 'approved' or 'rejected'"},
            status=400,
        )

    invoice_id = payload.get("invoice_id")
    invoice_number = (payload.get("invoice_number") or payload.get("inv_number") or "").strip()
    if not invoice_id and not invoice_number:
        return JsonResponse(
            {"success": False, "error": "invoice_id or invoice_number is required"},
            status=400,
        )

    with transaction.atomic():
        # Always update uploaded invoices (this is what already works)
        qs_uploaded = _build_invoice_qs(InvoiceDataUploaded, payload)
        updated_uploaded = qs_uploaded.update(approve_reject=state)

        # Update InvoiceData ONLY if it has approve_reject field
        updated_api = 0
        if _has_field(InvoiceData, "approve_reject"):
            qs_api = _build_invoice_qs(InvoiceData, payload)
            updated_api = qs_api.update(approve_reject=state)

        total_updated = updated_uploaded + updated_api

        # Fallback: relax debtor filter if nothing matched
        debtor_name = (payload.get("debtor_name") or payload.get("debtor") or "").strip()
        if total_updated == 0 and debtor_name:
            relaxed = dict(payload)
            relaxed["debtor_name"] = ""
            qs_uploaded = _build_invoice_qs(InvoiceDataUploaded, relaxed)
            updated_uploaded = qs_uploaded.update(approve_reject=state)

            updated_api = 0
            if _has_field(InvoiceData, "approve_reject"):
                qs_api = _build_invoice_qs(InvoiceData, relaxed)
                updated_api = qs_api.update(approve_reject=state)

            total_updated = updated_uploaded + updated_api

    # ✅ IMPORTANT: return what your frontend likely expects
    return JsonResponse(
        {
            "success": True,          # <-- many UIs check this
            "ok": True,               # <-- keep compatibility
            "approve_reject": state,
            "rows_updated": total_updated,              # <-- many UIs check this
            "rows_updated_uploaded": updated_uploaded,
            "rows_updated_api": updated_api,
        },
        status=200,
    )








#--------  ----------- ----------- -----------

# start TAX  statements file upload logic 


#--------- ---------- ----------- -----------





from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .services import TaxDocumentService


@csrf_exempt
@require_POST
def upload_tax_document(request):
    doc_type = request.POST.get("data_type") or request.POST.get("doc_type")
    uploaded_file = request.FILES.get("file")

    ctx = {
        "transaction_id": (request.POST.get("transaction_id") or "").strip(),
        "originator": (request.POST.get("originator") or "").strip() or None,
        "abn": (request.POST.get("abn") or "").strip() or None,
        "acn": (request.POST.get("acn") or "").strip() or None,
        "company_name": (request.POST.get("company_name") or "").strip() or None,
    }

    if not doc_type:
        return JsonResponse({"ok": False, "success": False, "error": "Missing doc_type/data_type"}, status=400)
    if not uploaded_file:
        return JsonResponse({"ok": False, "success": False, "error": "Missing file upload"}, status=400)

    source_name = getattr(uploaded_file, "name", "upload.pdf")

    try:
        file_bytes = uploaded_file.read()
    except Exception as e:
        return JsonResponse({"ok": False, "success": False, "error": f"Failed to read uploaded file: {e}"}, status=400)

    result = TaxDocumentService.parse_and_insert(
        doc_type=doc_type,
        file_bytes=file_bytes,
        source_file_name=source_name,
        ctx=ctx,
    )

    # mirror ok for your frontend
    result["success"] = bool(result.get("ok"))
    status = 200 if result.get("ok") else int(result.get("status_code") or 400)
    return JsonResponse(result, status=status)











#--------  ----------- ----------- -----------

# Fetch and display tax statements  logic 


#--------- ---------- ----------- -----------



from django.http import JsonResponse
from .services import StatutoryPacketService

def fetch_statutory_obligations(request, entity_id):
    try:
        data = StatutoryPacketService.get_statutory_packet(entity_id=entity_id)
        return JsonResponse({"success": True, **data})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)











#--------  ----------- ----------- -----------

#FInancial Statement notes saving


#--------- ---------- ----------- -----------



# efs_data_financial/core/views.py  (additions)
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import FinancialStatementNotes

log = logging.getLogger(__name__)

def _clean_identifier(s: str) -> str:
    """
    Strip spaces/punctuation and keep only letters+digits.
    Works for ABN or ACN. We just need *a stable company ID string*.
    """
    if not s:
        return ""
    return "".join(ch for ch in s.strip() if ch.isalnum())

import uuid

@csrf_exempt
@require_POST
def save_financial_notes(request):
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "invalid json"}, status=400)

    raw_tx   = (body.get("transaction_id") or "").strip()
    raw_abn  = (body.get("abn") or "").strip()
    raw_acn  = (body.get("acn") or "").strip()
    ftype    = (body.get("financial_data_type") or "").strip() or "General"
    notes    = (body.get("notes") or "").strip()

    # prefer ABN if present, else ACN
    company_id_clean_abn = _clean_identifier(raw_abn)
    company_id_clean_acn = _clean_identifier(raw_acn)

    if not company_id_clean_abn and not company_id_clean_acn:
        return JsonResponse(
            {"success": False, "message": "Missing company identifier (ABN or ACN)"},
            status=400
        )

    if not notes:
        return JsonResponse(
            {"success": False, "message": "Notes is blank"},
            status=400
        )

    # if caller didn't pass tx, generate one
    tx_uuid = raw_tx or str(uuid.uuid4())

    obj = FinancialStatementNotes.objects.create(
        transaction_id=tx_uuid,
        abn=company_id_clean_abn or "",   # keep both instead of jamming ACN into abn
        acn=company_id_clean_acn or "",
        financial_data_type=ftype,
        notes=notes,
    )

    return JsonResponse(
        {"success": True, "id": str(obj.id), "message": "Notes saved"},
        status=200
    )




# efs_data_financial/core/views.py
# --- keep the rest of the file exactly as-is ---
# just make sure these imports are present with this block:

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils.timezone import localtime
from django.db.models import Q  # <-- this was missing
from .models import FinancialData
from .utils_financials import pivot_multi_year
from . import ai_financials
import re

_SENT_END = re.compile(r'[.!?]["\’”)]*$')        # sentence end heuristics
_LIST_MARK = re.compile(r'^\d+\.$')              # "1." "2." list markers
_ALL_CAPS = re.compile(r'^[A-Z0-9&\-/]{3,}$')    # crude ALL CAPS heading

def _clean_wrapped_text(text: str) -> str:
    """
    (unchanged from your version)
    """
    if not text:
        return ""

    s = text.replace("\r\n", "\n").replace("\r", "\n")
    raw = s

    paras = re.split(r"\n\s*\n", s.strip(), flags=re.MULTILINE)
    fixed_paras = []
    for p in paras:
        if not p.strip():
            continue
        lines = [ln.strip() for ln in p.split("\n") if ln.strip()]
        if not lines:
            continue

        buf = []
        for ln in lines:
            if buf and buf[-1].endswith("-"):
                buf[-1] = buf[-1][:-1] + ln
            else:
                buf.append(ln)

        joined = " ".join(buf)
        joined = re.sub(r"\s{2,}", " ", joined)
        fixed_paras.append(joined.strip())

    if fixed_paras:
        longish = sum(1 for p in fixed_paras if len(p.split()) > 3)
        if longish / max(1, len(fixed_paras)) > 0.6:
            return "\n\n".join(fixed_paras).strip()

    tokens = re.findall(r'\S+', raw)
    out_lines = []
    line = []

    def _flush_line():
        if line:
            out_lines.append(" ".join(line).strip())
            line.clear()

    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        if _LIST_MARK.match(tok):
            _flush_line()
            line.append(tok)
            i += 1
            i_continue = i
            while i_continue < n:
                nxt = tokens[i_continue]
                line.append(nxt)
                if _SENT_END.search(nxt):
                    break
                i_continue += 1
            i = i_continue + 1
            _flush_line()
            continue

        if _ALL_CAPS.match(tok):
            _flush_line()
            caps = [tok]
            i += 1
            while i < n and _ALL_CAPS.match(tokens[i]):
                caps.append(tokens[i])
                i += 1
            out_lines.append(" ".join(caps))
            continue

        line.append(tok)
        if _SENT_END.search(tok):
            _flush_line()
        i += 1

    _flush_line()

    merged = []
    buf = []
    for L in out_lines:
        if not L:
            continue
        buf.append(L)
        if _SENT_END.search(L):
            merged.append(" ".join(buf))
            buf = []
    if buf:
        merged.append(" ".join(buf))

    result = "\n\n".join(x.strip() for x in merged if x.strip())
    result = re.sub(r'[ \t]{2,}', ' ', result)
    return result.strip()


def _norm_abn(s: str) -> str:
    """
    you already had a _norm_abn earlier in this file doing "keep only digits".
    reusing that logic here is fine for BOTH ABN (11 digits) and ACN (9 digits).
    """
    if not s:
        return ""
    return "".join(ch for ch in s if ch.isdigit())


def _rows_for_kind_distinct_years(qs, kind, n_years):
    """
    unchanged logic: pick up to n_years distinct years for that statement.
    """
    seen = set()
    out = []
    for row in qs:
        raw = getattr(row, kind) or {}
        if ai_financials.is_enabled():
            try:
                raw = ai_financials.ai_normalize_statement(
                    raw,
                    kind.replace('_', ' ').title()
                )
            except Exception:
                pass

        yr = (
            row.year
            if isinstance(row.year, int) and row.year >= 1900
            else (localtime(row.timestamp).year if row.timestamp else 0)
        )

        if yr not in seen and len(seen) < n_years:
            seen.add(yr)
            out.append((yr, raw))

    out.sort(key=lambda t: t[0], reverse=True)
    return out


from django.db.models import Q

def _digits_only(val: str) -> str:
    """Keep only digits so it works for ABN, ACN, whatever."""
    return "".join(ch for ch in str(val or "") if ch.isdigit())

def _company_match_q(model_cls, company_id: str) -> Q:
    """
    Build a Q() that finds rows for this entity even if we only know ACN or ABN.

    - Always try abn == company_id (if model has abn)
    - Always try acn == company_id (if model has acn)
    - If company_id is 9 digits (ACN), ALSO match abn__endswith=that 9-digit ACN
      because ABN ends with ACN.
    - If company_id is 11 digits (ABN), ALSO match acn == last 9 digits.
    """
    fields = {f.name for f in model_cls._meta.get_fields()}
    q = Q()

    if "abn" in fields:
        q |= Q(abn=company_id)
    if "acn" in fields:
        q |= Q(acn=company_id)

    # 9-digit ACN: allow ABN ending with it
    if len(company_id) == 9 and "abn" in fields:
        q |= Q(abn__endswith=company_id)

    # 11-digit ABN: allow ACN == last9
    if len(company_id) == 11 and "acn" in fields:
        q |= Q(acn=company_id[-9:])

    return q






# more helpers 


# ---------- Month helpers ----------
MONTHS_ORDER = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]
MONTH_ALIASES = {
    "jan":"January","january":"January",
    "feb":"February","february":"February",
    "mar":"March","march":"March",
    "apr":"April","april":"April",
    "may":"May",
    "jun":"June","june":"June",
    "jul":"July","july":"July",
    "aug":"August","august":"August",
    "sep":"September","sept":"September","september":"September",
    "oct":"October","october":"October",
    "nov":"November","november":"November",
    "dec":"December","december":"December",
}

def _norm_key(s: str) -> str:
    return (s or "").replace("\ufeff","").strip()

def _is_month_name(s: str) -> bool:
    return _norm_key(s).lower() in MONTH_ALIASES

def _canonical_month(s: str) -> str:
    return MONTH_ALIASES[_norm_key(s).lower()]

def _detect_month_columns(rows) -> list[str]:
    """Return month columns present (calendar order) or []."""
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return []
    seen = set()
    for r in rows:
        for k in r.keys():
            if _is_month_name(k):
                seen.add(_canonical_month(k))
    if not seen:
        return []
    return [m for m in MONTHS_ORDER if m in seen]

def _remap_payload_months_to_yearish(rows, months, base_year=9100):
    """
    Map month columns -> fake 4-digit ints (9101..9112) so pivot_multi_year treats
    them as 'years'. Returns (new_rows, ordered_fake_years[int], back_map[int->month]).
    """
    if not months:
        return rows, [], {}
    back_map: dict[int, str] = {}
    ordered_fake_years: list[int] = []
    month_to_fake: dict[str, int] = {}
    for i, m in enumerate(months, start=1):
        fake = base_year + i         # e.g. 9101, 9102, ...
        back_map[fake] = m
        ordered_fake_years.append(fake)
        month_to_fake[m] = fake

    new_rows = []
    for r in rows:
        nr = {}
        for k, v in r.items():
            if _is_month_name(k):
                nr[str(month_to_fake[_canonical_month(k)])] = v  # column label must contain the 4-digit number
            else:
                nr[_norm_key(k)] = v
        new_rows.append(nr)
    return new_rows, ordered_fake_years, back_map

def _remap_pivot_back_to_months(pivot_obj, back_map: dict[int,str], ordered_fake_years: list[int]):
    if not back_map:
        return pivot_obj
    # pivot_multi_year -> {"years":[ints], "sections":[{"lines":[{"values":{int:val}}]}]}
    pivot_obj["years"] = [ back_map.get(y, str(y)) for y in ordered_fake_years ]
    for sec in pivot_obj.get("sections", []):
        for line in sec.get("lines", []):
            values = line.get("values", {}) or {}
            to_add = {}
            to_del = []
            for ykey, val in list(values.items()):
                # ykey may already be int; ensure int comparison
                try:
                    yint = int(ykey)
                except Exception:
                    continue
                if yint in back_map:
                    to_add[back_map[yint]] = val
                    to_del.append(ykey)
            for yk in to_del:
                values.pop(yk, None)
            values.update(to_add)
    return pivot_obj
# -----------------------------------




@require_GET
def fetch_financial_sections_pivot(request, abn):
    # how many distinct periods (your existing param)
    try:
        n_years = max(1, int(request.GET.get("years", "2")))
    except Exception:
        n_years = 2

    company_id = _digits_only(abn)
    if not company_id:
        return JsonResponse({
            "abn": "",
            "years": [],
            "profit_loss": {"years": [], "sections": []},
            "balance_sheet": {"years": [], "sections": []},
            "cash_flow": {"years": [], "sections": []},
            "financial_statement_notes": ""
        }, status=200)

    qs = (
        FinancialData.objects
        .filter(_company_match_q(FinancialData, company_id))
        .order_by("-timestamp", "-year")
    )[:200]
    rows = list(qs)
    if not rows:
        return JsonResponse({
            "abn": company_id,
            "years": [],
            "profit_loss": {"years": [], "sections": []},
            "balance_sheet": {"years": [], "sections": []},
            "cash_flow": {"years": [], "sections": []},
            "financial_statement_notes": ""
        }, status=200)

    # pick latest distinct (existing helper you pasted)
    pl_rows = _rows_for_kind_distinct_years(rows, "profit_loss",   n_years)
    bs_rows = _rows_for_kind_distinct_years(rows, "balance_sheet", n_years)
    cf_rows = _rows_for_kind_distinct_years(rows, "cash_flow",     n_years)

    # ---------- P&L (month-aware) ----------
    pl_payload = (pl_rows[0][1] if pl_rows else []) or []
    pl_months = _detect_month_columns(pl_payload)
    if pl_months:
        remapped, fake_years, back_map = _remap_payload_months_to_yearish(pl_payload, pl_months)
        # pivot expects list[(yr_hint, raw)] — yr_hint is irrelevant for matrix rows
        pl = pivot_multi_year([(0, remapped)])
        pl = _remap_pivot_back_to_months(pl, back_map, fake_years)
    else:
        pl = pivot_multi_year(pl_rows)

    # ---------- Balance Sheet (month-aware) ----------
    bs_payload = (bs_rows[0][1] if bs_rows else []) or []
    bs_months = _detect_month_columns(bs_payload)
    if bs_months:
        remapped, fake_years, back_map = _remap_payload_months_to_yearish(bs_payload, bs_months)
        bs = pivot_multi_year([(0, remapped)])
        bs = _remap_pivot_back_to_months(bs, back_map, fake_years)
    else:
        bs = pivot_multi_year(bs_rows)

    # ---------- Cash Flow (month-aware) ----------
    cf_payload = (cf_rows[0][1] if cf_rows else []) or []
    cf_months = _detect_month_columns(cf_payload)
    if cf_months:
        remapped, fake_years, back_map = _remap_payload_months_to_yearish(cf_payload, cf_months)
        cf = pivot_multi_year([(0, remapped)])
        cf = _remap_pivot_back_to_months(cf, back_map, fake_years)
    else:
        cf = pivot_multi_year(cf_rows)

    # notes (same as yours)
    notes = ""
    for r in rows:
        if r.financial_statement_notes:
            notes = r.financial_statement_notes
            break
    notes = _clean_wrapped_text(notes or "")

    # top-level years list (unchanged numeric years from DB/timestamps)
    try:
        distinct_years = sorted({
            (
                r.year
                if isinstance(r.year, int) and r.year >= 1900
                else (localtime(r.timestamp).year if r.timestamp else 0)
            )
            for r in rows
        }, reverse=True)
    except Exception:
        distinct_years = []

    return JsonResponse({
        "abn": company_id,                 # keep key name for FE
        "years": distinct_years,
        "profit_loss": pl,
        "balance_sheet": bs,
        "cash_flow": cf,
        "financial_statement_notes": notes,
    }, status=200)





#------ PPSR model code 
#------ PPSR model code 
#------ PPSR model code 


import io, re, glob, os, shutil, tempfile, subprocess, logging, uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Registration

# Optional deps used by upload fast/slow paths
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# ---------------------------
# Reuse helpers from agents if available (NO overrides)
# ---------------------------

# digits-only
try:
    _digits_only  # defined in agents section
except NameError:
    def _digits_only(s):  # fallback if agents helper not loaded
        return "".join(ch for ch in str(s or "") if ch.isdigit())

# ABN→ACN normalization (prefer agents’ version if present)
try:
    _abn_to_acn  # defined in agents section
except NameError:
    def _abn_to_acn(s: str) -> str:
        d = _digits_only(s)
        return d[-9:] if len(d) >= 9 else d

# Registration normalizer for JSON (prefer agents’ version)
try:
    _ppsr_norm_row  # from agents block
except NameError:
    def _ppsr_norm_row(r: Registration) -> dict:
        st = r.start_time
        et = r.end_time
        if st and not timezone.is_aware(st):
            st = timezone.make_aware(st, timezone.get_current_timezone())
        if et and not timezone.is_aware(et):
            et = timezone.make_aware(et, timezone.get_current_timezone())
        return {
            "id": str(r.id),
            "transaction_id": str(r.transaction_id) if r.transaction_id else None,
            "abn": r.abn,
            "registration_number": r.registration_number,
            "registration_kind": r.registration_kind,
            "start_time": st.isoformat() if st else None,
            "end_time": et.isoformat() if et else None,
            "change_number": r.change_number,
            "change_time": r.change_time.isoformat() if r.change_time else None,
            "collateral_class_type": r.collateral_class_type,
            "collateral_type": r.collateral_type,
            "collateral_class_description": r.collateral_class_description,
            "are_proceeds_claimed": bool(r.are_proceeds_claimed),
            "is_security_interest_registration_kind": bool(r.is_security_interest_registration_kind),
            "are_assets_subject_to_control": bool(r.are_assets_subject_to_control),
            "is_inventory": bool(r.is_inventory),
            "is_pmsi": bool(r.is_pmsi),
            "is_subordinate": bool(r.is_subordinate),
            "grantor_organisation_identifier": r.grantor_organisation_identifier,
            "grantor_organisation_identifier_type": r.grantor_organisation_identifier_type,
            "grantor_organisation_name": r.grantor_organisation_name,
            "security_party_groups": r.security_party_groups,
            "grantors": r.grantors,
            "address_for_service": r.address_for_service,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }







# ---------------------------
# PPSR UPLOAD (XML fast-path + PDF fallback)
# This is kept here but avoids re-defining any agents helpers.
# ---------------------------

# Accept dd/mm/yyyy and dd/mm/yyyy HH:MM (12h or 24h)
DATE_FMT = "%d/%m/%Y"
DATETIME_FMTS = ["%d/%m/%Y %I:%M %p", "%d/%m/%Y %H:%M", "%d/%m/%Y"]

# Optional: honor settings.PDFTOHTML_BIN if provided
try:
    from django.conf import settings
    PDFTOHTML_BIN = getattr(settings, "PDFTOHTML_BIN", None)
except Exception:
    PDFTOHTML_BIN = None

def _find_pdftohtml_bin() -> str:
    if PDFTOHTML_BIN and os.path.exists(PDFTOHTML_BIN):
        return PDFTOHTML_BIN
    cand = shutil.which("pdftohtml")
    if cand:
        return cand
    for p in (
        "/usr/bin/pdftohtml",
        "/usr/local/bin/pdftohtml",
        "/opt/homebrew/bin/pdftohtml",
        "/usr/local/opt/poppler/bin/pdftohtml",
    ):
        if os.path.exists(p):
            return p
    raise RuntimeError("pdftohtml not found. Install poppler-utils or set PDFTOHTML_BIN.")

# --- Tiny XML helpers (local to upload path only) ---
NS = {"n": "http://schemas.ppsr.gov.au/notifications"}

def _first(elem, path): return elem.find(path, NS) if elem is not None else None
def _all(elem, path):   return elem.findall(path, NS) if elem is not None else []
def _text(el):          return (el.text or "").strip() if el is not None else ""
def _bool_xml(el):
    if el is None or el.text is None: return None
    t = el.text.strip().lower()
    if t in ("true","t","1","yes","y"): return True
    if t in ("false","f","0","no","n"): return False
    return None
def _dt_xml(el):
    if el is None: return None
    txt = (el.text or "").strip()
    if not txt: return None
    return parse_datetime(txt) or (datetime.fromisoformat(txt) if "T" in txt else None)
def _date_from_dt_xml(el):
    dtt = _dt_xml(el)
    return dtt.date() if dtt else None

def _extract(pattern: str, text: str, flags=re.IGNORECASE) -> Optional[str]:
    m = re.search(pattern, text, flags)
    return (m.group(1) or "").strip() if m else None

def _to_bool(s: Optional[str]) -> Optional[bool]:
    if s is None: return None
    v = s.strip().lower()
    if v in {"yes","y","true"}: return True
    if v in {"no","n","false"}: return False
    return None

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s: return None
    try:
        return datetime.strptime(s.strip(), DATE_FMT).date()
    except ValueError:
        return None

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s: return None
    cleaned = re.sub(r"\s*\(?[A-Z]{2,}\)?$", "", s.strip())
    for fmt in DATETIME_FMTS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            pass
    d = _extract(r"(\d{2}/\d{2}/\d{4})", cleaned)
    if not d: return None
    try:
        base = datetime.strptime(d, DATE_FMT)
        t = _extract(r"(\d{2}:\d{2}(?:\s*[AP]M)?)", cleaned)
        if t:
            for f in ("%H:%M", "%I:%M %p"):
                try:
                    tt = datetime.strptime(t.upper(), f)
                    return base.replace(hour=tt.hour, minute=tt.minute)
                except ValueError:
                    pass
        return base
    except ValueError:
        return None

def _clean(s: Optional[str]) -> Optional[str]:
    if not s: return s
    # strip bidi/zero-width
    return re.sub(r"[\u200e\u200f\u202a-\u202e\u200b\u2060\uFEFF]", "", s).strip()

def _clamp(s: Optional[str], n: int) -> Optional[str]:
    s = _clean(s)
    return s[:n] if s and len(s) > n else s

def _pdf_bytes_to_xml_text(pdf_bytes: bytes) -> str:
    pdftohtml = _find_pdftohtml_bin()
    with tempfile.TemporaryDirectory() as tmpd:
        pdf_path = os.path.join(tmpd, "upload.pdf")
        with open(pdf_path, "wb") as fh:
            fh.write(pdf_bytes)
        out_base = os.path.join(tmpd, "ppsr")
        proc = subprocess.run(
            [pdftohtml, "-c", "-hidden", "-xml", pdf_path, out_base],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="ignore").strip()
            logger.error("pdftohtml failed: %s", err)
            raise RuntimeError(f"pdftohtml failed: {err or 'unknown error'}")

        xml_candidates = glob.glob(os.path.join(tmpd, "*.xml"))
        if not xml_candidates:
            xml_path = out_base + ".xml"
            if not os.path.exists(xml_path):
                raise RuntimeError("No XML file produced by pdftohtml.")
            xml_candidates = [xml_path]

        lines: List[str] = []
        for xml_path in sorted(xml_candidates):
            with open(xml_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "lxml-xml")
            for page in soup.find_all("page"):
                for t in page.find_all("text"):
                    lines.append(t.get_text())
                lines.append("\n")
        return "\n".join(lines).strip()

def _drop_before_second_occurrence(text: str, needle: str) -> str:
    matches = list(re.finditer(re.escape(needle), text, flags=re.I))
    return text[matches[1].start():] if len(matches) >= 2 else text

def parse_registration_block(block_ns: str, search_date, key_abn_or_acn: str) -> Registration:
    block_ns = _clean(block_ns) or ""
    def g(p, text=None):
        text = text if text is not None else block_ns
        m = re.search(p, text, flags=re.I | re.S)
        return (m.group(1) or "").strip() if m else None

    reg_no     = g(r"PPSRRegistrationnumber:([0-9A-Za-z\-]+?)(?=Changenumber:)")
    change_no  = g(r"Changenumber:([0-9A-Za-z\-]+)")
    reg_kind   = g(r"Registrationkind:([A-Za-z ]+?)((?=Givingofnoticeidentifier:)|(?=Registrationstarttime:)|$)")
    giving_id  = g(r"Givingofnoticeidentifier:([0-9A-Za-z\-]+)")

    start_raw  = g(r"Registrationstarttime:([0-9/:\(\)A-Za-z]+?)(?=Registrationendtime:)")
    end_raw    = g(r"Registrationendtime:([0-9/:\(\)A-Za-z]+?)(?=Registrationlastchanged:)")
    change_raw = g(r"Registrationlastchanged:([0-9/:\(\)A-Za-z]+)")

    start_ts  = _parse_dt(start_raw)
    end_ts    = None if (end_raw and re.search(r"nostatedendtime|noend|n/?a", end_raw, re.I)) else _parse_dt(end_raw)
    change_ts = _parse_dt(change_raw)

    grantor_id  = g(r"GrantorDetails.*?Organisationidentifier:([0-9A-Za-z ]+?)(?=Organisationidentifiertype:)")
    grantor_typ = g(r"Organisationidentifiertype:([A-Za-z]+?)(?=Organisationname:)")
    grantor_nm  = g(r"Organisationname:([A-Z0-9\.\&\-\(\) ]+?)(?:\(Verified\)|CollateralDetails|$)")

    coll_type  = g(r"CollateralDetails.*?Collateraltype:([A-Za-z ]+?)(?=Collateralclass:)")
    coll_class = g(r"Collateralclass:([A-Za-z\- ]+?)(?=Description:)")
    coll_desc  = g(r"Description:(.+?)(?=Proceeds:|Inventory:|SubjecttoControl:|PurchaseMoneySecurityInterest:|PMSI:|$)")

    proceeds_y = g(r"Proceeds:(Yes|No)")
    proceeds_d = g(r"Proceeds:Yes\-([A-Za-z ]+?)(?=Inventory:|SubjecttoControl:|PurchaseMoneySecurityInterest:|PMSI:|$)")
    inventory  = g(r"Inventory:(Yes|No)")
    subj_ctrl  = g(r"SubjecttoControl:(Yes|No)")
    pmsi       = g(r"(?:PurchaseMoneySecurityInterest|PMSI):(Yes|No)")

    # basic address scrape (kept minimal)
    addr_sec = g(r"AddressforService(.*?)(?=PPSRRegistrationDetails|$)")
    address_for_service = None
    if addr_sec:
        parts = [p for p in (x.strip() for x in re.split(r"(?:,|;)", addr_sec)) if p]
        address_for_service = {"lines": parts} if parts else None

    reg_no    = _clamp(reg_no,   20)
    change_no = _clamp(change_no, 20)

    return Registration(
        abn=_clean(key_abn_or_acn) or None,  # already normalized to 9-digit ACN upstream
        search_date=search_date,
        registration_number=reg_no,
        start_time=start_ts,
        end_time=end_ts,
        change_number=change_no,
        change_time=change_ts,
        registration_kind=_clean(reg_kind),
        is_migrated=None,
        is_transitional=None,
        grantor_organisation_identifier=_clean(grantor_id),
        grantor_organisation_identifier_type=_clean(grantor_typ),
        grantor_organisation_name=_clean(grantor_nm),
        collateral_class_type=_clean(coll_class),
        collateral_type=_clean(coll_type),
        collateral_class_description=_clean(coll_desc),
        are_proceeds_claimed=_to_bool(proceeds_y),
        proceeds_claimed_description=_clean(proceeds_d),
        is_security_interest_registration_kind=None,
        are_assets_subject_to_control=_to_bool(subj_ctrl),
        is_inventory=_to_bool(inventory),
        is_pmsi=_to_bool(pmsi),
        is_subordinate=None,
        giving_of_notice_identifier=_clean(giving_id),
        security_party_groups=None,
        grantors=None,
        address_for_service=address_for_service,
    )


@csrf_exempt
def upload_ppsr_data_view(request):
    """
    POST (multipart): file=..., abn=..., transaction_id=...
    - XML fast-path (preferred)
    - PDF fallback (pdftohtml → XML; else PyPDF2)
    Stores rows under 9-digit ACN so read-side (UI + agents) can find them.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "POST required"}, status=405)

    f       = request.FILES.get("file")
    abn_in  = (request.POST.get("abn") or "").strip()
    tx_raw  = (request.POST.get("transaction_id") or "").strip()

    if not f or not abn_in:
        return JsonResponse({"success": False, "message": "Missing file or ABN."}, status=400)

    try:
        tx_uuid = uuid.UUID(str(tx_raw).strip()) if tx_raw else None
    except Exception:
        logger.warning("transaction_id not a valid UUID: %r", tx_raw)
        tx_uuid = None

    def _raw_bytes(uploaded) -> bytes:
        b = uploaded.read()
        if not b:
            raise ValueError("Empty file.")
        return b

    blob = _raw_bytes(f)
    acn_key_from_abn = _abn_to_acn(abn_in)

    # ---------- XML FAST-PATH ----------
    is_xml = (getattr(f, "content_type", "") in ("text/xml", "application/xml")) or f.name.lower().endswith(".xml")
    if is_xml:
        try:
            root = ET.fromstring(blob)
        except ET.ParseError as e:
            return JsonResponse({"success": False, "message": f"Invalid XML: {e}"}, status=400)

        search_date = _date_from_dt_xml(_first(root, "n:SearchExecutedDateTime"))
        results = _all(root, "n:SearchByGrantorSearchResults/n:ResultDetails/n:ResultDetail")
        if not results:
            return JsonResponse({"success": False, "message": "No ResultDetail blocks found."}, status=400)

        created_ids = []
        for rd in results:
            cr = _first(rd, "n:CollateralRegistration")
            if cr is None:
                continue

            reg = Registration()
            if tx_uuid:
                reg.transaction_id = tx_uuid
            if search_date:
                reg.search_date = search_date

            # Registration details
            rdets = _first(cr, "n:RegistrationDetails")
            if rdets is not None:
                reg.registration_number = _text(_first(rdets, "n:RegistrationNumber")) or None
                reg.registration_kind   = _text(_first(rdets, "n:RegistrationKind")) or None
                reg.change_number       = _text(_first(rdets, "n:ChangeNumber")) or None
                reg.giving_of_notice_identifier = _text(_first(rdets, "n:GivingOfNoticeIdentifier")) or None
                reg.start_time          = _dt_xml(_first(rdets, "n:RegistrationStartTime"))
                reg.end_time            = _dt_xml(_first(rdets, "n:RegistrationEndTime"))
                reg.change_time         = _dt_xml(_first(rdets, "n:RegistrationChangeTime"))
                reg.is_migrated         = _bool_xml(_first(rdets, "n:IsMigrated"))
                reg.is_subordinate      = _bool_xml(_first(rdets, "n:IsSubordinate"))
                reg.is_transitional     = _bool_xml(_first(rdets, "n:IsTransitional"))

            # Collateral
            cd = _first(cr, "n:CollateralDetails")
            if cd is not None:
                reg.collateral_class_type         = _text(_first(cd, "n:CollateralClassType")) or None
                reg.collateral_class_description  = _text(_first(cd, "n:CollateralDescription")) or None
                reg.collateral_type               = _text(_first(cd, "n:CollateralType")) or None
                reg.are_assets_subject_to_control = _bool_xml(_first(cd, "n:AreAssetsSubjectToControl"))
                reg.are_proceeds_claimed          = _bool_xml(_first(cd, "n:AreProceedsClaimed"))
                reg.proceeds_claimed_description  = _text(_first(cd, "n:ProceedsClaimedDescription")) or None
                reg.is_inventory                  = _bool_xml(_first(cd, "n:IsInventory"))
                reg.is_pmsi                       = _bool_xml(_first(cd, "n:IsPMSI"))

            # Grantors JSON + surface first org to infer ACN row key
            grantors_el = _first(cr, "n:Grantors")
            primary_org_num = None
            if grantors_el is not None:
                gnodes = _all(grantors_el, "n:GrantorWithVerificationStatus")
                if gnodes:
                    org = _first(gnodes[0], "n:Organisation")
                    if org is not None:
                        primary_org_num = _text(_first(org, "n:OrganisationNumber")) or None

            # Row key: ACN (from XML if present) else last 9 of uploaded ABN
            reg.abn = _abn_to_acn(primary_org_num or abn_in)

            # Optional blobs (kept minimal)
            # If you already have JSON collectors elsewhere, feel free to plug them in here.

            if any([reg.registration_number, reg.collateral_type, reg.grantor_organisation_name]):
                reg.save()
                created_ids.append(str(reg.id))

        logger.info("PPSR XML upload stored %d registrations (tx=%s, key=%s)", len(created_ids), tx_uuid, reg.abn if created_ids else acn_key_from_abn)
        return JsonResponse({"success": True, "message": f"{len(created_ids)} PPSR registration(s) processed.", "registration_ids": created_ids})

    # ---------- PDF → text fallback ----------
    try:
        try:
            all_text = _pdf_bytes_to_xml_text(blob)
        except Exception as e:
            logger.warning("pdftohtml XML extraction failed (%s). Falling back to PyPDF2 text.", e)
            reader = PdfReader(io.BytesIO(blob))
            all_text = "\n".join((page.extract_text() or "") for page in reader.pages)

        if not all_text.strip():
            return JsonResponse({"success": False, "message": "No text found in PDF file."}, status=400)

        search_date_str = _extract(
            r"This\s+search\s+reflects\s+the\s+data\s+contained\s+in\s+the\s+PPSR\s+at\s+(\d{2}/\d{2}/\d{4})",
            all_text,
        )
        search_date = _parse_date(search_date_str)

        filtered_text = _drop_before_second_occurrence(all_text, "PPSR Registration Details")
        if not filtered_text.strip():
            return JsonResponse({"success": False, "message": "No PPSR registration details found."}, status=400)

        filtered_ns = re.sub(r"\s+", "", filtered_text)
        parts = re.split(r"(PPSRRegistrationDetails)", filtered_ns, flags=re.I)
        if len(parts) < 3:
            return JsonResponse({"success": False, "message": "No PPSR registration blocks found in PDF."}, status=400)

        row_key = _abn_to_acn(abn_in)

        created_ids = []
        for i in range(1, len(parts), 2):
            block_ns = (parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")).strip()
            try:
                reg = parse_registration_block(block_ns, search_date, row_key)
                if tx_uuid:
                    reg.transaction_id = tx_uuid
                if any([reg.registration_number, reg.collateral_type, reg.grantor_organisation_name]):
                    reg.save()
                    created_ids.append(str(reg.id))
            except Exception as ex:
                logger.warning("Failed to parse a registration block: %s", ex)

        logger.info("PPSR PDF upload stored %d registrations (tx=%s, key=%s)", len(created_ids), tx_uuid, row_key)
        return JsonResponse({"success": True, "message": f"{len(created_ids)} PPSR registration(s) processed.", "registration_ids": created_ids})

    except Exception as e:
        logger.exception("PPSR processing failed")
        return JsonResponse({"success": False, "message": f"PPSR processing failed: {e}"}, status=500)









#------ endpoint for RAG service to enable RAG generation.html page to display list of data models from efs_data_financials service 
#------ endpoint for RAG service to enable RAG generation.html page to display list of data models from efs_data_financials service 
#------ endpoint for RAG service to enable RAG generation.html page to display list of data models from efs_data_financials service 
#------ endpoint for RAG service to enable RAG generation.html page to display list of data models from efs_data_financials service 

import inspect
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import models as django_models

from . import models as core_models  # this is efs_data_financials/core/models.py


def _get_model_classes_from_core():
    """
    Introspect core.models and return a dict:
        { "ModelName": <ModelClass>, ... }

    Ignores Django internals, Meta classes, and abstract models.
    """
    model_map = {}
    for name, obj in inspect.getmembers(core_models):
        if (
            inspect.isclass(obj)
            and issubclass(obj, django_models.Model)
            and obj is not django_models.Model
        ):
            meta = getattr(obj, "_meta", None)
            if meta is not None and getattr(meta, "abstract", False):
                # skip abstract base models
                continue
            model_map[name] = obj
    return model_map


def _get_model_names_from_core():
    """
    Returns a simple list of model names, used by /api/model-list/
    (backwards-compatible).
    """
    return list(_get_model_classes_from_core().keys())


def _get_model_metadata_from_core():
    """
    Returns a list of dicts, one per concrete model:
      [
        { "name": "FinancialData", "fields": ["id", "timestamp", "abn", ...] },
        ...
      ]

    We only include concrete, non-auto-created fields (i.e. real DB columns).
    """
    metadata = []
    model_map = _get_model_classes_from_core()

    for name, Model in model_map.items():
        field_names = []
        for f in Model._meta.get_fields():
            # Skip reverse/auto-created relations; keep concrete fields
            if f.auto_created:
                continue
            # Drop reverse FK/M2M directions (like financialdata_set, etc.)
            if f.many_to_many or f.one_to_many:
                continue

            field_names.append(f.name)

        metadata.append({
            "name": name,
            "fields": field_names,
        })

    return metadata


@csrf_exempt
def model_list_api(request):
    """
    GET /api/model-list/
    Returns (legacy, name-only):
        { "models": ["FinancialData", "LedgerData", ...] }
    """
    if request.method != "GET":
        return JsonResponse({"message": "GET only"}, status=405)

    return JsonResponse({"models": _get_model_names_from_core()})


@csrf_exempt
def model_metadata_api(request):
    """
    GET /api/model-metadata/
    Returns (new, richer):
        {
          "models": [
            { "name": "FinancialData",
              "fields": ["id","timestamp","abn","acn","company_name","year",
                         "financials","profit_loss","balance_sheet","cash_flow",
                         "financial_statement_notes","subsidiaries","raw"]
            },
            ...
          ]
        }
    """
    if request.method != "GET":
        return JsonResponse({"message": "GET only"}, status=405)

    return JsonResponse({"models": _get_model_metadata_from_core()})







#-------automateed financial statement analysis --------------



#includes financials, assets, AR Ledger, AP ledger etc tabs


#-------automateed financial statement analysis --------------




# agent entrypoint: POST /sales/run_financial_analysis/
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings

from pathlib import Path
import importlib.util
import json

# Normalized names we accept from the UI  ->  filename (without .py)
ALIAS_TO_FILENAME = {
    "ar_ledger":               "ar_ledger",
    "ap_ledger":               "ap_ledger",
    "assets":                  "assets",
    "financials":              "financial_statements",   # legacy alias
    "financial_statements":    "financial_statements",
    "liabilities":             "liabilities",
    "ppsr":                    "ppsr",
    "statutory_obligations":   "statutory_obligations",
    "ar_ap_invoices":          "ar_ap_invoices",

}

# Where to look for agent files (searched in order). Keep it flexible.
REL_AGENT_DIRS = [
    Path("efs_data_financial/core/agent_code"),
    Path("efs_data_financial/agent_code"),
    Path("efs_data/agent_code"),
    Path("core/agent_code"),
    Path("agent_code"),
]

def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    # 1) Django BASE_DIR if set
    try:
        roots.append(Path(settings.BASE_DIR).resolve())
    except Exception:
        pass
    # 2) Nearby filesystem (repo/app parents)
    here = Path(__file__).resolve()
    for p in [here.parents[1], here.parents[2], here.parents[3]]:
        if p and p.exists():
            roots.append(p)
    # 3) Optional env var override
    env_root = Path(str(getattr(settings, "EFS_AGENT_ROOT", ""))) if hasattr(settings, "EFS_AGENT_ROOT") else None
    if env_root and env_root.exists():
        roots.append(env_root.resolve())
    # 4) (Optional) your known absolute project root, only if present
    mac_root = Path("/Users/patrickcrivelligmail.com/Desktop/efs4_docker")
    if mac_root.exists():
        roots.append(mac_root.resolve())

    # De-dup while preserving order
    seen = set()
    uniq: list[Path] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq

def _find_agent_file(mod_basename: str) -> Path | None:
    """Return a Path to <mod_basename>.py if found under known dirs, else None."""
    for root in _candidate_roots():
        for rel in REL_AGENT_DIRS:
            candidate = (root / rel / f"{mod_basename}.py")
            if candidate.exists():
                return candidate
    return None

def _load_module_from_file(mod_basename: str):
    """Dynamically load a module object from a file path."""
    file_path = _find_agent_file(mod_basename)
    if not file_path:
        tried = [str(r / d) for r in _candidate_roots() for d in REL_AGENT_DIRS]
        raise FileNotFoundError(
            f"Script '{mod_basename}.py' not found. Searched: " + " | ".join(tried)
        )
    spec = importlib.util.spec_from_file_location(f"agent_{mod_basename}", str(file_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module

@csrf_exempt
def run_financial_analysis(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    abn = data.get("abn")
    acn = data.get("acn")
    transaction_id = data.get("transaction_id")

    # e.g. "Financial Statements" -> "financial_statements"
    analysis_type = (data.get("analysis_type") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not analysis_type:
        return JsonResponse({"success": False, "message": "Missing analysis_type"}, status=400)

    mod_basename = ALIAS_TO_FILENAME.get(analysis_type)
    if not mod_basename:
        return JsonResponse({"success": False, "message": f"Unknown analysis type: {analysis_type}"}, status=400)

    try:
        module = _load_module_from_file(mod_basename)
        if not hasattr(module, "run_analysis"):
            return JsonResponse({"success": False, "message": f"'run_analysis' not found in {mod_basename}.py"}, status=500)

        summary, table_html = module.run_analysis(abn=abn, acn=acn, transaction_id=transaction_id)
        return JsonResponse({"success": True, "summary": summary, "table_html": table_html})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)




from decimal import Decimal
from django.db.models import Sum, Q
from django.db.models.functions import Lower

def _money(val):
    """Format Decimal/None as currency string."""
    if val is None:
        val = Decimal("0")
    return f"${val:,.0f}"  # no cents; change to :,.2f if you want cents

def build_invoice_totals_by_debtor(tx_str: str):
    """
    Returns:
      {
        "costco": {"approved": Decimal(...), "rejected": Decimal(...)},
        "coles":  {"approved": Decimal(...), "rejected": Decimal(...)},
        ...
      }
    Pulls:
      - InvoiceData: all rows for transaction_id=tx_str
      - InvoiceDataUploaded: only rows where invoice_state='open' for transaction_id=tx_str
    Groups by debtor + approve_reject.
    """
    totals = {}

    def _add(debtor, status, amt):
        if not debtor:
            return
        key = debtor.strip().lower()
        status = (status or "").strip().lower()
        if status not in ("approved", "rejected"):
            return
        bucket = totals.setdefault(key, {"approved": Decimal("0"), "rejected": Decimal("0")})
        bucket[status] += (amt or Decimal("0"))

    # --- InvoiceData (all invoices for tx) ---
    rows = (
        InvoiceData.objects
        .filter(transaction_id=tx_str)
        .values("debtor", "approve_reject")
        .annotate(total=Sum("amount_due"))
    )
    for r in rows:
        _add(r["debtor"], r["approve_reject"], r["total"])

    # --- InvoiceDataUploaded (only open invoices for tx) ---
    rows2 = (
        InvoiceDataUploaded.objects
        .filter(transaction_id=tx_str, invoice_state__iexact="open")
        .values("debtor", "approve_reject")
        .annotate(total=Sum("amount_due"))
    )
    for r in rows2:
        _add(r["debtor"], r["approve_reject"], r["total"])

    return totals

# efs_data_financial/views.py

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import DebtorsCreditReport, InvoiceData, InvoiceDataUploaded
from .utils_financials import summarize_debtor_credit_report

@require_GET
def debtor_credit_reports_by_transaction(request):
    tx = (request.GET.get("transaction_id") or "").strip()
    if not tx:
        return JsonResponse({"success": False, "message": "transaction_id is required"}, status=400)

    qs = DebtorsCreditReport.objects.filter(transaction_id=tx).order_by("-created_at")

    # Build invoice totals lookup once for this transaction
    invoice_totals = build_invoice_totals_by_debtor(tx_str=tx)

    items = []
    for inst in qs:
        base_summary = summarize_debtor_credit_report(inst)

        debtor_key = (inst.debtor_name or "").strip().lower()
        totals = invoice_totals.get(debtor_key, {"approved": 0, "rejected": 0})

        # Append requested text
        approved_txt = _money(totals.get("approved"))
        rejected_txt = _money(totals.get("rejected"))

        extended_summary = (
            f"{base_summary}"
            f" | Approved invoices = {approved_txt}"
            f" | Rejected Invoices = {rejected_txt}"
        )

        items.append({
            "id": inst.id,
            "transaction_id": str(inst.transaction_id),
            "debtor_name": inst.debtor_name,
            "debtor_abn": inst.debtor_abn,
            "debtor_acn": inst.debtor_acn,
            "state": inst.state,
            "debtor_start_date": inst.debtor_start_date.isoformat() if inst.debtor_start_date else None,
            "summary": extended_summary,
        })

    return JsonResponse({
        "success": True,
        "count": len(items),
        "items": items,
    })



# efs_data_financial/core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponseBadRequest
from django.db.models import Q
import uuid

from .models import (
    # Assets
    AssetScheduleRow, PPEAsset,
    # NAV
    NetAssetValueSnapshot, NAVAssetLine, NAVPlantandequipmentLine, NAVARLine, NAVLiabilityLine,
    # Invoices / Ledgers / Notes / PPSR
    InvoiceData, tf_InvoiceData, scf_InvoiceData,
    LedgerData, UploadedLedgerData, UploadAPLedgerData,
    FinancialStatementNotes, Registration,
    # 👇 we will delete this by primary key (id), not transaction_id
    FinancialData,
)

def _parse_uuid(tx):
    try:
        return uuid.UUID(str(tx).strip())
    except Exception:
        return None

def _txn_q(tx):
    """Char/UUID tolerant filter for models that have `transaction_id`."""
    tx_str = str(tx).strip()
    q = Q(transaction_id=tx_str)
    u = _parse_uuid(tx_str)
    if u:
        q |= Q(transaction_id=u) | Q(transaction_id=str(u))
    return q

@csrf_exempt
def purge_by_tx(request, tx):
    if request.method not in ("DELETE", "POST"):
        return HttpResponseNotAllowed(["DELETE", "POST"])

    tx_str = str(tx).strip()
    if not tx_str or tx_str.lower() in ("null", "none"):
        return HttpResponseBadRequest("invalid or empty transaction id")

    counts = {}

    # 1) Purge all tx-keyed tables in this service
    for Model, label in [
        (AssetScheduleRow,       "AssetScheduleRow"),
        (PPEAsset,               "PPEAsset"),
        (InvoiceData,            "InvoiceData"),
        (tf_InvoiceData,         "tf_InvoiceData"),
        (scf_InvoiceData,        "scf_InvoiceData"),
        (LedgerData,             "LedgerData"),
        (UploadedLedgerData,     "UploadedLedgerData"),
        (UploadAPLedgerData,     "UploadAPLedgerData"),
        (FinancialStatementNotes,"FinancialStatementNotes"),
        (Registration,           "Registration"),
    ]:
        try:
            deleted, _ = Model.objects.filter(_txn_q(tx_str)).delete()
        except Exception:
            # fallback to plain string match if the field type is only CharField
            deleted, _ = Model.objects.filter(transaction_id=tx_str).delete()
        counts[label] = deleted

    # 2) Special case: FinancialData does NOT have transaction_id.
    #    Your transaction id is the PRIMARY KEY 'id' (UUID).
    fd_deleted = 0
    u = _parse_uuid(tx_str)
    if u:
        fd_deleted, _ = FinancialData.objects.filter(id=u).delete()
    # if tx_str isn't a valid UUID, nothing is deleted (by design)
    counts["FinancialData"] = fd_deleted

    return JsonResponse({"status": "success", "tx": tx_str, "counts": counts}, status=200)


@csrf_exempt
def nav_purge_by_tx(request, tx):
    if request.method not in ("DELETE", "POST"):
        return HttpResponseNotAllowed(["DELETE", "POST"])

    # NetAssetValueSnapshot.transaction_id is a CharField → match on str(tx)
    tx_str = str(tx).strip()
    snap_ids = list(
        NetAssetValueSnapshot.objects
        .filter(transaction_id=tx_str)
        .values_list("id", flat=True)
    )

    counts = {"NAVAssetLine":0,"NAVPlantandequipmentLine":0,"NAVARLine":0,"NAVLiabilityLine":0,"NetAssetValueSnapshot":0}
    if snap_ids:
        counts["NAVAssetLine"], _             = NAVAssetLine.objects.filter(snapshot_id__in=snap_ids).delete()
        counts["NAVPlantandequipmentLine"], _ = NAVPlantandequipmentLine.objects.filter(snapshot_id__in=snap_ids).delete()
        counts["NAVARLine"], _                = NAVARLine.objects.filter(snapshot_id__in=snap_ids).delete()
        counts["NAVLiabilityLine"], _         = NAVLiabilityLine.objects.filter(snapshot_id__in=snap_ids).delete()
        counts["NetAssetValueSnapshot"], _    = NetAssetValueSnapshot.objects.filter(id__in=snap_ids).delete()

    return JsonResponse({"status": "success", "tx": tx_str, "counts": counts}, status=200)





#-------#-------#-------#-------#-------

#-------JSON P&L, BS CF data send from RAG Generation

#-------#-------#-------#-------#-------

import json
import uuid
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import FinancialData

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def upsert_financial_json(request):
    """
    Upsert JSON into FinancialData for a given transaction ID.

    Expected payload (JSON):
    {
      "id": "<transaction_uuid_as_string>",   # FinancialData.id
      "abn": "<abn_or_empty>",
      "acn": "<acn_or_empty>",
      "company_name": "<company name>",
      "year": 2023,              # optional
      "field": "balance_sheet",  # or "profit_loss" or "cash_flow"
      "data": [ ... ]            # JSON array/object to store
    }

    Logic:
      - If FinancialData(id) exists: update given JSON field and meta.
      - If not: create new instance with that id and meta.
      - If field already has JSON, it is overwritten.
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"message": f"Invalid JSON: {e}"}, status=400)

    transaction_id = body.get("id") or body.get("transaction_id")
    field = body.get("field")
    data = body.get("data")

    abn = body.get("abn")
    acn = body.get("acn")
    company_name = body.get("company_name")
    year = body.get("year")  # optional

    if not transaction_id:
        return JsonResponse({"message": "id (transaction_id) is required"}, status=400)

    if field not in ("profit_loss", "balance_sheet", "cash_flow"):
        return JsonResponse(
            {"message": "field must be one of: profit_loss, balance_sheet, cash_flow"},
            status=400,
        )

    if data is None:
        return JsonResponse({"message": "data is required"}, status=400)

    # Ensure transaction_id is a UUID
    try:
        tx_uuid = uuid.UUID(str(transaction_id))
    except ValueError:
        return JsonResponse(
            {"message": "id/transaction_id must be a valid UUID string"},
            status=400,
        )

    # Only update the specific JSON field + provided meta
    defaults = {
        "abn": abn,
        "acn": acn,
        "company_name": company_name,
        field: data,
    }
    if year is not None:
        defaults["year"] = year

    obj, created = FinancialData.objects.update_or_create(
        id=tx_uuid,
        defaults=defaults,
    )

    return JsonResponse(
        {
            "status": "ok",
            "created": created,
            "id": str(obj.id),
            "field": field,
        },
        status=200,
    )




#-------#-------#-------#-------#-------

#-------Accounts receivable and Accounts payable data send from RAG Generation

#-------#-------#-------#-------#-------


from django.conf import settings

import json
import uuid
import logging

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import UploadedLedgerData, UploadAPLedgerData

logger = logging.getLogger(__name__)

# 🔴 IMPORTANT: this must match the alias used in fetch_financial_data
DB_ALIAS = getattr(settings, "EFS_DATA_DB_ALIAS", "default")


def _clean_amount(val):
    """
    Normalise numeric-like values to a plain string without commas/currency.
    Safe to call on already-clean values.
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s in ("", "-", "—"):
        return s
    s = s.replace(",", "").replace("$", "")
    return s




@csrf_exempt
def bulk_upload_ar_ledger(request):
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"message": f"Invalid JSON: {e}"}, status=400)

    rows = body.get("rows", [])
    if not isinstance(rows, list):
        return JsonResponse({"message": "rows must be a JSON array."}, status=400)

    # 🔹 normalise abn / acn exactly once here
    abn = (body.get("abn") or "").strip()
    acn = (body.get("acn") or "").strip()
    transaction_id = body.get("transaction_id") or str(uuid.uuid4())

    created_ids = []

    try:
        with transaction.atomic(using=DB_ALIAS):
            for row in rows:
                if not isinstance(row, dict):
                    continue

                debtor = (
                    row.get("debtor")
                    or row.get("contact")  # convenient alias
                    or ""
                ).strip()

                if not debtor:
                    continue

                obj = UploadedLedgerData.objects.using(DB_ALIAS).create(
                    abn=abn,
                    acn=acn,
                    transaction_id=transaction_id,
                    debtor=debtor,
                    aged_receivables=_clean_amount(row.get("aged_receivables")),
                    days_0_30=_clean_amount(row.get("days_0_30")),
                    days_31_60=_clean_amount(row.get("days_31_60")),
                    days_61_90=_clean_amount(row.get("days_61_90")),
                    days_90_plus=_clean_amount(row.get("days_90_plus")),
                    notes=row.get("notes") or "",
                )
                created_ids.append(obj.id)

        return JsonResponse(
            {
                "message": "ok",
                "transaction_id": transaction_id,
                "created_count": len(created_ids),
                "ids": created_ids,
            },
            status=201,
        )

    except Exception as e:
        logger.exception("Failed to bulk upload AR ledger data")
        return JsonResponse(
            {"message": "Failed to store AR ledger data", "error": str(e)},
            status=500,
        )


@csrf_exempt
def bulk_upload_ap_ledger(request):
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"message": f"Invalid JSON: {e}"}, status=400)

    rows = body.get("rows", [])
    if not isinstance(rows, list):
        return JsonResponse({"message": "rows must be a JSON array."}, status=400)

    abn = (body.get("abn") or "").strip()
    acn = (body.get("acn") or "").strip()
    transaction_id = body.get("transaction_id") or str(uuid.uuid4())

    created_ids = []

    try:
        with transaction.atomic(using=DB_ALIAS):
            for row in rows:
                if not isinstance(row, dict):
                    continue

                creditor = (
                    row.get("creditor")
                    or row.get("contact")  # optional alias
                    or ""
                ).strip()

                if not creditor:
                    continue

                obj = UploadAPLedgerData.objects.using(DB_ALIAS).create(
                    abn=abn,
                    acn=acn,
                    transaction_id=transaction_id,
                    creditor=creditor,
                    aged_payables=_clean_amount(row.get("aged_payables")),
                    days_0_30=_clean_amount(row.get("days_0_30")),
                    days_31_60=_clean_amount(row.get("days_31_60")),
                    days_61_90=_clean_amount(row.get("days_61_90")),
                    days_90_plus=_clean_amount(row.get("days_90_plus")),
                    notes=row.get("notes") or "",
                )
                created_ids.append(obj.id)

        return JsonResponse(
            {
                "message": "ok",
                "transaction_id": transaction_id,
                "created_count": len(created_ids),
                "ids": created_ids,
            },
            status=201,
        )

    except Exception as e:
        logger.exception("Failed to bulk upload AP ledger data")
        return JsonResponse(
            {"message": "Failed to store AP ledger data", "error": str(e)},
            status=500,
        )
