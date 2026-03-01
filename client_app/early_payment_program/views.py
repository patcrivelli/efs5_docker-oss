from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone

import csv
import uuid
from decimal import Decimal

from .models import scf_InvoiceData


def index(request):
    return render(request, "early_payment_program/index.html")


@require_POST
def upload_invoices(request):
    """
    Handles invoice uploads from Upload Modal when data_type = 'invoices'

    ✅ Creates ONLY scf_InvoiceData rows
    ❌ Does NOT create scf_ApplicationData
    """

    uploaded_file = request.FILES.get("file")
    abn = request.POST.get("abn", "").strip()
    contact_name = request.user.username if request.user.is_authenticated else "Unknown"

    if not uploaded_file:
        return JsonResponse(
            {"success": False, "error": "No file uploaded"},
            status=400
        )

    # One transaction_id per upload batch
    transaction_id = str(uuid.uuid4())

    try:
        decoded = uploaded_file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded)

        invoices = []

        with transaction.atomic():
            for row in reader:
                invoices.append(
                    scf_InvoiceData(
                        transaction_id=transaction_id,
                        abn=abn,
                        name=contact_name,
                        debtor=row.get("debtor"),
                        inv_number=row.get("inv_number"),
                        due_date=row.get("due_date") or None,
                        date_funded=row.get("date_funded") or None,
                        amount_funded=Decimal(row.get("amount_funded") or 0),
                        amount_due=Decimal(row.get("amount_due") or 0),
                        face_value=Decimal(row.get("face_value") or 0),
                        discount_percentage=Decimal(row.get("discount_percentage") or 0),
                        sif_batch=row.get("sif_batch") or None,
                    )
                )

            scf_InvoiceData.objects.bulk_create(invoices)

        return JsonResponse({
            "success": True,
            "transaction_id": transaction_id,
            "invoices_created": len(invoices),
        })

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500
        )


from django.http import JsonResponse
from .models import scf_InvoiceData


def fetch_scf_invoices_by_name(request):
    """
    Fetch SCF invoices by matching `name`
    (used for Early Payment Program display)
    """

    name = request.GET.get("name")

    if not name:
        return JsonResponse({"invoices": []})

    invoices = scf_InvoiceData.objects.filter(
        name=name
    ).order_by("due_date")

    data = [
        {
            "invoice_number": inv.inv_number,
            "created_at": inv.date_funded.strftime("%b %d, %Y") if inv.date_funded else "",
            "repayment_date": inv.due_date.strftime("%b %d, %Y") if inv.due_date else "",
            "amount_due": float(inv.amount_due or 0),
            "status": "Available",  # SCF invoices are implicitly available
        }
        for inv in invoices
    ]

    return JsonResponse({"invoices": data})


from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone

import json
import uuid
from decimal import Decimal
from datetime import datetime

from .models import (
    scf_ApplicationData,
    scf_ApplicationInvoiceData,
    scf_InvoiceData,  # ✅ add
)


def _parse_date(value):
    """
    Accepts:
      - 'YYYY-MM-DD'
      - 'Jan 24, 2026' (or similar)
      - datetime/date objects
    Returns date or None.
    """
    if not value:
        return None

    # Already date/datetime?
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass

    if isinstance(value, str):
        v = value.strip()
        # ISO
        try:
            return datetime.strptime(v, "%Y-%m-%d").date()
        except Exception:
            pass
        # 'Jan 24, 2026'
        try:
            return datetime.strptime(v, "%b %d, %Y").date()
        except Exception:
            pass

    return None


@require_POST
def submit_scf_funding_application(request):
    """
    Creates:
      - 1 scf_ApplicationData
      - N scf_ApplicationInvoiceData
    Linked via shared transaction_id (UUID)

    ✅ Updated:
    - If abn/acn/name not provided, derive from scf_InvoiceData using invoice_number(s)
    - Populates ABN/ACN/Name into BOTH application + application invoices
    """
    try:
        data = json.loads(request.body or "{}")

        # Values from client (may be blank on this page)
        abn = (data.get("abn") or "").strip()
        acn = (data.get("acn") or "").strip()
        name = (data.get("name") or "").strip()
        originator = (data.get("originator") or "Shift").strip()
        invoices = data.get("invoices") or []

        if not invoices:
            return JsonResponse({"success": False, "error": "No invoices selected"}, status=400)

        # ✅ collect selected invoice numbers from payload
        selected_inv_numbers = []
        for inv in invoices:
            inv_no = (inv.get("invoice_number") or inv.get("inv_number") or "").strip()
            if inv_no:
                selected_inv_numbers.append(inv_no)

        if not selected_inv_numbers:
            return JsonResponse({"success": False, "error": "Selected invoices missing invoice_number"}, status=400)

        # ✅ If ABN/ACN/Name missing, derive from scf_InvoiceData
        derived_rows = list(
            scf_InvoiceData.objects.filter(inv_number__in=selected_inv_numbers).values(
                "inv_number", "abn", "acn", "name", "debtor",
                "date_funded", "due_date", "amount_due", "face_value"
            )
        )

        if not derived_rows:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Could not derive ABN/ACN/Name (no matching scf_InvoiceData found for selected invoices).",
                    "selected_inv_numbers": selected_inv_numbers[:10],
                },
                status=400,
            )

        # Map by inv_number for quick lookup
        inv_map = {r["inv_number"]: r for r in derived_rows}

        # Choose canonical derived metadata from first matched invoice
        first = derived_rows[0]
        derived_abn = (first.get("abn") or "").strip()
        derived_acn = (first.get("acn") or "").strip()
        derived_name = (first.get("name") or "").strip()

        # If client did not provide, fill from derived
        if not abn:
            abn = derived_abn
        if not acn:
            acn = derived_acn
        if not name:
            name = derived_name

        # Sanity: we need at least ABN or ACN to be useful downstream
        if not abn and not acn:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Cannot create SCF application without ABN/ACN (not provided and not derivable from scf_InvoiceData).",
                },
                status=400,
            )

        # Calculate amount_requested from payload (or fallback to stored values)
        amount_requested = Decimal("0.00")
        for inv in invoices:
            amt = inv.get("amount_due")
            if amt is None:
                # fallback to stored
                inv_no = (inv.get("invoice_number") or inv.get("inv_number") or "").strip()
                stored = inv_map.get(inv_no)
                amt = stored.get("amount_due") if stored else 0
            amount_requested += Decimal(str(amt or 0))

        transaction_id = uuid.uuid4()

        with transaction.atomic():
            application = scf_ApplicationData.objects.create(
                transaction_id=transaction_id,
                application_time=timezone.now(),
                contact_name=name,
                abn=abn,
                acn=acn,
                originator=originator,
                product="Supply Chain Finance",
                amount_requested=amount_requested,

                # placeholders as you had
                bureau_token="BUREAU_TOKEN_PLACEHOLDER",
                accounting_token="ACCOUNTING_TOKEN_PLACEHOLDER",
                bankstatements_token="BANKSTATEMENTS_TOKEN_PLACEHOLDER",
                ppsr_token="PPSR_TOKEN_PLACEHOLDER",
            )

            app_invoices = []
            for inv in invoices:
                inv_no = (inv.get("invoice_number") or inv.get("inv_number") or "").strip()
                stored = inv_map.get(inv_no, {})

                debtor = (inv.get("debtor") or stored.get("debtor") or "").strip() or None

                due_date = _parse_date(inv.get("repayment_date")) or stored.get("due_date") or None
                date_funded = stored.get("date_funded") or timezone.now().date()

                amount_due = inv.get("amount_due")
                if amount_due is None:
                    amount_due = stored.get("amount_due") or 0

                face_value = stored.get("face_value")
                if face_value is None:
                    face_value = amount_due

                app_invoices.append(
                    scf_ApplicationInvoiceData(
                        transaction_id=transaction_id,
                        abn=abn,
                        acn=acn,
                        name=name,
                        debtor=debtor,
                        inv_number=inv_no,
                        date_funded=date_funded,
                        due_date=due_date,
                        face_value=Decimal(str(face_value or 0)),
                        amount_due=Decimal(str(amount_due or 0)),
                        amount_funded=Decimal("0.00"),
                        discount_percentage=Decimal("0.00"),
                        sif_batch=None,
                    )
                )

            scf_ApplicationInvoiceData.objects.bulk_create(app_invoices)

        return JsonResponse(
            {
                "success": True,
                "transaction_id": str(transaction_id),
                "invoices_created": len(app_invoices),
                "abn": abn,
                "acn": acn,
                "name": name,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

import os
import json
import logging
import requests

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import scf_ApplicationData, scf_ApplicationInvoiceData

logger = logging.getLogger(__name__)

# ✅ Match your other products
APPLICATION_AGGREGATE_BASE = os.getenv("APPLICATION_AGGREGATE_BASE", "http://127.0.0.1:8016/api")
EFS_DATA_FINANCIAL_BASE    = os.getenv("EFS_DATA_FINANCIAL_BASE",    "http://127.0.0.1:8019/api/financial")


def post_payload(base_url: str, endpoint: str, payload: dict):
    """
    Posts JSON to downstream service and returns structured result.
    Never raises.
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


def _get_latest_scf_transaction_id():
    """
    Latest SCF transaction = newest row in scf_ApplicationInvoiceData (created_at DESC).
    """
    latest_row = scf_ApplicationInvoiceData.objects.order_by("-created_at").first()
    return str(latest_row.transaction_id) if latest_row else None


@csrf_exempt
def send_scf_application_data(request):
    """
    SCF Application → application_aggregate
    - No ABN required
    - Uses latest transaction_id from scf_ApplicationInvoiceData.created_at
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        txid = _get_latest_scf_transaction_id()
        if not txid:
            return JsonResponse({"success": False, "error": "No SCF application invoice rows found"}, status=404)

        app = scf_ApplicationData.objects.filter(transaction_id=txid).first()
        if not app:
            return JsonResponse(
                {"success": False, "error": f"No scf_ApplicationData found for transaction_id={txid}"},
                status=404,
            )

        application_payload = {
            "transaction_id": txid,
            "application_time": app.application_time.isoformat() if app.application_time else None,
            "abn": app.abn,
            "acn": app.acn,

            # aggregate typically expects company_name
            "company_name": app.contact_name,
            "contact_name": app.contact_name,

            "bankstatements_token": app.bankstatements_token,
            "bureau_token": app.bureau_token,
            "accounting_token": app.accounting_token,
            "ppsr_token": app.ppsr_token,
            "contact_email": app.contact_email,
            "contact_number": app.contact_number,
            "originator": app.originator,
            "amount_requested": str(app.amount_requested) if app.amount_requested is not None else None,
            "product": app.product or "SCF / Early Payments",

            # if your aggregate requires state
            "state": "sales_just_in",
        }

        downstream = post_payload(APPLICATION_AGGREGATE_BASE, "receive-scf-application-data/", application_payload)

        if downstream["status"] < 200 or downstream["status"] >= 300:
            logger.warning("application_aggregate rejected SCF app payload %s", downstream)
            return JsonResponse(
                {"success": False, "error": "application_aggregate rejected SCF application payload", "downstream": downstream},
                status=502,
            )

        return JsonResponse({"success": True, "transaction_id": txid, "downstream": downstream}, status=200)

    except Exception as e:
        logger.exception("send_scf_application_data failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def send_scf_invoice_data(request):
    """
    SCF Invoices → efs_data_financial
    - transaction_id optional
    - If not supplied, uses latest transaction_id from scf_ApplicationInvoiceData.created_at
    - Sends invoice rows from scf_ApplicationInvoiceData (NOT scf_InvoiceData)
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body or "{}")
        txid = (data.get("transaction_id") or "").strip()

        if not txid:
            txid = _get_latest_scf_transaction_id()

        if not txid:
            return JsonResponse({"success": False, "error": "No SCF transaction found to post invoices"}, status=404)

        inv_qs = scf_ApplicationInvoiceData.objects.filter(transaction_id=txid).order_by("created_at")
        if not inv_qs.exists():
            return JsonResponse(
                {"success": False, "error": f"No scf_ApplicationInvoiceData found for transaction_id={txid}"},
                status=404,
            )

        invoices_payload = {
            "invoices": [
                {
                    "transaction_id": txid,
                    "abn": inv.abn,
                    "acn": inv.acn,
                    "name": inv.name,
                    "debtor": inv.debtor,
                    "date_funded": inv.date_funded.isoformat() if inv.date_funded else None,
                    "due_date": inv.due_date.isoformat() if inv.due_date else None,
                    "amount_funded": str(inv.amount_funded) if inv.amount_funded is not None else None,
                    "amount_due": str(inv.amount_due) if inv.amount_due is not None else None,
                    "discount_percentage": str(inv.discount_percentage) if inv.discount_percentage is not None else None,
                    "face_value": str(inv.face_value) if inv.face_value is not None else None,
                    "sif_batch": inv.sif_batch,

                    # ✅ keep both for receiver compatibility
                    "inv_number": inv.inv_number,
                    "invoice_number": inv.inv_number,
                }
                for inv in inv_qs
            ]
        }

        downstream = post_payload(EFS_DATA_FINANCIAL_BASE, "receive-scf-invoice-data/", invoices_payload)

        if downstream["status"] < 200 or downstream["status"] >= 300:
            logger.warning("efs_data_financial rejected SCF invoice payload %s", downstream)
            return JsonResponse(
                {"success": False, "error": "efs_data_financial rejected SCF invoice payload", "downstream": downstream},
                status=502,
            )

        return JsonResponse({"success": True, "transaction_id": txid, "downstream": downstream}, status=200)

    except Exception as e:
        logger.exception("send_scf_invoice_data failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
