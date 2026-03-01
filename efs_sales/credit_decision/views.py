from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt   # <-- missing import
import json   # <-- add this
from .models import CreditDecisionParametersGlobalSettings
from django.http import JsonResponse




def index(request):
    return render(request, "credit_decision/index.html")


@csrf_exempt
def receive_credit_settings(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        CreditDecisionParametersGlobalSettings.objects.create(**data)
        return JsonResponse({"message": "Credit decision settings saved"})
    return JsonResponse({"message": "Invalid request"}, status=400)


# efs_sales/credit_decision/views.py
import uuid, requests
from django.conf import settings
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

from core.models import SalesOverride  # <-- moved here
from .models import CreditDecisionParametersGlobalSettings  # lives in the credit_decision app

DATA_SERVICE_BASE = getattr(settings, "EFS_DATA_URL", "http://localhost:8003/bureau").rstrip("/")
TIMEOUT = getattr(settings, "REQUESTS_DEFAULT_TIMEOUT", 8)


def _latest_settings_for(originator: str | None):
    qs = CreditDecisionParametersGlobalSettings.objects.all()
    row = qs.filter(originator=originator).order_by("-timestamp").first() if originator else None
    if not row:
        row = qs.filter(originator__isnull=True).order_by("-timestamp").first() or \
              qs.filter(originator="").order_by("-timestamp").first()
    return row


@require_GET
def fetch_sales_override(request, transaction_id: str):
    # transaction_id is a UUID
    try:
        tx_id = uuid.UUID(str(transaction_id))
    except Exception:
        return HttpResponseBadRequest("invalid transaction_id")

    originator = (request.GET.get("originator") or "").strip() or None

    # 1) latest override row (to get ABN + states)
    row = SalesOverride.objects.filter(transactionID=tx_id).order_by("-created_at").first()
    if not row:
        # keep 404 so the UI can show "no overrides" but still render logic from settings + report elsewhere
        return JsonResponse({"error": "No Sales Overrides found for this Transaction ID"}, status=404)

    abn = (row.ABN or "").strip()

    # 2) latest settings (switches + threshold)
    settings_row = _latest_settings_for(originator)
    settings_json = {}
    if settings_row:
        settings_json = {
            "credit_score_threshold": settings_row.credit_score_threshold,
            "insolvencies_switch": settings_row.insolvencies_switch,
            "payment_defaults_current_switch": settings_row.payment_defaults_current_switch,
            "credit_enquiries_switch": settings_row.credit_enquiries_switch,
            "court_actions_current_switch": settings_row.court_actions_current_switch,
            "ato_tax_default_switch": settings_row.ato_tax_default_switch,
            "payment_defaults_resolved_switch": settings_row.payment_defaults_resolved_switch,
            "credit_score_switch": settings_row.credit_score_switch,
        }

    # 3) bureau report from Data service
    report_json = {
        "insolvencies": [],
        "paymentDefaults": [],
        "mercantileEnquiries": [],
        "courtJudgements": [],
        "atoTaxDefault": [],
        "loans": [],
        "anzsic": [],
    }
    if abn:
        try:
            r = requests.get(
                f"{DATA_SERVICE_BASE}/api/bureau/credit-report",
                params={"abn": abn},
                timeout=TIMEOUT,
            )
            if r.ok:
                src = r.json().get("report", r.json()) or {}
                report_json = {
                    "insolvencies": src.get("insolvencies", []),
                    "paymentDefaults": src.get("payment_defaults", []),
                    "mercantileEnquiries": src.get("mercantile_enquiries", []),
                    "courtJudgements": src.get("court_judgements", []),
                    "atoTaxDefault": src.get("ato_tax_default", []),
                    "loans": src.get("loans", []),
                    "anzsic": src.get("anzsic", []),
                }
            elif r.status_code == 404:
                # leave defaults
                pass
            else:
                return JsonResponse({"error": f"data service {r.status_code}: {r.text[:200]}"},
                                    status=502)
        except requests.RequestException as e:
            return JsonResponse({"error": f"data service error: {e}"}, status=502)

    # 4) flatten override row
    sales_override_data = {
        "ABN": abn,
        "Insolvencies": "Yes" if row.Insolvencies else "No",
        "Insolvencies_state": row.Insolvencies_state,
        "Payment_Defaults": "Yes" if row.Payment_Defaults else "No",
        "Payment_Defaults_state": row.Payment_Defaults_state,
        "Mercantile_Enquiries": "Yes" if row.Mercantile_Enquiries else "No",
        "Mercantile_Enquiries_state": row.Mercantile_Enquiries_state,
        "Court_Judgements": "Yes" if row.Court_Judgements else "No",
        "Court_Judgements_state": row.Court_Judgements_state,
        "ATO_Tax_Default": "Yes" if row.ATO_Tax_Default else "No",
        "ATO_Tax_Default_state": row.ATO_Tax_Default_state,
        "Loans": "Yes" if row.Loans else "No",
        "Loans_state": row.Loans_state,
        "ANZSIC": "Yes" if row.ANZSIC else "No",
        "ANZSIC_state": row.ANZSIC_state,
        "Credit_Score_Threshold": row.Credit_score_threshold,
        "Credit_Score_Threshold_state": row.Credit_score_threshold_state,
        "Sales_Notes": row.Sales_notes or "No notes",
        "data": settings_json,
        "reportData": report_json,
    }
    return JsonResponse(sales_override_data, status=200)







""" 
from django.http import JsonResponse
from .models import SalesOverride

def fetch_sales_override(request, transaction_id):
    try:
        # Get the most recent SalesOverride entry for the given transaction_id
        sales_override = SalesOverride.objects.filter(transactionID=transaction_id).order_by('-created_at').first()

        if not sales_override:
            return JsonResponse({'error': 'No Sales Overrides found for this Transaction ID'}, status=404)
        selected_originator = request.GET.get('originator', None)
        data  = {}
        if selected_originator:
            settings = CreditDecisionParametersGlobalSettings.objects.filter(originator=selected_originator).order_by('-timestamp').first()
            print(selected_originator)
            if settings:
                # Prepare data to return, including the credit_score_switch state
                data = {
                    'credit_score_threshold': settings.credit_score_threshold,
                    'insolvencies_switch': settings.insolvencies_switch,
                    'payment_defaults_current_switch': settings.payment_defaults_current_switch,
                    'credit_enquiries_switch': settings.credit_enquiries_switch,
                    'court_actions_current_switch': settings.court_actions_current_switch,
                    'ato_tax_default_switch': settings.ato_tax_default_switch,
                    'payment_defaults_resolved_switch': settings.payment_defaults_resolved_switch,
                    'credit_score_switch': settings.credit_score_switch  # Fetch the credit_score_switch value
                }
        credit_report = CreditReport.objects.using('default').filter(abn=sales_override.ABN).latest('created_at')
        
        # Return the data as JSON
        reportData = {
            'insolvencies': credit_report.report.get('insolvencies', []),
            'paymentDefaults': credit_report.report.get('paymentDefaults', []),
            'mercantileEnquiries': credit_report.report.get('mercantileEnquiries', []),
            'courtJudgements': credit_report.report.get('courtJudgements', []),
            'atoTaxDefault': credit_report.report.get('atoTaxDefault', []),
            'loans': credit_report.report.get('loans', []),
            'anzsic': credit_report.report.get('anzsic', [])
        }
        # Prepare data to return
        sales_override_data = {
            'ABN': sales_override.ABN,
            'Insolvencies': 'Yes' if sales_override.Insolvencies else 'No',
            'Insolvencies_state': sales_override.Insolvencies_state,
            'Payment Defaults': 'Yes' if sales_override.Payment_Defaults else 'No',
            'Payment_Defaults_state': sales_override.Payment_Defaults_state,
            'Mercantile Enquiries': 'Yes' if sales_override.Mercantile_Enquiries else 'No',
            'Mercantile_Enquiries_state': sales_override.Mercantile_Enquiries_state,
            'Court Judgements': 'Yes' if sales_override.Court_Judgements else 'No',
            'Court_Judgements_state': sales_override.Court_Judgements_state,
            'ATO Tax Default': 'Yes' if sales_override.ATO_Tax_Default else 'No',
            'ATO_Tax_Default_state': sales_override.ATO_Tax_Default_state,
            'Loans': 'Yes' if sales_override.Loans else 'No',
            'Loans_state': sales_override.Loans_state,
            'ANZSIC': 'Yes' if sales_override.ANZSIC else 'No',
            'ANZSIC_state': sales_override.ANZSIC_state,
            'Credit Score Threshold': sales_override.Credit_score_threshold,
            'Credit_Score_Threshold_state': sales_override.Credit_score_threshold_state,
            'Sales Notes': sales_override.Sales_notes or 'No notes',
            "data":data,
            'reportData':reportData
        }

        return JsonResponse(sales_override_data, status=200)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

        
        """