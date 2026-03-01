

import json
import logging
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

log = logging.getLogger(__name__)

# --- Modal page renderer ---
def modal_apis(request):
    ctx = {
        "abn":        request.GET.get("abn", ""),
        "tx":         request.GET.get("tx", ""),
        "originator": request.GET.get("originator", ""),
        "product":    request.GET.get("product", ""),
    }
    return render(request, "apis.html", ctx)

# --- Dummy application lookup (replace with real DB/service call) ---
def get_application_by_transaction_id(transaction_id: str):
    """
    Replace this stub with actual DB lookup or API call.
    For now, just return a fake app for demo purposes.
    """
    if not transaction_id:
        return None
    return {
        "transaction_id": transaction_id,
        "bureau_token": "HARDCODED_BUREAU_TOKEN",
        "abn": "19155437620",   # hardcoded for now
        "acn": "155437620",
    }


HARDCODED_BUREAU_TOKEN = (
"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkNyZWRpdG9yd2F0Y2giLCJpYXQiOjE1MTYyMzkwMjIsInRoYW5rcyI6IlRoYW5rcyBmb3IgdHJ5aW5nIG91dCB0aGUgQ1cgQVBJLCB3ZSdkIGxvdmUgdG8gaGF2ZSB5b3UgYXMgYSBjdXN0b21lciA6KSJ9.q5hTaEcKnCKF9MV1jYu9UJrHANexixRApb3IpG9AyHc"
)
from .serializers import FetchBureauRequestSerializer
from .services import CreditorWatchClient


@csrf_exempt
@require_POST
def fetch_bureau_data(request):
    s = FetchBureauRequestSerializer(data=json.loads(request.body.decode("utf-8")))
    s.is_valid(raise_exception=True)
    data = s.validated_data

    tx         = data.get("transaction_id") or ""
    abn        = data.get("abn") or ""
    acn        = data.get("acn") or ""
    product    = data.get("product") or ""
    originator = data.get("originator") or ""
    token      = data.get("bureau_token") or ""

    if not token:
        token = HARDCODED_BUREAU_TOKEN

    cw = CreditorWatchClient(token)
    credit_report, credit_score = {}, {}
    try:
        credit_report = cw.get_credit_report(abn, acn)
    except Exception as e:
        log.exception("CreditorWatch credit-report fetch failed for %s/%s: %s", abn, acn, e)
    try:
        credit_score = cw.get_credit_score(abn, acn)
    except Exception as e:
        log.exception("CreditorWatch credit-score fetch failed for %s/%s: %s", abn, acn, e)

    return JsonResponse({
        "success": True,
        "abn": abn,
        "acn": acn,
        "product": product,
        "originator": originator,
        "credit_report": credit_report or {},
        "credit_score": credit_score or {},
    })

# efs_apis/core/views.py
from django.conf import settings
from django.http import JsonResponse

def application_details(request):
    tx = request.GET.get("tx", "")

    # Pull the app token from settings and expose it to the modal so the browser can pass it back
    raw = getattr(settings, "EFS_CW_APP_TOKEN", "") or ""
    # strip any accidental "Bearer " prefix here too
    token = raw.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].lstrip()

    return JsonResponse({
        "application": {
            "transaction_id": tx,
            "contact_name": "—",
            "acn": "155437620",
            "contact_email": "",
            "application_time": "",
            "product": "",
            "bureau_token": token,   # <<< real JWT here, no "Bearer "
        }
    })





import json, logging, requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

def _bank_base() -> str:
    return getattr(settings, "EFS_DATA_BANKSTATEMENTS_BASE_URL", "http://localhost:8020").rstrip("/")

def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

# efs_apis/core/views.py  (port 8017)
import logging
logger = logging.getLogger(__name__)

@csrf_exempt
def fetch_bank_statements(request):
    target = f"{_bank_base()}/api/bankstatements/ingest-local/"
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"status": "error", "message": "invalid json"}, status=400)

    try:
        r = requests.post(target, json=payload, headers=_api_key_header(), timeout=15)
        ct = r.headers.get("Content-Type", "")
        body = r.json() if "application/json" in ct else {"status":"error","message": r.text}
        if not r.ok:
            logger.error("bank ingest failed %s: %s", r.status_code, body)
        return JsonResponse(body, status=r.status_code)
    except Exception as e:
        logger.exception("proxy to bank ingest failed")
        return JsonResponse({"status":"error","message":str(e)}, status=502)


# efs_apis/core/views.py
import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import (
    ServiceError,
    CreditorWatchClient,
    FinancialDataServiceClient,
    _normalize_bearer_token,
)

log = logging.getLogger(__name__)

def _fin_base() -> str:
    return getattr(settings, "EFS_DATA_FINANCIAL_BASE_URL", "http://localhost:8019").rstrip("/")

def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

@csrf_exempt
@require_POST
def fetch_accounting_data(request):
    """
    POST {abn, bureau_token?, transaction_id?, originator?, product?, year?}
    1) Calls CreditorWatch /financials/{abn}?year=...
    2) Normalizes one record
    3) Forwards to efs_data_financial /api/financials/store/
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "invalid json"}, status=400)

    abn          = (body.get("abn") or "").strip()
    year         = int(body.get("year") or 2022)  # pick a sensible default or pass through
    originator   = body.get("originator") or ""
    product      = body.get("product") or ""

    # Prefer explicit bureau_token from request; otherwise use settings token
    bureau_token = _normalize_bearer_token(body.get("bureau_token") or getattr(settings, "EFS_CW_APP_TOKEN", ""))

    if not abn:
        return JsonResponse({"success": False, "message": "abn required"}, status=400)
    if not bureau_token:
        return JsonResponse({"success": False, "message": "CreditorWatch token missing; set EFS_CW_APP_TOKEN or pass bureau_token"}, status=400)

    # 1) Fetch from CreditorWatch
    try:
        cw = CreditorWatchClient(token=bureau_token)
        cw_data = cw.get_financials(abn, year=year)
    except ServiceError as e:
        log.error("CW financials error: %s", e)
        return JsonResponse({"success": False, "message": str(e)}, status=502)
    except Exception as e:
        log.exception("CW financials request failed")
        return JsonResponse({"success": False, "message": f"CreditorWatch error: {e}"}, status=502)

    # 2) Normalize one record for the data service
    record = {
        "abn": abn,
        "acn": (cw_data.get("acn") or cw_data.get("ACN") or ""),
        "company_name": (
            cw_data.get("entityName")
            or cw_data.get("companyName")
            or cw_data.get("tradingName")
            or ""
        ),
        "year": year,
        "financials": cw_data,  # keep whole doc for traceability
        "profit_loss": cw_data.get("profitLoss") or cw_data.get("profit_and_loss"),
        "balance_sheet": cw_data.get("balanceSheet") or cw_data.get("balance_sheet"),
        "subsidiaries": cw_data.get("subsidiaries") or [],
        "raw": cw_data,
        # Optional extras:
        # "originator": originator,
        # "product": product,
    }

    # 3) Forward to efs_data_financial
    try:
        store_client = FinancialDataServiceClient()
        stored = store_client.store_financials({"record": record})
    except ServiceError as e:
        log.error("data_financial store error: %s", e)
        return JsonResponse({"success": False, "message": str(e)}, status=502)
    except Exception as e:
        log.exception("Forward to data_financial failed")
        return JsonResponse({"success": False, "message": f"forward error: {e}"}, status=502)

    return JsonResponse(
        {"success": True, "message": "Financials stored", "stored": stored},
        status=200,
    )




# efs_apis/core/views.py
import json
import logging
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

# efs_apis/core/views.py
@csrf_exempt
@require_POST
def fetch_ppsr_data(request):
    try:
        payload = json.loads(request.body)
        transaction_id = payload.get("transaction_id")  # <- get TX from the page
        abn = payload.get("abn")
        originator = payload.get("originator")

        if not abn:
            return JsonResponse({'success': False, 'message': 'Missing ABN in request'}, status=400)

        acn = "144644244"
        token = "fWmFgNGUaOmbso213o5ue0B9L0VN6tGIiTWzr329FkZfwKmwdweqwepX"
        url = f"https://api-sandbox.creditorwatch.com.au/api/ppsr/grantor?api_token={token}"

        body_data = {
            "searchGrantorType": "Organisation",
            "organisationSearchBy": "ACN",
            "organisationNumber": acn
        }

        headers = {"Content-Type": "application/json"}
        response = requests.post(url, headers=headers, data=json.dumps(body_data))

        if response.status_code == 200:
            data = response.json()

            # Forward to data service WITH transaction_id
            store_url = "http://localhost:8019/api/ppsr/store/"
            store_payload = {
                "abn": abn,
                "transaction_id": transaction_id,   # <- thread it through
                "data": data
            }
            store_resp = requests.post(store_url, json=store_payload)

            if store_resp.status_code in (200, 201):
                return JsonResponse({'success': True, 'message': 'PPSR data fetched and stored successfully.'})
            else:
                logger.error("efs_data_financial store error: %s %s", store_resp.status_code, store_resp.text)
                return JsonResponse({'success': False, 'message': 'Fetched but failed to store'}, status=502)
        else:
            return JsonResponse({
                'success': False,
                'message': f'Failed to fetch PPSR data. Status Code: {response.status_code}',
                'error': response.text
            }, status=500)

    except Exception as e:
        logger.exception("PPSR fetch failed")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
