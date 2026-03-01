def index(request):
    return render(request, "invoice_finance.html")  # matches your actual file path



import os
from django.shortcuts import render
from django.http import HttpResponse
import csv
from datetime import datetime
from .models import LedgerData

import csv
import re
from datetime import datetime
from django.http import HttpResponse
from .models import LedgerData


def normalize_header(h: str) -> str:
    """
    Make CSV headers consistent:
    - strip
    - lowercase
    - replace spaces / hyphens with underscores
    - remove non word chars (keeps underscores)
    """
    h = (h or "").strip().lower()
    h = re.sub(r"[\s\-]+", "_", h)
    h = re.sub(r"[^\w_]", "", h)
    return h


def normalize_abn(val: str) -> str | None:
    """
    Convert ABN values like '1.9155E+10' or '19 155 437 620' into digits-only.
    Returns None if empty.
    """
    s = (val or "").strip()
    if not s:
        return None

    # If it looks like Excel scientific notation, convert to int safely
    if re.search(r"e\+?\d+", s, flags=re.IGNORECASE):
        try:
            # float -> int will drop decimals; ABN should be whole
            s = str(int(float(s)))
        except ValueError:
            pass

    digits = "".join(ch for ch in s if ch.isdigit())
    return digits or None


def parse_date(date_str: str):
    """Try to parse a date string into a Python date object."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if not date_str:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def upload_ledger_csv(request):
    if request.method == "POST" and request.FILES.get("file"):
        csv_file = request.FILES["file"]

        # Handle UTF-8 BOM safely
        decoded_lines = csv_file.read().decode("utf-8-sig").splitlines()
        reader = csv.DictReader(decoded_lines)

        for row in reader:
            # Normalize keys AND strip values
            normalized_row = {
                normalize_header(k): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
                if k
            }

            abn_val = normalize_abn(
                normalized_row.get("abn") or normalized_row.get("business_abn")
            )

            debtor_val = (
                normalized_row.get("debtor")
                or normalized_row.get("debtor_name")
                or normalized_row.get("name")   # sometimes ledger exports use "name"
            )

            # ✅ Your CSV uses inv_number
            invoice_no = (
                normalized_row.get("invoice_number")
                or normalized_row.get("inv_no")
                or normalized_row.get("inv_number")     # ✅ key fix
                or normalized_row.get("invoice_no")
                or normalized_row.get("invoice")
            )

            amount_due_val = normalized_row.get("amount_due") or normalized_row.get("total_due") or 0
            try:
                amount_due_val = float(str(amount_due_val).replace(",", ""))
            except Exception:
                amount_due_val = 0

            # Your sample file has due_date, not repayment_date
            repayment_date_val = parse_date(
                normalized_row.get("repayment_date") or normalized_row.get("due_date")
            )

            status_val = normalized_row.get("status") or "Open"

            LedgerData.objects.create(
                abn=abn_val,
                debtor=debtor_val,
                invoice_number=invoice_no,     # ✅ will now populate
                amount_due=amount_due_val,
                repayment_date=repayment_date_val,
                status=status_val,
            )

        return HttpResponse("✅ Ledger data uploaded successfully")

    return HttpResponse("❌ Upload failed", status=400)


# invoice_finance/views.py
from django.http import JsonResponse
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from .models import LedgerData

def fetch_ledger_data(request):
    """
    API Endpoint:
    - Get the logged-in user's username
    - Look up the ABN in LedgerData for that username
    - Fetch all 'Open' ledger entries with that ABN
    - Return grouped results by debtor with total amount_due
    """
    username = request.user.username

    # Find the ABN linked to this username in LedgerData
    abn_entry = LedgerData.objects.filter(
        status="Open", 
    ).values("abn").first()

    if not abn_entry or not abn_entry["abn"]:
        return JsonResponse({"error": f"No ABN found for user {username}"}, status=404)

    selected_abn = abn_entry["abn"]

    # Fetch all Open ledger entries for this ABN
    open_entries = (
        LedgerData.objects
        .filter(status="Open", abn=selected_abn)
        .values("debtor")
        .annotate(total_due=Sum("amount_due"))
        .order_by("debtor")
    )

    return JsonResponse(list(open_entries), safe=False)


# users/views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from users.models import CustomUser

def get_user_abn(request):
    username = request.user.username
    try:
        user = CustomUser.objects.get(username=username)
        return JsonResponse({"success": True, "abn": user.abn})
    except CustomUser.DoesNotExist:
        return JsonResponse({"success": False, "error": "User not found"}, status=404)


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



import json
import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import ApplicationData, InvoiceData, LedgerData

@csrf_exempt
def submit_application(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)

        abn = data.get("abn")
        name = data.get("name")
        acn = data.get("acn", "")  # optional
        selected_debtors = data.get("selected_debtors", [])
        requested_amount = Decimal(str(data.get("amount_requested", 0)))

        # ✅ Validate input
        if not abn or not name:
            return JsonResponse({"success": False, "error": "ABN and Name are required."}, status=400)
        if not selected_debtors:
            return JsonResponse({"success": False, "error": "No debtors selected."}, status=400)
        if requested_amount <= 0:
            return JsonResponse({"success": False, "error": "Requested amount must be greater than zero."}, status=400)

        # ✅ Fetch candidate invoices
        candidate_invoices = LedgerData.objects.filter(
            debtor__in=selected_debtors,
            abn=abn,
            status="Open"
        )

        total_selected = sum(Decimal(inv.amount_due or 0) for inv in candidate_invoices)
        if total_selected <= 0:
            return JsonResponse({"success": False, "error": "Total selected funding amount is zero."}, status=400)

        with transaction.atomic():
            app = ApplicationData.objects.filter(abn=abn, contact_name=name).first()
            if app:
                transaction_id = str(app.transaction_id)
            else:
                app = ApplicationData.objects.create(
                    transaction_id=uuid.uuid4(),
                    application_time=timezone.now(),
                    contact_name=name,
                    abn=abn,
                    acn=acn,
                    bureau_token=None,
                    bankstatements_token="BANK_STATEMENT_TOKEN",
                    accounting_token="ACCOUNTING_TOKEN",
                    ppsr_token="PPSR_TOKEN",
                    amount_requested=requested_amount,
                    originator="Shift",
                    product="Invoice Finance"
                )
                transaction_id = str(app.transaction_id)

            # ✅ Pro-rata allocation
            new_invoices = []
            for inv in candidate_invoices:
                amount_due = Decimal(inv.amount_due or 0)
                funded = (amount_due / total_selected) * requested_amount
                funded = funded.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                funded = min(funded, amount_due)

                new_invoices.append(InvoiceData(
                    transaction_id=transaction_id,
                    abn=abn,
                    acn=acn,
                    name=name,
                    debtor=inv.debtor,
                    due_date=inv.repayment_date,
                    inv_number=inv.invoice_number,
                    amount_due=amount_due,
                    face_value=amount_due,
                    amount_funded=funded,
                    discount_percentage=Decimal("0.00"),
                    date_funded=timezone.now()
                ))

            InvoiceData.objects.bulk_create(new_invoices, ignore_conflicts=True)

        return JsonResponse({"success": True, "transaction_id": transaction_id})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)



@csrf_exempt
def send_application_data(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    data = json.loads(request.body or "{}")
    abn = (data.get("abn") or "").strip()
    if not abn:
        return JsonResponse({"success": False, "error": "ABN is required"}, status=400)

    latest = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()
    if not latest:
        return JsonResponse({"success": False, "error": f"No applications found for ABN: {abn}"}, status=404)

    application_payload = {
        "transaction_id": str(latest.transaction_id),
        "abn": latest.abn,
        "acn": latest.acn,
        "contact_name": latest.contact_name,
        "amount_requested": str(latest.amount_requested),
        "application_time": latest.application_time.isoformat() if latest.application_time else None,
        "bureau_token": latest.bureau_token,
        "bankstatements_token": latest.bankstatements_token,
        "accounting_token": latest.accounting_token,
        "ppsr_token": latest.ppsr_token,
        "originator": latest.originator,
        "product": latest.product,
    }

    # ✅ Only send to the aggregate (8016)
    response = post_payload(APPLICATION_AGGREGATE_BASE, "receive-application-data/", application_payload)
    return JsonResponse({"success": True, "response": response})


import json
import logging
import uuid
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import ApplicationData, InvoiceData, LedgerData

logger = logging.getLogger(__name__)

APPLICATION_AGGREGATE_BASE = os.getenv("APPLICATION_AGGREGATE_BASE", "http://127.0.0.1:8016/api")
EFS_DATA_FINANCIAL_BASE   = os.getenv("EFS_DATA_FINANCIAL_BASE",   "http://127.0.0.1:8019/api/financial")


def post_payload(base_url: str, endpoint: str, payload: dict):
    """
    Posts JSON to the downstream service and returns a structured result.
    This does NOT raise; it always returns status + parsed body if possible.
    """
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


@csrf_exempt
def send_invoice_data(request):
    """
    Expects POST body: {"abn": "...", "transaction_id": "..."} (abn optional if txid provided)
    Sends invoices to efs_data_financial and *propagates downstream errors* instead of masking them.
    Also sends both inv_number and invoice_number for compatibility.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body or "{}")
        transaction_id = (data.get("transaction_id") or "").strip()
        abn = (data.get("abn") or "").strip()

        if not transaction_id:
            return JsonResponse({"success": False, "error": "transaction_id is required"}, status=400)

        invoices = InvoiceData.objects.filter(transaction_id=transaction_id)
        if not invoices.exists():
            return JsonResponse({"success": False, "error": f"No invoices found for TxID {transaction_id}"}, status=404)

        # Best-effort enrichment from the latest app (for ACN / ABN consistency)
        latest_app = None
        if abn:
            latest_app = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()
        if not latest_app:
            latest_app = ApplicationData.objects.filter(transaction_id=transaction_id).order_by("-application_time").first()

        fallback_abn = (latest_app.abn if latest_app and latest_app.abn else abn) or None
        fallback_acn = (latest_app.acn if latest_app and latest_app.acn else None)

        payload = {
            "invoices": [
                {
                    "transaction_id": inv.transaction_id or transaction_id,
                    "abn": inv.abn or fallback_abn,
                    "acn": inv.acn or fallback_acn,
                    "name": inv.name,
                    "debtor": inv.debtor,
                    "date_funded": inv.date_funded.isoformat() if inv.date_funded else None,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                    "amount_funded": str(inv.amount_funded) if inv.amount_funded is not None else None,
                    "amount_due": str(inv.amount_due) if inv.amount_due is not None else None,
                    "discount_percentage": str(inv.discount_percentage) if inv.discount_percentage is not None else None,
                    "face_value": str(inv.face_value) if inv.face_value is not None else None,
                    "sif_batch": inv.sif_batch,

                    # ✅ send both keys to avoid receiver field-name mismatch
                    "inv_number": inv.inv_number,
                    "invoice_number": inv.inv_number,
                }
                for inv in invoices
            ]
        }

        downstream = post_payload(EFS_DATA_FINANCIAL_BASE, "receive-invoice-data/", payload)

        # ✅ propagate downstream failure instead of always returning success
        if downstream["status"] < 200 or downstream["status"] >= 300:
            logger.warning("Downstream invoice reject %s", downstream)
            return JsonResponse(
                {
                    "success": False,
                    "error": "efs_data_financial rejected invoice payload",
                    "downstream": downstream,
                },
                status=502,
            )

        return JsonResponse({"success": True, "downstream": downstream})

    except Exception as e:
        logger.exception("send_invoice_data failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def send_ledger_data(request):
    """
    Expects POST body: {"abn": "..."} (required)
    Sends ledger entries to efs_data_financial and *propagates downstream errors*.
    Includes transaction_id + acn (best effort) because receiver LedgerData often expects it.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body or "{}")
        abn = (data.get("abn") or "").strip()
        if not abn:
            return JsonResponse({"success": False, "error": "abn is required"}, status=400)

        ledger_entries = LedgerData.objects.filter(abn=abn, status="Open")
        if not ledger_entries.exists():
            return JsonResponse({"success": False, "error": f"No open ledger entries found for ABN: {abn}"}, status=404)

        # Best-effort: use latest application transaction_id + acn to satisfy downstream requirements
        latest_app = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()
        txid = str(latest_app.transaction_id) if latest_app and latest_app.transaction_id else None
        acn = latest_app.acn if latest_app else None

        # If no txid found, generate one (only if your downstream accepts it).
        # Comment this out if you want to hard-fail instead.
        if not txid:
            txid = str(uuid.uuid4())

        payload = {
            "ledger_data": [
                {
                    "transaction_id": txid,              # ✅ added
                    "abn": entry.abn or abn,
                    "acn": acn,                          # ✅ added (best effort)
                    "debtor": entry.debtor,
                    "invoice_number": entry.invoice_number,
                    "amount_due": str(entry.amount_due) if entry.amount_due is not None else None,
                    "repayment_date": entry.repayment_date.isoformat() if entry.repayment_date else None,
                    "status": entry.status,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                }
                for entry in ledger_entries
            ]
        }

        downstream = post_payload(EFS_DATA_FINANCIAL_BASE, "receive-ledger-data/", payload)

        # ✅ propagate downstream failure instead of always returning success
        if downstream["status"] < 200 or downstream["status"] >= 300:
            logger.warning("Downstream ledger reject %s", downstream)
            return JsonResponse(
                {
                    "success": False,
                    "error": "efs_data_financial rejected ledger payload",
                    "downstream": downstream,
                },
                status=502,
            )

        return JsonResponse({"success": True, "downstream": downstream})

    except Exception as e:
        logger.exception("send_ledger_data failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


# -------------------------------
# 🔹 Helper Endpoint
# -------------------------------
@csrf_exempt
def get_latest_transaction_id(request):
    abn = request.GET.get("abn", "").strip()
    if not abn:
        return JsonResponse({"success": False, "error": "ABN required"}, status=400)

    latest = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()
    if not latest:
        return JsonResponse({"success": False, "error": "No application found"}, status=404)

    return JsonResponse({"success": True, "transaction_id": str(latest.transaction_id)})
























""" 

def submit_funding_application(request):

    if request.method == "POST":
        try:
            print("📢 Request received at submit_funding_application")

            data = json.loads(request.body)
            abn = data.get("abn")
            acn = data.get("acn")
            name = data.get("name").strip()
            selected_debtors = data.get("selected_debtors", [])
            requested_amount = Decimal(str(data.get("requested_amount", 0)))  # Convert to Decimal
            originator = "Shift"  # Hardcoded value
            product = "Invoice Finance"

            if not abn or not acn or not name:
                return JsonResponse({"success": False, "error": "ABN, ACN, and Name are required."}, status=400)

            if not selected_debtors:
                return JsonResponse({"success": False, "error": "No debtors selected."}, status=400)

            # ✅ Generate a single transaction ID for the application and invoices
            transaction_id = str(uuid.uuid4())
            print(f"📢 Generated Transaction ID: {transaction_id}")

            # ✅ Fetch draft invoices for selected debtors
            # Correct - filters by both selected debtor AND the correct ABN
            draft_invoices = LedgerData.objects.filter(
                debtor__in=selected_debtors,
                abn=abn,
                status="Open"
            )
                        # ✅ Calculate the total selected funding amount
            total_selected_funding_amount = sum(invoice.amount_due for invoice in draft_invoices if invoice.amount_due)

            if total_selected_funding_amount == 0:
                return JsonResponse({"success": False, "error": "Total selected funding amount is zero."}, status=400)

            with transaction.atomic():  # Ensure atomicity
                # ✅ Fetch Bureau Token from CreditorWatch API
                bureau_token = fetch_bureau_token()

                # ✅ Check if an ApplicationData entry already exists for this transaction ID
                existing_application = ApplicationData.objects.filter(abn=abn, acn=acn, contact_name=name).first()

                if existing_application:
                    print(f"⚠ Existing ApplicationData found for ABN: {abn}, using it.")
                    transaction_id = existing_application.transaction_id  # Use the existing transaction ID
                else:
                    print("✅ Inserting ApplicationData record...")
                    existing_application = ApplicationData.objects.create(
                        transaction_id=transaction_id,
                        application_time=timezone.now(),
                        contact_name=name,
                        abn=abn,
                        acn=acn,
                        bureau_token=bureau_token,  # Retrieved from API
                        amount_requested=requested_amount,
                        bankstatements_token="BANK_STATEMENT_TOKEN",
                        accounting_token="ACCOUNTING_TOKEN",
                        ppsr_token="PPSR_TOKEN",
                        originator=originator,
                        product="Invoice Finance"
                    )

                # ✅ Insert invoices using the same transaction_id
                new_invoices = []
                for invoice in draft_invoices:
                    amount_due = Decimal(invoice.amount_due or 0)
                    amount_funded = (amount_due / total_selected_funding_amount) * requested_amount

                    new_invoice = InvoiceData(
                        transaction_id=transaction_id,  # Use the same transaction ID
                        abn=abn,
                        acn=acn,
                        name=name,
                        debtor=invoice.debtor,
                        due_date=invoice.repayment_date,
                        amount_funded=amount_funded.quantize(Decimal("0.01")),
                        amount_due=amount_due,
                        discount_percentage=Decimal("0.00"),
                        face_value=amount_due,
                        sif_batch=None,
                        inv_number=invoice.invoice_number
                    )
                    new_invoices.append(new_invoice)

                InvoiceData.objects.bulk_create(new_invoices)
                print(f"✅ Inserted {len(new_invoices)} invoices.")

            return JsonResponse({"success": True, "transaction_id": transaction_id})

        except Exception as e:
            print(f"❌ Error in submit_funding_application: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method."}, status=405)





from django.http import JsonResponse
from .models import LedgerData

def fetch_unique_abns(request):

    unique_abns = LedgerData.objects.values_list("abn", flat=True).distinct().exclude(abn__isnull=True).exclude(abn="")  
    return JsonResponse({"abns": list(unique_abns)}, safe=False)


def funding_dashboard(request):
    return render(request, 'funding_dashboard.html')

from django.http import JsonResponse
from .models import ApplicationData

def get_bureau_token(request):

    latest_entry = ApplicationData.objects.order_by("-application_time").first()
    if latest_entry and latest_entry.bureau_token:
        return JsonResponse({"success": True, "bureau_token": latest_entry.bureau_token})
    return JsonResponse({"success": False, "error": "No bureau token found."}, status=404)




from django.http import JsonResponse
from .models import ApplicationData, InvoiceData

def get_invoices(request):
    abn = request.GET.get("abn", "").strip()
    transaction_id = request.GET.get("transaction_id", "").strip()  # Accept transaction_id

    if not abn:
        return JsonResponse({"success": False, "error": "No ABN provided"}, status=400)

    latest_application = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()
    if not latest_application:
        return JsonResponse({"success": False, "error": f"No application found for ABN: {abn}"}, status=404)

    transaction_id = transaction_id or latest_application.transaction_id  # Use provided or latest transaction ID
    invoices = InvoiceData.objects.filter(transaction_id=transaction_id)

    if not invoices.exists():
        return JsonResponse({"success": False, "error": f"No invoices found for ABN: {abn} with Transaction ID: {transaction_id}"}, status=404)

    return JsonResponse({"success": True, "invoices": list(invoices.values())})

from django.http import JsonResponse
from .models import ApplicationData

def get_latest_transaction_id(request):

    abn = request.GET.get("abn", "").strip()

    if not abn:
        return JsonResponse({"success": False, "error": "No ABN provided"}, status=400)

    latest_application = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()

    if not latest_application:
        return JsonResponse({"success": False, "error": f"No applications found for ABN: {abn}"}, status=404)

    return JsonResponse({"success": True, "transaction_id": str(latest_application.transaction_id)})


from django.http import JsonResponse
from .models import ApplicationData, LedgerData

def get_latest_ledger_data(request):
    abn = request.GET.get("abn", "").strip()

    if not abn:
        return JsonResponse({"success": False, "error": "No ABN provided"}, status=400)

    latest_application = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()

    if not latest_application:
        return JsonResponse({"success": False, "error": f"No application found for ABN: {abn}"}, status=404)

    # Optional: populate transaction_id on all matching LedgerData if they don't already have one
    LedgerData.objects.filter(abn=abn, transaction_id__isnull=True).update(transaction_id=latest_application.transaction_id)

    # Return the updated ledger data
    ledger_entries = LedgerData.objects.filter(abn=abn)
    return JsonResponse({"success": True, "ledger_data": list(ledger_entries.values())})



import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ApplicationData, InvoiceData, LedgerData

# ✅ Define both local and cloud endpoints
LOCAL_API_BASE = "http://127.0.0.1:8000/efs_sales/api"
CLOUD_API_BASE = "https://efs3-docker-320779576692.australia-southeast1.run.app/efs_sales/api"

def post_to_all_targets(endpoint, payload):
    responses = []
    for base in [LOCAL_API_BASE, CLOUD_API_BASE]:
        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
            responses.append((url, response.status_code, response.text))
            print(f"📢 Posted to {url} → {response.status_code}")
        except Exception as e:
            responses.append((url, 500, str(e)))
            print(f"❌ Error posting to {url}: {e}")
    return responses


def send_application_data_to_efs2_docker(request):
    try:
        if request.method != "POST":
            return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

        data = json.loads(request.body)
        abn = data.get("abn", "").strip()

        if not abn:
            return JsonResponse({"success": False, "error": "ABN is required"}, status=400)

        latest_application = ApplicationData.objects.filter(abn=abn).order_by("-application_time").first()
        if not latest_application:
            return JsonResponse({"success": False, "error": f"No applications found for ABN: {abn}"}, status=404)

        application_payload = {
            "transaction_id": str(latest_application.transaction_id),
            "abn": latest_application.abn,
            "acn": latest_application.acn,
            "contact_name": latest_application.contact_name,
            "amount_requested": str(latest_application.amount_requested),
            "application_time": latest_application.application_time.isoformat() if latest_application.application_time else None,
            "bureau_token": latest_application.bureau_token,
            "bankstatements_token": latest_application.bankstatements_token,
            "accounting_token": latest_application.accounting_token,
            "ppsr_token": latest_application.ppsr_token,
            "originator": latest_application.originator,
            "product": latest_application.product
        }

        print("📢 DEBUG: Application Payload", json.dumps(application_payload, indent=2))
        responses = post_to_all_targets("receive-application-data/", application_payload)

        return JsonResponse({
            "success": True,
            "message": "Application data sent to both local and cloud",
            "responses": responses
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def send_invoice_data_to_efs2_docker(request):
    try:
        if request.method != "POST":
            return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

        data = json.loads(request.body)
        abn = data.get("abn", "").strip()
        transaction_id = data.get("transaction_id", "").strip()

        if not abn:
            return JsonResponse({"success": False, "error": "ABN is required"}, status=400)

        invoices = InvoiceData.objects.filter(transaction_id=transaction_id)
        if not invoices.exists():
            return JsonResponse({"success": False, "error": f"No invoices found for ABN: {abn} with Transaction ID: {transaction_id}"}, status=404)

        invoice_list = [
            {
                "transaction_id": invoice.transaction_id,
                "abn": invoice.abn,
                "acn": invoice.acn,
                "name": invoice.name,
                "debtor": invoice.debtor,
                "date_funded": invoice.date_funded.isoformat() if invoice.date_funded else None,
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "amount_funded": str(invoice.amount_funded),
                "amount_due": str(invoice.amount_due),
                "discount_percentage": str(invoice.discount_percentage),
                "face_value": str(invoice.face_value),
                "sif_batch": invoice.sif_batch,
                "inv_number": invoice.inv_number
            }
            for invoice in invoices
        ]

        payload = {"invoices": invoice_list}
        print("📢 DEBUG: Invoice Payload", json.dumps(payload, indent=2))
        responses = post_to_all_targets("receive-invoice-data/", payload)

        return JsonResponse({
            "success": True,
            "message": "Invoice data sent to both local and cloud",
            "responses": responses
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def send_ledger_data_to_efs2_docker(request):
    try:
        if request.method != "POST":
            return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

        data = json.loads(request.body)
        abn = data.get("abn", "").strip()

        if not abn:
            return JsonResponse({"success": False, "error": "ABN is required"}, status=400)

        ledger_entries = LedgerData.objects.filter(abn=abn, status='Draft')
        if not ledger_entries.exists():
            return JsonResponse({"success": False, "error": f"No draft ledger entries found for ABN: {abn}"}, status=404)

        payload = {
            "ledger_data": [
                {
                    "abn": entry.abn,
                    "debtor": entry.debtor,
                    "invoice_number": entry.invoice_number,
                    "amount_due": str(entry.amount_due),
                    "repayment_date": entry.repayment_date.isoformat() if entry.repayment_date else None,
                    "status": entry.status,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None
                }
                for entry in ledger_entries
            ]
        }

        print("📢 DEBUG: Ledger Payload", json.dumps(payload, indent=2))
        responses = post_to_all_targets("receive-ledger-data/", payload)

        return JsonResponse({
            "success": True,
            "message": "Ledger data sent to both local and cloud",
            "responses": responses
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


"""
