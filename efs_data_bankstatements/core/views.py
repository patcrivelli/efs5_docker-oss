# efs_data_bankstatements/core/views.py
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt          # ✅ correct module
from django.views.decorators.http import require_GET, require_POST

import re
import statistics
from django.db.models import Q


from .models import Bank, BankAccount, Transaction

log = logging.getLogger(__name__)

@require_GET
def ping(request):
    return JsonResponse({"status": "ok", "app": "bankstatements"})

@require_GET
def bank_statements_page(request):
    return render(request, "bankstatements.html")

@require_GET
def bank_statements_modal(request):
    """Returns the Bank Statements modal fragment."""
    abn = request.GET.get("abn", "")
    return render(request, "bank_statements.html", {"abn": abn})

def _to_decimal(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None

def _to_date(v):
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(v[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(v[:10]).date()
    except Exception:
        return None

@csrf_exempt
@require_POST
def ingest_local_bankstatements(request):
    """
    POST {"abn": "..."} -> read BANKSTATEMENTS_FILE and upsert:
      - Bank keyed by (abn, bank_slug)
      - BankAccount keyed by (abn, bank, bsb, account_number)
      - Transaction keyed by (account, date, description, amount)
    """
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "invalid json body"}, status=400)

    # 🔒 Normalise ABN to digits-only (fixes invisible chars / punctuation mismatches)
    raw_abn = body.get("abn") or ""
    abn = _digits_only(raw_abn)
    if not abn:
        return JsonResponse({"status": "error", "message": "abn required"}, status=400)

    path = Path(getattr(settings, "BANKSTATEMENTS_FILE",
                        Path(settings.BASE_DIR) / "bankstatements.json"))
    if not path.exists():
        return JsonResponse({"status": "error", "message": f"file not found: {path}"}, status=404)

    try:
        data = json.loads(path.read_text())
    except Exception as e:
        log.exception("Failed reading bank statements file")
        return JsonResponse({"status": "error", "message": f"failed to read file: {e}"}, status=500)

    created = {"banks": 0, "accounts": 0, "transactions": 0}
    updated = {"banks": 0, "accounts": 0, "transactions": 0}

    try:
        with transaction.atomic():
            for b in data.get("banks", []):
                bank_slug = b.get("bankSlug") or ""
                bank_name = b.get("bankName") or ""

                bank, b_created = Bank.objects.get_or_create(
                    abn=abn,
                    bank_slug=bank_slug,
                    defaults={"bank_name": bank_name},
                )
                if b_created:
                    created["banks"] += 1
                else:
                    if bank_name and bank.bank_name != bank_name:
                        bank.bank_name = bank_name
                        bank.save(update_fields=["bank_name"])
                        updated["banks"] += 1

                for a in b.get("bankAccounts", []):
                    bsb = a.get("bsb") or ""
                    acct_no = a.get("accountNumber") or ""

                    acc_defaults = {
                        "account_type": a.get("accountType") or "",
                        "account_holder": a.get("accountHolder") or "",
                        "account_holder_type": a.get("accountHolderType") or "",
                        "account_name": a.get("accountName") or "",
                        "current_balance": _to_decimal(a.get("currentBalance")),
                        "available_balance": _to_decimal(a.get("availableBalance")),
                    }

                    account, acc_created = BankAccount.objects.get_or_create(
                        abn=abn,
                        bank=bank,
                        bsb=bsb,
                        account_number=acct_no,
                        defaults=acc_defaults,
                    )
                    if acc_created:
                        created["accounts"] += 1
                    else:
                        changed = False
                        for f, v in acc_defaults.items():
                            if getattr(account, f) != v:
                                setattr(account, f, v)
                                changed = True
                        if changed:
                            account.save(update_fields=list(acc_defaults.keys()))
                            updated["accounts"] += 1

                    for t in a.get("transactions", []):
                        dt   = _to_date(t.get("date"))
                        desc = t.get("description") or ""
                        amt  = _to_decimal(t.get("amount"))

                        tx_defaults = {
                            "balance": _to_decimal(t.get("balance")),
                            "transaction_type": t.get("type") or "",
                            "tags": t.get("tags") or None,
                            "logo": t.get("logo") or None,
                            "suburb": t.get("suburb") or None,
                        }

                        tx, tx_created = Transaction.objects.get_or_create(
                            abn=abn,
                            account=account,
                            date=dt,
                            description=desc,
                            amount=amt,
                            defaults=tx_defaults,
                        )
                        if tx_created:
                            created["transactions"] += 1
                        else:
                            changed = False
                            for f, v in tx_defaults.items():
                                if getattr(tx, f) != v:
                                    setattr(tx, f, v)
                                    changed = True
                            if changed:
                                tx.save(update_fields=list(tx_defaults.keys()))
                                updated["transactions"] += 1

    except Exception as e:
        log.exception("Ingest failed")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({
        "status": "success",
        "file": str(path),
        "created": created,
        "updated": updated,
    }, status=200)







from django.http import JsonResponse

# Existing ones (ping, bank_statements_modal, ingest_local_bankstatements...)

# efs_data_bankstatements/core/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import BankAccount, Transaction


from django.http import JsonResponse
from django.apps import apps

def list_models(request):
    """
    Return a JSON list of all models in this service (efs_data_bankstatements).
    """
    app_models = apps.get_app_config("core").get_models()
    model_names = [m.__name__ for m in app_models]
    return JsonResponse({"models": model_names})


#--------------end point for efs_agents service--------
#--------------end point for efs_agents service--------
#--------------end point for efs_agents service--------
#--------------end point for efs_agents service--------
#--------------end point for efs_agents service--------



# efs_data_bankstatements/core/views.py
import math
import uuid
import datetime as dt
from collections import defaultdict

from django.db.models import Prefetch, Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET
from django.utils.timezone import now

from .models import Bank, BankAccount, Transaction


def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _parse_accounts_qs(val: str | None):
    """
    ?accounts=<uuid1,uuid2,...>  (account_id values)
    Returns set[uuid.UUID] or empty set.
    """
    out = set()
    if not val:
        return out
    for raw in str(val).split(","):
        raw = raw.strip()
        try:
            out.add(uuid.UUID(raw))
        except Exception:
            pass
    return out


def _months_back_start(m: int) -> dt.date:
    m = max(1, min(int(m or 6), 36))
    # crude but fine for summaries
    return (now().date() - dt.timedelta(days=30 * m))


@require_GET
def display_bank_account_data(request, abn: str):
    """
    GET /display_bank_account_data/<abn>/
    Returns:
      {
        "success": true,
        "data": [
          {
            "bank": {...},
            "account": {...},
            "transactions": [{...}, ...]   # all txns for this account (ordered by date asc)
          }, ...
        ]
      }
    Optional filter: ?accounts=<uuid,uuid,...>
    """
    abn_digits = _digits_only(abn)
    if not abn_digits:
        return JsonResponse({"success": False, "message": "ABN required"}, status=400)

    allowed_ids = _parse_accounts_qs(request.GET.get("accounts"))

    qs_accounts = (
        BankAccount.objects
        .select_related("bank")
        .filter(abn=abn_digits)
    )
    if allowed_ids:
        qs_accounts = qs_accounts.filter(account_id__in=allowed_ids)

    # Prefetch transactions once, keep order
    qs_tx = Transaction.objects.order_by("date", "created_at")
    accounts = qs_accounts.prefetch_related(Prefetch("transactions", queryset=qs_tx))

    data = []
    for acc in accounts:
        bank = acc.bank
        data.append({
            "bank": {
                "bank_id": str(bank.bank_id),
                "bank_name": bank.bank_name,
                "bank_slug": bank.bank_slug,
                "created_at": bank.created_at.isoformat(),
            },
            "account": {
                "account_id": str(acc.account_id),
                "abn": acc.abn,
                "account_type": acc.account_type,
                "account_holder": acc.account_holder,
                "account_holder_type": acc.account_holder_type,
                "account_name": acc.account_name,
                "bsb": acc.bsb,
                "account_number": acc.account_number,
                "current_balance": float(acc.current_balance or 0.0),
                "available_balance": float(acc.available_balance or 0.0),
                "created_at": acc.created_at.isoformat(),
            },
            "transactions": [
                {
                    "transaction_id": str(t.transaction_id),
                    "abn": t.abn,
                    "acn": t.acn,
                    "date": t.date.isoformat() if t.date else None,
                    "description": t.description,
                    "amount": float(t.amount or 0.0),
                    "balance": float(t.balance or 0.0),
                    "transaction_type": t.transaction_type,
                    "tags": t.tags,
                    "logo": t.logo,
                    "suburb": t.suburb,
                    "created_at": t.created_at.isoformat(),
                }
                for t in acc.transactions.all()
            ],
        })

    return JsonResponse({"success": True, "data": data}, status=200)




@require_GET
def bankstatements_summary(request, abn: str):
    """
    GET /bankstatements/summary/<abn>/?months=6&accounts=uuid,uuid
    Computes a compact summary over the last N months (default 6).
    Returns:
      {
        "overall": {...},
        "per_account": [...],
        "as_of": "YYYY-MM-DD",
        "window_start": "YYYY-MM-DD",
        "window_months": 6
      }
    """
    abn_digits = _digits_only(abn)
    if not abn_digits:
        return JsonResponse({"success": False, "message": "ABN required"}, status=400)

    months = int(request.GET.get("months", 6) or 6)
    window_start = _months_back_start(months)
    allowed_ids = _parse_accounts_qs(request.GET.get("accounts"))

    accounts = (
        BankAccount.objects
        .select_related("bank")
        .filter(abn=abn_digits)
    )
    if allowed_ids:
        accounts = accounts.filter(account_id__in=allowed_ids)

    # pull only transactions in window for summary
    tx_qs = Transaction.objects.filter(
        account__in=accounts,
        date__gte=window_start
    ).order_by("date", "created_at")

    # group by account
    per_account = []
    tx_by_account = defaultdict(list)
    for t in tx_qs:
        tx_by_account[t.account_id].append(t)

    def _safe_float(x): 
        try: return float(x or 0.0)
        except Exception: return 0.0

    all_days_negative = set()
    total_inflows = total_outflows = 0.0
    start_bal_total = end_bal_total = 0.0

    for acc in accounts:
        txs = tx_by_account.get(acc.account_id, [])
        # compute start/end balance using first/last available balance in window
        if txs:
            start_balance = _safe_float(txs[0].balance)
            end_balance   = _safe_float(txs[-1].balance)
        else:
            # fallback to snapshot on account table
            start_balance = _safe_float(acc.current_balance)
            end_balance   = _safe_float(acc.current_balance)

        inflows  = sum(_safe_float(t.amount) for t in txs if _safe_float(t.amount) > 0)
        outflows = sum(abs(_safe_float(t.amount)) for t in txs if _safe_float(t.amount) < 0)

        # days negative (unique dates)
        neg_days = {t.date for t in txs if _safe_float(t.balance) < 0 and t.date}
        all_days_negative |= neg_days

        # max drawdown (simple peak-to-trough on txn balances)
        peak = -1e18
        max_dd = 0.0
        for t in txs:
            bal = _safe_float(t.balance)
            peak = max(peak, bal)
            max_dd = max(max_dd, peak - bal)

        # avg daily balance (approx: mean of balance points)
        if txs:
            avg_bal = sum(_safe_float(t.balance) for t in txs) / max(1, len(txs))
        else:
            avg_bal = _safe_float(acc.current_balance)

        per_account.append({
            "account_id": str(acc.account_id),
            "account_holder": acc.account_holder,
            "account_name": acc.account_name,
            "bank_name": acc.bank.bank_name if acc.bank_id else None,
            "start_balance": start_balance,
            "end_balance": end_balance,
            "avg_daily_balance": avg_bal,
            "total_inflows": inflows,
            "total_outflows": outflows,
            "net_cashflow": inflows - outflows,
            "days_negative": len(neg_days),
            "max_drawdown": max_dd,
        })

        total_inflows  += inflows
        total_outflows += outflows
        start_bal_total += start_balance
        end_bal_total   += end_balance

    summary = {
        "as_of": now().date().isoformat(),
        "window_start": window_start.isoformat(),
        "window_months": months,
        "overall": {
            "num_accounts": accounts.count(),
            "start_balance": start_bal_total,
            "end_balance": end_bal_total,
            "avg_daily_balance": (
                sum(p["avg_daily_balance"] for p in per_account) / max(1, len(per_account))
            ),
            "total_inflows": total_inflows,
            "total_outflows": total_outflows,
            "net_cashflow": total_inflows - total_outflows,
            "days_negative": len(all_days_negative),
            "max_drawdown": max((p["max_drawdown"] for p in per_account), default=0.0),
        },
        "per_account": per_account,
    }
    return JsonResponse(summary, status=200, safe=False)


# efs_data_bankstatements/core/views.py
from django.template.loader import render_to_string
from django.utils.html import escape

@require_GET
def modal_bank_statements(request):
    """
    GET /modal/bank-statements?abn=...
    Return the FULL fragment that contains:
      - <div id="bankStatementsModal" ...> ... </div>
      - the scripts that define the initializer
    No <html>/<body> wrappers.
    """
    abn = _digits_only(request.GET.get("abn"))
    html = render_to_string("bankstatements.html", {"abn": abn})
    return HttpResponse(html, content_type="text/html; charset=utf-8")




#--------#--------#--------#--------#--------#--------


#--------ai code helper functions 


#--------#--------#--------#--------#--------


# efs_data_bankstatements/core/views.py
import datetime as dt
import math
import uuid
from collections import defaultdict

from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import BankAccount, Transaction
from .ai_bankstatements import generate_bankstatements_sales_memo


def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _parse_accounts_list(val) -> set[uuid.UUID]:
    """
    Accepts either:
      - list of UUID strings
      - comma-separated string
    """
    out = set()
    if not val:
        return out
    if isinstance(val, str):
        parts = [p.strip() for p in val.split(",") if p.strip()]
    elif isinstance(val, (list, tuple)):
        parts = [str(p).strip() for p in val if str(p).strip()]
    else:
        parts = [str(val).strip()]

    for raw in parts:
        try:
            out.add(uuid.UUID(raw))
        except Exception:
            pass
    return out


def _months_back_start(m: int) -> dt.date:
    m = max(1, min(int(m or 3), 36))
    return (now().date() - dt.timedelta(days=30 * m))


def _safe_float(x) -> float:
    try:
        return float(x or 0.0)
    except Exception:
        return 0.0


def _daily_balance_deltas(transactions):
    """
    Mimics your front-end approach: uses consecutive balance changes as cash movement proxy.
    Returns: inflows, outflows, net, deltas(list), neg_days(set[date])
    """
    tx = []
    for t in transactions:
        if not t.date:
            continue
        bal = _safe_float(t.balance)
        tx.append((t.date, bal))

    tx.sort(key=lambda x: x[0])
    if len(tx) < 2:
        return 0.0, 0.0, 0.0, [], set()

    day_sums = defaultdict(float)
    neg_days = set()
    for d, b in tx:
        if b < 0:
            neg_days.add(d)

    for i in range(1, len(tx)):
        d = tx[i][0]
        delta = tx[i][1] - tx[i - 1][1]
        day_sums[d] += delta

    inflows = sum(v for v in day_sums.values() if v > 0)
    outflows = sum(-v for v in day_sums.values() if v < 0)
    deltas = list(day_sums.values())
    return inflows, outflows, inflows - outflows, deltas, neg_days


def _max_drawdown(balance_series):
    peak = -1e18
    max_dd = 0.0
    for b in balance_series:
        peak = max(peak, b)
        max_dd = max(max_dd, peak - b)
    return max_dd


def _volatility(values):
    """
    Std dev of daily deltas (simple). Returns 0 if <2 values.
    """
    if not values or len(values) < 2:
        return 0.0
    mu = sum(values) / len(values)
    var = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def analyse_accounts(abn: str, months: int, allowed_ids: set[uuid.UUID] | None = None):
    abn_digits = _digits_only(abn)
    if not abn_digits:
        raise ValueError("ABN required")

    window_start = _months_back_start(months)

    qs_accounts = (
        BankAccount.objects
        .select_related("bank")
        .filter(abn=abn_digits)
    )
    if allowed_ids:
        qs_accounts = qs_accounts.filter(account_id__in=allowed_ids)

    qs_tx = Transaction.objects.filter(date__gte=window_start).order_by("date", "created_at")
    accounts = qs_accounts.prefetch_related(Prefetch("transactions", queryset=qs_tx))

    per_account = []
    overall_inflows = overall_outflows = 0.0
    start_bal_total = end_bal_total = 0.0
    all_neg_days = set()
    max_dd_overall = 0.0
    vol_sum = 0.0
    vol_n = 0

    for acc in accounts:
        txs = list(acc.transactions.all())

        # start/end using first/last txn balance in window if present
        if txs:
            start_balance = _safe_float(txs[0].balance)
            end_balance = _safe_float(txs[-1].balance)
            bal_series = [_safe_float(t.balance) for t in txs]
            avg_bal = sum(bal_series) / max(1, len(bal_series))
        else:
            start_balance = _safe_float(acc.current_balance)
            end_balance = _safe_float(acc.current_balance)
            bal_series = [end_balance]
            avg_bal = end_balance

        inflows, outflows, net, deltas, neg_days = _daily_balance_deltas(txs)
        dd = _max_drawdown(bal_series)
        vol = _volatility(deltas)

        per_account.append({
            "account_id": str(acc.account_id),
            "account_holder": acc.account_holder,
            "account_name": acc.account_name,
            "bank_name": acc.bank.bank_name if acc.bank_id else None,
            "start_balance": start_balance,
            "end_balance": end_balance,
            "avg_daily_balance": avg_bal,
            "total_inflows": inflows,
            "total_outflows": outflows,
            "net_cashflow": net,
            "days_negative": len(neg_days),
            "max_drawdown": dd,
            "volatility": vol,
            "txn_count": len(txs),
        })

        overall_inflows += inflows
        overall_outflows += outflows
        start_bal_total += start_balance
        end_bal_total += end_balance
        all_neg_days |= neg_days
        max_dd_overall = max(max_dd_overall, dd)
        if vol > 0:
            vol_sum += vol
            vol_n += 1

    overall = {
        "num_accounts": len(per_account),
        "start_balance": start_bal_total,
        "end_balance": end_bal_total,
        "avg_daily_balance": (sum(p["avg_daily_balance"] for p in per_account) / max(1, len(per_account))),
        "total_inflows": overall_inflows,
        "total_outflows": overall_outflows,
        "net_cashflow": overall_inflows - overall_outflows,
        "days_negative": len(all_neg_days),
        "max_drawdown": max_dd_overall,
        "volatility": (vol_sum / vol_n) if vol_n else 0.0,
    }

    return {
        "as_of": now().date().isoformat(),
        "window_start": window_start.isoformat(),
        "window_months": months,
        "overall": overall,
        "per_account": per_account,
    }


def _interest_expense(amount_borrowed: float, interest_rate_pct: float, months: int) -> float:
    # simple interest expense over timeframe
    annual_rate = (interest_rate_pct or 0.0) / 100.0
    return (amount_borrowed or 0.0) * annual_rate * (months / 12.0)


import json
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    # remove ```json ... ``` or ``` ... ```
    s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def build_bankstatements_memo_prompt(metrics: dict, serviceability: dict) -> str:
    o = (metrics or {}).get("overall", {}) or {}
    per = (metrics or {}).get("per_account", []) or []

    # Don’t dump huge raw per-account objects to the model.
    # Create a compact per-account summary list.
    per_compact = []
    for a in per[:6]:  # cap
        per_compact.append({
            "account_holder": a.get("account_holder"),
            "start_balance": a.get("start_balance"),
            "end_balance": a.get("end_balance"),
            "avg_daily_balance": a.get("avg_daily_balance"),
            "total_inflows": a.get("total_inflows"),
            "total_outflows": a.get("total_outflows"),
            "net_cashflow": a.get("net_cashflow"),
            "days_negative": a.get("days_negative"),
            "max_drawdown": a.get("max_drawdown"),
            "volatility": a.get("volatility"),
        })

    return f"""
You are a credit analyst writing INTERNAL SALES NOTES for a lender.
Write a concise but useful memo (roughly 250–450 words) based ONLY on the facts provided.
Do NOT output JSON. Do NOT use code fences. Output plain text with headings.

Facts:
- Window: {metrics.get('window_months')} months, start: {metrics.get('window_start')}, as_of: {metrics.get('as_of')}
- Accounts: {o.get('num_accounts')}
- Start balance: {o.get('start_balance')}
- End balance: {o.get('end_balance')}
- Avg daily balance: {o.get('avg_daily_balance')}
- Total inflows: {o.get('total_inflows')}
- Total outflows: {o.get('total_outflows')}
- Net cashflow: {o.get('net_cashflow')}
- Days negative: {o.get('days_negative')}
- Max drawdown: {o.get('max_drawdown')}
- Volatility: {o.get('volatility')}

Serviceability:
- Interest expense: {serviceability.get('interest_expense')}
- Gross interest coverage: {serviceability.get('gross_interest_coverage')}
- Net interest coverage: {serviceability.get('net_interest_coverage')}

Per-account summary (compact):
{per_compact}

Required output format:

Summary:
- (1–2 sentences)

Key positives:
- bullet points (if any)

Key concerns / red flags:
- bullet points

What we should ask / verify:
- bullet points

Recommendation:
- Approve / Conditional / Decline
- If conditional, list specific conditions.
""".strip()


def deterministic_flags(metrics: dict, serviceability: dict):
    """Always gives you something useful even if the LLM is weak."""
    o = (metrics or {}).get("overall", {}) or {}
    flags = []

    try:
        end_bal = float(o.get("end_balance") or 0)
        net_cf = float(o.get("net_cashflow") or 0)
        neg_days = int(o.get("days_negative") or 0)
        max_dd = float(o.get("max_drawdown") or 0)
        vol = float(o.get("volatility") or 0)
        net_cov = serviceability.get("net_interest_coverage")

        if end_bal < 0:
            flags.append("END_BALANCE_NEGATIVE")
        if net_cf < 0:
            flags.append("NET_CASHFLOW_NEGATIVE")
        if neg_days >= 10:
            flags.append("FREQUENT_NEGATIVE_BALANCE_DAYS")
        if max_dd > 0 and max_dd > abs(end_bal) * 0.5:
            flags.append("LARGE_DRAWDOWN")
        if vol and vol > 50000:
            flags.append("HIGH_VOLATILITY")
        if net_cov is not None and net_cov < 1:
            flags.append("NET_INTEREST_COVERAGE_BELOW_1X")
    except Exception:
        pass

    return flags


def generate_bankstatements_sales_notes(metrics: dict, serviceability: dict) -> str:
    prompt = build_bankstatements_memo_prompt(metrics, serviceability)

    # Re-use the existing Gemini function, but read from "summary"
    ai = generate_bankstatements_ai_notes({"prompt": prompt})

    text = (ai.get("summary") or "").strip()
    return strip_code_fences(text)



def _clean_supplier_display_name(description: str) -> str:
    """
    Create a more human-readable supplier name from raw transaction description.
    Less aggressive than _normalize_supplier_name().
    """
    s = (description or "").strip()
    if not s:
        return "Unknown Supplier"

    # Remove common payment prefixes but keep the likely supplier/entity text
    s = re.sub(r"(?i)\b(payment to|invoice payment|direct debit|debit|transfer to|payment)\b[:\-\s]*", "", s)
    s = re.sub(r"(?i)\b(ref|reference)\b[:\-\s]*[A-Z0-9\-_/ ]+", "", s)

    # Clean spacing/punctuation
    s = re.sub(r"\s+", " ", s).strip(" -:|")

    # If all caps, make more readable
    if s.isupper():
        s = s.title()

    return s[:120] if s else "Unknown Supplier"



#--------#--------#--------#--------#--------#--------


#--------ai code view code to send to ai_bankstatements.py


#--------#--------#--------#--------#--------




@csrf_exempt
@require_POST
def bankstatements_analyse_and_ai(request, abn: str):
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    months = int(body.get("months") or 3)
    allowed_ids = _parse_accounts_list(body.get("accounts"))
    amount_borrowed = float(body.get("amount_borrowed") or 0.0)
    interest_rate_pct = float(body.get("interest_rate_pct") or 0.0)

    try:
        metrics = analyse_accounts(abn=abn, months=months, allowed_ids=allowed_ids or None)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)

    inflows = float(metrics["overall"]["total_inflows"] or 0.0)
    net = float(metrics["overall"]["net_cashflow"] or 0.0)
    ie = _interest_expense(amount_borrowed, interest_rate_pct, months)

    gross_cov = (inflows / ie) if ie > 0 and inflows > 0 else None
    net_cov = (net / ie) if ie > 0 else None

    serviceability = {
        "gross_interest_coverage": gross_cov,
        "net_interest_coverage": net_cov,
        "interest_expense": ie,
    }

    # ✅ payload that the memo AI can actually reason over
    ai_payload = {
        "abn": _digits_only(abn),
        "widget_state": {
            "months": months,
            "amount_borrowed": amount_borrowed,
            "interest_rate_pct": interest_rate_pct,
            "selected_accounts": [str(x) for x in (allowed_ids or [])],
        },
        "metrics": metrics,
        "serviceability": serviceability,
    }

    # --- NEW: produce memo text that actually analyses metrics
    try:
        memo_text = generate_bankstatements_sales_memo(ai_payload)
        if not (memo_text or "").strip():
            memo_text = "AI returned empty output. Please re-run."
    except Exception as e:
        memo_text = f"AI unavailable: {e}"

    flags = deterministic_flags(metrics, serviceability)
    short_summary = (memo_text.splitlines()[0][:220] if memo_text else "")

    return JsonResponse({
        "success": True,
        "metrics": metrics,
        "serviceability": serviceability,
        "ai": {
            "sales_notes": memo_text,     # ✅ paste THIS into Sales Notes
            "summary": short_summary,
            "risk_flags": flags,
            "highlights": [],
        }
    }, status=200)




#-------------#-------------#-------------#-------------



#-------------helper code for details bankstatement analysis


#-------------#-------------#-------------#-------------
# ----- Detailed supplier analysis helpers (views.py) -----

import re
import statistics
import datetime as dt
from collections import defaultdict
from django.db.models import Q
from django.utils.timezone import now
from collections import defaultdict, Counter

from .models import Transaction


def _normalize_supplier_name(description: str) -> str:
    """
    Heuristic normalization for recurring supplier grouping.
    Keeps it simple and deterministic.
    """
    s = (description or "").upper().strip()

    # remove card/reference noise and long numbers
    s = re.sub(r"\b\d{4,}\b", " ", s)
    s = re.sub(
        r"\b(?:REF|REFERENCE|TRANSFER|PAYMENT|FAST PAYMENT|OSKO|NPP|DEBIT|CREDIT|DIRECT DEBIT|DD)\b",
        " ",
        s,
    )
    s = re.sub(r"[^A-Z0-9& ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # common prefixes / junk
    junk = {"PAYMENT", "TRANSFER", "DEBIT", "CREDIT", "DIRECT", "BANK", "ONLINE", "INTERNET"}
    parts = [p for p in s.split() if p not in junk]

    # keep first few tokens to create a stable supplier key
    key = " ".join(parts[:4]).strip()
    return key or "UNKNOWN SUPPLIER"


def _month_key(d):
    return d.strftime("%Y-%m") if d else None


def _interval_trend(intervals: list[int]) -> str:
    """
    Simple trend for spacing between payments:
    - increasing => possible cash flow stress
    - decreasing => improving regularity / catch-up
    - stable / mixed
    """
    if not intervals or len(intervals) < 2:
        return "insufficient_data"

    changes = []
    for i in range(1, len(intervals)):
        changes.append(intervals[i] - intervals[i - 1])

    pos = sum(1 for c in changes if c > 0)
    neg = sum(1 for c in changes if c < 0)
    zero = sum(1 for c in changes if c == 0)

    if pos >= max(2, neg + 1):
        return "lengthening"
    if neg >= max(2, pos + 1):
        return "shortening"
    if zero == len(changes):
        return "stable"
    return "mixed"


def _classify_supplier_stress(intervals: list[int]) -> str:
    if not intervals or len(intervals) < 2:
        return "unknown"
    trend = _interval_trend(intervals)
    if trend == "lengthening":
        return "possible_cashflow_stress"
    if trend == "shortening":
        return "improving_or_catchup"
    if trend == "stable":
        return "stable_payment_cadence"
    return "mixed_pattern"


def build_detailed_supplier_analysis(abn: str, acn: str | None = None):
    """
    Directly analyses Transaction rows (transaction-by-transaction) and returns
    recurring supplier payment analysis for the 5 largest suppliers over the last 6 months.

    Matching logic:
      - ABN match OR ACN match (if ACN supplied)
    Payment logic:
      - outgoing transactions only (amount < 0)
      - grouped by normalized supplier description
    """
    abn_digits = _digits_only(abn)
    acn_digits = _digits_only(acn) if acn else None

    six_months_ago = now().date() - dt.timedelta(days=30 * 6)

    q = Q(date__gte=six_months_ago) & Q(amount__lt=0)
    id_q = Q(abn=abn_digits)
    if acn_digits:
        id_q = id_q | Q(acn=acn_digits)

    txs = (
        Transaction.objects
        .filter(q & id_q)
        .select_related("account")
        .order_by("date", "created_at")
    )

    grouped = defaultdict(list)

    for t in txs:
        supplier_key = _normalize_supplier_name(t.description or "")
        if supplier_key == "UNKNOWN SUPPLIER":
            continue

        amt = abs(float(t.amount or 0.0))  # outgoing payment as positive number
        if amt <= 0:
            continue

        grouped[supplier_key].append({
            "date": t.date,
            "amount": amt,
            "description": t.description or "",
            "account_id": str(t.account_id) if getattr(t, "account_id", None) else None,
            "account_name": getattr(t.account, "account_name", None) if getattr(t, "account", None) else None,
            "account_holder": getattr(t.account, "account_holder", None) if getattr(t, "account", None) else None,
            "transaction_id": str(t.transaction_id),
        })

    supplier_rows = []

    for supplier_key, rows in grouped.items():
        rows = [r for r in rows if r.get("date") is not None]
        rows.sort(key=lambda x: x["date"])
        if len(rows) < 2:
            continue  # recurring => at least 2 payments

        total_paid = sum(float(r.get("amount") or 0.0) for r in rows)
        payment_count = len(rows)
        avg_payment = (total_paid / payment_count) if payment_count else 0.0

        # monthly totals
        monthly_map = defaultdict(float)
        for r in rows:
            mk = _month_key(r.get("date"))
            if mk:
                monthly_map[mk] += float(r.get("amount") or 0.0)

        monthly_totals = [
            {"month": k, "total": round(v, 2)}
            for k, v in sorted(monthly_map.items())
            if k
        ]

        # intervals between payments (days)
        intervals = []
        for i in range(1, len(rows)):
            prev_d = rows[i - 1].get("date")
            curr_d = rows[i].get("date")
            if prev_d and curr_d:
                delta_days = (curr_d - prev_d).days
                intervals.append(int(delta_days))

        avg_days_between = round(sum(intervals) / len(intervals), 2) if intervals else None

        # sequence of changes in intervals
        interval_change_sequence = []
        if len(intervals) >= 2:
            for i in range(1, len(intervals)):
                interval_change_sequence.append(int(intervals[i] - intervals[i - 1]))

        interval_trend = _interval_trend(intervals)
        stress_signal = _classify_supplier_stress(intervals)

        payment_values = [float(r.get("amount") or 0.0) for r in rows]
        payment_stddev = round(statistics.pstdev(payment_values), 2) if len(payment_values) >= 2 else 0.0

        # sample raw descriptions (helps interpretation / QA)
        sample_descriptions = []
        seen_desc = set()
        for r in rows:
            d = (r.get("description") or "").strip()
            if d and d not in seen_desc:
                seen_desc.add(d)
                sample_descriptions.append(d)
            if len(sample_descriptions) >= 3:
                break

        # choose a display name from the most common cleaned raw descriptions
        cleaned_names = []
        for r in rows:
            cleaned = _clean_supplier_display_name(r.get("description") or "")
            if cleaned and cleaned != "Unknown Supplier":
                cleaned_names.append(cleaned)

        if cleaned_names:
            name_counts = Counter(cleaned_names)
            supplier_display_name = name_counts.most_common(1)[0][0]
        else:
            # fallback to normalized grouping key
            supplier_display_name = supplier_key.title()

        supplier_rows.append({
            "supplier": supplier_key,                # backward-compatible field
            "supplier_key": supplier_key,            # explicit grouping key
            "supplier_display_name": supplier_display_name,  # NEW human-readable label
            "total_paid_6m": round(total_paid, 2),
            "payment_count": payment_count,
            "avg_payment": round(avg_payment, 2),
            "payment_stddev": payment_stddev,
            "avg_days_between": avg_days_between,
            "intervals": intervals,
            "interval_change_sequence": interval_change_sequence,
            "interval_trend": interval_trend,
            "stress_signal": stress_signal,
            "monthly_totals": monthly_totals,
            "first_payment_date": rows[0]["date"].isoformat() if rows and rows[0].get("date") else None,
            "last_payment_date": rows[-1]["date"].isoformat() if rows and rows[-1].get("date") else None,
            "sample_descriptions": sample_descriptions,
        })

    supplier_rows.sort(key=lambda x: x["total_paid_6m"], reverse=True)
    top_5 = supplier_rows[:5]

    lengthening_count = sum(1 for s in top_5 if s.get("interval_trend") == "lengthening")
    shortening_count = sum(1 for s in top_5 if s.get("interval_trend") == "shortening")
    mixed_count = sum(1 for s in top_5 if s.get("interval_trend") == "mixed")
    stable_count = sum(1 for s in top_5 if s.get("interval_trend") == "stable")

    return {
        "window_months": 6,
        "matched_by": {
            "abn": abn_digits or None,
            "acn": acn_digits or None,
            "logic": "abn OR acn (if acn supplied)",
        },
        "top_suppliers": top_5,
        "summary": {
            "supplier_groups_considered": len(supplier_rows),
            "top_suppliers_returned": len(top_5),
            "lengthening_count": lengthening_count,
            "shortening_count": shortening_count,
            "stable_count": stable_count,
            "mixed_count": mixed_count,
        }
    }





@csrf_exempt
@require_POST
def bankstatements_analyse_and_ai(request, abn: str):
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    months = int(body.get("months") or 3)
    allowed_ids = _parse_accounts_list(body.get("accounts"))
    amount_borrowed = float(body.get("amount_borrowed") or 0.0)
    interest_rate_pct = float(body.get("interest_rate_pct") or 0.0)

    # NEW: toggle + ACN from frontend
    detailed_analysis = bool(body.get("detailed_analysis"))
    acn = (body.get("acn") or "").strip() or None

    try:
        metrics = analyse_accounts(abn=abn, months=months, allowed_ids=allowed_ids or None)
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=400)

    inflows = float(metrics["overall"]["total_inflows"] or 0.0)
    net = float(metrics["overall"]["net_cashflow"] or 0.0)
    ie = _interest_expense(amount_borrowed, interest_rate_pct, months)

    gross_cov = (inflows / ie) if ie > 0 and inflows > 0 else None
    net_cov = (net / ie) if ie > 0 else None

    serviceability = {
        "gross_interest_coverage": gross_cov,
        "net_interest_coverage": net_cov,
        "interest_expense": ie,
    }

    # NEW: detailed transaction-level supplier analysis (direct from Transaction model)
    detailed_tx_analysis = None
    if detailed_analysis:
        try:
            detailed_tx_analysis = build_detailed_supplier_analysis(abn=abn, acn=acn)
        except Exception as e:
            log.exception("Detailed supplier analysis failed")
            detailed_tx_analysis = {
                "error": str(e),
                "top_suppliers": [],
                "summary": {"top_suppliers_returned": 0}
            }

    # payload passed to AI
    ai_payload = {
        "abn": _digits_only(abn),
        "widget_state": {
            "months": months,
            "amount_borrowed": amount_borrowed,
            "interest_rate_pct": interest_rate_pct,
            "selected_accounts": [str(x) for x in (allowed_ids or [])],
            "detailed_analysis": detailed_analysis,
        },
        "metrics": metrics,
        "serviceability": serviceability,
        "detailed_transaction_analysis": detailed_tx_analysis,  # NEW
    }

    try:
        memo_text = generate_bankstatements_sales_memo(ai_payload)
        if not (memo_text or "").strip():
            memo_text = "AI returned empty output. Please re-run."
    except Exception as e:
        memo_text = f"AI unavailable: {e}"

    # IMPORTANT: if detailed analysis is ON, append a deterministic structured section
    # so the user ALWAYS gets the supplier-payment output even if the model ignores it.
    if detailed_analysis and detailed_tx_analysis:
        lines = []
        lines.append("")
        lines.append("Detailed Analysis")
        lines.append("Recurring Supplier Payments (Top 5 by total paid - last 6 months)")

        top = detailed_tx_analysis.get("top_suppliers") or []
        if not top:
            lines.append("- No recurring supplier payment patterns identified from transaction-level data.")
        else:
            # portfolio summary block (helps the user immediately see stress pattern concentration)
            summ = detailed_tx_analysis.get("summary") or {}
            lines.append(
                "Portfolio Summary: "
                f"considered={summ.get('supplier_groups_considered', 0)}, "
                f"top5_returned={summ.get('top_suppliers_returned', 0)}, "
                f"lengthening={summ.get('lengthening_count', 0)}, "
                f"stable={summ.get('stable_count', 0)}, "
                f"shortening={summ.get('shortening_count', 0)}, "
                f"mixed={summ.get('mixed_count', 0)}"
            )
            matched_by = detailed_tx_analysis.get("matched_by") or {}
            lines.append(
                "Match Basis: "
                f"ABN={matched_by.get('abn') or 'N/A'}, "
                f"ACN={matched_by.get('acn') or 'N/A'}, "
                f"Logic={matched_by.get('logic') or 'N/A'}"
            )
            lines.append("")

            for s in top:
                supplier_name = s.get("supplier_display_name") or s.get("supplier") or "Unknown Supplier"
                lines.append(f"- Supplier: {supplier_name}")
                lines.append(f"  Total Paid (6m): ${float(s.get('total_paid_6m') or 0):,.2f}")
                lines.append(f"  Payment Count: {s.get('payment_count')}")
                lines.append(f"  Avg Payment: ${float(s.get('avg_payment') or 0):,.2f}")
                lines.append(f"  Avg Days Between Payments: {s.get('avg_days_between') if s.get('avg_days_between') is not None else 'N/A'}")
                lines.append(f"  Payment Spacing Trend: {s.get('interval_trend', 'N/A')}")
                lines.append(f"  Stress Signal: {s.get('stress_signal', 'N/A')}")

                monthly = s.get("monthly_totals") or []
                if monthly:
                    monthly_str = ", ".join(
                        [f"{m.get('month')}=${float(m.get('total') or 0):,.2f}" for m in monthly]
                    )
                    lines.append(f"  Monthly Totals: {monthly_str}")

                intervals = s.get("intervals") or []
                if intervals:
                    lines.append(f"  Intervals Between Payments (days): {', '.join(str(x) for x in intervals)}")

                changes = s.get("interval_change_sequence") or []
                if changes:
                    # safe formatting for ints
                    fmt_changes = ", ".join([f"{int(x):+d}" for x in changes])
                    lines.append(f"  Interval Change Sequence (days): {fmt_changes}")

                samples = s.get("sample_descriptions") or []
                if samples:
                    lines.append(f"  Sample Descriptions: {' | '.join(samples)}")

                lines.append("")

        memo_text = (memo_text.rstrip() + "\n\n" + "\n".join(lines)).strip()

    flags = deterministic_flags(metrics, serviceability)
    short_summary = (memo_text.splitlines()[0][:220] if memo_text else "")

    return JsonResponse({
        "success": True,
        "metrics": metrics,
        "serviceability": serviceability,
        "detailed_transaction_analysis": detailed_tx_analysis,  # NEW
        "ai": {
            "sales_notes": memo_text,
            "summary": short_summary,
            "risk_flags": flags,
            "highlights": [],
        }
    }, status=200)
