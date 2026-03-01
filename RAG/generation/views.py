import logging
import json
import os
import requests
from typing import List, Dict, Any
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings

from retrieval.models import RetrievalLog

logger = logging.getLogger(__name__)

# ---------------------------------
# existing helpers
# ---------------------------------

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

# ---------------------------------
# NEW: talk to efs_data_financials service
# ---------------------------------

def _financials_base() -> str:
    """
    Base URL for the efs_data_financials service.
    That service runs on port 8019.
    """
    # If you later move this to settings, great. For now we hardcode localhost:8019.
    return getattr(settings, "EFS_DATA_FINANCIALS_BASE_URL", "http://localhost:8019").rstrip("/")




def fetch_financial_models() -> List[Dict[str, Any]]:
    """
    Fetch model metadata from efs_data_financials.

    Preferred (new) endpoint:
      GET /api/model-metadata/
      {
        "models": [
          { "name": "FinancialData", "fields": ["id","timestamp","abn", ...] },
          ...
        ]
      }

    Fallback (legacy) endpoint:
      GET /api/model-list/
      { "models": ["FinancialData", "LedgerData", ...] }

    Returns a list of dicts:
      [
        { "name": "FinancialData", "fields": ["id","timestamp",...] },
        { "name": "LedgerData",   "fields": [] },
        ...
      ]
    """
    base = _financials_base()

    # 1) Try the new metadata endpoint
    try:
        url_meta = f"{base}/api/model-metadata/"
        resp = requests.get(url_meta, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])

        if isinstance(models, list) and models and isinstance(models[0], dict):
            result: List[Dict[str, Any]] = []
            for m in models:
                name = str(m.get("name") or m.get("model") or "").strip()
                if not name:
                    continue
                fields = m.get("fields") or []
                # force to list of strings
                fields = [str(f) for f in fields if f]
                result.append({"name": name, "fields": fields})
            return result
    except Exception:
        logger.exception("Failed to fetch model metadata from efs_data_financials")

    # 2) Fallback to legacy list of names only
    try:
        url_list = f"{base}/api/model-list/"
        resp = requests.get(url_list, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models_list = data.get("models", [])
        return [
            {"name": str(m), "fields": []}
            for m in models_list
        ]
    except Exception:
        logger.exception("Failed to fetch model list from efs_data_financials (fallback)")
        return []


# ---------------------------------
# Page render
# ---------------------------------

def generation_home(request):
    """
    Main page render for generation.html
    Adds:
    - originators / selected_originator (existing)
    - retrieval_logs (existing)
    - financial_models (NEW structure): list of {name, fields}
    """
    ctx = base_context(request)

    ctx.update({
        "page_title": "RAG - Generation",
        "retrieval_logs": RetrievalLog.objects.order_by("-created_at")[:50],
        "financial_models": fetch_financial_models(),
    })

    return render(request, "generation.html", ctx)


# If you still need generation_page separately elsewhere, keep it aligned:
def generation_page(request):
    ctx = base_context(request)
    ctx.update({
        "page_title": "RAG - Generation",
        "retrieval_logs": RetrievalLog.objects.order_by("-created_at")[:50],
        "financial_models": fetch_financial_models(),
    })
    return render(request, "generation.html", ctx)
# ---------------------------------
# Create Originator (unchanged)
# ---------------------------------

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

    return redirect("generation_home")


# ---------------------------------
# GEMINI CONFIG + ACTION ENDPOINTS
# ---------------------------------

GEMINI_API_KEY = "AIzaSyC0XC_LDLVUEP3S_fX7cKjaQEkIylYOC6s"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"




# ---------------------------------
# Generate P&L, BS and CF statements
# ---------------------------------


@csrf_exempt
def run_generation(request):
    """Run a saved query through Gemini AI and return a generated answer."""
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
        log_id = body.get("log_id")
        log = RetrievalLog.objects.get(id=log_id)
    except RetrievalLog.DoesNotExist:
        return JsonResponse({"message": "Log not found"}, status=404)
    except Exception as e:
        return JsonResponse({"message": f"Invalid request: {e}"}, status=400)

    prompt = f"""
    User query: {log.query_text}

    Retrieved context:
    {json.dumps(log.results, indent=2)}

    Instruction: Provide a clean, human-readable answer based only on the context above.
    """

    try:
        headers = {"Content-Type": "application/json"}
        params = {"key": GEMINI_API_KEY}

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }

        resp = requests.post(GEMINI_API_URL, headers=headers, params=params, json=payload)
        resp.raise_for_status()
        data = resp.json()

        answer = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
        )
        if not answer:
            answer = "⚠️ No answer returned by Gemini."

        return JsonResponse({"answer": answer})

    except Exception as e:
        logger.error(f"❌ Generation error: {e}", exc_info=True)
        return JsonResponse({"message": "Generation failed", "error": str(e)}, status=500)


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json, re, requests, logging

logger = logging.getLogger(__name__)

YEAR_KEY_RE = re.compile(r"^\d{4}$")

def _to_num_str(val: str) -> str:
    """
    Coerce any numeric-like value to a plain string without commas/currency.
    Keep "-" or "" as-is if provided. Otherwise return the original as str.
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s in ("", "-", "—"):
        return "" if s != "-" else "-"
    # remove currency and thousand separators
    s = s.replace(",", "").replace("$", "")
    # accept leading +/-
    try:
        # allow floats and ints
        f = float(s)
        # return minimal string form without scientific notation
        return str(f).rstrip("0").rstrip(".") if "." in str(f) else str(int(f))
    except Exception:
        return s  # leave as-is if not numeric

def _clean_key(k: str) -> str:
    # strip BOM and whitespace
    return (k or "").replace("\ufeff", "").strip()

def _normalize_rows(rows):
    """
    Ensure each row looks like:
      { "Line Item": "<text>", "<YYYY>": "<amount>", ... }
    - Drop unknown keys except 4-digit year keys
    - Rename Item -> Line Item
    - Coerce all amounts to strings (no commas/$)
    """
    norm = []
    # discover the union of year keys present (optional; we’ll keep whatever shows up)
    for r in rows:
        if not isinstance(r, dict):
            continue
        new_row = {}

        # Normalize keys
        tmp = {}
        for k, v in r.items():
            nk = _clean_key(k)
            tmp[nk] = v

        # Map possible item keys to "Line Item"
        line_item = (
            tmp.get("Line Item")
            or tmp.get("Item")
            or tmp.get("LineItem")
            or tmp.get("line_item")
            or tmp.get("lineitem")
            or ""
        )
        line_item = str(line_item).strip()
        new_row["Line Item"] = line_item

        # Keep only year keys (4 digits)
        for k, v in tmp.items():
            if YEAR_KEY_RE.match(k):
                new_row[k] = _to_num_str(v)

        # If there are non-year numeric columns (e.g., "2023 (Actual)"), try extract year
        for k, v in tmp.items():
            if k in new_row:  # already captured
                continue
            m = re.match(r"^(\d{4})\b", k)
            if m and m.group(1) not in new_row:
                new_row[m.group(1)] = _to_num_str(v)

        # require at least Line Item
        if new_row.get("Line Item", ""):
            norm.append(new_row)

    return norm


# ---------------------------------
# Convert P&L, BS and CF statements to JSON 
# ---------------------------------


@csrf_exempt
def convert_to_json(request):
    """
    Ask Gemini to turn retrieved chunks into a strict JSON array of objects:
      { "Line Item": "...", "<YYYY>": "...", "<YYYY2>": "..." }
    - Years are dynamic (1 or many)
    - Values MUST be strings, no commas or currency
    - Only return JSON (no prose)
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
        log_id = body.get("log_id")
        log = RetrievalLog.objects.get(id=log_id)
    except RetrievalLog.DoesNotExist:
        return JsonResponse({"message": "Log not found"}, status=404)
    except Exception as e:
        return JsonResponse({"message": f"Invalid request: {e}"}, status=400)

    # --- Prompt updated to dynamically produce "Line Item" + year columns ---
    extraction_prompt = f"""
You are a strict data extraction engine.

INPUTS:
1) User query.
2) Retrieved context (may include financial lines across one or multiple years).

TASK:
Return ONLY a JSON array of objects. No prose.
Each object MUST follow this shape:
{{
  "Line Item": "<text label>",
  "<YYYY>": "<number-as-string>",
  "<YYYY2>": "<number-as-string>",
  ... (zero or more additional 4-digit year keys)
}}

RULES:
- "Line Item" is required on every row.
- Year keys MUST be 4-digit years only (e.g., "2021", "2022", "2023", "2024").
- If a value is missing, use "" (empty string).
- Values must be numeric strings only (no commas, $, spaces, or percent signs). Examples: "12345", "-987.65", "".
- Do NOT include any keys other than "Line Item" and 4-digit years.
- Do NOT include commentary before or after the JSON.

User query:
{log.query_text}

Retrieved context:
{json.dumps(log.results, indent=2)}
""".strip()

    try:
        headers = {"Content-Type": "application/json"}
        params = {"key": GEMINI_API_KEY}  # ensure this is imported/available
        payload = {
            "contents": [
                {
                    "parts": [{"text": extraction_prompt}]
                }
            ]
        }

        resp = requests.post(GEMINI_API_URL, headers=headers, params=params, json=payload)
        resp.raise_for_status()
        data = resp.json()

        raw_answer = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
        )

        # Try to parse JSON
        parsed_rows = None
        try:
            parsed_rows = json.loads(raw_answer)
        except Exception:
            # salvage [ ... ]
            try:
                start = raw_answer.find('[')
                end   = raw_answer.rfind(']')
                if start != -1 and end != -1 and end > start:
                    candidate = raw_answer[start:end+1]
                    parsed_rows = json.loads(candidate)
            except Exception:
                parsed_rows = None

        if parsed_rows is None:
            return JsonResponse(
                {"json_rows": raw_answer, "warning": "Model did not return clean JSON. Showing raw response."},
                status=200
            )

        # Normalize to the required, consistent structure
        normalized = _normalize_rows(parsed_rows)

        return JsonResponse({"json_rows": normalized}, status=200)

    except Exception as e:
        logger.error(f"❌ JSON conversion error: {e}", exc_info=True)
        return JsonResponse({"message": "Convert to JSON failed", "error": str(e)}, status=500)



# ---------------------------------
# Generate AR Ledger 
# ---------------------------------

# at top with other imports
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
def AR_LedgerData(request):
    """
    Placeholder endpoint for AR Ledger uploads from the RAG UI.
    For now it just echoes what it received.
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    logger.info("Upload_AR_LedgerData called with payload: %s", payload)

    return JsonResponse(
        {
            "status": "ok",
            "view": "Upload_AR_LedgerData",
            "received": payload,
        },
        status=200,
    )

# ---------------------------------
# Generate AP Ledger 
# ---------------------------------



@csrf_exempt
def AP_LedgerDat(request):
    """
    Placeholder endpoint for Accounts Payable ledger uploads.
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    logger.info("Upload_AP_LedgerDat called with payload: %s", payload)

    return JsonResponse(
        {
            "status": "ok",
            "view": "Upload_AP_LedgerDat",
            "received": payload,
        },
        status=200,
    )


# ---------------------------------
# Generate Fixed_assets_vehicles
# ---------------------------------




@csrf_exempt
def Fixed_assets_vehicles(request):
    """
    Placeholder endpoint for Fixed Assets – Vehicles uploads.
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    logger.info("Fixed_assets_vehicles called with payload: %s", payload)

    return JsonResponse(
        {
            "status": "ok",
            "view": "Fixed_assets_vehicles",
            "received": payload,
        },
        status=200,
    )

# ---------------------------------
# Generate Fixed_assets_plant_equipment
# ---------------------------------


@csrf_exempt
def Fixed_assets_plant_equipment(request):
    """
    Placeholder endpoint for Fixed Assets – Plant & Equipment uploads.
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    logger.info("Fixed_assets_plant_equipment called with payload: %s", payload)

    return JsonResponse(
        {
            "status": "ok",
            "view": "Fixed_assets_plant_equipment",
            "received": payload,
        },
        status=200,
    )





## ------ delete data models
## ------ delete data models
## ------ delete data models
## ------ delete data models
## ------ delete data models
## ------ delete data models




from django.db import connection, transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
@require_POST
def flush_rag_data(request):
    """
    Danger button.
    Truncates all RAG pipeline tables so we can re-upload fresh docs
    without old embeddings / chunks / logs hanging around.

    This mirrors:

    BEGIN;
    TRUNCATE TABLE
      embeddings_embedding,
      chunking_element,
      chunking_extractionrun,
      ingestion_documentfile,
      ingestion_document,
      retrieval_retrievallog
    RESTART IDENTITY CASCADE;
    COMMIT;
    """

    try:
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("""
                    TRUNCATE TABLE
                      embeddings_embedding,
                      chunking_element,
                      chunking_extractionrun,
                      ingestion_documentfile,
                      ingestion_document,
                      retrieval_retrievallog
                    RESTART IDENTITY CASCADE;
                """)
        return JsonResponse({"status": "ok", "message": "RAG data flushed."}, status=200)

    except Exception as e:
        logger.exception("❌ Failed to flush RAG data")
        return JsonResponse(
            {"status": "error", "message": f"Flush failed: {e}"},
            status=500
        )




#__________ code for dropdown menu in generation.html page/ data from application_aggregate servioce __________

import logging
import json
import requests
from typing import List, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

# ... existing _profile_base, _api_key_header, fetch_originators, base_context, 
# _financials_base, fetch_financial_models live above here ...


def _aggregate_base() -> str:
    """
    Base URL for the application_aggregate service (port 8016).
    """
    return getattr(
        settings,
        "EFS_APPLICATION_AGGREGATE_BASE_URL",
        "http://localhost:8016",
    ).rstrip("/")


def fetch_sales_review_deals(originator_name: str) -> List[Dict[str, Any]]:
    """
    Call application_aggregate to fetch deals for a given originator,
    filtered to state='sales_review'.

      GET {AGG_BASE}/api/sales-review-deals/?originator=<name>&state=sales_review

    Returns: list of {
        "transaction_id": "...",
        "company_name": "...",
        "abn": "...",
        "acn": "..."
    }
    """
    if not originator_name:
        return []

    try:
        url = f"{_aggregate_base()}/api/sales-review-deals/"
        params = {
            "originator": originator_name,
            "state": "sales_review",
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        deals = data.get("deals", [])

        cleaned: List[Dict[str, Any]] = []
        for d in deals:
            tx = str(d.get("transaction_id") or "").strip()
            name = str(d.get("company_name") or "").strip()
            abn = str(d.get("abn") or "").strip()
            acn = str(d.get("acn") or "").strip()

            if tx or name:
                cleaned.append(
                    {
                        "transaction_id": tx,
                        "company_name": name or "(no name)",
                        "abn": abn,
                        "acn": acn,
                    }
                )
        return cleaned

    except Exception:
        logger.exception(
            "Failed to fetch sales review deals from application_aggregate"
        )
        return []


def generation_home(request):
    """
    Main page render for generation.html
    """
    ctx = base_context(request)  # has originators + selected_originator

    selected_originator = ctx.get("selected_originator") or {}
    originator_name = selected_originator.get("originator")

    ctx.update({
        "page_title": "RAG - Generation",
        "retrieval_logs": RetrievalLog.objects.order_by("-created_at")[:50],
        "financial_models": fetch_financial_models(),
        "sales_review_deals": fetch_sales_review_deals(originator_name),
    })

    return render(request, "generation.html", ctx)


def generation_page(request):
    # if you still use this alias elsewhere
    ctx = base_context(request)

    selected_originator = ctx.get("selected_originator") or {}
    originator_name = selected_originator.get("originator")

    ctx.update({
        "page_title": "RAG - Generation",
        "retrieval_logs": RetrievalLog.objects.order_by("-created_at")[:50],
        "financial_models": fetch_financial_models(),
        "sales_review_deals": fetch_sales_review_deals(originator_name),
    })
    return render(request, "generation.html", ctx)





#---------#---------#---------


#--------- code to post   P&L, BS CF JSON data  to efs_data_financial 


#---------#---------#---------


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


@csrf_exempt
def post_financial_data(request):
    """
    Receive structured JSON + deal metadata from the Generation UI
    and forward it to the efs_data_financial service (port 8019).

    For now this only supports:
      model == 'FinancialData'
      field in ['profit_loss', 'balance_sheet', 'cash_flow']

    The FinancialData.id is set to the transaction_id (UUID string) from Deals.
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"message": f"Invalid JSON: {e}"}, status=400)

    model = body.get("model")
    field = body.get("field")
    json_rows = body.get("json_rows")
    transaction_id = body.get("transaction_id")
    company_name = body.get("company_name")
    abn = body.get("abn")
    acn = body.get("acn")

    # For now: strictly limit to FinancialData + a small set of fields
    if model != "FinancialData":
        return JsonResponse({"message": "Only FinancialData is supported for posting."}, status=400)

    if field not in ("profit_loss", "balance_sheet", "cash_flow"):
        return JsonResponse({"message": "Field must be one of: profit_loss, balance_sheet, cash_flow."}, status=400)

    if not transaction_id:
        return JsonResponse({"message": "transaction_id is required."}, status=400)

    if json_rows is None:
        return JsonResponse({"message": "json_rows is required."}, status=400)

    payload = {
        # FinancialData identifiers / meta
        "id": transaction_id,          # becomes FinancialData.id (UUID primary key)
        "abn": abn,
        "acn": acn,
        "company_name": company_name,
        # optional 'year' could go here if you want to compute it later
        # "year": ...,
        # which JSON field to overwrite
        "field": field,
        "data": json_rows,
    }

    try:
        base = _financials_base()  # already defined above, points at http://localhost:8019 by default
        url = f"{base}/api/financial-data/upsert-json/"

        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        remote_data = resp.json()

        return JsonResponse(
            {"message": "ok", "remote": remote_data},
            status=200,
        )
    except Exception as e:
        logger.exception("Failed to post financial data to efs_data_financial")
        return JsonResponse(
            {"message": "Failed to post to efs_data_financial", "error": str(e)},
            status=502,
        )






#-------#-------#-------#-------#-------

#-------Post Accounts reciavble and payable data send from RAG Generation

#-------#-------#-------#-------#-------
    

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
import logging
import requests
import uuid

logger = logging.getLogger(__name__)



import re

def _ledger_csv_abn(abn: str) -> str:
    """
    Make the ABN look exactly like the CSV-exported ABN.

    The CSV that works contains an invisible U+202C (POP DIRECTIONAL
    FORMATTING) after the 11 digits, e.g. '64074499068\\u202c'.

    We mimic that here so rows created via the RAG pipeline match
    rows created via the CSV import pipeline.
    """
    s = (abn or "").strip()
    if not s:
        return ""

    # If it's 11 digits with no control char, append U+202C
    if re.fullmatch(r"\d{11}", s) and not s.endswith("\u202c"):
        s = s + "\u202c"

    return s




def _financials_base() -> str:
    """
    Base URL for the efs_data_financials service.
    Already used by post_financial_data.
    """
    return getattr(settings, "EFS_DATA_FINANCIALS_BASE_URL", "http://localhost:8019").rstrip("/")


def _clean_amount(val):
    """
    Normalise numeric-like values to a plain string without commas/currency.
    Keep empty / '-' as-is.
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s in ("", "-", "—"):
        return s
    # remove currency / thousand separators
    s = s.replace(",", "").replace("$", "")
    return s


def _normalise_ledger_rows(rows, dataset: str):
    """
    Ensure the rows we send to efs_data_financial look like the CSV-import format.

    For AR:
      - mandatory name field: debtor
      - total column: aged_receivables

    For AP:
      - mandatory name field: creditor
      - total column: aged_payables

    All bucket columns are cleaned with _clean_amount.
    """
    normalised = []

    if dataset == "ar_ledger":
        name_key = "debtor"
        total_key = "aged_receivables"
    else:  # accounts_payable
        name_key = "creditor"
        total_key = "aged_payables"

    for row in rows:
        if not isinstance(row, dict):
            continue

        r = dict(row)  # shallow copy so we don't mutate caller

        # Fill in the name from `contact` if missing
        if not r.get(name_key):
            contact = (r.get("contact") or "").strip()
            if contact:
                r[name_key] = contact

        # If still no name, skip (downstream rows must have a debtor/creditor)
        name_val = (r.get(name_key) or "").strip()
        if not name_val:
            continue
        r[name_key] = name_val

        # Clean numeric-like fields
        for key in [total_key, "days_0_30", "days_31_60", "days_61_90", "days_90_plus"]:
            if key in r:
                r[key] = _clean_amount(r.get(key))

        # Notes can be left as-is, but ensure it's a string
        if "notes" in r and r["notes"] is None:
            r["notes"] = ""

        normalised.append(r)

    return normalised



import re

def _normalise_abn_or_acn(value: str) -> str:
    """
    Normalise ABN/ACN to digits-only.

    This removes:
      - spaces
      - commas
      - any invisible Unicode control characters (like U+202C)
    so that values coming from RAG, CSV uploads, and other services
    are *identical* at the database level.
    """
    if not value:
        return ""
    s = str(value)
    # Strip whitespace/control chars then keep only digits
    s = re.sub(r"\D+", "", s)
    return s


@csrf_exempt
def post_ledger_data(request):
    """
    Receive AR/AP ledger data from the Generation UI and forward it
    to efs_data_financial.

    Expected JSON body from the frontend:

    {
      "dataset": "ar_ledger" | "accounts_payable",
      "transaction_id": "uuid-string",
      "company_name": "Hawking Electrical Pty Ltd",
      "abn": "64074499068",
      "acn": "123456789",
      "rows": [...]
    }
    """
    if request.method != "POST":
        return JsonResponse({"message": "POST required"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"message": f"Invalid JSON: {e}"}, status=400)

    dataset = body.get("dataset")
    if dataset not in ("ar_ledger", "accounts_payable"):
        return JsonResponse(
            {"message": "dataset must be 'ar_ledger' or 'accounts_payable'."},
            status=400,
        )

    # ---- match CSV behaviour for ids and parties ----
    transaction_id = body.get("transaction_id") or str(uuid.uuid4())

    raw_abn = body.get("abn") or ""
    raw_acn = body.get("acn") or ""

    # 🔴 key fix: normalise to digits-only so it matches CSV-import path
    abn = _normalise_abn_or_acn(raw_abn)
    acn = _normalise_abn_or_acn(raw_acn)

    company_name = body.get("company_name") or ""

    rows = body.get("rows", [])
    if not isinstance(rows, list):
        return JsonResponse({"message": "rows must be an array"}, status=400)

    # 🔴 make row structure match CSV-imported rows exactly
    rows = _normalise_ledger_rows(rows, dataset)

    payload = {
        "dataset": dataset,
        "transaction_id": transaction_id,
        "abn": abn,
        "acn": acn,
        "company_name": company_name,
        "rows": rows,
    }

    try:
        base = _financials_base()

        if dataset == "ar_ledger":
            url = f"{base}/api/ledger-data/bulk-upload/"
        else:  # accounts_payable
            url = f"{base}/api/ap-ledger-data/bulk-upload/"

        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        remote = resp.json()

        return JsonResponse(
            {"message": "ok", "remote": remote},
            status=200,
        )

    except Exception as e:
        logger.exception("Failed to post AR/AP ledger data to efs_data_financial")
        return JsonResponse(
            {
                "message": "Failed to post ledger data to efs_data_financial",
                "error": str(e),
            },
            status=502,
        )
