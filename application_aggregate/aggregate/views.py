import logging
import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import InvoiceFinanceApplicationService
from django.shortcuts import render

logger = logging.getLogger(__name__)

@csrf_exempt
def receive_application_data(request):
    """Receiver endpoint for ApplicationData from client_app."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        logger.debug(f"📌 Received Invoice Finance application data:\n{json.dumps(data, indent=4)}")

        # Ensure transaction_id
        transaction_id = data.get("transaction_id") or str(uuid.uuid4())
        data["transaction_id"] = transaction_id

        # Ensure state always has a default
        data.setdefault("state", "sales_just_in")

        # Process via service
        result = InvoiceFinanceApplicationService.process_application_data(data)

        return JsonResponse(
            result,
            status=201 if result["status"] == "success" else 400
        )

    except Exception as e:
        logger.exception("🔥 Exception in receive_application_data")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# application_aggregate/aggregate/views.py
import json
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from .models import ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData

# --- helpers ---------------------------------------------------------

def _all_models():
    # Keep product tables separate but queryable together
    return [ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData]

def _select_model_for_product(product: str):
    p = (product or "").lower()
    if "trade" in p or p == "tf": return TfApplicationData
    if "supply" in p or "scf" in p: return ScfApplicationData
    if "insurance" in p or "ipf" in p: return IpfApplicationData
    return ApplicationData  # default (Invoice Finance / IF)

def _app_to_dict(obj):
    return {
        "id": obj.id,
        "transaction_id": obj.transaction_id,
        "application_time": obj.application_time.isoformat() if obj.application_time else None,

        # ✅ NEW / UPDATED FIELDS:
        "company_name": getattr(obj, "company_name", None),
        "abn": obj.abn,
        "acn": getattr(obj, "acn", None),

        # ✅ keep the rest of the payload the UI expects
        "bankstatements_token": obj.bankstatements_token,
        "bureau_token": obj.bureau_token,
        "accounting_token": obj.accounting_token,
        "ppsr_token": obj.ppsr_token,
        "contact_email": obj.contact_email,
        "contact_number": obj.contact_number,
        "originator": obj.originator,
        "state": obj.state,
        "amount_requested": str(obj.amount_requested) if obj.amount_requested is not None else None,
        "product": obj.product,
        "insurance_premiums": obj.insurance_premiums,

        # (optional backwards compat - only include if you still have it on the model)
        "contact_name": getattr(obj, "contact_name", None),
    }


def _filter_qs(qs, originator=None, states=None, tx=None):
    if originator:
        qs = qs.filter(originator__iexact=originator)
    if states:
        qs = qs.filter(state__in=states)
    if tx:
        qs = qs.filter(transaction_id=tx)
    return qs

# --- endpoints matching your existing urls.py -----------------------

# GET /api/applications/?states=a,b&originator=Foo
#     &transaction_id=<tx>  (optional)
def list_applications(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    originator = request.GET.get("originator") or None
    states = request.GET.get("states")
    states = [s.strip() for s in states.split(",")] if states else None
    tx = request.GET.get("transaction_id")

    # Specific-transaction query path (still returns 200/404 appropriately)
    if tx:
        for Model in _all_models():
            obj = _filter_qs(Model.objects.all(), originator, states, tx=tx).first()
            if obj:
                return JsonResponse({"application": _app_to_dict(obj)}, status=200)
        return JsonResponse({"error": "not found"}, status=404)

    # List path → ALWAYS 200, even when empty
    items = []
    for Model in _all_models():
        qs = _filter_qs(Model.objects.all(), originator, states)
        items.extend(_app_to_dict(a) for a in qs)

    # Optional: sort newest first
    items.sort(key=lambda d: (d.get("application_time") or "", d.get("id") or 0), reverse=True)
    return JsonResponse({"applications": items}, status=200)

# GET /api/applications/<tx>/
def get_application(request, tx):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    for Model in _all_models():
        obj = Model.objects.filter(transaction_id=tx).first()
        if obj:
            return JsonResponse({"application": _app_to_dict(obj)}, status=200)
    return JsonResponse({"error": "not found"}, status=404)

# POST /api/applications/<tx>/state/
@csrf_exempt
def update_state(request, tx):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    data = json.loads(request.body or "{}")
    new_state = data.get("state")
    product = data.get("product")
    if not new_state:
        return JsonResponse({"status": "error", "message": "state required"}, status=400)

    models_to_search = [_select_model_for_product(product)] if product else _all_models()
    for Model in models_to_search:
        obj = Model.objects.filter(transaction_id=tx).first()
        if obj:
            obj.state = new_state
            obj.save(update_fields=["state"])
            return JsonResponse({"status": "success"}, status=200)
    return JsonResponse({"status": "error", "message": "not found"}, status=404)

# POST /api/applications/state/  (fallback without tx in path)
@csrf_exempt
def update_state_fallback(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    data = json.loads(request.body or "{}")
    tx = data.get("transaction_id")
    if not tx:
        return JsonResponse({"status": "error", "message": "transaction_id required"}, status=400)
    return update_state(request, tx)

# POST /api/applications/ingest/
@csrf_exempt
def ingest_application(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    data = json.loads(request.body or "{}")
    tx = data.get("transaction_id")
    product = data.get("product")
    if not tx:
        return JsonResponse({"status": "error", "message": "transaction_id required"}, status=400)

    Model = _select_model_for_product(product)
    obj, created = Model.objects.get_or_create(transaction_id=tx, defaults={})
    for f in ["application_time","company_name","abn","acn","bankstatements_token","bureau_token",
              "accounting_token","ppsr_token","contact_email","contact_number","originator",
              "state","amount_requested","product","insurance_premiums"]:
        if f in data:
            setattr(obj, f, data[f])
    obj.save()
    return JsonResponse({"status": "success", "created": created}, status=201 if created else 200)






#----------#----------#----------#----------

#trade finance


#----------#----------#----------#----------



import json
import uuid
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import TradeFinanceApplicationService

logger = logging.getLogger(__name__)

@csrf_exempt
def receive_tf_application_data(request):
    """Receiver endpoint for TF ApplicationData from client_app."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body or "{}")
        logger.debug("📌 Received TF application data:\n%s", json.dumps(data, indent=2))

        # Ensure transaction_id
        data["transaction_id"] = data.get("transaction_id") or str(uuid.uuid4())

        # Ensure defaults
        data.setdefault("state", "sales_just_in")
        data.setdefault("product", "Trade Finance")

        # If client sends contact_name only, copy into company_name (aggregate base expects company_name)
        if not data.get("company_name") and data.get("contact_name"):
            data["company_name"] = data["contact_name"]

        result = TradeFinanceApplicationService.process_application_data(data)

        return JsonResponse(result, status=201 if result["status"] == "success" else 400)

    except Exception as e:
        logger.exception("🔥 Exception in receive_tf_application_data")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)







#----------#----------#----------#----------

#scf/earlypayments 


#----------#----------#----------#----------





# application_aggregate/aggregate/views.py
import json
import uuid
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services import ScfApplicationService

logger = logging.getLogger(__name__)

@csrf_exempt
def receive_scf_application_data(request):
    """Receiver endpoint for SCF ApplicationData from client_app."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body or "{}")
        logger.debug("📌 Received SCF application data:\n%s", json.dumps(data, indent=2))

        # Ensure transaction_id
        data["transaction_id"] = data.get("transaction_id") or str(uuid.uuid4())

        # Defaults
        data.setdefault("state", "sales_just_in")
        data.setdefault("product", "SCF / Early Payments")

        # Map contact_name -> company_name for BaseApplicationData compatibility
        if not data.get("company_name") and data.get("contact_name"):
            data["company_name"] = data["contact_name"]

        result = ScfApplicationService.process_application_data(data)
        return JsonResponse(result, status=201 if result["status"] == "success" else 400)

    except Exception as e:
        logger.exception("🔥 Exception in receive_scf_application_data")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)





#----------#----------#----------#----------

#Kanban board display


#----------#----------#----------#----------



from itertools import chain

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData
from .serializers import (
    ApplicationDataSerializer,
    TfApplicationDataSerializer,
    ScfApplicationDataSerializer,
    IpfApplicationDataSerializer,
)


def _filter_common(qs, originator=None):
    if originator:
        qs = qs.filter(originator=originator)
    return qs


@api_view(["GET"])
def applications_list(request):
    """
    Returns a flat list of applications across all aggregate_* tables.
    Optional filter:
      ?originator=<originator name>
    """
    originator = (request.GET.get("originator") or "").strip() or None

    # Query + serialize each model independently, then merge.
    a_qs  = _filter_common(ApplicationData.objects.all(), originator=originator).order_by("-application_time")[:200]
    tf_qs = _filter_common(TfApplicationData.objects.all(), originator=originator).order_by("-application_time")[:200]
    scf_qs= _filter_common(ScfApplicationData.objects.all(), originator=originator).order_by("-application_time")[:200]
    ipf_qs= _filter_common(IpfApplicationData.objects.all(), originator=originator).order_by("-application_time")[:200]

    a  = ApplicationDataSerializer(a_qs, many=True).data
    tf = TfApplicationDataSerializer(tf_qs, many=True).data
    scf= ScfApplicationDataSerializer(scf_qs, many=True).data
    ipf= IpfApplicationDataSerializer(ipf_qs, many=True).data

    # Add app_type so the UI can show/diagnose what product stream it came from
    for row in a:   row["app_type"] = "application"
    for row in tf:  row["app_type"] = "tf_application"
    for row in scf: row["app_type"] = "scf_application"
    for row in ipf: row["app_type"] = "ipf_application"

    merged = list(chain(a, tf, scf, ipf))

    # Sort most recent first (application_time can be null)
    merged.sort(key=lambda r: (r.get("application_time") is not None, r.get("application_time") or ""), reverse=True)

    return Response(merged)




#----- ----#----- ----#----- ----#----- ----#----- ----

#fetch and display application_aggregate data in efs_agent service

#----- ----#----- ----#----- ----#----- ----#----- ----


# application_aggregate/aggregate/views.py
import json
import logging
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from .models import InvoiceFinanceTerms  # keep your existing import
from .models import DealCondition  # <-- add this

logger = logging.getLogger(__name__)

# ---------- helper utilities ----------

def _strip_prefixes(values: dict, product: str) -> dict:
    """
    Map form field names to model fields by removing the product prefix.
    Currently supports Invoice Finance 'if_'.
    """
    # Extend this map when you add models for TF/IPF/SCF.
    prefix_map = {
        "invoice finance": "if_",
        # "trade finance": "tf_",
        # "insurance premium funding": "ipf_",
        # "supply chain finance": "scf_",
    }
    prefix = prefix_map.get((product or "").lower(), "if_")
    cleaned = {}
    for k, v in (values or {}).items():
        if k.startswith(prefix):
            cleaned[k[len(prefix):]] = v
        else:
            # ignore unrelated keys silently
            pass
    return cleaned

def _coerce_to_field_type(model_cls, field_name: str, value):
    """
    Coerce 'value' to the Django field's Python type.
    Unknown fields are ignored by caller.
    """
    try:
        field = model_cls._meta.get_field(field_name)
    except FieldDoesNotExist:
        return (False, None)

    if isinstance(field, models.DecimalField):
        try:
            return (True, Decimal(str(value)))
        except (InvalidOperation, TypeError, ValueError):
            return (False, None)
    if isinstance(field, models.IntegerField):
        try:
            return (True, int(value))
        except (TypeError, ValueError):
            return (False, None)
    # CharField, TextField, etc.
    return (True, value)

# ---------- terms modal endpoints ----------

@require_GET
def terms_modal(request):
    tx = request.GET.get("tx", "")
    return render(request, "terms.html", {"tx": tx})

@require_GET
def fetch_terms(request):
    """
    Fetch stored terms. Prefer 'abn' param; fall back to legacy 'tx'.
    """
    abn = request.GET.get("abn") or request.GET.get("tx")
    if not abn:
        return HttpResponseBadRequest("Missing abn")
    t = InvoiceFinanceTerms.objects.filter(abn=abn).first()
    return JsonResponse({
        "exists": bool(t),
        "abn": abn,
        "originator": getattr(t, "originator", None),
        "facility_limit": str(getattr(t, "facility_limit", "")) if t else None,
        "legal_fees": str(getattr(t, "legal_fees", "")) if t else None,
        "establishment_fee": str(getattr(t, "establishment_fee", "")) if t else None,
        "advanced_rate": str(getattr(t, "advanced_rate", "")) if t else None,
        "minimum_term": getattr(t, "minimum_term", None) if t else None,
        "notice_period": getattr(t, "notice_period", None) if t else None,
        "recourse_period": getattr(t, "recourse_period", None) if t else None,
        "service_fee_amount": str(getattr(t, "service_fee_amount", "")) if t else None,
        "service_fee_percent": str(getattr(t, "service_fee_percent", "")) if t else None,
        "concentration_amount": str(getattr(t, "concentration_amount", "")) if t else None,
        "concentration_percent": str(getattr(t, "concentration_percent", "")) if t else None,
        "base_rate": str(getattr(t, "base_rate", "")) if t else None,
        "charge_rate": str(getattr(t, "charge_rate", "")) if t else None,
        "discount_per_invoice": str(getattr(t, "discount_per_invoice", "")) if t else None,
    })


# application_aggregate/aggregate/views.py

import json
import logging
import re

from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import models

from .models import InvoiceFinanceTerms

logger = logging.getLogger(__name__)

# ---------- helpers ----------

_DIGITS_RE = re.compile(r"\D+")

def _digits_only(s: str) -> str:
    return _DIGITS_RE.sub("", str(s or ""))

def _strip_prefixes(values: dict, product: str | None) -> dict:
    """
    Accepts {"if_facility_limit": 10000, "if_advanced_rate": 80, ...}
    and returns {"facility_limit": 10000, "advanced_rate": 80, ...}
    Only strips prefixes we know about (if_, invoice_finance_).
    """
    if not isinstance(values, dict):
        return {}

    out = {}
    for k, v in values.items():
        key = str(k or "")
        for pref in ("if_", "invoice_finance_"):
            if key.startswith(pref):
                key = key[len(pref):]
                break
        out[key] = v
    return out

def _coerce_to_field_type(model_cls: type[models.Model], field_name: str, raw_val):
    """
    Attempt to coerce raw_val to the Django field's python type.
    Returns (ok: bool, coerced_value).
    Unknown fields return (False, raw_val).
    """
    try:
        field = model_cls._meta.get_field(field_name)
    except Exception:
        return False, raw_val

    # None passes through for nullable fields
    if raw_val is None:
        return True, None

    try:
        if isinstance(field, (models.DecimalField, models.FloatField)):
            # allow "1,234" / "(1,234)" / "1234.56"
            s = str(raw_val).strip()
            neg = s.startswith("(") and s.endswith(")")
            s = s.strip("()").replace(",", "")
            val = float(s)
            return True, (-val if neg else val)

        if isinstance(field, (models.IntegerField, models.BigIntegerField, models.SmallIntegerField)):
            s = str(raw_val).strip().replace(",", "")
            return True, int(float(s))  # tolerate "1234.0"

        if isinstance(field, models.CharField) or isinstance(field, models.TextField):
            return True, str(raw_val).strip()

        if isinstance(field, models.BooleanField):
            if isinstance(raw_val, bool):
                return True, raw_val
            s = str(raw_val).strip().lower()
            return True, s in {"1", "true", "yes", "y", "on"}

        if isinstance(field, models.DateTimeField):
            # Accept ISO string; let model/DB do final validation
            return True, str(raw_val)

        # Fallback: let Django handle it if possible
        return True, raw_val
    except Exception:
        logger.debug("Coercion failed for %s=%r", field_name, raw_val, exc_info=True)
        return False, raw_val




# -----------------------------
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import DealCondition
from .serializers import DealConditionSerializer

@api_view(["GET"])
def deal_conditions_by_tx(request, tx):
    tx = (tx or "").strip()
    qs = DealCondition.objects.filter(transaction_id__iexact=tx).order_by("-date_created")
    ser = DealConditionSerializer(qs, many=True)
    return Response(ser.data)




########################


##save terms 


########################


from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# IMPORTANT: import your terms models
from .models import InvoiceFinanceTerms, TradeFinanceTerms, SupplyChainFinanceTerms


def _digits_only(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _select_terms_model_and_prefixes(product: str):
    """
    Returns (ModelClass, prefixes_tuple, canonical_product_name)
    """
    p = (product or "").strip().lower()

    # SCF
    if "supply" in p or "scf" in p or "early payment" in p:
        return (SupplyChainFinanceTerms, ("scf_", "supply_chain_finance_"), "Supply Chain Finance")

    # TF
    if "trade" in p or p == "tf":
        return (TradeFinanceTerms, ("tf_", "trade_finance_"), "Trade Finance")

    # default IF
    return (InvoiceFinanceTerms, ("if_", "invoice_finance_"), "Invoice Finance")


def _strip_prefixes(values: dict, prefixes: tuple, model_cls=None):
    """
    Strips prefixes ONLY if the stripped key exists as a field on model_cls.
    Otherwise keeps original key.
    """
    if not isinstance(values, dict):
        return {}

    model_fields = set()
    if model_cls is not None:
        model_fields = {f.name for f in model_cls._meta.get_fields()}

    out = {}
    for k, v in values.items():
        original_key = str(k or "")
        key = original_key

        for pref in prefixes:
            if key.startswith(pref):
                candidate = key[len(pref):]
                # Only accept stripped name if it is a real model field
                if not model_fields or candidate in model_fields:
                    key = candidate
                else:
                    key = original_key
                break

        out[key] = v
    return out



def _coerce_to_field_type(model_cls, field_name: str, raw_val, logger=None):
    """
    Coerce raw_val into the model field's type.
    Unknown fields => (False, raw_val)
    """
    try:
        field = model_cls._meta.get_field(field_name)
    except Exception:
        return False, raw_val

    if raw_val is None:
        return True, None

    try:
        from django.db import models
        from decimal import Decimal

        if isinstance(field, (models.DecimalField, models.FloatField)):
            s = str(raw_val).strip()
            neg = s.startswith("(") and s.endswith(")")
            s = s.strip("()").replace(",", "")
            val = Decimal(s)
            return True, (-val if neg else val)

        if isinstance(field, (models.IntegerField, models.BigIntegerField, models.SmallIntegerField)):
            s = str(raw_val).strip().replace(",", "")
            return True, int(Decimal(s))  # tolerate "1234.0"

        if isinstance(field, (models.CharField, models.TextField)):
            return True, str(raw_val).strip()

        if isinstance(field, models.BooleanField):
            if isinstance(raw_val, bool):
                return True, raw_val
            s = str(raw_val).strip().lower()
            return True, s in {"1", "true", "yes", "y", "on"}

        return True, raw_val
    except Exception:
        if logger:
            logger.debug("Coercion failed for %s=%r", field_name, raw_val, exc_info=True)
        return False, raw_val


@csrf_exempt
@require_POST
def save_terms(request):
    """
    Saves terms into the correct Terms model based on product.
    Supports:
      - Flat fields payload
      - Legacy {"values": {...}} payload with prefixed keys
    Upserts by ABN.
    """
    # ---- parse JSON ----
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return HttpResponseBadRequest("Invalid JSON")

    product = (payload.get("product") or "Invoice Finance").strip()
    TermsModel, prefixes, canonical_product = _select_terms_model_and_prefixes(product)

    # ---- sanitize ids ----
    abn_raw = payload.get("abn") or payload.get("abn_number")
    abn = _digits_only(abn_raw)
    if len(abn) != 11:
        return JsonResponse({"status": "error", "message": "ABN must be 11 digits"}, status=400)

    acn_raw = payload.get("acn")
    acn = _digits_only(acn_raw) if acn_raw else None
    if acn and len(acn) != 9:
        return JsonResponse({"status": "error", "message": "ACN must be 9 digits"}, status=400)

    originator_name = (payload.get("originator") or payload.get("originator_name") or "").strip() or None
    if originator_name and len(originator_name) > 255:
        originator_name = originator_name[:255]

    # ---- collect fields to apply ----
    flat_fields = {
        k: v for k, v in payload.items()
        if k not in {"product", "values", "originator_name"}
    }
    values_block = payload.get("values") or {}

    # Strip only prefixes relevant to this product
    cleaned_from_values = _strip_prefixes(values_block, prefixes, model_cls=TermsModel)

    # Merge (values block wins)
    to_apply = {**flat_fields, **cleaned_from_values}

    # Remove ids/meta (not model fields)
    for k in ("abn", "abn_number", "acn", "originator", "originator_name", "product"):
        to_apply.pop(k, None)

    # ---- upsert by ABN (per product model) ----
    terms, created = TermsModel.objects.get_or_create(
        abn=abn,
        defaults={
            "originator": originator_name,
            "acn": acn,
        },
    )

    updated_fields = []

    # Keep these up to date on every model
    if originator_name and originator_name != (getattr(terms, "originator", None) or ""):
        terms.originator = originator_name
        updated_fields.append("originator")

    if acn is not None and acn != (getattr(terms, "acn", None) or ""):
        terms.acn = acn
        updated_fields.append("acn")

    # ---- set model fields (ignore unknowns safely) ----
    for field_name, raw_val in to_apply.items():
        ok, coerced = _coerce_to_field_type(TermsModel, field_name, raw_val, logger=logger)
        if not ok:
            logger.debug("Skipping unknown/invalid field %s=%r for %s", field_name, raw_val, TermsModel.__name__)
            continue

        try:
            TermsModel._meta.get_field(field_name)  # ensure real field
            setattr(terms, field_name, coerced)
            updated_fields.append(field_name)
        except Exception:
            logger.debug("Unknown model field: %s on %s", field_name, TermsModel.__name__)
            continue

    # ---- persist ----
    if created:
        terms.save()
        status_code = 201
    elif updated_fields:
        terms.save(update_fields=list(sorted(set(updated_fields))))
        status_code = 200
    else:
        status_code = 200

    return JsonResponse(
        {
            "status": "success",
            "created": created,
            "id": terms.id,
            "product": canonical_product,
            "model": TermsModel.__name__,
            "message": "Terms saved" if updated_fields or created else "No changes",
        },
        status=status_code,
    )




########################


##Deal workshop!


########################




# application_aggregate/aggregate/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData

# application_aggregate/aggregate/views.py
# application_aggregate/aggregate/views.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .models import ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData

def _all_aggregate_models():
    return [ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData]

@require_GET
def aggregate_by_tx(request, tx: str):
    tx = (tx or "").strip()
    if not tx:
        return JsonResponse({"ok": False, "error": "transaction_id required"}, status=400)

    obj = None
    for Model in _all_aggregate_models():
        candidate = (
            Model.objects
            .filter(transaction_id=tx)
            .order_by("-application_time", "-id")
            .first()
        )
        if candidate:
            obj = candidate
            break

    if not obj:
        return JsonResponse(
            {"ok": True, "found": False, "transaction_id": tx},
            status=200,
        )

    # ✅ IMPORTANT: include links + link_description
    return JsonResponse(
        {
            "ok": True,
            "found": True,
            "model": obj.__class__.__name__,
            "db_table": obj._meta.db_table,

            "transaction_id": obj.transaction_id,
            "company_name": obj.company_name,
            "amount_requested": str(obj.amount_requested) if obj.amount_requested is not None else None,

            "abn": obj.abn,
            "acn": obj.acn,
            "state": obj.state,
            "product": obj.product,

            "links": obj.links or [],
            "link_description": obj.link_description or "",
        },
        status=200,
    )







#-----------fetch application aggregate data for efs_agent service -------


from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Value, F
from django.db.models.functions import Replace

from .models import (
    InvoiceFinanceTerms,
    TradeFinanceTerms,
    SupplyChainFinanceTerms,
    ApplicationData,
    TfApplicationData,
    ScfApplicationData,
    IpfApplicationData,
)

def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

def _clean_digits_expr(field_name: str):
    return Replace(
        Replace(
            Replace(
                Replace(
                    Replace(F(field_name), Value(" "), Value("")),
                    Value("-"), Value("")
                ),
                Value("/"), Value("")
            ),
            Value("."), Value("")
        ),
        Value("\t"), Value("")
    )

def _serialize_terms(obj, product: str) -> dict:
    base = {
        "product": product,
        "id": obj.id,
        "originator": getattr(obj, "originator", None),
        "abn": getattr(obj, "abn", None),
        "acn": getattr(obj, "acn", None),
        "timestamp": obj.timestamp.isoformat() if getattr(obj, "timestamp", None) else None,
    }

    if product == "invoice_finance":
        base.update({
            "facility_limit": str(obj.facility_limit),
            "legal_fees": str(obj.legal_fees),
            "establishment_fee": str(obj.establishment_fee),
            "advanced_rate": str(obj.advanced_rate),
            "minimum_term": obj.minimum_term,
            "notice_period": obj.notice_period,
            "recourse_period": obj.recourse_period,
            "service_fee_amount": str(obj.service_fee_amount),
            "service_fee_percent": str(obj.service_fee_percent),
            "concentration_amount": str(obj.concentration_amount),
            "concentration_percent": str(obj.concentration_percent),
            "base_rate": str(obj.base_rate),
            "charge_rate": str(obj.charge_rate),
            "discount_per_invoice": str(obj.discount_per_invoice),
        })
        return base

    if product == "trade_finance":
        base.update({
            "facility_limit": str(obj.facility_limit),
            "legal_fees": str(obj.legal_fees),
            "establishment_fee": str(obj.establishment_fee),
            "advanced_rate": str(obj.advanced_rate),
            "interest_rate": str(obj.interest_rate),
            "minimum_term": obj.minimum_term,
            "notice_period": obj.notice_period,
            "payment_term": obj.payment_term,
            "num_installments": obj.num_installments,
            "installment_period": obj.installment_period,
            "service_fee_amount": str(obj.service_fee_amount),
            "service_fee_percent": str(obj.service_fee_percent),
            "base_rate": str(obj.base_rate),
            "charge_rate": str(obj.charge_rate),
        })
        return base

    if product == "supply_chain_finance":
        base.update({
            "scf_limit": str(obj.scf_limit),
            "scf_setup_fee": str(obj.scf_setup_fee),
            "scf_discount_rate": str(obj.scf_discount_rate),
            "scf_payment_terms": obj.scf_payment_terms,
            "scf_min_invoice": str(obj.scf_min_invoice),
            "scf_rate_per_invoice": str(obj.scf_rate_per_invoice),
        })
        return base

    return base

def _latest_terms_for_model(model_cls, product: str, abn_digits: str, acn_digits: str):
    qs = model_cls.objects.all()

    if abn_digits and len(abn_digits) == 11:
        abn_clean = _clean_digits_expr("abn")
        obj = (
            qs.annotate(_abn_clean=abn_clean)
              .filter(_abn_clean=abn_digits)
              .order_by("-timestamp", "-id")
              .first()
        )
        if obj:
            return _serialize_terms(obj, product), "abn"

    if acn_digits and len(acn_digits) == 9:
        acn_clean = _clean_digits_expr("acn")
        obj = (
            qs.annotate(_acn_clean=acn_clean)
              .filter(_acn_clean=acn_digits)
              .order_by("-timestamp", "-id")
              .first()
        )
        if obj:
            return _serialize_terms(obj, product), "acn"

    return None, None

def _get_application_by_tx(tx: str):
    for model_cls, product in [
        (ApplicationData, "invoice_finance"),
        (TfApplicationData, "trade_finance"),
        (ScfApplicationData, "supply_chain_finance"),
        (IpfApplicationData, "ipf"),
    ]:
        obj = model_cls.objects.filter(transaction_id=tx).first()
        if obj:
            return obj, product
    return None, None

@require_GET
def terms_fetch(request):
    """
    GET /application/terms/fetch/?abn=123...
    GET /application/terms/fetch/?acn=...
    GET /application/terms/fetch/?tx=<transaction_id>   (tx used ONLY to find ABN/ACN from application tables)
    GET /application/terms/fetch/?tx=...&abn=...        (tx -> app still preferred for ABN/ACN, request values used as fallback)
    """
    tx = (request.GET.get("tx") or request.GET.get("transaction_id") or "").strip()

    abn_digits = _digits_only((request.GET.get("abn") or "").strip())
    acn_digits = _digits_only((request.GET.get("acn") or "").strip())

    app_product = None
    app_found = False

    # ✅ If tx is supplied: use it ONLY against Application tables to get ABN/ACN
    if tx:
        app_obj, app_product = _get_application_by_tx(tx)
        if app_obj:
            app_found = True
            abn_digits = _digits_only(getattr(app_obj, "abn", "") or "") or abn_digits
            acn_digits = _digits_only(getattr(app_obj, "acn", "") or "") or acn_digits

    if not (abn_digits or acn_digits):
        return JsonResponse(
            {"ok": False, "error": "Provide tx (that resolves to ABN/ACN) or provide abn/acn"},
            status=400
        )

    results = {}
    sources = {}

    inv, inv_src = _latest_terms_for_model(InvoiceFinanceTerms, "invoice_finance", abn_digits, acn_digits)
    tf,  tf_src  = _latest_terms_for_model(TradeFinanceTerms, "trade_finance", abn_digits, acn_digits)
    scf, scf_src = _latest_terms_for_model(SupplyChainFinanceTerms, "supply_chain_finance", abn_digits, acn_digits)

    results["invoice_finance"] = inv
    results["trade_finance"] = tf
    results["supply_chain_finance"] = scf

    sources["invoice_finance"] = inv_src
    sources["trade_finance"] = tf_src
    sources["supply_chain_finance"] = scf_src

    candidates = [x for x in [inv, tf, scf] if x and x.get("timestamp")]
    candidates.sort(key=lambda d: (d.get("timestamp") or "", d.get("id") or 0), reverse=True)
    latest_any = candidates[0] if candidates else (inv or tf or scf)

    return JsonResponse({
        "ok": True,
        "query": {
            "tx": tx or None,
            "abn": abn_digits or None,
            "acn": acn_digits or None,
        },
        "application_context": {
            "found": app_found,
            "product": app_product,
        },
        "sources": sources,
        "latest_any": latest_any,
        "latest": results,
    }, status=200)








#-------code to link applications-----


    #code to link applications


#-------code to link applications-----

# this code displays the modal to create the links between entities 


# ============================================================
# application_aggregate/core/views.py  (LINKING SECTION ONLY)
# ============================================================

import json
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Value
from django.db.models.functions import Replace
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData

log = logging.getLogger(__name__)

# ------------------------------------------------------------
# 0) Model -> Product mapping (used ONLY for link_description text)
# ------------------------------------------------------------
MODEL_TO_PRODUCT = {
    "ApplicationData": "Invoice finance",
    "TfApplicationData": "Trade finance",
    "ScfApplicationData": "Supply chain finance",
    "IpfApplicationData": "Insurance premium funding",
}

CONCRETE_MODELS = [
    ("ApplicationData", ApplicationData),
    ("TfApplicationData", TfApplicationData),
    ("ScfApplicationData", ScfApplicationData),
    ("IpfApplicationData", IpfApplicationData),
]


# ------------------------------------------------------------
# 1) Shared helpers
# ------------------------------------------------------------
def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _classify_id_type(digits: str) -> str:
    """
    11 digits -> 'abn'
     9 digits -> 'acn'
    else -> ''
    """
    if len(digits) == 11:
        return "abn"
    if len(digits) == 9:
        return "acn"
    return ""


def _valid_len(kind, val):
    if kind == "abn":
        return len(val) == 11
    if kind == "acn":
        return len(val) == 9
    return False


def _norm_digits_expr(field_name: str):
    """
    DB expression to strip common separators so we can do digits-only equality.
    """
    expr = F(field_name)
    for ch in (" ", "-", "/", ".", "\u00A0"):
        expr = Replace(expr, Value(ch), Value(""))
    return expr


# ------------------------------------------------------------
# 2) Resolve which model(s) an entity belongs to (optionally per transaction_id)
#    This is the ONLY "new logic" and it is used ONLY for description text.
# ------------------------------------------------------------
def _resolve_models_for_entity(id_digits: str, id_type: str, transaction_id: str = "") -> list[str]:
    """
    Return list of model names that match this entity ID.
    If transaction_id is provided, it narrows the match to that specific row.

    This lets us say things like:
      "Invoice finance ApplicationData"
      "Trade finance TfApplicationData"
    in link_description.
    """
    if not id_digits or id_type not in ("abn", "acn"):
        return []

    tx = (transaction_id or "").strip()
    hits = []

    for model_name, Model in CONCRETE_MODELS:
        qs = Model.objects.all()

        if id_type == "abn":
            qs = qs.annotate(_abn_digits=_norm_digits_expr("abn")).filter(_abn_digits=id_digits)
        else:
            qs = qs.annotate(_acn_digits=_norm_digits_expr("acn")).filter(_acn_digits=id_digits)

        if tx:
            qs = qs.filter(transaction_id=tx)

        if qs.exists():
            hits.append(model_name)

    return hits


def _models_to_label(model_names: list[str]) -> str:
    """
    ["TfApplicationData"] -> "Trade finance TfApplicationData"
    ["ApplicationData","TfApplicationData"] -> "Invoice finance ApplicationData / Trade finance TfApplicationData"
    """
    if not model_names:
        return ""
    bits = []
    for mn in model_names:
        prod = MODEL_TO_PRODUCT.get(mn, "")
        bits.append(f"{prod} {mn}".strip() if prod else mn)
    return " / ".join(bits)


# ------------------------------------------------------------
# 3) ABN / ACN dropdown endpoints (unchanged behaviour)
# ------------------------------------------------------------
MODEL_SOURCES = [
    ("ApplicationData", ApplicationData),
    ("TfApplicationData", TfApplicationData),
    ("ScfApplicationData", ScfApplicationData),
    ("IpfApplicationData", IpfApplicationData),
]


@require_GET
def application_abns(request):
    """
    Return ABNs as dropdown options per INSTANCE (row),
    including transaction_id + state.
    """
    items = []
    seen = set()  # (abn_digits, model_name, transaction_id)

    for model_name, Model in MODEL_SOURCES:
        qs = (
            Model.objects
            .exclude(abn__isnull=True).exclude(abn="")
            .values("abn", "transaction_id", "state")
        )

        for row in qs.iterator():
            digits = _digits_only(row.get("abn", ""))
            if len(digits) != 11:
                continue

            tx = str(row.get("transaction_id") or "").strip()
            st = str(row.get("state") or "").strip()

            key = (digits, model_name, tx)
            if key in seen:
                continue
            seen.add(key)

            tx_short = (tx[:8] + "…") if len(tx) > 9 else tx

            items.append({
                "id": digits,
                "transaction_id": tx,
                "state": st,
                "sources": [model_name],
                "label": f"{digits} — {model_name} — {st or 'no_state'} — {tx_short or 'no_tx'}",
            })

    items.sort(key=lambda x: (x["id"], x["sources"][0], x.get("state") or "", x.get("transaction_id") or ""))
    return JsonResponse({"ok": True, "abns": items})


@require_GET
def application_acns(request):
    """
    Return ACNs as dropdown options per INSTANCE (row),
    including transaction_id + state.
    """
    items = []
    seen = set()  # (acn_digits, model_name, transaction_id)

    for model_name, Model in MODEL_SOURCES:
        qs = (
            Model.objects
            .exclude(acn__isnull=True).exclude(acn="")
            .values("acn", "transaction_id", "state")
        )

        for row in qs.iterator():
            digits = _digits_only(row.get("acn", ""))
            if len(digits) != 9:
                continue

            tx = str(row.get("transaction_id") or "").strip()
            st = str(row.get("state") or "").strip()

            key = (digits, model_name, tx)
            if key in seen:
                continue
            seen.add(key)

            tx_short = (tx[:8] + "…") if len(tx) > 9 else tx

            items.append({
                "id": digits,
                "transaction_id": tx,
                "state": st,
                "sources": [model_name],
                "label": f"{digits} — {model_name} — {st or 'no_state'} — {tx_short or 'no_tx'}",
            })

    items.sort(key=lambda x: (x["id"], x["sources"][0], x.get("state") or "", x.get("transaction_id") or ""))
    return JsonResponse({"ok": True, "acns": items})


# ------------------------------------------------------------
# 4) Links storage helper (unchanged behaviour)
# ------------------------------------------------------------
def _append_link_obj(existing_list, new_id, new_type, new_tx=None, new_state=None):
    """
    Normalize existing_list to list[dict] and append a NEW dict link.
    - Keeps legacy strings working.
    - Dedupe by (id, type, transaction_id) so you can store multiple links
      to the same id/type if transaction_id differs.
    """
    normalized = []

    for item in (existing_list or []):
        # existing dict (might already contain tx/state)
        if isinstance(item, dict):
            cur_id = _digits_only(item.get("id", ""))
            cur_type = (item.get("type") or "").strip().lower()

            if cur_type not in ("abn", "acn"):
                if len(cur_id) == 11:
                    cur_type = "abn"
                elif len(cur_id) == 9:
                    cur_type = "acn"

            if not (cur_id and cur_type in ("abn", "acn")):
                continue

            obj = {"id": cur_id, "type": cur_type}

            # preserve if already present
            tx = (item.get("transaction_id") or "").strip()
            st = (item.get("state") or "").strip()
            if tx:
                obj["transaction_id"] = tx
            if st:
                obj["state"] = st

            normalized.append(obj)
            continue

        # legacy string
        cur_id = _digits_only(item)
        cur_type = ""
        if len(cur_id) == 11:
            cur_type = "abn"
        elif len(cur_id) == 9:
            cur_type = "acn"

        if cur_id and cur_type:
            normalized.append({"id": cur_id, "type": cur_type})

    # append the new link object (with tx/state)
    if new_id and new_type in ("abn", "acn"):
        new_obj = {"id": new_id, "type": new_type}
        if new_tx:
            new_obj["transaction_id"] = str(new_tx).strip()
        if new_state:
            new_obj["state"] = str(new_state).strip()
        normalized.append(new_obj)

    # dedupe by (id, type, transaction_id)
    dedup = {}
    for obj in normalized:
        key = (obj["id"], obj["type"], obj.get("transaction_id", ""))
        dedup[key] = obj

    return list(dedup.values())


# ------------------------------------------------------------
# 5) Description helper (UPDATED: now includes model/product label strings)
# ------------------------------------------------------------
def _append_description(existing_desc,
                        id_a, type_a, models_a_label,
                        id_b, type_b, models_b_label,
                        nature_text):
    left_label  = "ABN" if type_a == "abn" else "ACN"
    right_label = "ABN" if type_b == "abn" else "ACN"

    left = f"{id_a} ({left_label})"
    right = f"{id_b} ({right_label})"

    # ✅ Add "Invoice finance ApplicationData" etc (if known)
    if models_a_label:
        left = f"{left} {models_a_label}"
    if models_b_label:
        right = f"{right} {models_b_label}"

    if nature_text:
        new_line = f"{left} linked to {right} [{nature_text}]"
    else:
        new_line = f"{left} linked to {right}"

    existing_desc = (existing_desc or "").strip()
    lines = [l.strip() for l in existing_desc.splitlines() if l.strip()]
    if new_line not in lines:
        lines.append(new_line)
    return "\n".join(lines)


# ------------------------------------------------------------
# 6) Update rows for a given entity (UPDATED signature + description call)
# ------------------------------------------------------------
def _update_id(id_digits, id_type, other_digits, other_type, nature_text,
               other_tx=None, other_state=None,
               self_models_label="", other_models_label=""):
    updated = 0
    skipped = 0
    errors = []

    for Model in (ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData):
        if id_type == "abn":
            rows = (
                Model.objects
                .annotate(_abn_digits=_norm_digits_expr("abn"))
                .filter(_abn_digits=id_digits)
            )
        else:
            rows = (
                Model.objects
                .annotate(_acn_digits=_norm_digits_expr("acn"))
                .filter(_acn_digits=id_digits)
            )

        for r in rows:
            try:
                r.links = _append_link_obj(
                    getattr(r, "links", None),
                    other_digits,
                    other_type,
                    new_tx=other_tx,
                    new_state=other_state,
                )

                # ✅ UPDATED: include the model/product labels in link_description
                r.link_description = _append_description(
                    getattr(r, "link_description", None),
                    id_digits, id_type, self_models_label,
                    other_digits, other_type, other_models_label,
                    nature_text
                )

                r.save(update_fields=["links", "link_description"])
                updated += 1

            except ValidationError as ve:
                skipped += 1
                errors.append({
                    "model": Model._meta.label,
                    "pk": getattr(r, "pk", None),
                    "error": "ValidationError",
                    "detail": ve.message_dict if hasattr(ve, "message_dict") else str(ve),
                })
            except Exception as e:
                skipped += 1
                errors.append({
                    "model": Model._meta.label,
                    "pk": getattr(r, "pk", None),
                    "error": type(e).__name__,
                    "detail": str(e),
                })

    return updated, skipped, errors


# ------------------------------------------------------------
# 7) Save links endpoint (UPDATED: computes labels and passes them to _update_id)
# ------------------------------------------------------------
@require_POST
@csrf_exempt
@transaction.atomic
def application_links_save(request):
    """
    Accepts:
    {
      "id_a": "12345678901",
      "id_b": "987654321",
      "id_type_a": "abn"|"acn",
      "id_type_b": "abn"|"acn",
      "nature_a": "...",
      "nature_b": "...",

      // OPTIONAL (from dropdown instance metadata)
      "transaction_id_a": "...",
      "transaction_id_b": "...",
      "state_a": "...",
      "state_b": "..."
    }

    Updates BOTH directions across all models:
      - add B into A.links and A into B.links
      - append descriptive line into link_description (NOW includes product/model)
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    id_a       = body.get("id_a") or body.get("abn_a") or ""
    id_b       = body.get("id_b") or body.get("abn_b") or ""
    id_type_a  = (body.get("id_type_a") or ("abn" if body.get("abn_a") else "")).strip().lower()
    id_type_b  = (body.get("id_type_b") or ("abn" if body.get("abn_b") else "")).strip().lower()
    nature_a   = (body.get("nature_a") or "").strip()
    nature_b   = (body.get("nature_b") or "").strip()

    # existing optional metadata (you already had this)
    tx_a = (body.get("transaction_id_a") or "").strip()
    tx_b = (body.get("transaction_id_b") or "").strip()
    st_a = (body.get("state_a") or "").strip()
    st_b = (body.get("state_b") or "").strip()

    id_a_digits = _digits_only(id_a)
    id_b_digits = _digits_only(id_b)

    if id_type_a not in ("abn", "acn") or id_type_b not in ("abn", "acn"):
        return JsonResponse({"ok": False, "error": "id_type_a/b must be 'abn' or 'acn'."}, status=400)

    if not _valid_len(id_type_a, id_a_digits) or not _valid_len(id_type_b, id_b_digits):
        return JsonResponse({"ok": False, "error": "IDs must match correct length: ABN=11, ACN=9."}, status=400)

    # ✅ NEW (but safe): infer which model(s) each side belongs to,
    # using transaction_id if provided to disambiguate.
    label_a = _models_to_label(_resolve_models_for_entity(id_a_digits, id_type_a, tx_a))
    label_b = _models_to_label(_resolve_models_for_entity(id_b_digits, id_type_b, tx_b))

    try:
        # Update A rows (describe A -> B)
        a_updated, a_skipped, a_errors = _update_id(
            id_a_digits, id_type_a,
            id_b_digits, id_type_b,
            nature_a,
            other_tx=tx_b,
            other_state=st_b,
            self_models_label=label_a,
            other_models_label=label_b,
        )

        # Update B rows (describe B -> A)
        b_updated, b_skipped, b_errors = _update_id(
            id_b_digits, id_type_b,
            id_a_digits, id_type_a,
            nature_b,
            other_tx=tx_a,
            other_state=st_a,
            self_models_label=label_b,
            other_models_label=label_a,
        )

    except Exception as e:
        return JsonResponse(
            {"ok": False, "error": f"Save failed: {type(e).__name__}: {e}"},
            status=500,
        )

    return JsonResponse(
        {
            "ok": True,
            "updated_rows": {"a": a_updated, "b": b_updated},
            "skipped_rows": {"a": a_skipped, "b": b_skipped},
            "errors": (a_errors + b_errors)[:50],
            # optional debug so you can see what it inferred
            "labels": {"a": label_a, "b": label_b},
        },
        status=200,
    )


# ------------------------------------------------------------
# 8) Linked-entities graph endpoint (UNCHANGED from your section)
# ------------------------------------------------------------
def _id_pattern(id_digits: str) -> str:
    return rf'^(?:[^0-9]*{"[^0-9]*".join(list(id_digits))}[^0-9]*)$'


def _normalize_links(raw_links):
    if raw_links is None:
        raw_links = []

    norm = []
    if not isinstance(raw_links, list):
        return norm

    for entry in raw_links:
        if isinstance(entry, str):
            digits = _digits_only(entry)
            t = _classify_id_type(digits)
            if digits and t:
                norm.append({"id": digits, "type": t})
            continue

        if isinstance(entry, dict):
            digits = _digits_only(entry.get("id", ""))
            t = (entry.get("type") or "").strip().lower()
            if t not in ("abn", "acn"):
                t = _classify_id_type(digits)
            if digits and t and _classify_id_type(digits) == t:
                norm.append({"id": digits, "type": t})
            continue

    seen = {}
    for l in norm:
        seen[(l["id"], l["type"])] = l
    return list(seen.values())


def _collect_rows_for_entity_id(entity_digits: str, entity_type: str):
    models = [ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData]
    matched_rows = []

    col_regex_filter = (
        Q(abn__regex=_id_pattern(entity_digits))
        if entity_type == "abn"
        else Q(acn__regex=_id_pattern(entity_digits))
    )

    for mdl in models:
        qs = mdl.objects.filter(
            col_regex_filter
            | Q(links__icontains=entity_digits)
        )

        for row in qs:
            abn_digits = _digits_only(getattr(row, "abn", "") or "")
            acn_digits = _digits_only(getattr(row, "acn", "") or "")
            links_norm = _normalize_links(getattr(row, "links", []))
            matched_rows.append({
                "model": mdl._meta.db_table,
                "transaction_id": getattr(row, "transaction_id", "") or "",
                "abn": abn_digits,
                "acn": acn_digits,
                "links": links_norm,
                "link_description": (getattr(row, "link_description", "") or "").strip(),
                "contact_name": getattr(row, "contact_name", "") or "",
                "product": getattr(row, "product", "") or "",
                "state": getattr(row, "state", "") or "",
            })
    return matched_rows


def _build_graph(seed_id: str, rows: list[dict]):
    nodes = {}
    edges = []

    def add_node(id_digits: str, row: dict):
        if not id_digits:
            return
        if id_digits not in nodes:
            nodes[id_digits] = {
                "id": id_digits,
                "contact_names": set(),
                "products": set(),
                "states": set(),
            }
        if row.get("contact_name"):
            nodes[id_digits]["contact_names"].add(row["contact_name"])
        if row.get("product"):
            nodes[id_digits]["products"].add(row["product"])
        if row.get("state"):
            nodes[id_digits]["states"].add(row["state"])

    for r in rows:
        main_ids = []
        if r["abn"]:
            main_ids.append(r["abn"])
        if r["acn"]:
            main_ids.append(r["acn"])

        for mid in main_ids:
            add_node(mid, r)

        link_desc = r["link_description"]
        for link_obj in r["links"]:
            linked_id = link_obj.get("id", "")
            if not linked_id:
                continue

            add_node(linked_id, r)

            for mid in main_ids:
                if not mid or mid == linked_id:
                    continue
                edges.append({
                    "from": mid,
                    "to": linked_id,
                    "note": link_desc,
                })

    for _, info in nodes.items():
        info["contact_names"] = list(info["contact_names"])
        info["products"] = list(info["products"])
        info["states"] = list(info["states"])

    return {
        "seed": seed_id,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


@require_GET
def linked_entities(request):
    raw_id = request.GET.get("abn", "") or request.GET.get("id", "")
    entity_digits = _digits_only(raw_id)
    entity_type = _classify_id_type(entity_digits)

    if not entity_digits or not entity_type:
        return JsonResponse(
            {
                "ok": False,
                "error": "ID must be a valid 11-digit ABN or 9-digit ACN",
                "id": entity_digits,
            },
            status=400,
        )

    rows = _collect_rows_for_entity_id(entity_digits, entity_type)

    if not rows:
        return JsonResponse({
            "ok": True,
            "seed": entity_digits,
            "ids": [],
            "graph": {"seed": entity_digits, "nodes": [], "edges": []},
        })

    all_ids = set()
    for r in rows:
        if r["abn"]:
            all_ids.add(r["abn"])
        if r["acn"]:
            all_ids.add(r["acn"])
        for l in r["links"]:
            if l.get("id"):
                all_ids.add(l["id"])

    graph = _build_graph(entity_digits, rows)

    return JsonResponse({
        "ok": True,
        "seed": entity_digits,
        "ids": sorted(all_ids),
        "graph": graph,
    }, status=200)


########################
# End linked_entities Section 
########################
















########################

##Delete Transactions!!!!

########################


        ########################

        ##Delete application!!!!

        ########################

# DELETE/POST: /api/applications/<tx>/delete/
# application_aggregate/core/views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseNotAllowed

@csrf_exempt
def delete_application(request, tx):
    if request.method not in ("DELETE", "POST"):
        return HttpResponseNotAllowed(["DELETE", "POST"])

    product = request.GET.get("product")
    models_to_search = [_select_model_for_product(product)] if product else _all_models()

    deleted_primary = None
    primary_model = None
    for Model in models_to_search:
        obj = Model.objects.filter(transaction_id=tx).first()
        if obj:
            primary_model = Model._meta.db_table
            obj.delete()
            deleted_primary = True
            break

    # ✅ use the HTTP fan-out
    purge_summary = _purge_downstream_for_tx_http(tx)

    status = 200 if deleted_primary else 404
    payload = {
        "status": "success" if deleted_primary else "error",
        "deleted_tx": tx,
        "primary_model": primary_model,
        "purge_summary": purge_summary,
    }
    if not deleted_primary:
        payload["message"] = "application row not found (downstream still purged by tx)"

    return JsonResponse(payload, status=status, safe=False)

# application_aggregate/core/views.py (excerpt)
# application_aggregate/core/views.py (excerpt)
# application_aggregate/core/views.py (excerpt)
# application_aggregate/core/views.py (excerpt)
import os, requests

EFS_DATA_FINANCIAL_BASE = os.getenv("EFS_DATA_FINANCIAL_BASE", "http://localhost:8019")
# Remove efs_sales here; NAV is in efs_data_financial

def _purge_downstream_for_tx_http(tx: str):
    summary = []

    def hit(base, path, label):
        try:
            r = requests.post(f"{base}{path}", timeout=10)
            data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
            summary.append((label, r.status_code, data.get("counts", {})))
        except Exception as e:
            summary.append((label, 502, {"error": str(e)}))

    # assets in efs_data_financial
    hit(EFS_DATA_FINANCIAL_BASE, f"/api/purge/{tx}/",      "efs_data_financial.assets")
    # NAV (snapshot + lines) also in efs_data_financial
    hit(EFS_DATA_FINANCIAL_BASE, f"/api/nav/purge/{tx}/",  "efs_data_financial.nav")

    return summary


#__________  RAG/Generation code for dropdown menu in generation.html page  __________



# application_aggregate/aggregate/views.py

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import ApplicationData



def sales_review_deals(request):
    """
    Returns deals for a given originator (and optional state),
    based on aggregate_applicationdata.

    GET /api/sales-review-deals/?originator=<name>&state=sales_review
    """
    originator = request.GET.get("originator") or ""
    state = request.GET.get("state") or "sales_review"

    qs = ApplicationData.objects.all()

    if originator:
        qs = qs.filter(originator=originator)

    if state:
        qs = qs.filter(state=state)

    qs = qs.order_by("-application_time")[:200]

    deals = [
        {
            "transaction_id": obj.transaction_id,
            "company_name": obj.company_name,
            "abn": obj.abn,
            "acn": obj.acn,
        }
        for obj in qs
    ]

    return JsonResponse({"deals": deals})



#__________ #__________ #__________ #__________ 


#Fetch and display application data in right side panel dropdown menu


#__________ #__________ #__________ #__________ 


import os
import logging
import requests

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import (
    ApplicationData,
    TfApplicationData,
    ScfApplicationData,
    IpfApplicationData,
)

logger = logging.getLogger(__name__)


def _profile_base() -> str:
    return os.getenv("EFS_PROFILE_URL", "http://localhost:8002").rstrip("/")


def _originator_name_from_id(originator_id: str) -> str | None:
    """
    Convert originator numeric ID (from efs_profile) into originator name string.
    Returns None if not found.
    """
    if not originator_id:
        return None

    try:
        url = f"{_profile_base()}/api/originators/"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()

        originators = data.get("originators", data if isinstance(data, list) else [])
        for o in originators:
            if str(o.get("id")) == str(originator_id):
                # your profile API uses "originator" for name
                return o.get("originator")
    except Exception:
        logger.exception("Failed to map originator id -> name via efs_profile")

    return None


def _clean_qs(qs):
    return qs.exclude(transaction_id__isnull=True).exclude(transaction_id="")


def _qs_to_deals(qs, product_fallback: str | None = None):
    """
    Convert a queryset to a list of dicts with stable keys.
    """
    rows = _clean_qs(qs).values(
        "transaction_id",
        "company_name",
        "product",
        "originator",
        "state",
        "application_time",
        "abn",
    )

    out = []
    for r in rows:
        if product_fallback and not r.get("product"):
            r["product"] = product_fallback
        out.append(r)
    return out


@require_GET
def live_deals(request):
    """
    GET /api/live-deals/
    Optional filters:
      - ?originators=<id>  (numeric originator id from profile service)
      - ?originator=<name> (originator string name)
    Returns: JSON list
    """
    originator_id = request.GET.get("originators")  # from your left dropdown
    originator_name = request.GET.get("originator")  # optional direct filter

    # If they passed originators=<id>, map to name
    if originator_id and not originator_name:
        originator_name = _originator_name_from_id(originator_id)

    def maybe_filter(qs):
        if originator_name:
            return qs.filter(originator=originator_name)
        return qs

    deals = []
    deals += _qs_to_deals(maybe_filter(ApplicationData.objects.all()), product_fallback=None)
    deals += _qs_to_deals(maybe_filter(TfApplicationData.objects.all()), product_fallback=None)
    deals += _qs_to_deals(maybe_filter(ScfApplicationData.objects.all()), product_fallback=None)
    deals += _qs_to_deals(maybe_filter(IpfApplicationData.objects.all()), product_fallback=None)

    # Sort: newest first if you prefer; otherwise company then product
    # Here: newest application_time first (None goes last)
    def sort_key(d):
        t = d.get("application_time")
        # t might be None; sort None last
        return (t is None, t)

    deals.sort(key=sort_key, reverse=True)

    return JsonResponse(deals, safe=False)






#---------#---------#---------#---------#---------
        

#--------Save  Deal conditions 
        

#---------#---------#---------#---------



from rest_framework import generics, permissions
from .models import DealCondition
from .serializers import DealConditionSerializer


class DealConditionCreateView(generics.CreateAPIView):
    """
    Accepts POST JSON and creates a DealCondition row.
    """
    queryset = DealCondition.objects.all()
    serializer_class = DealConditionSerializer

    # For internal microservice use, keep it open or switch to JWT later
    permission_classes = [permissions.AllowAny]
