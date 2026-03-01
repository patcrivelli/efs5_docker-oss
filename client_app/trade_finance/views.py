from django.shortcuts import render
def index(request):
    return render(request, "trade_finance/index.html")





from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from decimal import Decimal
import pandas as pd
from .models import AccontsPayableLedgerData


@csrf_exempt
def upload_ap_ledger(request):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Invalid request method"},
            status=405
        )

    uploaded_file = request.FILES.get("file")
    abn = request.POST.get("abn")
    user_name = request.POST.get("user_name")  # ✅ NEW

    if not uploaded_file:
        return JsonResponse(
            {"success": False, "error": "No file uploaded"},
            status=400
        )

    filename = uploaded_file.name.lower()

    try:
        # --- Read file ---
        if filename.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
        else:
            return JsonResponse(
                {"success": False, "error": "Unsupported file type"},
                status=400
            )

        # --- Normalise headers ---
        df.columns = (
            df.columns
              .str.strip()
              .str.lower()
              .str.replace(" ", "_")
        )

        created = 0

        for _, row in df.iterrows():
            AccontsPayableLedgerData.objects.create(
                abn=abn,
                user_name=user_name,  # ✅ STORED HERE

                supplier=str(
                    row.get("suppliers") or row.get("supplier") or ""
                ).strip(),

                invoice_number=str(
                    row.get("inv_number") or row.get("invoice_number") or ""
                ).strip(),

                amount_due=Decimal(str(row.get("amount_due") or 0)),
                status="Open"
            )
            created += 1

        return JsonResponse({
            "success": True,
            "rows_created": created
        })

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500
        )



from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import AccontsPayableLedgerData

@login_required
def fetch_accounts_payable_ledger(request):
    # Use logged-in user
    username = request.user.username

    # Option A (simplest): filter directly by stored user_name
    qs = AccontsPayableLedgerData.objects.filter(
        user_name=username,
        status="Open"
    ).order_by("supplier", "invoice_number")

    # If you ALSO want ABN match, do this instead:
    # abn = getattr(request.user, "abn", None)
    # qs = AccontsPayableLedgerData.objects.filter(
    #     abn=abn,
    #     user_name=username,
    #     status="Open"
    # ).order_by("supplier", "invoice_number")

    return JsonResponse({
        "success": True,
        "data": [
            {
                "supplier": r.supplier,
                "invoice_number": r.invoice_number,
                "amount_due": str(r.amount_due),
                "repayment_date": r.repayment_date.isoformat() if r.repayment_date else None,
                "status": r.status,
            }
            for r in qs
        ]
    })





from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal
import json
from .models import TF_ApplicationData

def TF_application_store(request):
    """
    API Endpoint to store Trade Finance application data into TF_ApplicationData model.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            abn = data.get("abn")
            acn = data.get("acn")
            contact_name = data.get("contact_name")
            amount_requested = Decimal(str(data.get("amount_requested", 0)))
            bureau_token = data.get("bureau_token")
            bankstatements_token = data.get("bankstatements_token")
            accounting_token = data.get("accounting_token")
            ppsr_token = data.get("ppsr_token")
            originator = data.get("originator", "Shift")
            product = data.get("product", "Trade Finance")

            if not abn or not acn or not contact_name:
                return JsonResponse({"success": False, "error": "Missing required fields."}, status=400)

            # Save data to TF_ApplicationData
            application = TF_ApplicationData.objects.create(
                abn=abn,
                acn=acn,
                contact_name=contact_name,
                amount_requested=amount_requested,
                bureau_token=bureau_token,
                bankstatements_token=bankstatements_token,
                accounting_token=accounting_token,
                ppsr_token=ppsr_token,
                originator=originator,
                application_time=timezone.now(),
                product=product
            )

            return JsonResponse({"success": True, "transaction_id": str(application.transaction_id)})

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)



def fetch_bureau_token():
    """
    Fetch Bureau Token from CreditorWatch API.
    """
    try:
        response = requests.post("https://api-sandbox.creditorwatch.com.au/login", json={
            "username": "sandbox@cw.com.au",
            "password": "s@ndb0x@cw"
        })
        response.raise_for_status()
        data = response.json()
        return data.get("token", None)
    except requests.exceptions.RequestException:
        return None  # If API call fails, token will be null



from django.http import JsonResponse
from .models import TF_ApplicationData, TF_InvoiceData

def tf_get_invoices(request):
    abn = request.GET.get("abn", "").strip()
    transaction_id = request.GET.get("transaction_id", "").strip()

    if not abn:
        return JsonResponse({"success": False, "error": "No ABN provided"}, status=400)

    latest_application = TF_ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()
    if not latest_application:
        return JsonResponse({"success": False, "error": f"No application found for ABN: {abn}"}, status=404)

    transaction_id = transaction_id or str(latest_application.transaction_id)

    invoices = TF_InvoiceData.objects.filter(transaction_id=transaction_id)

    if not invoices.exists():
        return JsonResponse({
            "success": False,
            "error": f"No invoices found for ABN: {abn} with Transaction ID: {transaction_id}"
        }, status=404)

    return JsonResponse({
        "success": True,
        "invoices": list(invoices.values())
    })


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from .models import TF_InvoiceData
import json

def TF_invoice_store(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            abn = data.get("abn")
            acn = data.get("acn")
            name = data.get("name")
            transaction_id = data.get("transaction_id")
            invoices = data.get("invoices", [])

            if not abn or not acn or not name or not transaction_id or not invoices:
                return JsonResponse({"success": False, "error": "Missing required fields."}, status=400)

            stored_count = 0

            for invoice in invoices:
                TF_InvoiceData.objects.create(
                    abn=abn,
                    acn=acn,
                    name=name,
                    transaction_id=transaction_id,
                    credit=invoice.get("credit"),
                    inv_number=invoice.get("inv_number"),
                    amount_due=invoice.get("amount_due"),
                    amount_funded=invoice.get("amount_due"),  # Optional: funding = due
                    date_funded=timezone.now()
                )
                stored_count += 1

            return JsonResponse({
                "success": True,
                "message": f"{stored_count} invoice(s) stored successfully.",
                "transaction_id": transaction_id
            })

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)








#--------#--------#--------#--------#--------
    
#   post data to application_aggregate service and efs_data_financial service


#--------#--------#--------#--------#--------





def tf_get_latest_transaction_id(request):
    abn = request.GET.get("abn", "").strip()
    if not abn:
        return JsonResponse({"success": False, "error": "No ABN provided"}, status=400)

    latest = TF_ApplicationData.objects.filter(abn=abn).order_by("-application_time", "-id").first()
    if not latest:
        return JsonResponse({"success": False, "error": f"No applications found for ABN: {abn}"}, status=404)

    return JsonResponse({"success": True, "transaction_id": str(latest.transaction_id)})



import os
import json
import logging
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import TF_ApplicationData, TF_InvoiceData

logger = logging.getLogger(__name__)

APPLICATION_AGGREGATE_BASE = os.getenv("APPLICATION_AGGREGATE_BASE", "http://127.0.0.1:8016")
EFS_DATA_FINANCIAL_BASE   = os.getenv("EFS_DATA_FINANCIAL_BASE",   "http://127.0.0.1:8019/api/financial")



def post_payload(base_url: str, endpoint: str, payload: dict):
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
    except requests.RequestException as e:
        return {"url": url, "status": 0, "body": {"error": str(e)}}

    try:
        body = resp.json()
    except ValueError:
        body = resp.text

    return {"url": url, "status": resp.status_code, "body": body}


def _latest_tf_application():
    """
    Returns latest TF_ApplicationData.
    Uses application_time DESC, then id DESC to handle nulls/ties.
    """
    return TF_ApplicationData.objects.order_by("-application_time", "-id").first()


@csrf_exempt
def send_tf_application_data(request):
    """
    Keeps the same URL + signature, but:
    - ABN is OPTIONAL (ignored if missing)
    - If ABN is provided, uses latest for that ABN
    - If ABN missing, uses latest overall TF application
    Posts to application_aggregate/receive-tf-application-data/
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body or "{}")
        abn = (data.get("abn") or "").strip()

        # ✅ Prefer ABN-specific latest if provided; otherwise latest overall
        if abn:
            latest = TF_ApplicationData.objects.filter(abn=abn).order_by("-application_time", "-id").first()
        else:
            latest = _latest_tf_application()

        if not latest:
            return JsonResponse({"success": False, "error": "No TF_ApplicationData found"}, status=404)

        txid = str(latest.transaction_id)

        application_payload = {
            "transaction_id": txid,
            "application_time": latest.application_time.isoformat() if latest.application_time else None,
            "abn": latest.abn,
            "acn": latest.acn,

            # ✅ aggregate expects company_name
            "company_name": latest.contact_name,
            "contact_name": latest.contact_name,

            "amount_requested": str(latest.amount_requested) if latest.amount_requested is not None else None,
            "bureau_token": latest.bureau_token,
            "bankstatements_token": latest.bankstatements_token,
            "accounting_token": latest.accounting_token,
            "ppsr_token": latest.ppsr_token,
            "contact_email": latest.contact_email,
            "contact_number": latest.contact_number,
            "originator": latest.originator,
            "product": latest.product or "Trade Finance",
            "state": getattr(latest, "state", None) or "sales_just_in",
        }

        downstream = post_payload(APPLICATION_AGGREGATE_BASE, "receive-tf-application-data/", application_payload)

        if downstream["status"] < 200 or downstream["status"] >= 300:
            logger.warning("Aggregate rejected TF app payload %s", downstream)
            return JsonResponse(
                {"success": False, "error": "application_aggregate rejected TF application payload", "downstream": downstream},
                status=502,
            )

        return JsonResponse({"success": True, "downstream": downstream, "transaction_id": txid})

    except Exception as e:
        logger.exception("send_tf_application_data failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def send_tf_invoice_data(request):
    """
    Keeps the same URL + signature, but:
    - transaction_id is OPTIONAL
    - If transaction_id provided, use it
    - Else, use latest TF application transaction_id
    Posts to efs_data_financial/receive-tf-invoice-data/
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body or "{}")

        transaction_id = (data.get("transaction_id") or "").strip()
        abn = (data.get("abn") or "").strip()

        latest_app = None

        # ✅ If txid not provided, derive from latest TF app (ABN-specific if given)
        if not transaction_id:
            if abn:
                latest_app = TF_ApplicationData.objects.filter(abn=abn).order_by("-application_time", "-id").first()
            else:
                latest_app = _latest_tf_application()

            if not latest_app:
                return JsonResponse({"success": False, "error": "No TF_ApplicationData found to derive transaction_id"}, status=404)

            transaction_id = str(latest_app.transaction_id)
        else:
            # ✅ If txid provided, still try to fetch app for enrichment (optional)
            latest_app = TF_ApplicationData.objects.filter(transaction_id=transaction_id).order_by("-application_time", "-id").first()
            if not latest_app and abn:
                latest_app = TF_ApplicationData.objects.filter(abn=abn).order_by("-application_time", "-id").first()

        invoices = TF_InvoiceData.objects.filter(transaction_id=transaction_id)
        if not invoices.exists():
            return JsonResponse({"success": False, "error": f"No TF invoices found for TxID {transaction_id}"}, status=404)

        fallback_abn = (latest_app.abn if latest_app and latest_app.abn else abn) or None
        fallback_acn = (latest_app.acn if latest_app and latest_app.acn else None)

        payload = {
            "invoices": [
                {
                    "transaction_id": inv.transaction_id or transaction_id,
                    "abn": inv.abn or fallback_abn,
                    "acn": inv.acn or fallback_acn,
                    "name": inv.name,

                    # ✅ receiver uses debtor; TF model uses credit
                    "debtor": inv.credit,

                    "date_funded": inv.date_funded.isoformat() if inv.date_funded else None,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,

                    "amount_funded": str(inv.amount_funded) if inv.amount_funded is not None else None,
                    "amount_due": str(inv.amount_due) if inv.amount_due is not None else None,
                    "discount_percentage": str(inv.discount_percentage) if inv.discount_percentage is not None else None,
                    "face_value": str(inv.face_value) if inv.face_value is not None else None,

                    "sif_batch": inv.sif_batch,
                    "inv_number": inv.inv_number,

                    # optional compatibility
                    "invoice_number": inv.inv_number,
                }
                for inv in invoices
            ]
        }

        downstream = post_payload(EFS_DATA_FINANCIAL_BASE, "receive-tf-invoice-data/", payload)

        if downstream["status"] < 200 or downstream["status"] >= 300:
            logger.warning("efs_data_financial rejected TF invoice payload %s", downstream)
            return JsonResponse(
                {"success": False, "error": "efs_data_financial rejected TF invoice payload", "downstream": downstream},
                status=502,
            )

        return JsonResponse({"success": True, "downstream": downstream, "transaction_id": transaction_id})

    except Exception as e:
        logger.exception("send_tf_invoice_data failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
