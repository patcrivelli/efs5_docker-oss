import logging
import os
import json
import traceback
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Min
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import (
    TransactionLedger,
    TransactionDetails,
    InvoiceRepayments,
    DrawdownData,
    Drawdown,
)

logger = logging.getLogger(__name__)

# ---------------------------
# Service URL helpers
# ---------------------------
def _profile_base() -> str:
    return (
        getattr(settings, "EFS_PROFILE_BASE_URL", None)
        or os.getenv("EFS_PROFILE_URL", "http://localhost:8002")
    ).rstrip("/")


# ---------------------------
# Originators (shared pattern)
# ---------------------------
def fetch_originators(timeout: int = 5):
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("originators", data if isinstance(data, list) else [])
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []


def build_base_context(request):
    originators = fetch_originators()
    selected_originator = None
    selected_id = request.GET.get("originators")
    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected_originator = {"id": o.get("id"), "originator": o.get("originator")}
                break
    return {"originators": originators, "selected_originator": selected_originator}


# ---------------------------
# Helpers
# ---------------------------
def _to_decimal(val):
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_date(val):
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(val, fmt).date()
        except Exception:
            continue
    return None


def _is_closed_state(state: str) -> bool:
    if not state:
        return False
    s = state.strip().lower()
    # Only treat truly closed states as "Closed" tab.
    return s in {"closed", "closed_repaid"}


# ---------------------------
# Page view (renders HTML)
# ---------------------------
from decimal import Decimal
from django.db.models import Sum, Min

def invoice_finance_page(request):
    ctx = build_base_context(request)
    selected_originator_name = (ctx.get("selected_originator") or {}).get("originator")

    # ----------------------------
    # Drawdowns for Invoice Finance (unprocessed) - originator filtered
    # ----------------------------
    drawdown_qs = DrawdownData.objects.filter(product__iexact="Invoice Finance")
    if selected_originator_name:
        drawdown_qs = drawdown_qs.filter(originator=selected_originator_name)

    drawdown_data = (
        drawdown_qs.filter(state__in=["lms_unprocessed", "unprocessed"])
        .order_by("-drawdown_time")
    )

    # ----------------------------
    # ✅ Determine which transactions belong to this originator
    # Use TransactionLedger as the source of truth
    # ----------------------------
    ledger_qs = TransactionLedger.objects.filter(product__iexact="Invoice Finance")
    if selected_originator_name:
        ledger_qs = ledger_qs.filter(originator=selected_originator_name)

    allowed_trans_ids = list(ledger_qs.values_list("trans_id", flat=True))

    # If an originator is selected and they have no transactions, show empty page (not "all")
    if selected_originator_name and not allowed_trans_ids:
        ctx.update(
            {
                "drawdown_data": drawdown_data,
                "payments_transactions": [],
                "closed_transactions": [],
            }
        )
        return render(request, "invoice_finance.html", ctx)

    # ----------------------------
    # Aggregate transactions from details (Invoice Finance only)
    # ✅ Filter by allowed_trans_ids when present
    # ----------------------------
    details_qs = TransactionDetails.objects.filter(product__iexact="Invoice Finance")
    if selected_originator_name:
        details_qs = details_qs.filter(trans_id__in=allowed_trans_ids)

    tx_rows = (
        details_qs.values("trans_id")
        .annotate(
            total_amount_funded=Sum("amount_funded"),
            first_date_funded=Min("date_funded"),
        )
        .order_by("trans_id")
    )

    payments_transactions, closed_transactions = [], []

    for tx in tx_rows:
        trans_id = tx["trans_id"]

        ledger = TransactionLedger.objects.filter(trans_id=trans_id).first()
        abn = ledger.abn if ledger else "N/A"
        name = ledger.name if ledger else "N/A"
        state = (ledger.state or "").strip() if ledger else ""

        total_repaid = (
            InvoiceRepayments.objects.filter(trans_id=trans_id, product__iexact="Invoice Finance")
            .aggregate(total=Sum("amount_repaid"))
            .get("total")
            or Decimal("0.00")
        )

        total_drawn = (
            Drawdown.objects.filter(trans_id=trans_id, product__iexact="Invoice Finance")
            .aggregate(total=Sum("amount_drawndown"))
            .get("total")
            or Decimal("0.00")
        )

        total_amount_funded = (tx["total_amount_funded"] or Decimal("0.00")) + total_drawn
        amount_due = total_amount_funded - total_repaid
        date_funded = tx["first_date_funded"] or "N/A"

        row = {
            "abn": abn,
            "name": name,
            "trans_id": trans_id,
            "total_amount_funded": total_amount_funded,
            "amount_repaid": total_repaid,
            "amount_due": amount_due,
            "date_funded": date_funded,
        }

        (closed_transactions if _is_closed_state(state) else payments_transactions).append(row)

    ctx.update(
        {
            "drawdown_data": drawdown_data,
            "payments_transactions": payments_transactions,
            "closed_transactions": closed_transactions,
        }
    )
    return render(request, "invoice_finance.html", ctx)


# ---------------------------
# Ingestion endpoint (finance → LMS)
# ---------------------------

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
import json

@csrf_exempt
def ingest_transaction(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    ledger = payload.get("ledger") or {}
    invoices = payload.get("invoices") or []

    trans_id = (ledger.get("trans_id") or "").strip()
    if not trans_id:
        return JsonResponse({"success": False, "error": "Missing trans_id in ledger"}, status=400)

    ledger_product = ledger.get("product") or "Invoice Finance"
    today = timezone.localdate()  # ✅ always "today" in Django's timezone

    with transaction.atomic():
        ledger_defaults = {
            "originator": ledger.get("originator"),
            "abn": ledger.get("abn"),
            "acn": ledger.get("acn"),
            "name": ledger.get("name"),
            "amount_funded": _to_decimal(ledger.get("amount_funded")),
            "amount_repaid": _to_decimal(ledger.get("amount_repaid")),
            "amount_due": _to_decimal(ledger.get("amount_due")),
            "state": (ledger.get("state") or "").strip().lower(),
            "product": ledger_product,
        }

        ledger_obj, _ = TransactionLedger.objects.update_or_create(
            trans_id=trans_id, defaults=ledger_defaults
        )

        saved = 0
        for inv in invoices:
            inv_num = (inv.get("invoice_number") or inv.get("inv_number") or "").strip()
            if not inv_num:
                continue

            product = inv.get("product") or ledger_product

            inv_defaults = {
                "originator": inv.get("originator") or ledger.get("originator"),
                "debtor": inv.get("debtor"),
                "due": _to_date(inv.get("due") or inv.get("due_date")),
                "amount_funded": _to_decimal(inv.get("amount_funded")),
                "amount_repaid": _to_decimal(inv.get("amount_repaid")),
                "amount_due": _to_decimal(inv.get("amount_due")),
                "face_value": _to_decimal(inv.get("face_value")),
                "abn": inv.get("abn"),
                "acn": inv.get("acn"),
                "product": product,

                # ✅ FORCE date_funded to TODAY every time (overrides existing too)
                "date_funded": today,
            }

            TransactionDetails.objects.update_or_create(
                trans_id=trans_id,
                invoice_number=inv_num,
                defaults=inv_defaults,
            )
            saved += 1

    return JsonResponse(
        {"success": True, "trans_id": trans_id, "ledger_id": ledger_obj.id, "invoices_saved": saved},
        status=200,
    )


# ---------------------------
# JSON endpoints used by the html page
# ---------------------------




def fetch_invoice_data(request, transaction_id):
    invoice_data = []
    try:
        ledger = TransactionLedger.objects.get(trans_id=transaction_id)
        transaction_abn = ledger.abn

        # Optional product terms (safe to fail)
        base_rate = Decimal("0.00")
        charge_rate = Decimal("0.00")
        try:
            from .models import InvoiceFinanceTerms  # optional
            terms = InvoiceFinanceTerms.objects.filter(abn=transaction_abn).latest("id")
            base_rate = terms.base_rate
            charge_rate = terms.charge_rate
        except Exception:
            pass

        daily_interest_rate = (
            (base_rate / Decimal("100.00") + charge_rate / Decimal("100.00")) / Decimal("365.00")
        )

        details_qs = TransactionDetails.objects.filter(
            trans_id=transaction_id, product__iexact="Invoice Finance"
        )
        if not details_qs.exists():
            return JsonResponse({"invoices": []})

        today = date.today()

        for detail in details_qs:
            # Sum repayments for this invoice
            repaid = (
                InvoiceRepayments.objects.filter(
                    trans_id=transaction_id,
                    invoice_number=detail.invoice_number,
                    product__iexact="Invoice Finance",
                ).aggregate(total=Sum("amount_repaid"))["total"]
                or Decimal("0.00")
            )

            # Base funded amount from details
            amount_funded = detail.amount_funded or Decimal("0.00")

            # Sum any drawdowns applied to this invoice
            dd = (
                Drawdown.objects.filter(
                    trans_id=transaction_id,
                    invoice_number=detail.invoice_number,
                    product__iexact="Invoice Finance",
                ).aggregate(total=Sum("amount_drawndown"))["total"]
                or Decimal("0.00")
            )

            # ✅ OLD MODEL: amount_due = (amount_funded + drawdown) - repaid
            gross_funded = amount_funded + dd
            amount_due = gross_funded - repaid

            # Interest on updated amount_due
            days_outstanding = Decimal("0")
            if detail.date_funded and isinstance(detail.date_funded, date):
                days_outstanding = Decimal(str((today - detail.date_funded).days))
            interest = amount_due * daily_interest_rate * days_outstanding

            invoice_data.append(
                {
                    "invoice_number": detail.invoice_number,
                    "debtor": detail.debtor or "N/A",
                    "due": detail.due.strftime("%Y-%m-%d") if detail.due else "N/A",
                    "amount_funded": float(amount_funded),
                    "drawdown": float(dd),                       # keep showing drawdown column
                    "amount_repaid": float(repaid),
                    "amount_due": float(amount_due),             # ← now includes drawdown
                    "interest": float(interest),
                    "face_value": float(detail.face_value) if detail.face_value is not None else "N/A",
                    "date_funded": detail.date_funded.strftime("%Y-%m-%d") if detail.date_funded else "N/A",
                    "days_0_30": getattr(detail, "days_0_30", 0),
                    "days_31_60": getattr(detail, "days_31_60", 0),
                    "days_61_90": getattr(detail, "days_61_90", 0),
                    "days_91_120": getattr(detail, "days_91_120", 0),
                    "days_121_plus": getattr(detail, "days_121_plus", 0),
                    "total_current": getattr(detail, "total_current", 0),
                    "total_overdue": getattr(detail, "total_overdue", 0),
                }
            )

        return JsonResponse({"invoices": invoice_data})

    except TransactionLedger.DoesNotExist:
        return JsonResponse({"invoices": []})
    except Exception as e:
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)


def fetch_invoice_repayments(request, transaction_id):
    repayments = InvoiceRepayments.objects.filter(trans_id=transaction_id, product__iexact="Invoice Finance")
    data = {}
    for r in repayments:
        inv = r.invoice_number or ""
        data[inv] = data.get(inv, 0.0) + float(r.amount_repaid or 0)
    return JsonResponse(data)


from django.utils import timezone
from django.db.models import Q, Sum

@csrf_exempt
def allocate_payment(request):
    """
    Supports TWO modes:

    (A) SINGLE-INVOICE MODE (backwards compatible)
        Payload must include:
          - trans_id
          - invoice_number
          - amount_repaid
        -> Creates ONE InvoiceRepayments row (same behaviour as today)

    (B) BULK/GROUP MODE (new)
        Payload includes:
          - amount_repaid (required)
          - abn and/or acn (required)
          - originator (optional but recommended)
          - allocation_id (optional)
          - date_repaid (optional)
        -> Allocates across invoices in first matching ledger (oldest-first),
           then proceeds to next matching ledger(s) (same ABN/ACN [+ originator filter]),
           until exhausted. Returns remaining_to_return if still leftover.

    Notes:
    - Uses "Amount Due" per invoice as: (amount_funded + drawdowns) - repayments
    - Updates TransactionLedger.updated_at on any ledger touched by this allocation.
    - Inserts InvoiceRepayments rows into your InvoiceRepayments model.
    """

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # -----------------------------
    # Parse shared inputs
    # -----------------------------
    trans_id = (payload.get("trans_id") or "").strip() or None
    invoice_number = (payload.get("invoice_number") or "").strip() or None

    amount_repaid = _to_decimal(payload.get("amount_repaid")) or Decimal("0.00")
    if amount_repaid <= 0:
        return JsonResponse({"error": "amount_repaid must be > 0"}, status=400)

    date_repaid = _to_date(payload.get("date_repaid")) or date.today()
    allocation_id = (payload.get("allocation_id") or "").strip() or None

    abn = (payload.get("abn") or "").strip() or None
    acn = (payload.get("acn") or "").strip() or None
    originator = (payload.get("originator") or "").strip() or None  # optional

    # ==========================================================
    # (A) SINGLE-INVOICE MODE (existing behaviour)
    # ==========================================================
    if trans_id and invoice_number:
        # Keep current behaviour — create one repayment row
        InvoiceRepayments.objects.create(
            trans_id=trans_id,
            invoice_number=invoice_number,
            amount_repaid=amount_repaid,
            date_repaid=date_repaid,
            allocation_id=allocation_id,
            abn=abn,
            acn=acn,                     # ✅ if your concrete model has it
            originator=originator,       # ✅ if your concrete model has it
            product="Invoice Finance",
        )

        # Touch ledger updated_at so it reflects activity
        TransactionLedger.objects.filter(trans_id=trans_id).update(updated_at=timezone.now())

        return JsonResponse(
            {
                "status": "success",
                "mode": "single",
                "trans_id": trans_id,
                "invoice_number": invoice_number,
                "allocated": str(amount_repaid),
                "remaining_to_return": "0.00",
            },
            status=200,
        )

    # ==========================================================
    # (B) BULK/GROUP MODE
    # ==========================================================
    if not abn and not acn:
        return JsonResponse(
            {"error": "Bulk allocation requires abn and/or acn (or provide trans_id + invoice_number for single mode)."},
            status=400,
        )

    remaining = amount_repaid

    # Build ledger filter (Invoice Finance only)
    ledger_filter = Q(product__iexact="Invoice Finance")

    # Match ABN and/or ACN
    if abn and acn:
        # match either
        ledger_filter &= (Q(abn=abn) | Q(acn=acn))
    elif abn:
        ledger_filter &= Q(abn=abn)
    else:
        ledger_filter &= Q(acn=acn)

    # Optional originator scoping (keeps allocation inside that originator)
    if originator:
        ledger_filter &= Q(originator=originator)

    ledgers = list(
        TransactionLedger.objects
        .filter(ledger_filter)
        .order_by("created_at")   # ✅ oldest-first
        .values("trans_id", "abn", "acn", "originator")
    )

    if not ledgers:
        return JsonResponse({"error": "No matching transactions found for bulk allocation"}, status=404)

    allocations_made = 0
    invoices_touched = 0
    ledgers_touched = set()

    def _invoice_outstanding(_trans_id: str, _invoice_number: str, base_funded: Decimal):
        """Outstanding = (funded + drawdowns) - repayments"""
        repaid = (
            InvoiceRepayments.objects.filter(
                trans_id=_trans_id,
                invoice_number=_invoice_number,
                product__iexact="Invoice Finance",
            )
            .aggregate(total=Sum("amount_repaid"))
            .get("total")
            or Decimal("0.00")
        )

        dd = (
            Drawdown.objects.filter(
                trans_id=_trans_id,
                invoice_number=_invoice_number,
                product__iexact="Invoice Finance",
            )
            .aggregate(total=Sum("amount_drawndown"))
            .get("total")
            or Decimal("0.00")
        )

        gross = (base_funded or Decimal("0.00")) + dd
        outstanding = gross - repaid
        return outstanding

    with transaction.atomic():
        for led in ledgers:
            if remaining <= 0:
                break

            tx = led["trans_id"]
            if not tx:
                continue

            # invoices in this ledger
            details = list(
                TransactionDetails.objects.filter(
                    trans_id=tx,
                    product__iexact="Invoice Finance",
                ).order_by("date_funded", "invoice_number")
            )
            if not details:
                continue

            for d in details:
                if remaining <= 0:
                    break

                inv_no = (d.invoice_number or "").strip()
                if not inv_no:
                    continue

                outstanding = _invoice_outstanding(tx, inv_no, d.amount_funded or Decimal("0.00"))
                if outstanding <= 0:
                    continue

                pay = remaining if remaining <= outstanding else outstanding
                remaining -= pay

                # ✅ Insert repayment row
                InvoiceRepayments.objects.create(
                    trans_id=tx,
                    originator=d.originator or led.get("originator") or originator,
                    invoice_number=inv_no,
                    amount_repaid=pay,
                    date_repaid=date_repaid,
                    allocation_id=allocation_id,
                    abn=d.abn or led.get("abn") or abn,
                    acn=led.get("acn") or acn,
                    product="Invoice Finance",
                )

                allocations_made += 1
                invoices_touched += 1
                ledgers_touched.add(tx)

        # Touch updated_at on all ledgers involved
        if ledgers_touched:
            TransactionLedger.objects.filter(trans_id__in=list(ledgers_touched)).update(updated_at=timezone.now())

    return JsonResponse(
        {
            "status": "success",
            "mode": "bulk",
            "total_payment": str(amount_repaid),
            "allocated": str(amount_repaid - remaining),
            "remaining_to_return": str(remaining),
            "allocations_made": allocations_made,
            "invoices_paid": invoices_touched,
            "ledgers_touched": len(ledgers_touched),
            "message": (
                f"Allocated {amount_repaid - remaining} across invoices."
                + (f" Return {remaining} to client." if remaining > 0 else "")
            ),
        },
        status=200,
    )


@csrf_exempt
def close_transaction(request, trans_id):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method."}, status=400)
    try:
        ledger = TransactionLedger.objects.get(trans_id=trans_id)
        ledger.state = "closed"   # ← lowercase as per your requirement
        ledger.save()
        return JsonResponse({"status": "success", "message": "Transaction closed successfully."})
    except TransactionLedger.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Transaction not found."}, status=404)



from django.utils import timezone



@csrf_exempt
def allocate_drawdown_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body or "{}")
        transaction_id = data.get("transaction_id")
        if not transaction_id:
            return JsonResponse({"error": "Missing transaction_id"}, status=400)

        drawdown_instance = DrawdownData.objects.get(transaction_id=transaction_id)
        abn = (drawdown_instance.abn or "").strip() or None
        acn = (drawdown_instance.acn or "").strip() or None
        originator = (drawdown_instance.originator or "").strip() or None

        drawdown_amount = drawdown_instance.amount_requested or Decimal("0.00")
        if not abn:
            return JsonResponse({"error": "DrawdownData missing ABN."}, status=400)
        if drawdown_amount <= 0:
            return JsonResponse({"error": "Drawdown amount must be > 0."}, status=400)

        THRESH = Decimal("0.80")
        remaining = drawdown_amount

        # ✅ Find ALL ledgers for this ABN (and optionally ACN) for Invoice Finance
        ledger_qs = TransactionLedger.objects.filter(
            abn=abn,
            product__iexact="Invoice Finance",
        )
        if originator:
            ledger_qs = ledger_qs.filter(originator=originator)

        # If you truly want ACN matching too, uncomment this:
        # NOTE: TransactionLedger does not have ACN in your base model.
        # If you add acn to TransactionLedger, you can filter here.
        #
        # if acn:
        #     ledger_qs = ledger_qs.filter(acn=acn)

        ledgers = list(ledger_qs.order_by("created_at"))
        if not ledgers:
            return JsonResponse({"error": f"No transactions found for ABN {abn}"}, status=404)

        # Totals for diagnostics
        blocked_repaid = 0
        blocked_pct = 0
        blocked_nofv = 0
        total_allocations = 0
        ledgers_used = []

        def eligible_invoices_for_ledger(trans_id: str):
            """
            Returns:
              eligible: list[(TransactionDetails, headroom_cap)]
              total_headroom: Decimal
              blocked counters (local)
            """
            nonlocal blocked_repaid, blocked_pct, blocked_nofv

            invoices = TransactionDetails.objects.filter(
                trans_id=trans_id,
                product__iexact="Invoice Finance",
            ).order_by("date_funded")

            eligible = []
            total_headroom = Decimal("0.00")

            for inv in invoices:
                inv_no = inv.invoice_number
                if not inv_no:
                    continue

                repaid = (
                    InvoiceRepayments.objects.filter(
                        trans_id=trans_id,
                        invoice_number=inv_no,
                        product__iexact="Invoice Finance",
                    ).aggregate(total=Sum("amount_repaid"))["total"]
                    or Decimal("0.00")
                )

                # Rule #1: if repaid > 0, never allocate more drawdowns
                if repaid > 0:
                    blocked_repaid += 1
                    continue

                funded = inv.amount_funded or Decimal("0.00")

                existing_dd = (
                    Drawdown.objects.filter(
                        trans_id=trans_id,
                        invoice_number=inv_no,
                        product__iexact="Invoice Finance",
                    ).aggregate(total=Sum("amount_drawndown"))["total"]
                    or Decimal("0.00")
                )

                face_value = inv.face_value or Decimal("0.00")
                if face_value <= 0:
                    blocked_nofv += 1
                    continue

                gross_funded = funded + existing_dd
                pct_funded = gross_funded / face_value

                # Rule #2: block if already >= 80%
                if pct_funded >= THRESH:
                    blocked_pct += 1
                    continue

                # Cap: do not allow gross_funded to exceed 80% of face_value
                max_allowed_gross = face_value * THRESH
                headroom = max_allowed_gross - gross_funded

                if headroom <= 0:
                    blocked_pct += 1
                    continue

                eligible.append((inv, headroom))
                total_headroom += headroom

            return eligible, total_headroom
        
        with transaction.atomic():
                # Iterate through all ledgers until remaining is fully allocated or none eligible
                for ledger in ledgers:
                    if remaining <= 0:
                        break

                    trans_id = ledger.trans_id

                    eligible, total_headroom = eligible_invoices_for_ledger(trans_id)
                    if total_headroom <= 0:
                        continue  # try next ledger

                    # We'll only mark this ledger as "used" if we actually allocate something into it
                    allocations = []
                    remaining_for_this_ledger = remaining

                    # Allocate within this ledger using the same proportional-by-headroom method
                    for inv, headroom in eligible:
                        if remaining_for_this_ledger <= 0:
                            break

                        share_ratio = (headroom / total_headroom) if total_headroom > 0 else Decimal("0.00")

                        # Allocate from the REMAINING amount (not original amount_requested)
                        alloc_amt = min((remaining * share_ratio), headroom, remaining_for_this_ledger)

                        if alloc_amt <= 0:
                            continue

                        allocations.append((inv, alloc_amt))
                        remaining_for_this_ledger -= alloc_amt

                    # Persist allocations for this ledger
                    if allocations:
                        # ✅ Record this ledger as used (so we can bump updated_at once per ledger)
                        ledgers_used.append(trans_id)

                        for inv, amt in allocations:
                            Drawdown.objects.create(
                                trans_id=trans_id,
                                originator=originator,
                                invoice_number=inv.invoice_number,
                                amount_drawndown=amt,
                                date_drawndown=timezone.now().date(),  # ✅ prefer timezone-aware
                                allocation_id=transaction_id,          # link back to DrawdownData.transaction_id
                                abn=abn,
                                product="Invoice Finance",
                            )
                            total_allocations += 1

                        # ✅ bump updated_at for this ledger immediately (or do it once at end—see below)
                        TransactionLedger.objects.filter(trans_id=trans_id).update(updated_at=timezone.now())

                    # Update global remaining (subtract what we actually used here)
                    used = (remaining - remaining_for_this_ledger)
                    remaining -= used

                # Mark request allocated if we allocated *anything* (or keep your preferred state logic)
                if total_allocations > 0:
                    drawdown_instance.state = "allocated"
                else:
                    drawdown_instance.state = "unallocated"  # optional; or keep "lms_unprocessed"

                drawdown_instance.save()

        return JsonResponse(
            {
                "status": "success" if total_allocations > 0 else "error",
                "message": "Allocated drawdown across transactions." if total_allocations > 0 else "No eligible invoices found across transactions.",
                "allocated_to": total_allocations,  # number of invoice allocations (Drawdown rows)
                "ledgers_used": ledgers_used,        # which trans_ids received allocations
                "unallocated_amount": float(remaining if remaining > 0 else 0),
                "blocked_repaid": blocked_repaid,
                "blocked_pct": blocked_pct,
                "blocked_no_face_value": blocked_nofv,
            },
            status=200 if total_allocations > 0 else 400,
        )

    except DrawdownData.DoesNotExist:
        return JsonResponse({"error": "DrawdownData not found for the given transaction_id"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)



from django.core.files.storage import FileSystemStorage

@csrf_exempt
def handle_file_upload(request):
    """
    Accepts CSV/XLS/XLSX, parses with pandas (and openpyxl for Excel),
    and returns normalized rows so your JS can render the Repayments table.
    Expected keys in the response 'data' list:
      - Date, Amount, Account Number, Transaction Type, Transaction Details, Balance, Merchant Name
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    uploaded_file = request.FILES["file"]
    fs = FileSystemStorage()
    saved_name = fs.save(uploaded_file.name, uploaded_file)
    abs_path = fs.path(saved_name)

    try:
        # Lazy import so the app can still run without pandas until this path is exercised
        try:
            import pandas as pd  # type: ignore
        except Exception as e:
            return JsonResponse({"error": f"pandas not installed: {e}"}, status=500)

        ext = os.path.splitext(abs_path)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(abs_path)
        elif ext in (".xls", ".xlsx"):
            try:
                import openpyxl  # type: ignore  # ensures engine available
            except Exception as e:
                return JsonResponse({"error": f"openpyxl not installed: {e}"}, status=500)
            df = pd.read_excel(abs_path)
        else:
            return JsonResponse({"error": "Unsupported file format"}, status=400)

        # ---- Normalize to columns your template expects ----
        colmap = {
            "Date": ["date", "transaction date", "posted date", "value date"],
            "Amount": ["amount", "debit", "credit", "transaction amount", "money in", "money out"],
            "Account Number": ["account number", "account", "acct", "bsb/account", "bsb account"],
            "Transaction Type": ["type", "transaction type", "txn type", "category"],
            "Transaction Details": ["description", "details", "narration", "transaction details", "reference", "memo"],
            "Balance": ["balance", "closing balance", "running balance"],
            "Merchant Name": ["merchant name", "merchant", "payee", "payer", "counterparty", "company"],
        }

        lower_cols = {c.lower(): c for c in df.columns}

        def pick_target(std_key: str):
            for cand in colmap[std_key]:
                if cand in lower_cols:
                    return lower_cols[cand]
            return None

        # Build output frame with expected keys; fill missing with empty strings
        import pandas as pd
        out = pd.DataFrame()
        for key in colmap.keys():
            src = pick_target(key)
            out[key] = df[src] if src else ""

        # Format dates and currency-like fields
        if "Date" in out.columns:
            out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
            out["Date"] = out["Date"].fillna("")

        from decimal import Decimal
        def fmt_amt(x):
            try:
                val = Decimal(str(x).replace(",", ""))
            except Exception:
                return ""
            return f"{val:.2f}"

        for amtcol in ("Amount", "Balance"):
            if amtcol in out.columns:
                out[amtcol] = out[amtcol].apply(fmt_amt)

        data = out.to_dict(orient="records")
        return JsonResponse({"data": data})

    except Exception as e:
        logger.exception("File parsing error")
        return JsonResponse({"error": f"File parsing error: {e}"}, status=500)
    finally:
        # Optional: clean up the temporary file
        try:
            fs.delete(saved_name)
        except Exception:
            pass


#-------------------------

#-endpoints for the drawdowns 
        
#---------------------------
# efs_lms_invoice_finance/core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseNotAllowed
from decimal import Decimal, InvalidOperation
import json
import logging

from .models import DrawdownData  # <-- concrete model exists in this service

logger = logging.getLogger(__name__)


def _to_decimal(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


@csrf_exempt
def pay_drawdown(request):
    """
    Upsert a drawdown row into the LMS 'DrawdownData' table.
    Expected payload (JSON):
      {
        "transaction_id": "...",   # REQUIRED
        "abn": "...",
        "originator": "...",
        "product": "...",
        "amount_requested": "...", # number or string; stored as Decimal
        "state": "lms_unprocessed" # optional; default applied if missing
        ... other optional fields ...
      }
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    # Parse JSON
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    tx = (data.get("transaction_id") or "").strip()
    if not tx:
        return JsonResponse({"success": False, "error": "transaction_id required"}, status=400)

    # Build defaults for upsert
    defaults = {
        "drawdown_time":        data.get("drawdown_time"),
        "contact_name":         data.get("contact_name"),
        "abn":                  data.get("abn"),
        "acn":                  data.get("acn"),
        "bankstatements_token": data.get("bankstatements_token"),
        "bureau_token":         data.get("bureau_token"),
        "accounting_token":     data.get("accounting_token"),
        "ppsr_token":           data.get("ppsr_token"),
        "contact_email":        data.get("contact_email"),
        "contact_number":       data.get("contact_number"),
        "originator":           data.get("originator"),
        "state":               (data.get("state") or "lms_unprocessed"),
        "amount_requested":     _to_decimal(data.get("amount_requested")),
        "product":              data.get("product"),
        "insurance_premiums":   data.get("insurance_premiums"),
    }

    obj, created = DrawdownData.objects.update_or_create(
        transaction_id=tx,
        defaults=defaults,
    )

    logger.info("LMS IF pay_drawdown upserted tx=%s created=%s", tx, created)

    # Keep response JSON-only
    return JsonResponse({
        "success": True,
        "transaction_id": obj.transaction_id,
        "created": created,
        "state": obj.state,
    }, status=200)



#-------------------------

#- upload new invoices 
        
#---------------------------
# core/views.py
import csv
import io
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.utils import timezone   # ✅ NEW

from .models import TransactionLedger, TransactionDetails


def _parse_date(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _parse_decimal(value):
    if value is None:
        return None
    s = str(value).replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _pick(row, *keys):
    lower_map = {(k or "").strip().lower(): k for k in row.keys()}
    for key in keys:
        lk = (key or "").strip().lower()
        if lk in lower_map:
            return row.get(lower_map[lk])
    return None


@require_POST
@csrf_protect
def upload_invoices_csv(request):
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"status": "error", "message": "No file uploaded."}, status=400)

    originator = (request.GET.get("originator_name") or "").strip() or None
    product = "Invoice Finance"
    today = timezone.localdate()

    # ✅ NEW: read company_name from modal (multipart/form-data)
    modal_company_name = (request.POST.get("company_name") or "").strip() or None

    try:
        raw = f.read()
        text = raw.decode("utf-8-sig", errors="replace")
    except Exception:
        return JsonResponse({"status": "error", "message": "Unable to read CSV (encoding issue)."}, status=400)

    reader = csv.DictReader(io.StringIO(text))

    invoices = []
    for r in reader:
        invoice_number = (_pick(r, "inv_number", "invoice_number", "Invoice Number", "Inv #") or "").strip()
        if not invoice_number:
            continue

        invoices.append({
            "abn": (_pick(r, "abn", "ABN") or "").strip() or None,
            "acn": (_pick(r, "acn", "ACN") or "").strip() or None,
            # keep this for invoice rows if you ever need it, but NOT for ledger name
            "name": (_pick(r, "name", "Name", "Company Name") or "").strip() or None,
            "debtor": (_pick(r, "debtor", "Debtor") or "").strip() or None,
            "due": _parse_date(_pick(r, "due_date", "Due", "Due Date")),
            "amount_funded": _parse_decimal(_pick(r, "amount_funded", "Amount Funded")),
            "amount_due": _parse_decimal(_pick(r, "amount_due", "Amount Due", "Current Amount")),
            "face_value": _parse_decimal(_pick(r, "face_value", "Face Value")),
            "invoice_number": invoice_number,
        })

    if not invoices:
        return JsonResponse({"status": "error", "message": "No valid invoice rows found in CSV."}, status=400)

    trans_id = str(uuid.uuid4())

    head = invoices[0]
    abn = head.get("abn")
    acn = head.get("acn")

    # ✅ FIX: ledger name comes from modal first, fallback to CSV only if blank
    ledger_name = modal_company_name or head.get("name")

    total_funded = sum([(x.get("amount_funded") or Decimal("0")) for x in invoices])
    total_due = sum([(x.get("amount_due") or Decimal("0")) for x in invoices])

    created_details = 0
    updated_details = 0
    errors = 0
    error_rows = []

    with transaction.atomic():
        TransactionLedger.objects.create(
            trans_id=trans_id,
            abn=abn,
            acn=acn,
            originator=originator,
            name=ledger_name,  # ✅ now correct
            amount_funded=total_funded,
            amount_repaid=Decimal("0"),
            amount_due=total_due,
            state="open",
            product=product,
        )

        for inv in invoices:
            inv_num = (inv.get("invoice_number") or "").strip()
            if not inv_num:
                continue

            try:
                defaults = {
                    "originator": originator,
                    "debtor": inv.get("debtor"),
                    "due": inv.get("due"),
                    "amount_funded": inv.get("amount_funded"),
                    "amount_repaid": Decimal("0"),
                    "amount_due": inv.get("amount_due"),
                    "face_value": inv.get("face_value"),
                    "date_funded": today,
                    "abn": inv.get("abn"),
                    "acn": inv.get("acn"),
                    "product": product,
                }

                _, created = TransactionDetails.objects.update_or_create(
                    trans_id=trans_id,
                    invoice_number=inv_num,
                    defaults=defaults,
                )

                if created:
                    created_details += 1
                else:
                    updated_details += 1

            except Exception as e:
                errors += 1
                error_rows.append({"invoice_number": inv_num, "error": str(e)})

    return JsonResponse({
        "status": "success",
        "trans_id": trans_id,
        "created_ledgers": 1,
        "updated_ledgers": 0,
        "created_details": created_details,
        "updated_details": updated_details,
        "errors": errors,
        "error_rows": error_rows[:50],
    })


#-------------------------

#- new drawdowns
        
#---------------------------


from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from decimal import Decimal, InvalidOperation
import json
import uuid

from .models import DrawdownData  # your concrete model in this service


def _to_decimal_amount(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


@csrf_exempt
@require_POST
def create_drawdown_request(request):
    """
    Creates a minimal DrawdownData row from the Drawdowns modal.
    Inserts ONLY:
      - transaction_id (uuid)
      - state = lms_unprocessed
      - product = Invoice Finance
      - amount_requested
      - originator
      - abn/acn if provided
      - drawdown_time = now (so it shows in table)
    """
    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)

    amount = _to_decimal_amount(payload.get("amount_requested"))
    if amount is None or amount <= 0:
        return JsonResponse({"status": "error", "message": "amount_requested must be > 0."}, status=400)

    originator = (payload.get("originator") or "").strip() or None
    abn = (payload.get("abn") or "").strip() or None
    acn = (payload.get("acn") or "").strip() or None

    tx_id = str(uuid.uuid4())

    obj = DrawdownData.objects.create(
        transaction_id=tx_id,
        originator=originator,
        abn=abn,
        acn=acn,
        drawdown_time=timezone.now(),
        state="lms_unprocessed",
        amount_requested=amount,
        product="Invoice Finance",
    )

    return JsonResponse({
        "status": "success",
        "transaction_id": obj.transaction_id,
        "amount_requested": str(obj.amount_requested),
        "state": obj.state,
        "product": obj.product,
    }, status=200)
