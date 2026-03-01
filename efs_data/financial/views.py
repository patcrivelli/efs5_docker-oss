# financial/views.py
import logging
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import LoanApplicationService
from django.shortcuts import render

logger = logging.getLogger(__name__)


def financial_page(request):
    ctx = {}  # don’t override context processors
    return render(request, "financial.html", ctx)


@csrf_exempt
def proxy_view(request):
    """Pass-through proxy for external API calls."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        target_url = data.get("url")
        token = data.get("Authorization")

        if not target_url or not token:
            return JsonResponse({"error": "Missing URL or Authorization token"}, status=400)

        headers = {"Authorization": token, "Content-Type": "application/json"}
        response = requests.get(target_url, headers=headers)

        if response.status_code == 200:
            return JsonResponse(response.json(), safe=False)
        return JsonResponse({"error": f"API error {response.status_code}"}, status=response.status_code)

    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def receive_invoice_data(request):
    """Receive and persist invoice data."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        invoices = data.get("invoices", [])
        if not invoices:
            return JsonResponse({"status": "error", "message": "No invoices provided"}, status=400)

        result = LoanApplicationService.process_invoice_data({"invoices": invoices})
        return JsonResponse(result, status=201 if result["status"] == "success" else 400)
    except Exception as e:
        logger.error(f"Exception in receive_invoice_data: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def receive_ledger_data(request):
    """Receive and persist ledger data."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        ledger_entries = data.get("ledger_data", [])
        if not ledger_entries:
            return JsonResponse({"status": "error", "message": "No ledger data provided"}, status=400)

        result = LoanApplicationService.process_ledger_data(ledger_entries)
        return JsonResponse(result, status=201 if result["status"] == "success" else 400)
    except Exception as e:
        logger.error(f"Exception in receive_ledger_data: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@csrf_exempt
def store_fetched_data(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        data = json.loads(request.body)
        abn = data.get("abn")
        financials_data = data.get("financials_data")

        from .services import StoreFinancialsDataService
        StoreFinancialsDataService.store_financials_data(financials_data, abn=abn)

        return JsonResponse({"success": True})
    except Exception as e:
        logger.exception("Error saving Financials data")
        return JsonResponse({"error": str(e)}, status=500)


# ---------------- PPSR registraion ----------------


import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import StorePPSRDataService

logger = logging.getLogger(__name__)

@csrf_exempt
def store_ppsr_data(request):
    """
    Endpoint that receives PPSR data from efs_sales and stores it.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        abn = data.get("abn")
        acn = data.get("acn")  # ✅ if you want to also save the hardcoded ACN
        ppsr_data = data.get("ppsr_data")

        if not ppsr_data:
            return JsonResponse({"error": "Missing ppsr_data"}, status=400)

        success, msg = StorePPSRDataService.store_ppsr_data(ppsr_data, abn=abn, acn=acn)
        return JsonResponse({"success": success, "message": msg})

    except Exception as e:
        logger.exception("Error saving PPSR data")
        return JsonResponse({"error": str(e)}, status=500)



# ---------------- Accounting ----------------
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json, logging
from .models import FinancialData

logger = logging.getLogger(__name__)

@csrf_exempt
def store_accounting_data(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        data = json.loads(request.body)

        transaction_id = data.get("transaction_id")
        abn = data.get("abn")
        product = data.get("product")
        originator = data.get("originator")
        accounting_data = data.get("accounting_data")

        FinancialData.objects.create(
            abn=abn,
            company_name=accounting_data.get("companyName"),
            year=accounting_data.get("financialYear"),
            financials=accounting_data,
            profit_loss=accounting_data.get("profitAndLoss"),
            balance_sheet=accounting_data.get("balanceSheet"),
            subsidiaries=accounting_data.get("subsidiaries", []),
            raw=accounting_data,
        )
        return JsonResponse({"success": True})
    except Exception as e:
        logger.exception("Error saving Accounting data")
        return JsonResponse({"error": str(e)}, status=500)



from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Sum
from .models import FinancialData, LedgerData  # your model paths are correct

def _merge_dicts(*parts):
    out = {}
    for p in parts:
        if isinstance(p, dict):
            out.update(p)
    return out

def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

@require_GET
def get_financials_summary(request):
    abn = (request.GET.get("abn") or "").strip()
    if not abn:
        return JsonResponse({"success": False, "error": "ABN is required"}, status=400)

    # --- Build a {year: {company_name, profit_loss, balance_sheet}} map ---
    by_year = {}

    # Grab all rows for the ABN (some deployments store multiple snapshots)
    for row in FinancialData.objects.filter(abn=abn).order_by("-timestamp"):
        # 1) If row has explicit fields, take them
        if row.year and (row.profit_loss or row.balance_sheet):
            y = _int(row.year)
            if y:
                by_year.setdefault(y, {
                    "company_name": row.company_name,
                    "profit_loss": {},
                    "balance_sheet": {},
                })
                by_year[y]["profit_loss"] = _merge_dicts(by_year[y]["profit_loss"], row.profit_loss or {})
                by_year[y]["balance_sheet"] = _merge_dicts(by_year[y]["balance_sheet"], row.balance_sheet or {})

        # 2) Most of your data is in row.financials (bundled JSON)
        blob = row.financials
        if not blob:
            continue

        # Shape can be: dict with "financials": [...], or the list itself, or a single entry dict.
        if isinstance(blob, dict) and isinstance(blob.get("financials"), list):
            entries = blob["financials"]
            company_name = (blob.get("company") or {}).get("name") or row.company_name
        elif isinstance(blob, list):
            entries = blob
            company_name = row.company_name
        elif isinstance(blob, dict) and "financialYear" in blob:
            entries = [blob]
            company_name = row.company_name
        else:
            entries = []
            company_name = row.company_name

        for ent in entries:
            y = _int(ent.get("financialYear") or ent.get("year"))
            if not y:
                continue
            fs = ent.get("financialStatement") or {}
            # Prefer structured sections; fall back to `raw` if needed
            pl = fs.get("profitAndLoss") or fs.get("raw") or {}
            bs = fs.get("balanceSheet") or {}

            by_year.setdefault(y, {
                "company_name": company_name,
                "profit_loss": {},
                "balance_sheet": {},
            })
            by_year[y]["profit_loss"] = _merge_dicts(by_year[y]["profit_loss"], pl)
            by_year[y]["balance_sheet"] = _merge_dicts(by_year[y]["balance_sheet"], bs)

    # Available years (desc)
    years_available = sorted([y for y in by_year.keys() if y is not None], reverse=True)

    # Choose 2021/2022 if present; otherwise fall back to latest two
    f2021 = by_year.get(2021)
    f2022 = by_year.get(2022)
    if not (f2021 and f2022) and years_available:
        y_latest = years_available[0]
        y_prev = years_available[1] if len(years_available) > 1 else None
        f2022 = f2022 or by_year.get(y_latest)
        if y_prev is not None:
            f2021 = f2021 or by_year.get(y_prev)

    financials_2021 = [f2021] if f2021 else []
    financials_2022 = [f2022] if f2022 else []

    # --- AR ledger (you said status is "Open") ---
    ledger_qs = (
        LedgerData.objects
        .filter(abn=abn, status__iexact="Open")
        .values("debtor")
        .annotate(total_due=Sum("amount_due"))
        .order_by("debtor")
    )
    ar_ledger = [{"name": r["debtor"], "total_due": str(r["total_due"] or 0)} for r in ledger_qs]

    # Distinct debtors for the Debtors tab
    debtors_list = list(
        LedgerData.objects
        .filter(abn=abn)
        .exclude(debtor__isnull=True).exclude(debtor__exact="")
        .values_list("debtor", flat=True)
        .distinct()
    )

    return JsonResponse({
        "success": True,
        "financials_2021": financials_2021,
        "financials_2022": financials_2022,
        "ar_ledger": ar_ledger,
        "debtors_list": debtors_list,
        "available_years": years_available,
    })




# efs_data/financial/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import Registration  # your model shown in the prompt

def _reg_to_dict(r: Registration) -> dict:
    # ISO strings for datetimes/dates; JSONFields pass through
    return {
        "id": str(r.id),
        "abn": r.abn or None,
        "search_date": r.search_date.isoformat() if r.search_date else None,

        "registration_number": r.registration_number or None,
        "start_time": r.start_time.isoformat() if r.start_time else None,
        "end_time": r.end_time.isoformat() if r.end_time else None,
        "change_number": r.change_number or None,
        "change_time": r.change_time.isoformat() if r.change_time else None,
        "registration_kind": r.registration_kind or None,
        "is_migrated": bool(r.is_migrated) if r.is_migrated is not None else None,
        "is_transitional": bool(r.is_transitional) if r.is_transitional is not None else None,

        "grantor_organisation_identifier": r.grantor_organisation_identifier or None,
        "grantor_organisation_identifier_type": r.grantor_organisation_identifier_type or None,
        "grantor_organisation_name": r.grantor_organisation_name or None,

        "collateral_class_type": r.collateral_class_type or None,
        "collateral_type": r.collateral_type or None,
        "collateral_class_description": r.collateral_class_description or None,
        "are_proceeds_claimed": bool(r.are_proceeds_claimed) if r.are_proceeds_claimed is not None else None,
        "proceeds_claimed_description": r.proceeds_claimed_description or None,
        "is_security_interest_registration_kind": bool(r.is_security_interest_registration_kind) if r.is_security_interest_registration_kind is not None else None,
        "are_assets_subject_to_control": bool(r.are_assets_subject_to_control) if r.are_assets_subject_to_control is not None else None,
        "is_inventory": bool(r.is_inventory) if r.is_inventory is not None else None,
        "is_pmsi": bool(r.is_pmsi) if r.is_pmsi is not None else None,
        "is_subordinate": bool(r.is_subordinate) if r.is_subordinate is not None else None,
        "giving_of_notice_identifier": r.giving_of_notice_identifier or None,

        # JSON fields - keep as-is; your modal expects these shapes
        "security_party_groups": r.security_party_groups or [],
        "grantors": r.grantors or [],
        "address_for_service": r.address_for_service or {},

        "created_at": r.created_at.isoformat() if r.created_at else None,
    }

@require_GET
def get_ppsr_registrations(request):
    abn = (request.GET.get("abn") or "").strip()
    if not abn:
        return JsonResponse({"error": "abn required"}, status=400)

    qs = (Registration.objects
          .filter(abn=abn)
          .order_by("-search_date", "-created_at"))

    regs = [_reg_to_dict(r) for r in qs]
    if not regs:
        # 404 is fine; Sales will show “No data” gracefully
        return JsonResponse({"error": "not found"}, status=404)

    return JsonResponse({"registrations": regs})








# efs_data/financial/views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from .models import InvoiceData

def _jsonable(v):
    return str(v) if isinstance(v, Decimal) else v

@csrf_exempt
def invoices_by_transaction(request):
    tx = request.GET.get("transaction_id")
    if not tx:
        return JsonResponse({"error": "transaction_id is required"}, status=400)

    qs = InvoiceData.objects.filter(transaction_id=tx).order_by("id")
    out = [{
        "abn": inv.abn,
        "acn": inv.acn,
        "name": inv.name,
        "transaction_id": inv.transaction_id,
        "debtor": inv.debtor,
        "date_funded": inv.date_funded.isoformat() if inv.date_funded else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "amount_funded": _jsonable(inv.amount_funded),
        "amount_due": _jsonable(inv.amount_due),
        "discount_percentage": _jsonable(inv.discount_percentage),
        "face_value": _jsonable(inv.face_value),
        "sif_batch": inv.sif_batch,
        "inv_number": inv.inv_number,
    } for inv in qs]
    return JsonResponse(out, safe=False, status=200)






""" 

import json
import logging
import uuid
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import LoanApplicationService

logger = logging.getLogger(__name__)

@csrf_exempt
def receive_ledger_data(request):
    if request.method == 'POST':
        try:
            # Parse incoming JSON payload
            data = json.loads(request.body)
            ledger_entries = data.get('ledger_data', [])

            logger.debug(f"✅ Received ledger data: {ledger_entries}")  

            # Convert UUID and Decimal values before processing
            for entry in ledger_entries:
                # ❌ Ignore transaction_id if missing
                if 'transaction_id' in entry and entry['transaction_id']:
                    entry['transaction_id'] = str(entry['transaction_id'])  # Convert UUID to string
                else:
                    entry.pop('transaction_id', None)  # 🔥 Remove transaction_id if missing

                if 'amount_due' in entry:
                    entry['amount_due'] = str(entry['amount_due'])  # Convert Decimal to string

            # Send data to service layer
            result = LoanApplicationService.process_ledger_data(ledger_entries)

            if result['status'] == 'success':
                return JsonResponse({'status': 'success'}, status=201)
            else:
                logger.error(f"❌ Ledger Serializer Errors: {result['message']}")
                return JsonResponse({'status': 'error', 'message': result['message']}, status=400)

        except Exception as e:
            logger.error(f"🔥 Exception in receive_ledger_data: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)




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



@csrf_exempt
def receive_scf_invoice_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            logger.debug(f"📌 Received SCF invoice data: {json.dumps(data, indent=4)}")

            invoices = data.get('invoices', [])

            if not invoices:
                logger.error("❌ No SCF invoices found in request")
                return JsonResponse({'status': 'error', 'message': 'Invoice list is empty.'}, status=400)

            for invoice in invoices:
                if not invoice.get('transaction_id'):
                    logger.error("❌ Missing Transaction ID in one of the SCF invoices")
                    return JsonResponse({'status': 'error', 'message': 'Each invoice must include a transaction_id.'}, status=400)

            result = SCFFundingService.process_invoice_data({"invoices": invoices})

            if result['status'] == 'success':
                logger.debug(f"✅ SCF invoice data processed successfully for {len(invoices)} invoices.")
            else:
                logger.error(f"❌ Failed to process SCF invoice data: {result['message']}")

            return JsonResponse(result, status=201 if result['status'] == 'success' else 400)

        except Exception as e:
            logger.error(f"🔥 Exception in receive_scf_invoice_data: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)



"""