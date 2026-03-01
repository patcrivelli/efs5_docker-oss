from django.shortcuts import render

# Create your views here.
from django.http import JsonResponse


def ping(request):
    return JsonResponse({"status": "ok", "app": "bankstatements"})

def bank_statements_page(request):
    return render(request, "bankstatements.html")


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction as db_tx

# If your models are in this app:
from .models import Bank, BankAccount, Transaction
# If they live elsewhere, adjust the import accordingly.

@csrf_exempt
@require_POST
def ingest_bankstatements(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "invalid json"}, status=400)

    abn = (payload.get("abn") or "").strip()
    banks = payload.get("banks", [])
    if not abn or not isinstance(banks, list):
        return JsonResponse({"success": False, "message": "missing abn or invalid 'banks' list"}, status=400)

    counts = {"banks_created": 0, "accounts_created": 0, "transactions_created": 0, "transactions_existing": 0}

    try:
        with db_tx.atomic():
            for bank_data in banks:
                bank, bank_created = Bank.objects.get_or_create(
                    abn=abn,
                    bank_name=bank_data["bankName"],
                    bank_slug=bank_data["bankSlug"],
                )
                if bank_created:
                    counts["banks_created"] += 1

                for acct in bank_data.get("bankAccounts", []):
                    account, acct_created = BankAccount.objects.get_or_create(
                        abn=abn,
                        bank=bank,
                        account_type=acct["accountType"],
                        account_holder=acct["accountHolder"],
                        account_holder_type=acct["accountHolderType"],
                        account_name=acct["accountName"],
                        bsb=acct["bsb"],
                        account_number=acct["accountNumber"],
                        defaults={
                            "current_balance": acct.get("currentBalance", 0),
                            "available_balance": acct.get("availableBalance", 0),
                        },
                    )
                    if acct_created:
                        counts["accounts_created"] += 1
                    else:
                        changed = False
                        if "currentBalance" in acct:
                            account.current_balance = acct["currentBalance"]; changed = True
                        if "availableBalance" in acct:
                            account.available_balance = acct["availableBalance"]; changed = True
                        if changed:
                            account.save(update_fields=["current_balance", "available_balance"])

                    for tx in acct.get("transactions", []):
                        tx_obj, created = Transaction.objects.get_or_create(
                            abn=abn,
                            account=account,
                            date=tx["date"],
                            description=tx["description"],
                            amount=tx["amount"],
                            balance=tx["balance"],
                            transaction_type=tx.get("type"),
                            defaults={
                                "tags": tx.get("tags", []),
                                "logo": tx.get("logo", ""),
                                "suburb": tx.get("suburb", ""),
                            },
                        )
                        if created:
                            counts["transactions_created"] += 1
                        else:
                            counts["transactions_existing"] += 1

        return JsonResponse({"success": True, "counts": counts}, status=200)

    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)





from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
from datetime import datetime
from .models import BankAccount, Transaction

def _parse_date(s):
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

@require_GET
def accounts_with_transactions(request):
    """
    GET /bankstatements/api/accounts-with-transactions?abn=...&start=YYYY-MM-DD&end=YYYY-MM-DD&accounts=a,b,c
    Returns:
      { "data": [ {account_holder, account_name, account_id, account_type, account_number, transactions:[{date, balance}, ...]}, ... ] }
    """
    abn = (request.GET.get("abn") or "").strip()
    if not abn:
        return HttpResponseBadRequest("abn required")

    start = _parse_date(request.GET.get("start")) if request.GET.get("start") else None
    end = _parse_date(request.GET.get("end")) if request.GET.get("end") else None

    ids_param = (request.GET.get("accounts") or "").strip()
    account_ids = [s.strip() for s in ids_param.split(",") if s.strip()] if ids_param else []

    qs = BankAccount.objects.filter(abn=abn)
    if account_ids:
        qs = qs.filter(account_id__in=account_ids)

    data = []
    for acct in qs:
        tx = Transaction.objects.filter(account=acct)
        if start: tx = tx.filter(date__gte=start)
        if end:   tx = tx.filter(date__lte=end)
        tx = tx.order_by("date").values("date", "balance")

        data.append({
            "account_holder": acct.account_holder,
            "account_name": acct.account_name,
            "account_id": str(acct.account_id),
            "account_type": acct.account_type,
            "account_number": acct.account_number,
            "transactions": [
                {"date": t["date"].isoformat() if t["date"] else None,
                 "balance": float(t["balance"]) if t["balance"] is not None else None}
                for t in tx
            ],
        })

    # 200 with empty list if no accounts; keep client UX friendly.
    return JsonResponse({"data": data})

""" 
# ---------------- Bank Statements ----------------
@csrf_exempt
def store_bank_data(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    try:
        data = json.loads(request.body)
        transaction_id = data.get("transaction_id")
        abn = data.get("abn")
        product = data.get("product")
        originator = data.get("originator")
        bank_data = data.get("bank_data")

        BankStatements.objects.create(
            transaction_id=transaction_id,
            abn=abn,
            product=product,
            originator=originator,
            data=bank_data,
        )
        return JsonResponse({"success": True})
    except Exception as e:
        logger.exception("Error saving Bank data")
        return JsonResponse({"error": str(e)}, status=500)


"""