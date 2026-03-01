# efs_data/bureau/views.py
import json, logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .services import (
    StoreCreditReportService,
    StoreCompanySearchService,
    StoreDataBlockService,
)
from django.shortcuts import render

def bureau_page(request):
    return render(request, "bureau.html")


logger = logging.getLogger(__name__)

# This is an optional view you can keep for debugging purposes
@csrf_exempt
@require_POST
def proxy_view(request):
    try:
        data = json.loads(request.body)
        url = data.get("url")
        token = data.get("Authorization")
        resp = requests.get(url, headers={"Authorization": token})
        return JsonResponse(resp.json(), safe=False, status=resp.status_code)
    except Exception as e:
        logger.exception("Error in proxy_view")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_POST
def store_credit_report_data(request):
    try:
        data = json.loads(request.body)

        success, message = StoreCreditReportService.store_data(data)
        if not success:
            return JsonResponse({"success": False, "error": message}, status=400)

        return JsonResponse({"success": True, "message": message})
    except Exception as e:
        logger.exception("Error in store_credit_report_data")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_POST
def store_datablock_data(request):
    try:
        data = json.loads(request.body)
        abn = data.get("abn")
        datablock_data = data.get("datablock_data")
        if not abn or not datablock_data:
            return JsonResponse({"error": "Missing ABN or datablock data"}, status=400)
        
        success, message = StoreDataBlockService.store_data_block_data(abn, datablock_data)
        if not success:
            return JsonResponse({"success": False, "message": message}, status=500)
        return JsonResponse({"success": True, "message": "Datablock data stored successfully"})
    except Exception as e:
        logger.exception("Error storing datablock data")
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_POST
def store_company_search_data(request):
    try:
        data = json.loads(request.body)
        acn = data.get("acn")
        company_data = data.get("company_data")
        if not acn or not company_data:
            return JsonResponse({"error": "Missing ACN or company data"}, status=400)

        success, message = StoreCompanySearchService.store_company_search_data(acn, company_data)
        if not success:
            return JsonResponse({"success": False, "message": message}, status=500)
        return JsonResponse({"success": True, "message": "Company search data stored successfully"})
    except Exception as e:
        logger.exception("Error storing company search data")
        return JsonResponse({"error": str(e)}, status=500)
    






# efs_data/bureau/views.py
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from bureau.models import CreditReport  # must exist & be migrated

logger = logging.getLogger(__name__)

def _normalize(report_json: dict) -> dict:
    src = report_json or {}
    return {
        "insolvencies": src.get("insolvencies", []),
        "payment_defaults": src.get("payment_defaults", []),
        "mercantile_enquiries": src.get("mercantile_enquiries", []),
        "court_judgements": src.get("court_judgements", []),
        "ato_tax_default": src.get("ato_tax_default"),
        "loans": src.get("loans", []),
        "anzsic": src.get("anzsic", {}),
    }

@require_GET
def get_credit_report(request):
    """
    GET /bureau/api/bureau/credit-report?abn=XXXXXXXXXXX
    Returns the latest saved bureau report for the ABN, normalized.
    Never raises; returns 404 if none.
    """
    abn = (request.GET.get("abn") or "").strip()
    if not abn:
        return JsonResponse({"error": "abn required"}, status=400)

    try:
        row = (
            CreditReport.objects
            .filter(abn=abn)
            .order_by("-updated_at", "-created_at")
            .first()
        )
        if not row:
            # Return 404 (Sales will pass this through after step 2)
            return JsonResponse({"error": "not found"}, status=404)

        return JsonResponse({"report": _normalize(row.report)})
    except Exception as e:
        logger.exception("get_credit_report failed for ABN %s", abn)
        return JsonResponse({"error": f"internal error: {e.__class__.__name__}"}, status=500)



from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import CreditScore, CreditScoreHistory  # your bureau app models

@require_GET
def get_credit_score(request):
    abn = (request.GET.get("abn") or "").strip()
    if not abn:
        return JsonResponse({"error": "abn required"}, status=400)
    row = (CreditScore.objects
           .filter(abn=abn)
           .order_by("-updated_at", "-created_at")
           .first())
    if not row:
        return JsonResponse({"error": "not found"}, status=404)
    return JsonResponse({
        "current_credit_score": row.current_credit_score,
        "updated_at": row.updated_at.isoformat(),
    })

@require_GET
def get_credit_score_history(request):
    abn = (request.GET.get("abn") or "").strip()
    if not abn:
        return JsonResponse({"error": "abn required"}, status=400)
    rows = CreditScoreHistory.objects.filter(abn=abn).order_by("date")
    if not rows.exists():
        return JsonResponse({"history": []}, status=404)
    return JsonResponse({
        "history": [{"date": r.date.isoformat(), "score": r.score} for r in rows]
    })
