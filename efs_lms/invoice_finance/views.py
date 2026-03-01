# efs_lms/invoice_finance/views.py
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum, Max
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from .models import TransactionLedger, TransactionDetails
# If you also have repayments/drawdowns models in this app, import them as needed.
# from .models import InvoiceRepayments, Drawdown

def _amount(v):
    return v if isinstance(v, Decimal) else (Decimal(v) if v is not None else Decimal("0"))

def invoice_finance_page(request):
    """
    Build the context for the LMS Invoice Finance UI.
    Populates the Money Out table from TransactionLedger + TransactionDetails.
    """
    # --- Aggregate per-transaction invoice totals from details ---
    # totals_by_tx = { trans_id: {sum fields...} }
    totals_by_tx = defaultdict(lambda: {
        "total_amount_funded": Decimal("0"),
        "amount_repaid":      Decimal("0"),
        "amount_due":         Decimal("0"),
        "date_funded":        None,
    })

    # GROUP BY trans_id on details table
    for row in (
        TransactionDetails.objects
        .values("trans_id")
        .annotate(
            total_amount_funded=Sum("amount_funded"),
            amount_repaid=Sum("amount_repaid"),
            amount_due=Sum("amount_due"),
            date_funded=Max("date_funded"),
        )
    ):
        tx = row["trans_id"]
        totals_by_tx[tx] = {
            "total_amount_funded": _amount(row["total_amount_funded"]),
            "amount_repaid":      _amount(row["amount_repaid"]),
            "amount_due":         _amount(row["amount_due"]),
            "date_funded":        row["date_funded"],
        }

    # --- Build rows the template expects ---
    payments_transactions = []   # open/live
    closed_transactions   = []   # closed

    # What counts as "closed"? 1) explicit closed states OR 2) amount_due <= 0
    CLOSED_STATES = {"closed", "closed_funded", "closed_repaid", "closed_rejected"}

    for led in TransactionLedger.objects.all().order_by("-created_at"):
        tx = led.trans_id
        sums = totals_by_tx.get(tx, {
            "total_amount_funded": _amount(led.amount_funded),
            "amount_repaid":      _amount(led.amount_repaid),
            "amount_due":         _amount(led.amount_due),
            "date_funded":        None,
        })

        row = {
            "trans_id": tx,
            "abn": led.abn,
            "name": led.name,
            "state": led.state,
            "product": led.product,
            "date_funded": sums["date_funded"],
            "total_amount_funded": sums["total_amount_funded"],
            "amount_repaid": sums["amount_repaid"],
            "amount_due": sums["amount_due"],
        }

        is_closed = (led.state in CLOSED_STATES) or (sums["amount_due"] is not None and sums["amount_due"] <= 0)
        if is_closed:
            closed_transactions.append(row)
        else:
            payments_transactions.append(row)

    # Optional: filter by selected_originator if your base template sets it in the context
    selected_originator = request.GET.get("originator")  # or however you pass it in
    if selected_originator:
        # Note: your LMS ledger doesn’t have an 'originator' field; if you store it only in details,
        # you can filter details first and then keep matching trans_ids. Otherwise, skip this filter.
        pass

    # Base page URL for JS to derive LMS_BASE (your template already does this)
    page_url = reverse("invoice_finance:invoice_finance_page")

    ctx = {
        "selected_originator": {"originator": selected_originator} if selected_originator else None,
        "payments_transactions": payments_transactions,
        "closed_transactions": closed_transactions,
        "page_url": page_url,
    }
    return render(request, "invoice_finance/invoice_finance.html", ctx)

def fetch_invoice_data(request, trans_id: str):
    """
    Returns invoice rows for the +/- toggle (Money Out section).
    Uses TransactionDetails only, so it works even without a separate repayments table.
    """
    details = TransactionDetails.objects.filter(trans_id=trans_id).order_by("invoice_number")
    invoices = []
    today = date.today()

    for d in details:
        amount_funded = _amount(d.amount_funded)
        amount_repaid = _amount(d.amount_repaid)
        amount_due    = _amount(d.amount_due)

        invoices.append({
            "invoice_number": d.invoice_number,
            "debtor": d.debtor,
            "due": d.due.isoformat() if d.due else None,
            "amount_funded": str(amount_funded),
            "amount_repaid": str(amount_repaid),
            "amount_due":    str(amount_due),
            "interest":      "0.00",  # compute if you add terms logic
            "face_value":    str(_amount(d.face_value)) if d.face_value is not None else None,
            "date_funded":   d.date_funded.isoformat() if d.date_funded else None,
            # ageing buckets optional—include if your schema has them
            "days_0_30": 0,
            "days_31_60": 0,
            "days_61_90": 0,
            "days_91_120": 0,
            "days_121_plus": 0,
            "total_current": 0,
            "total_overdue": 0,
            # "drawdown": ... include if you track per-invoice drawdowns
        })

    return JsonResponse({"invoices": invoices})


# efs_lms/invoice_finance/views.py
import json
import logging
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import TransactionLedger, TransactionDetails

logger = logging.getLogger(__name__)

def _to_dec(x, default="0.00"):
    if x in (None, "", "null"):
        return Decimal(default)
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return Decimal(default)

def _required(d, key, path=""):
    v = d.get(key)
    if v in (None, ""):
        raise ValueError(f"Missing required field: {path + key}")
    return v

@csrf_exempt
def ingest_transaction(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    try:
        body = request.body.decode("utf-8") or "{}"
        data = json.loads(body)
    except Exception as e:
        return JsonResponse({"success": False, "error": f"Invalid JSON: {e}"}, status=400)

    try:
        # Accept BOTH shapes:
        # 1) { "ledger": {...}, "invoices":[...] }
        # 2) flat legacy shape: { "transaction_id": "...", "abn": "...", ... }
        if "ledger" in data:
            ledger_in = data.get("ledger") or {}
            invoices_in = data.get("invoices") or []
            trans_id = _required(ledger_in, "trans_id", "ledger.")
            abn = ledger_in.get("abn")
            name = ledger_in.get("name")
            amount_funded = _to_dec(ledger_in.get("amount_funded"))
            amount_repaid = _to_dec(ledger_in.get("amount_repaid"))
            amount_due    = _to_dec(ledger_in.get("amount_due"))
            state = ledger_in.get("state") or "closed_funded"
            product = ledger_in.get("product")

        else:
            # legacy/flat
            trans_id = _required(data, "transaction_id")
            abn = data.get("abn")
            name = data.get("name")
            amount_funded = _to_dec(data.get("amount_funded"))
            amount_repaid = _to_dec(data.get("amount_repaid"))
            amount_due    = _to_dec(data.get("amount_due"), default=str(amount_funded))
            state = data.get("state") or "closed_funded"
            product = data.get("product")
            invoices_in = data.get("invoices") or []

        # Upsert ledger
        ledger_obj, _ = TransactionLedger.objects.update_or_create(
            trans_id=trans_id,
            defaults={
                "abn": abn,
                "name": name,
                "amount_funded": amount_funded,
                "amount_repaid": amount_repaid,
                "amount_due": amount_due,
                "state": state,
                "product": product,
            },
        )

        # Invoices (optional)
        created_details = 0
        for i in invoices_in:
            # lenient keys from efs_data payload
            details = {
                "trans_id": trans_id,
                "debtor": i.get("debtor"),
                "due": i.get("due") or i.get("due_date"),
                "amount_funded": _to_dec(i.get("amount_funded")),
                "amount_repaid": _to_dec(i.get("amount_repaid")),
                "amount_due": _to_dec(i.get("amount_due")),
                "face_value": _to_dec(i.get("face_value")),
                "date_funded": i.get("date_funded"),
                "invoice_number": i.get("invoice_number") or i.get("inv_number"),
                "abn": i.get("abn"),
                "product": product,
            }
            TransactionDetails.objects.create(**details)
            created_details += 1

        return JsonResponse({
            "success": True,
            "trans_id": trans_id,
            "ledger_updated": True,
            "details_created": created_details,
        }, status=200)

    except ValueError as ve:
        # our explicit "missing required field" etc.
        return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        logger.exception("ingest_transaction failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
