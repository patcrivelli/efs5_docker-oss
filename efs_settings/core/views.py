# efs_settings/core/views.py
import logging
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from core.models import (
    CreditDecisionParametersGlobalSettings,
    ProductsGlobalSettings,
    BankStatementsGlobalSettings,
    FinancialsGlobalSettings,
)

logger = logging.getLogger(__name__)

# ---- helpers to talk to efs_profile ----
def _profile_base() -> str:
    return getattr(settings, "EFS_PROFILE_BASE_URL", "http://localhost:8002").rstrip("/")

def _api_key_header() -> dict:
    return {"X-API-Key": getattr(settings, "INTERNAL_API_KEY", "dev-key")}

def fetch_originators():
    try:
        r = requests.get(f"{_profile_base()}/api/originators/", timeout=5)
        r.raise_for_status()
        return r.json().get("originators", [])
    except Exception:
        logger.exception("Failed to fetch originators from efs_profile")
        return []

# ---- context ----
def base_context(request):
    originators = fetch_originators()
    selected_originator = None

    # Look for id in GET or POST
    selected_id = request.GET.get("originators") or request.POST.get("originator_id")

    if selected_id:
        for o in originators:
            if str(o.get("id")) == str(selected_id):
                selected_originator = o
                break

    return {
        "originators": originators,
        "selected_originator": selected_originator,
    }

# ---- pages ----
def settings_home(request):
    return render(request, "settings_home.html", base_context(request))

# efs_settings/core/views.py
from django.shortcuts import render
from core.models import (
    CreditDecisionParametersGlobalSettings,
    BankStatementsGlobalSettings,
    FinancialsGlobalSettings,
    ProductsGlobalSettings,
)
from .views import base_context  


from django.shortcuts import render

def settings_view(request, originator_id=None):
    context = base_context(request)
    selected_originator = context.get("selected_originator")

    # selected_originator is a dict from efs_profile → use .get(...)
    filter_kwargs = {}
    if selected_originator and selected_originator.get("originator"):
        filter_kwargs["originator"] = selected_originator.get("originator")

    credit_decision = CreditDecisionParametersGlobalSettings.objects.filter(
        **filter_kwargs
    ).order_by("-timestamp").first()

    bank_statements = BankStatementsGlobalSettings.objects.filter(
        **filter_kwargs
    ).order_by("-timestamp").first()

    financials = FinancialsGlobalSettings.objects.filter(
        **filter_kwargs
    ).order_by("-timestamp").first()

    products = ProductsGlobalSettings.objects.filter(
        **filter_kwargs
    ).order_by("-timestamp").first()

    context.update({
        "credit_decision_settings": credit_decision,
        "bank_statements_settings": bank_statements,
        "financials_settings": financials,
        "products_settings": products,
    })

    return render(request, "settings.html", context)

# ---- form handler ----
def create_originator(request):
    if request.method == "POST":
        payload = {
            "originator": request.POST.get("originator_name"),
            "created_by": request.POST.get("username"),
        }
        try:
            r = requests.post(
                f"{_profile_base()}/api/originators/create/",
                json=payload,
                headers=_api_key_header(),
                timeout=5,
            )
            if r.status_code not in (200, 201):
                logger.error("Originator create failed: %s %s", r.status_code, r.text)
        except Exception:
            logger.exception("Error calling efs_profile create originator")

    return redirect("settings_home")



from django.views.decorators.csrf import csrf_exempt

from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def save_settings(request):
    if request.method != "POST":
        return redirect("settings_view")

    # Avoid print() → can raise OSError on broken pipes
    logger.info("POST DATA for save_settings: %s", dict(request.POST))

    context = base_context(request)
    selected_originator = context.get("selected_originator")
    if not selected_originator:
        # No originator selected in the UI
        return redirect("settings_view")

    originator_name = selected_originator.get("originator")

    # ---- Credit Decision Parameters ----
    CreditDecisionParametersGlobalSettings.objects.create(
        originator=originator_name,
        credit_score_threshold=request.POST.get("credit_score_threshold", 500),
        credit_score_switch=("credit_score_switch" in request.POST),
        credit_enquiries_switch=("credit_enquiries_switch" in request.POST),
        court_actions_current_switch=("court_actions_current_switch" in request.POST),
        court_actions_resolved_switch=("court_actions_resolved_switch" in request.POST),
        payment_defaults_current_switch=("payment_defaults_current_switch" in request.POST),
        payment_defaults_resolved_switch=("payment_defaults_resolved_switch" in request.POST),
        insolvencies_switch=("insolvencies_switch" in request.POST),
        ato_tax_default_switch=("ato_tax_default_switch" in request.POST),
    )

    # ---- Bank Statements ----
    BankStatementsGlobalSettings.objects.create(
        originator=originator_name,
        debt_serviceability_coverage=request.POST.get("debt_serviceability_slider", 2.5),
        debt_serviceability_switch=("debt_serviceability_switch" in request.POST),
        inflow_outflow_ratio=request.POST.get("inflow_outflow_slider", 2.5),
        inflow_outflow_switch=("inflow_outflow_switch" in request.POST),
    )

    # ---- Financials ----
    FinancialsGlobalSettings.objects.create(
        originator=originator_name,
        ebitda_margin=request.POST.get("ebitda_margin_slider", 0.5),
        ebitda_margin_switch=("ebitda_margin_switch" in request.POST),
        debt_to_equity_ratio=request.POST.get("debt_equity_ratio_slider", 2.5),
        debt_to_equity_ratio_switch=("debt_equity_ratio_switch" in request.POST),
        liquidity_ratio=request.POST.get("liquidity_ratio_slider", 2.5),
        liquidity_ratio_switch=("liquidity_ratio_switch" in request.POST),
    )

    # ---- Products ----
    def parse_number(value):
        if value:
            try:
                # handles "3 Years" → 3
                return int(str(value).split()[0])
            except Exception:
                return None
        return None

    ProductsGlobalSettings.objects.create(
        originator=originator_name,
        term_loan_switch=("term_loan_switch" in request.POST),
        term_loan_duration_years=parse_number(request.POST.get("term_loan_duration_years")),
        term_loan_duration_months=parse_number(request.POST.get("term_loan_duration_months")),
        overdraft_switch=("overdraft_switch" in request.POST),
        overdraft_duration_years=parse_number(request.POST.get("overdraft_duration_years")),
        overdraft_duration_months=parse_number(request.POST.get("overdraft_duration_months")),
        credit_card_switch=("credit_card_switch" in request.POST),
        credit_card_duration_years=parse_number(request.POST.get("credit_card_duration_years")),
        credit_card_duration_months=parse_number(request.POST.get("credit_card_duration_months")),
        bulk_invoice_finance_switch=("bulk_invoice_finance_switch" in request.POST),
        single_invoice_finance_switch=("single_invoice_finance_switch" in request.POST),
        trade_finance_switch=("trade_finance_switch" in request.POST),
        trade_finance_installments=request.POST.get("trade_finance_installments"),
        trade_finance_installment_frequency=request.POST.get("trade_finance_frequency"),
        insurance_premium_funding_switch=("insurance_premium_funding_switch" in request.POST),
        insurance_premium_funding_installments=request.POST.get("insurance_premium_funding_installments"),
        insurance_premium_funding_installment_frequency=request.POST.get("insurance_premium_funding_frequency"),
    )

    # Safer redirect: prefer referer; fall back to your settings page
    return redirect(request.META.get("HTTP_REFERER") or "settings_view")


# efs_settings/core/views.py
import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import (
    CreditDecisionParametersGlobalSettings,
    ProductsGlobalSettings,
)

def _build_credit_payload(obj):
    return {
        "originator": obj.originator,
        "credit_score_threshold": obj.credit_score_threshold,
        "credit_score_switch": obj.credit_score_switch,
        "credit_enquiries_switch": obj.credit_enquiries_switch,
        "court_actions_current_switch": obj.court_actions_current_switch,
        "court_actions_resolved_switch": obj.court_actions_resolved_switch,
        "payment_defaults_current_switch": obj.payment_defaults_current_switch,
        "payment_defaults_resolved_switch": obj.payment_defaults_resolved_switch,
        "insolvencies_switch": obj.insolvencies_switch,
        "ato_tax_default_switch": obj.ato_tax_default_switch,
        "timestamp": obj.timestamp.isoformat(),
    }

def _build_products_payload(obj):
    return {
        "originator": obj.originator,
        "term_loan_switch": obj.term_loan_switch,
        "term_loan_duration_years": obj.term_loan_duration_years,
        "term_loan_duration_months": obj.term_loan_duration_months,
        "overdraft_switch": obj.overdraft_switch,
        "overdraft_duration_years": obj.overdraft_duration_years,
        "overdraft_duration_months": obj.overdraft_duration_months,
        "credit_card_switch": obj.credit_card_switch,
        "credit_card_duration_years": obj.credit_card_duration_years,
        "credit_card_duration_months": obj.credit_card_duration_months,
        "bulk_invoice_finance_switch": obj.bulk_invoice_finance_switch,
        "single_invoice_finance_switch": obj.single_invoice_finance_switch,
        "trade_finance_switch": obj.trade_finance_switch,
        "trade_finance_installments": obj.trade_finance_installments,
        "trade_finance_installment_frequency": obj.trade_finance_installment_frequency,
        "insurance_premium_funding_switch": obj.insurance_premium_funding_switch,
        "insurance_premium_funding_installments": obj.insurance_premium_funding_installments,
        "insurance_premium_funding_installment_frequency": obj.insurance_premium_funding_installment_frequency,
        "timestamp": obj.timestamp.isoformat(),
    }

def _post_json(url, payload, session, token, timeout=5):
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Token": token or "",
    }
    return session.post(url, json=payload, headers=headers, timeout=timeout)

# efs_settings/core/views.py

@csrf_exempt
def post_settings(request):
    if request.method != "POST":
        return JsonResponse({'message': 'Invalid request method'}, status=400)

    try:
        body = json.loads(request.body or "{}")
    except Exception:
        body = {}
    selected_originator = (body.get("originator") or "").strip() or None

    credit_qs = CreditDecisionParametersGlobalSettings.objects.all()
    products_qs = ProductsGlobalSettings.objects.all()
    if selected_originator:
        credit_qs = credit_qs.filter(originator=selected_originator)
        products_qs = products_qs.filter(originator=selected_originator)

    latest_credit = credit_qs.order_by("-timestamp").first()
    latest_products = products_qs.order_by("-timestamp").first()

    if not latest_credit and not latest_products:
        return JsonResponse(
            {'message': 'No settings found for this originator (or globally).'},
            status=404
        )

    credit_payload   = _build_credit_payload(latest_credit) if latest_credit else None
    products_payload = _build_products_payload(latest_products) if latest_products else None

    # ---- Targets (post to both, when configured) ----
    credit_targets, products_targets = [], []

    # Existing credit-decision service (keep if you already use it)
    base_credit_decision = getattr(settings, "EFS_CREDIT_DECISION_URL", "").strip()
    if base_credit_decision:
        credit_targets.append(f"{base_credit_decision.rstrip('/')}/api/settings/credit-decision/receive/")

    # NEW: also post credit settings to data-bureau
    base_data_bureau = getattr(settings, "EFS_DATA_BUREAU_URL", "").strip()
    if base_data_bureau:
        credit_targets.append(f"{base_data_bureau.rstrip('/')}/api/settings/credit-decision/receive/")

    # Products still go to data-bureau as before
    if base_data_bureau:
        products_targets.append(f"{base_data_bureau.rstrip('/')}/api/settings/products/receive/")

    s = requests.Session()
    token = getattr(settings, "EFS_INTERNAL_TOKEN", "")
    results = {"credit": [], "products": []}

    try:
        if credit_payload:
            for url in credit_targets:
                resp = _post_json(url, credit_payload, s, token)
                results["credit"].append({"url": url, "status": resp.status_code, "text": resp.text})
        if products_payload:
            for url in products_targets:
                resp = _post_json(url, products_payload, s, token)
                results["products"].append({"url": url, "status": resp.status_code, "text": resp.text})
    except Exception as e:
        return JsonResponse({'message': f'Error posting settings: {e}'}, status=500)

    ok = all(200 <= r["status"] < 300 for r in (results["credit"] + results["products"]))
    who = selected_originator or "All Originators"
    if ok:
        return JsonResponse({'message': f'Settings posted successfully for {who}!', 'details': results})
    else:
        return JsonResponse({'message': f'One or more posts failed for {who}', 'details': results}, status=502)
