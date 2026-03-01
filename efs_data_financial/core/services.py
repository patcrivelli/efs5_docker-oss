



#--------#--------#--------#--------#--------
    
#   invoice finance 


#--------#--------#--------#--------#--------



import logging
from django.db import transaction
from .models import InvoiceData, LedgerData
from .serializers import InvoiceDataSerializer, LedgerDataSerializer

logger = logging.getLogger(__name__)

class LoanApplicationService:
    @staticmethod
    @transaction.atomic
    def process_invoice_data(data: dict):
        invoices = data.get("invoices", [])
        if not invoices:
            return {"status": "error", "message": "No invoices found"}

        unique, skipped = [], []
        for inv in invoices:
            abn = inv.get("abn")
            inv_number = inv.get("inv_number")
            if abn and inv_number:
                exists = InvoiceData.objects.filter(abn=abn, inv_number=inv_number).exists()
                (skipped if exists else unique).append(inv)

        if not unique:
            return {"status": "skipped", "message": f"All invoices were duplicates: {skipped}"}

        ser = InvoiceDataSerializer(data=unique, many=True)
        if ser.is_valid():
            ser.save()
            return {"status": "success", "message": f"{len(unique)} invoices saved.", "skipped": skipped}
        return {"status": "error", "message": ser.errors}

    @staticmethod
    @transaction.atomic
    def process_ledger_data(entries: list[dict]):
        if not entries:
            return {"status": "error", "message": "No ledger entries provided"}

        unique, skipped = [], []
        for e in entries:
            abn = e.get("abn")
            invoice_number = e.get("invoice_number")
            if abn and invoice_number:
                exists = LedgerData.objects.filter(abn=abn, invoice_number=invoice_number).exists()
                (skipped if exists else unique).append(e)

        if not unique:
            return {"status": "skipped", "message": f"All ledger entries were duplicates: {skipped}"}

        ser = LedgerDataSerializer(data=unique, many=True)
        if ser.is_valid():
            ser.save()
            return {"status": "success", "message": f"{len(unique)} ledger entries saved.", "skipped": skipped}
        return {"status": "error", "message": ser.errors}





#--------#--------#--------#--------#--------
    
#   trade finance 


#--------#--------#--------#--------#--------



from .models import tf_InvoiceData
from .serializers import TFInvoiceDataSerializer
import logging

logger = logging.getLogger(__name__)


class TradeFinanceService:
    """
    efs_data_financial responsibility:
    - Store Trade Finance INVOICE data only
    - Never process or store application data
    """

    @staticmethod
    def process_invoice_data(data):
        invoices = data.get("invoices", [])

        if not invoices:
            return {
                'status': 'error',
                'message': 'No Trade Finance invoices found in request'
            }

        unique_invoices = []
        skipped = []

        for invoice in invoices:
            abn = invoice.get("abn")
            inv_number = invoice.get("inv_number")

            if not abn or not inv_number:
                continue

            if tf_InvoiceData.objects.filter(
                abn=abn,
                inv_number=inv_number
            ).exists():
                skipped.append(inv_number)
            else:
                unique_invoices.append(invoice)

        if not unique_invoices:
            return {
                'status': 'skipped',
                'message': f"All TF invoices are duplicates",
                'skipped': skipped
            }

        serializer = TFInvoiceDataSerializer(data=unique_invoices, many=True)

        if not serializer.is_valid():
            logger.error("❌ TF Invoice serializer errors: %s", serializer.errors)
            return {
                'status': 'error',
                'message': serializer.errors
            }

        serializer.save()

        logger.debug(
            "✅ %s TF invoices saved successfully. Skipped: %s",
            len(unique_invoices),
            skipped
        )

        return {
            'status': 'success',
            'message': f"{len(unique_invoices)} TF invoices saved",
            'saved': len(unique_invoices),
            'skipped': skipped
        }


#--------#--------#--------#--------#--------
    
#   supply chain finance 


#--------#--------#--------#--------#--------



# efs_data_financial/financial/services.py
import logging
from django.db import transaction
from .models import scf_InvoiceData
from .serializers import SCFInvoiceDataSerializer

logger = logging.getLogger(__name__)

class SCFFundingService:
    """
    efs_data_financial responsibility:
    - Store SCF invoice data only
    - Deduplicate using model unique constraints:
        (abn, inv_number) OR (acn, inv_number)
    """

    @staticmethod
    @transaction.atomic
    def process_invoice_data(data: dict) -> dict:
        invoices = data.get("invoices", [])
        if not invoices:
            return {"status": "error", "message": "No SCF invoices found in request"}

        unique_invoices = []
        skipped = []

        for inv in invoices:
            abn = (inv.get("abn") or "").strip()
            acn = (inv.get("acn") or "").strip()
            inv_number = (inv.get("inv_number") or inv.get("inv_number") or inv.get("inv_number") or inv.get("inv_number"))  # no-op safety
            inv_number = (inv.get("inv_number") or inv.get("inv_number"))  # keep simple

            # Your downstream model uses inv_number field name "inv_number" in HTML,
            # but your payload builder uses "inv_number" or "inv_number"?
            # Standardize here:
            inv_number = (inv.get("inv_number") or inv.get("inv_number") or inv.get("inv_number") or "").strip()
            if not inv_number:
                continue

            exists = False
            if abn:
                exists = scf_InvoiceData.objects.filter(abn=abn, inv_number=inv_number).exists()
            elif acn:
                exists = scf_InvoiceData.objects.filter(acn=acn, inv_number=inv_number).exists()
            else:
                # If neither ABN nor ACN, can't dedupe with your constraints; keep it out.
                continue

            if exists:
                skipped.append(inv_number)
            else:
                unique_invoices.append(inv)

        if not unique_invoices:
            return {
                "status": "skipped",
                "message": "All SCF invoices are duplicates",
                "skipped": skipped,
            }

        serializer = SCFInvoiceDataSerializer(data=unique_invoices, many=True)
        if not serializer.is_valid():
            logger.error("❌ SCF Invoice serializer errors: %s", serializer.errors)
            return {"status": "error", "message": serializer.errors}

        serializer.save()

        logger.debug("✅ %s SCF invoices saved successfully. Skipped: %s", len(unique_invoices), skipped)
        return {
            "status": "success",
            "message": f"{len(unique_invoices)} SCF invoices saved",
            "saved": len(unique_invoices),
            "skipped": skipped,
        }









class StoreFinancialDataService:
    """Stores company-level financial statements."""
    @staticmethod
    def store_financial_data(data):
        try:
            company = data.get("company", {}) or {}
            financials = data.get("financials", []) or []
            count = 0
            for f in financials:
                year = f.get("financialYear")
                stmt = f.get("financialStatement", {}) or {}
                pnl = stmt.get("profitAndLoss", {}) or {}
                bs = stmt.get("balanceSheet", {}) or {}
                FinancialData.objects.update_or_create(
                    abn=company.get("abn", ""),
                    year=year,
                    defaults={
                        "company_name": company.get("name", ""),
                        "financials": f,
                        "profit_loss": pnl,
                        "balance_sheet": bs,
                        "raw": f,
                    },
                )
                count += 1
            logger.info("Stored financials abn=%s count=%s", company.get("abn"), count)
            return {"status": "success", "count": count}
        except Exception as e:
            logger.exception("store_financial_data failed")
            return {"status": "error", "message": str(e)}



# efs_data_financials/core/services.py
import logging
import uuid
from datetime import datetime
from django.utils import timezone
from .models import Registration

logger = logging.getLogger(__name__)

class StorePPSRDataService:
    @staticmethod
    def parse_datetime(raw_value):
        if not raw_value:
            return None
        try:
            return datetime.strptime(raw_value, "%d-%m-%Y %H:%M:%S")
        except Exception:
            logger.warning("Invalid datetime format: %s", raw_value)
            return None

    @staticmethod
    def _parse_uuid_or_none(value):
        if not value:
            return None
        try:
            return uuid.UUID(str(value))
        except Exception:
            logger.warning("Invalid transaction_id (not a UUID): %r", value)
            return None

    @staticmethod
    def store_ppsr_data(data, abn=None, transaction_id=None):
        tx_uuid = StorePPSRDataService._parse_uuid_or_none(transaction_id)

        try:
            for reg in data.get("registrations", []):
                Registration.objects.create(
                    abn=abn,
                    transaction_id=tx_uuid,  # <- persist the page TX
                    search_date=timezone.now().date(),

                    registration_number=reg.get("registrationNumber"),
                    start_time=StorePPSRDataService.parse_datetime(reg.get("startTime")),
                    end_time=StorePPSRDataService.parse_datetime(reg.get("endTime")),
                    change_number=reg.get("changeNumber"),
                    change_time=StorePPSRDataService.parse_datetime(reg.get("changeTime")),
                    registration_kind=reg.get("registrationKind"),
                    is_migrated=reg.get("isMigrated"),
                    is_transitional=reg.get("isTransitional"),

                    grantor_organisation_identifier=(reg.get("grantor") or {}).get("organisationIdentifier"),
                    grantor_organisation_identifier_type=(reg.get("grantor") or {}).get("organisationIdentifierType"),
                    grantor_organisation_name=(reg.get("grantor") or {}).get("organisationName"),

                    collateral_class_type=(reg.get("collateral") or {}).get("collateralClassType"),
                    collateral_type=(reg.get("collateral") or {}).get("collateralType"),
                    collateral_class_description=(reg.get("collateral") or {}).get("collateralClassDescription"),
                    are_proceeds_claimed=(reg.get("collateral") or {}).get("areProceedsClaimed"),
                    proceeds_claimed_description=(reg.get("collateral") or {}).get("proceedsClaimedDescription"),
                    is_security_interest_registration_kind=(reg.get("collateral") or {}).get("isSecurityInterestRegistrationKind"),
                    are_assets_subject_to_control=(reg.get("collateral") or {}).get("areAssetsSubjectToControl"),
                    is_inventory=(reg.get("collateral") or {}).get("isInventory"),
                    is_pmsi=(reg.get("collateral") or {}).get("isPMSI"),
                    is_subordinate=(reg.get("collateral") or {}).get("isSubordinate"),
                    giving_of_notice_identifier=(reg.get("collateral") or {}).get("givingOfNoticeIdentifier"),

                    security_party_groups=reg.get("securityPartyGroups"),
                    grantors=reg.get("grantors"),
                    address_for_service=reg.get("addressForService"),
                )
        except Exception as e:
            logger.exception("store_ppsr_data failed")
            raise Exception(f"Failed to store PPSR data: {str(e)}")






#------------------------------------------

#upload invoices services 


#------------------------------------------

from typing import Tuple
from django.utils import timezone
from .models import FinancialData

def upsert_financial_record(rec: dict) -> Tuple[FinancialData, bool]:
    """
    Upsert by (abn, year). If year is missing, we just create new rows per payload.
    Returns (instance, created_bool).
    """
    abn  = (rec.get("abn") or "")[:11]
    year = rec.get("year")

    defaults = {
        "timestamp":     timezone.now(),
        "acn":           (rec.get("acn") or "")[:20],
        "company_name":  (rec.get("company_name") or "")[:255],
        "financials":    rec.get("financials"),
        "profit_loss":   rec.get("profit_loss"),
        "balance_sheet": rec.get("balance_sheet"),
        "subsidiaries":  rec.get("subsidiaries") or [],
        "raw":           rec.get("raw"),
    }

    if year is None:
        # No deterministic key -> create a new row every time
        obj = FinancialData.objects.create(abn=abn, **defaults)
        return obj, True

    obj, created = FinancialData.objects.update_or_create(
        abn=abn,
        year=int(year),
        defaults=defaults
    )
    return obj, created







# uploade invoices 
import csv
import io
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from django.db import transaction

from .models import InvoiceData, InvoiceDataUploaded, AP_InvoiceDataUploaded


# -------- helpers --------

def _norm_header(h: str) -> str:
    return (h or "").strip().lower().replace(" ", "_")


HEADER_MAP = {
    "abn": "abn",
    "acn": "acn",
    "name": "name",
    "transaction_id": "transaction_id",
    "trans_id": "transaction_id",
    "debtor": "debtor",

    "date_funded": "date_funded",
    "funded_date": "date_funded",

    "due_date": "due_date",
    "invoice_state": "invoice_state",
    "state": "invoice_state",

    "date_paid": "date_paid",
    "paid_date": "date_paid",

    "amount_funded": "amount_funded",
    "amount_due": "amount_due",
    "discount_percentage": "discount_percentage",
    "discount_%": "discount_percentage",
    "face_value": "face_value",
    "sif_batch": "sif_batch",
    "inv_number": "inv_number",
    "invoice_number": "inv_number",

    # ✅ optional CSV header support
    "approve_reject": "approve_reject",
    "approve/reject": "approve_reject",
}


# ✅ AP header map (same as AR but creditor instead of debtor)
AP_HEADER_MAP = {
    "abn": "abn",
    "acn": "acn",
    "name": "name",
    "transaction_id": "transaction_id",
    "trans_id": "transaction_id",

    # AP-specific counterparty column aliases
    "creditor": "creditor",
    "supplier": "creditor",
    "vendor": "creditor",
    "debtor": "creditor",  # optional compatibility fallback

    "date_funded": "date_funded",
    "funded_date": "date_funded",

    "due_date": "due_date",
    "invoice_state": "invoice_state",
    "state": "invoice_state",

    "date_paid": "date_paid",
    "paid_date": "date_paid",

    "amount_funded": "amount_funded",
    "amount_due": "amount_due",
    "discount_percentage": "discount_percentage",
    "discount_%": "discount_percentage",
    "face_value": "face_value",
    "sif_batch": "sif_batch",
    "inv_number": "inv_number",
    "invoice_number": "inv_number",

    "approve_reject": "approve_reject",
    "approve/reject": "approve_reject",
}


def _to_decimal(v) -> Optional[Decimal]:
    if v in (None, "", "—"):
        return None
    s = str(v).replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def _to_date(v) -> Optional[datetime.date]:
    if v in (None, "", "—"):
        return None
    s = str(v).strip()
    if not s:
        return None

    fmts = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except Exception:
            continue
    return None


def _pick_identity(abn, acn, form_abn, form_acn):
    abn = (abn or "").strip() or (form_abn or "").strip()
    acn = (acn or "").strip() or (form_acn or "").strip()
    return abn, acn


def _derive_approve_reject(invoice_state_val: str) -> Optional[str]:
    state = (invoice_state_val or "").strip().lower()
    if state == "open":
        return "approved"
    if state == "closed":
        return "closed"
    return None


def _upsert_uploaded(
    row_dict: Dict[str, Any],
    form_abn: str = "",
    form_acn: str = "",
    form_tx: str = ""
) -> bool:
    """
    Upsert strategy that respects your unique constraints:
    - If ABN present: use (abn, inv_number)
    - Else if ACN present: use (acn, inv_number)
    - Else fallback to (transaction_id, inv_number) best-effort
    """
    raw_abn = row_dict.get("abn")
    raw_acn = row_dict.get("acn")
    abn, acn = _pick_identity(raw_abn, raw_acn, form_abn, form_acn)

    inv_number = (row_dict.get("inv_number") or "").strip()

    # ✅ Prefer the transaction ID coming from the modal / form.
    #    Only if that's missing do we look at the CSV's transaction_id.
    if form_tx:
        tx = form_tx.strip()
    else:
        tx = (row_dict.get("transaction_id") or "").strip()

    # Skip rows with no invoice number at all
    if not inv_number:
        return False

    invoice_state_val = (row_dict.get("invoice_state") or "").strip() or None
    derived_ar = _derive_approve_reject(invoice_state_val)

    # We always enforce the derived rule during upload
    approve_reject_val = derived_ar

    defaults = {
        "abn": abn or None,
        "acn": acn or None,
        "name": (row_dict.get("name") or "").strip() or None,
        "transaction_id": tx or None,
        "debtor": (row_dict.get("debtor") or "").strip() or None,

        "date_funded": _to_date(row_dict.get("date_funded")),
        "due_date": _to_date(row_dict.get("due_date")),

        "invoice_state": invoice_state_val,
        "date_paid": _to_date(row_dict.get("date_paid")),

        "amount_funded": _to_decimal(row_dict.get("amount_funded")),
        "amount_due": _to_decimal(row_dict.get("amount_due")),
        "discount_percentage": _to_decimal(row_dict.get("discount_percentage")),
        "face_value": _to_decimal(row_dict.get("face_value")),
        "sif_batch": (row_dict.get("sif_batch") or "").strip() or None,
        "inv_number": inv_number or None,

        "approve_reject": approve_reject_val,
    }

    if abn:
        _, created = InvoiceDataUploaded.objects.update_or_create(
            abn=abn,
            inv_number=inv_number,
            defaults=defaults,
        )
        return created

    if acn:
        _, created = InvoiceDataUploaded.objects.update_or_create(
            acn=acn,
            inv_number=inv_number,
            defaults=defaults,
        )
        return created

    # Fallback when no ABN/ACN – now uses the canonical tx we just computed
    _, created = InvoiceDataUploaded.objects.update_or_create(
        transaction_id=tx,
        inv_number=inv_number,
        defaults=defaults,
    )
    return created





def _upsert_ap_uploaded(
    row_dict: Dict[str, Any],
    form_abn: str = "",
    form_acn: str = "",
    form_tx: str = ""
) -> bool:
    """
    Upsert strategy for AP uploaded invoices:
    - If ABN present: use (abn, inv_number)
    - Else if ACN present: use (acn, inv_number)
    - Else fallback to (transaction_id, inv_number)
    """
    raw_abn = row_dict.get("abn")
    raw_acn = row_dict.get("acn")
    abn, acn = _pick_identity(raw_abn, raw_acn, form_abn, form_acn)

    inv_number = (row_dict.get("inv_number") or "").strip()

    # Prefer transaction_id coming from form/modal
    if form_tx:
        tx = form_tx.strip()
    else:
        tx = (row_dict.get("transaction_id") or "").strip()

    if not inv_number:
        return False

    invoice_state_val = (row_dict.get("invoice_state") or "").strip() or None
    derived_ap = _derive_approve_reject(invoice_state_val)

    defaults = {
        "abn": abn or None,
        "acn": acn or None,
        "name": (row_dict.get("name") or "").strip() or None,
        "transaction_id": tx or None,

        # ✅ AP field (not debtor)
        "creditor": (row_dict.get("creditor") or "").strip() or None,

        "date_funded": _to_date(row_dict.get("date_funded")),
        "due_date": _to_date(row_dict.get("due_date")),

        "invoice_state": invoice_state_val,
        "date_paid": _to_date(row_dict.get("date_paid")),

        "amount_funded": _to_decimal(row_dict.get("amount_funded")),
        "amount_due": _to_decimal(row_dict.get("amount_due")),
        "discount_percentage": _to_decimal(row_dict.get("discount_percentage")),
        "face_value": _to_decimal(row_dict.get("face_value")),
        "sif_batch": (row_dict.get("sif_batch") or "").strip() or None,
        "inv_number": inv_number or None,

        "approve_reject": derived_ap,
    }

    if abn:
        _, created = AP_InvoiceDataUploaded.objects.update_or_create(
            abn=abn,
            inv_number=inv_number,
            defaults=defaults,
        )
        return created

    if acn:
        _, created = AP_InvoiceDataUploaded.objects.update_or_create(
            acn=acn,
            inv_number=inv_number,
            defaults=defaults,
        )
        return created

    _, created = AP_InvoiceDataUploaded.objects.update_or_create(
        transaction_id=tx,
        inv_number=inv_number,
        defaults=defaults,
    )
    return created


# -------- Invoice upload functions--------






def process_invoices_csv_upload(
    uploaded_file,
    form_abn: str = "",
    form_acn: str = "",
    form_tx: str = "",
) -> Tuple[int, int]:
    """
    Reads and upserts rows from a CSV upload into InvoiceDataUploaded.
    Returns: (rows_processed, rows_created)

    Raises ValueError with a user-friendly message for bad inputs.
    """
    if not uploaded_file:
        raise ValueError("Missing file.")

    if not uploaded_file.name.lower().endswith(".csv"):
        raise ValueError("Please upload a .csv file.")

    try:
        raw = uploaded_file.read().decode("utf-8-sig")
    except Exception:
        raw = uploaded_file.read().decode("latin-1")

    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ValueError("CSV has no headers.")

    # normalize headers
    norm_fields = [_norm_header(h) for h in reader.fieldnames]

    # build index mapping of csv header -> model field
    header_to_field = {}
    for original, normed in zip(reader.fieldnames, norm_fields):
        mapped = HEADER_MAP.get(normed)
        if mapped:
            header_to_field[original] = mapped

    created_count = 0
    processed = 0

    with transaction.atomic():
        for row in reader:
            processed += 1
            mapped_row = {}
            for k, v in row.items():
                field = header_to_field.get(k)
                if field:
                    mapped_row[field] = v

            created = _upsert_uploaded(
                mapped_row,
                form_abn=form_abn,
                form_acn=form_acn,
                form_tx=form_tx
            )
            if created:
                created_count += 1

    return processed, created_count


# ✅ NEW: AP CSV upload

def process_ap_invoices_csv_upload(
    uploaded_file,
    form_abn: str = "",
    form_acn: str = "",
    form_tx: str = "",
) -> Tuple[int, int]:
    """
    Reads and upserts rows from a CSV upload into AP_InvoiceDataUploaded.
    Returns: (rows_processed, rows_created)
    """
    if not uploaded_file:
        raise ValueError("Missing file.")

    if not uploaded_file.name.lower().endswith(".csv"):
        raise ValueError("Please upload a .csv file.")

    try:
        raw = uploaded_file.read().decode("utf-8-sig")
    except Exception:
        raw = uploaded_file.read().decode("latin-1")

    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ValueError("CSV has no headers.")

    norm_fields = [_norm_header(h) for h in reader.fieldnames]

    header_to_field = {}
    for original, normed in zip(reader.fieldnames, norm_fields):
        mapped = AP_HEADER_MAP.get(normed)
        if mapped:
            header_to_field[original] = mapped

    created_count = 0
    processed = 0

    with transaction.atomic():
        for row in reader:
            processed += 1
            mapped_row = {}
            for k, v in row.items():
                field = header_to_field.get(k)
                if field:
                    mapped_row[field] = v

            created = _upsert_ap_uploaded(
                mapped_row,
                form_abn=form_abn,
                form_acn=form_acn,
                form_tx=form_tx
            )
            if created:
                created_count += 1

    return processed, created_count






def fetch_invoices_combined_for_company(company_id: str) -> Dict[str, Any]:
    """
    Returns the same front-end contract as before:
      {"invoices": [...]}
    combining InvoiceData and InvoiceDataUploaded.
    """
    cid = (company_id or "").strip()
    if not cid:
        return {"invoices": []}

    digits = "".join([c for c in cid if c.isdigit()])
    is_abn = len(digits) == 11
    is_acn = len(digits) == 9

    api_qs = InvoiceData.objects.none()
    up_qs = InvoiceDataUploaded.objects.none()

    if is_abn:
        api_qs = InvoiceData.objects.filter(abn=digits)
        up_qs = InvoiceDataUploaded.objects.filter(abn=digits)
    elif is_acn:
        api_qs = InvoiceData.objects.filter(acn=digits)
        up_qs = InvoiceDataUploaded.objects.filter(acn=digits)
    else:
        api_qs = InvoiceData.objects.filter(abn=cid) | InvoiceData.objects.filter(acn=cid)
        up_qs = InvoiceDataUploaded.objects.filter(abn=cid) | InvoiceDataUploaded.objects.filter(acn=cid)

    def ser(obj, source):
        date_paid = getattr(obj, "date_paid", None)
        return {
            "abn": obj.abn,
            "acn": obj.acn,
            "name": obj.name,
            "transaction_id": obj.transaction_id,
            "debtor": obj.debtor,
            "date_funded": obj.date_funded.isoformat() if obj.date_funded else None,
            "due_date": obj.due_date.isoformat() if obj.due_date else None,
            "amount_funded": str(obj.amount_funded) if obj.amount_funded is not None else None,
            "amount_due": str(obj.amount_due) if obj.amount_due is not None else None,
            "discount_percentage": str(obj.discount_percentage) if obj.discount_percentage is not None else None,
            "face_value": str(obj.face_value) if obj.face_value is not None else None,
            "sif_batch": obj.sif_batch,
            "inv_number": obj.inv_number,
            "invoice_state": getattr(obj, "invoice_state", None),
            "date_paid": date_paid.isoformat() if date_paid else None,

            # ✅ include approve_reject when present (uploaded)
            "approve_reject": getattr(obj, "approve_reject", None),

            "source": source,
        }

    api_list = [ser(x, "api") for x in api_qs.order_by("-date_funded")[:200]]
    up_list = [ser(x, "uploaded") for x in up_qs.order_by("-date_funded")[:200]]

    combined = up_list + api_list
    return {"invoices": combined}




# ✅ NEW: AP fetch (uploaded AP only)
def fetch_ap_invoices_combined_for_company(company_id: str) -> Dict[str, Any]:
    """
    Returns:
      {"ap_invoices": [...]}
    from AP_InvoiceDataUploaded only (Payables sub-tab),
    filtered to invoice_state='open'.
    """
    cid = (company_id or "").strip()
    if not cid:
        return {"ap_invoices": []}

    digits = "".join([c for c in cid if c.isdigit()])
    is_abn = len(digits) == 11
    is_acn = len(digits) == 9

    up_qs = AP_InvoiceDataUploaded.objects.none()

    # ✅ only open invoices
    open_filter = Q(invoice_state__iexact="open")

    if is_abn:
        up_qs = AP_InvoiceDataUploaded.objects.filter(
            Q(abn=digits) & open_filter
        )
    elif is_acn:
        up_qs = AP_InvoiceDataUploaded.objects.filter(
            Q(acn=digits) & open_filter
        )
    else:
        up_qs = AP_InvoiceDataUploaded.objects.filter(
            (Q(abn=cid) | Q(acn=cid)) & open_filter
        )

    def ser_ap(obj):
        date_paid = getattr(obj, "date_paid", None)
        return {
            "id": obj.id,
            "abn": obj.abn,
            "acn": obj.acn,
            "name": obj.name,
            "transaction_id": obj.transaction_id,

            # ✅ AP-specific field
            "creditor": obj.creditor,

            "date_funded": obj.date_funded.isoformat() if obj.date_funded else None,
            "due_date": obj.due_date.isoformat() if obj.due_date else None,
            "amount_funded": str(obj.amount_funded) if obj.amount_funded is not None else None,
            "amount_due": str(obj.amount_due) if obj.amount_due is not None else None,
            "discount_percentage": str(obj.discount_percentage) if obj.discount_percentage is not None else None,
            "face_value": str(obj.face_value) if obj.face_value is not None else None,
            "sif_batch": obj.sif_batch,
            "inv_number": obj.inv_number,
            "invoice_state": getattr(obj, "invoice_state", None),
            "date_paid": date_paid.isoformat() if date_paid else None,
            "approve_reject": getattr(obj, "approve_reject", None),

            # helpful aliases for frontend reuse
            "invoice_number": obj.inv_number,
            "status": getattr(obj, "invoice_state", None),
            "open_closed": getattr(obj, "invoice_state", None),

            "source": "uploaded_ap",
        }

    ap_list = [ser_ap(x) for x in up_qs.order_by("-date_funded")[:200]]
    return {"ap_invoices": ap_list}





#------ ------ ------ ------ ------ ------ 
    
    #   Approve or reject  invoices  code 

#------ ------ ------ ------ ------ 
    
from .models import InvoiceDataUploaded


class InvoiceApprovalService:
    @staticmethod
    def set_approve_reject(*, invoice_number=None, invoice_id=None,
                           abn=None, acn=None, transaction_id=None,
                           debtor=None, state: str) -> int:

        qs = InvoiceDataUploaded.objects.all()

        if invoice_id:
            qs = qs.filter(id=invoice_id)
        elif invoice_number:
            qs = qs.filter(inv_number=invoice_number)

        if transaction_id:
            qs = qs.filter(transaction_id=transaction_id)

        if debtor:
            qs = qs.filter(debtor=debtor)

        if abn:
            qs = qs.filter(abn=abn)
        elif acn:
            qs = qs.filter(acn=acn)

        updated = qs.update(approve_reject=state)

        if updated == 0 and invoice_number:
            qs2 = InvoiceDataUploaded.objects.filter(inv_number=invoice_number)
            if abn:
                qs2 = qs2.filter(abn=abn)
            elif acn:
                qs2 = qs2.filter(acn=acn)
            updated = qs2.update(approve_reject=state)

        return updated





#--------  ----------- ----------- -----------

# start TAX  statements file parsing and insertion  logic 


#--------- ---------- ----------- -----------

import io
import re
import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
from datetime import datetime, date






# services.py
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

from .models import (
    TaxAccountTransaction,
    AtoPaymentPlanInstalment,
    TaxReturn,
    BusinessActivityStatement,
)


# ----------------parse_integrated_tax_account and parse_ato_payment_plan helpers ----------------


DATE_RE = re.compile(r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+(.*)$")
MONEY_RE = re.compile(r"\$[\d,]+\.\d{2}")
BAL_SIDE_RE = re.compile(r"\b(CR|DR)\b")

def _parse_au_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    return datetime.strptime(s, "%d %b %Y").date()

def _money_to_decimal(s: str) -> Decimal:
    return Decimal(s.replace("$", "").replace(",", "").strip())

def _hash_row(*parts: str) -> str:
    raw = "||".join((p or "").strip() for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = []
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    return "\n".join(pages)




def _redact_tfn(raw_payload: Any) -> Dict[str, Any]:
    """
    Ensure TFN is not stored. Removes common TFN keys if present.
    """
    if not isinstance(raw_payload, dict):
        return {}
    blocked = {"tfn", "tax_file_number", "taxfilenumber"}
    return {k: v for k, v in raw_payload.items() if k.lower().replace(" ", "_") not in blocked}


def _attach_context(payload: Dict[str, Any], ctx: Dict[str, Any], source_file_name: str) -> Dict[str, Any]:
    """
    Merge common context fields into an insert payload.
    """
    out = dict(payload or {})
    out["transaction_id"] = ctx.get("transaction_id") or out.get("transaction_id") or ""
    out["originator"] = ctx.get("originator")
    out["abn"] = ctx.get("abn")
    out["acn"] = ctx.get("acn")
    out["company_name"] = ctx.get("company_name")
    out["source_file_name"] = source_file_name
    return out




# ----------------parse_tax_return helpers ----------------





import io
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from io import BytesIO

import pdfplumber


_MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")
_ABN_RE = re.compile(r"\bAustralian Business Number\s+(\d{2}\s+\d{3}\s+\d{3}\s+\d{3})\b", re.I)
_YEAR_RE = re.compile(r"\bYear\s+(\d{4})\b")
_PERIOD_RE = re.compile(r"\b(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s*[—-]\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\b")
_TRUST_TYPE_RE = re.compile(r"TYPE OF TRUST\s+T\s*-\s*(.+)$", re.I)
_TAX_PAYABLE_RE = re.compile(r"Is any tax payable by the trustee\?\s+(Yes|No)", re.I)
_FINAL_RETURN_RE = re.compile(r"Final tax return\?\s+(Yes|No)", re.I)
_MAIN_BIZ_CODE_RE = re.compile(r"DESCRIPTION OF MAIN BUSINESS ACTIVITY\s+A\s+(\d{3,6})", re.I)

_OTHER_BUS_INCOME_RE = re.compile(r"Other business income\s+\$([\d,]+\.\d{2})", re.I)
_ALL_OTHER_EXP_RE = re.compile(r"All other expenses\s+\$([\d,]+\.\d{2})", re.I)
_NET_INCOME_RE = re.compile(r"Net income or loss from business.*?\$([\d,]+\.\d{2})", re.I)
_TOTAL_NET_INCOME_RE = re.compile(r"TOTAL NET INCOME\s+\$([\d,]+\.\d{2})", re.I)

_NON_RES_TRUST_RE = re.compile(r"Is the trust a non-resident trust\?\s+(Yes|No)", re.I)
_ANY_NON_RES_BEN_RE = re.compile(
    r"Was any beneficiary who was not a resident of Australia.*?presently\s+entitled.*?\?\s+(Yes|No)",
    re.I
)
_BEN_UNDER_DISABILITY_FROM_ANOTHER_TRUST_RE = re.compile(
    r"BENEFICIARY UNDER LEGAL DISABILITY.*?\n\s*(Yes|No)\b", re.I
)


def _to_decimal(s: Optional[str]) -> Optional[Decimal]:
    if not s:
        return None
    s = s.strip().replace(",", "")
    if not s:
        return None
    return Decimal(s)


def _to_bool_yesno(s: Optional[str]) -> Optional[bool]:
    if not s:
        return None
    s = s.strip().lower()
    if s == "yes":
        return True
    if s == "no":
        return False
    return None


def _parse_au_date_d_mmm_y(s: str):
    # "1 Jul 2023"
    return datetime.strptime(s.strip(), "%d %b %Y").date()



# ----------------parse_tax_return helpers ----------------


#none... 

# ---------------- parse_bas helpers  ----------------

def _digits_only(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _clip(s: str, n: int) -> str | None:
    s = (s or "").strip()
    if not s:
        return None
    return s[:n]



# ----------------  PARSERS  ----------------



def parse_integrated_tax_account(file_bytes: bytes) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Returns:
      header: dict of model-friendly header fields
      rows: list of dicts matching TaxAccountTransaction fields (minus ctx fields)
    """
    text = _extract_text_from_pdf_bytes(file_bytes)
    lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]

    header: Dict[str, Any] = {
        "company_name": None,
        "account_label": None,
        "statement_generated_at": None,
    }

    # header extraction (best-effort)
    for ln in lines:
        if ln.startswith("Client "):
            header["company_name"] = ln.replace("Client ", "").strip()
        if re.match(r"^(Income tax|GST|PAYG|Activity statement)\b", ln):
            header["account_label"] = ln.strip()
        if ln.startswith("Date generated "):
            ds = ln.replace("Date generated ", "").strip()
            try:
                header["statement_generated_at"] = datetime.strptime(ds, "%d %B %Y").date()
            except Exception:
                header["statement_generated_at"] = None

    # find table start
    try:
        header_idx = next(i for i, ln in enumerate(lines)
                          if ln.startswith("Processed date Effective date Description"))
        table_lines = lines[header_idx + 1 :]
    except StopIteration:
        table_lines = lines[:]  # fallback if header not found

    rows: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    def flush():
        nonlocal current
        if not current:
            return
        current["description"] = " ".join(current.get("_desc_parts", [])).strip() or "—"
        current.pop("_desc_parts", None)

        # optional dedupe helper
        current["source_row_hash"] = _hash_row(
            str(current.get("processed_date") or ""),
            str(current.get("effective_date") or ""),
            current.get("description") or "",
            str(current.get("debit_amount") or ""),
            str(current.get("credit_amount") or ""),
            str(current.get("balance_amount") or ""),
            current.get("balance_side") or "",
        )

        rows.append(current)
        current = None

    for ln in table_lines:
        # skip repeated headers / noise
        if ln.startswith("Processed date Effective date Description"):
            continue
        if ln.startswith("Agent ") or ln.startswith("Client ") or ln.startswith("ABN ") or ln.startswith("TFN "):
            continue

        m = DATE_RE.match(ln)
        if m:
            flush()
            processed_s, effective_s, rest = m.group(1), m.group(2), m.group(3)

            current = {
                "processed_date": _parse_au_date(processed_s),
                "effective_date": _parse_au_date(effective_s),
                "description": "",
                "debit_amount": None,
                "credit_amount": None,
                "balance_amount": None,
                "balance_side": None,
                "_desc_parts": [],
            }

            monies = MONEY_RE.findall(rest)
            side_m = BAL_SIDE_RE.search(rest)
            side = side_m.group(1) if side_m else None

            desc = rest
            for token in monies:
                desc = desc.replace(token, " ")
            if side:
                desc = re.sub(rf"\b{side}\b", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()
            if desc:
                current["_desc_parts"].append(desc)

            vals = [_money_to_decimal(x) for x in monies]

            if len(vals) == 3:
                current["debit_amount"], current["credit_amount"], current["balance_amount"] = vals[0], vals[1], vals[2]
                current["balance_side"] = side
            elif len(vals) == 2:
                if side:
                    # amount + balance; decide debit vs credit by text hints
                    if "refund" in rest.lower() or "interest" in rest.lower() or "credit" in rest.lower():
                        current["credit_amount"] = vals[0]
                    else:
                        current["debit_amount"] = vals[0]
                    current["balance_amount"] = vals[1]
                    current["balance_side"] = side
                else:
                    current["debit_amount"], current["credit_amount"] = vals[0], vals[1]
            elif len(vals) == 1:
                if "refund" in rest.lower() or "interest" in rest.lower() or "credit" in rest.lower():
                    current["credit_amount"] = vals[0]
                else:
                    current["debit_amount"] = vals[0]
                current["balance_side"] = side

            continue

        # continuation line
        if current:
            monies = MONEY_RE.findall(ln)
            side_m = BAL_SIDE_RE.search(ln)
            side = side_m.group(1) if side_m else None

            if monies:
                vals = [_money_to_decimal(x) for x in monies]
                if side and current["balance_amount"] is None:
                    current["balance_amount"] = vals[-1]
                    current["balance_side"] = current["balance_side"] or side
                    remaining = vals[:-1]
                    if remaining:
                        if current["debit_amount"] is None:
                            current["debit_amount"] = remaining[0]
                        elif current["credit_amount"] is None:
                            current["credit_amount"] = remaining[0]
                else:
                    for v in vals:
                        if current["debit_amount"] is None:
                            current["debit_amount"] = v
                        elif current["credit_amount"] is None:
                            current["credit_amount"] = v
                continue

            current["_desc_parts"].append(ln.strip())

    flush()
    return header, rows


def parse_ato_payment_plan(file_bytes: bytes) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Parse an ATO Activity Statement Account Payment Plan PDF.

    Returns:
      header_dict: plan-level fields to duplicate onto each AtoPaymentPlanInstalment row
      instalment_rows: [{instalment_date, status, instalment_amount}, ...]
    """
    import io
    import re
    from datetime import datetime
    from decimal import Decimal
    import pdfplumber

    # ---- helpers ----
    def _clean(s: str) -> str:
        return (s or "").strip()

    def _parse_date_ddmmyyyy(s: str):
        s = _clean(s)
        if not s:
            return None
        return datetime.strptime(s, "%d/%m/%Y").date()

    def _money_to_decimal(s: str):
        s = _clean(s)
        if not s:
            return None
        # "$32,645.00" -> Decimal("32645.00")
        s = s.replace("$", "").replace(",", "")
        return Decimal(s)

    # ---- extract full text ----
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    text = "\n".join(pages)

    # Normalize lines
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    header: Dict[str, Any] = {
        # plan metadata
        "agent_name": None,
        "activity_statement_number": None,
        "date_generated": None,
        "creation_date": None,
        "plan_balance_amount": None,
        "plan_balance_side": None,
        "plan_total_including_estimated_gic": None,
        "payment_method": None,
        "payment_frequency": None,
        "biller_code": None,
        "payment_reference_number": None,
        "ref": None,
        # NOTE: company_name/abn are handled by _attach_context(ctx, ...)
        # but we also parse them here as fallback
        "company_name": None,
        "abn": None,
    }

    # ---- regex patterns ----
    # Instalment schedule rows: "05/09/2025 Amount to pay $1,500.00"
    ROW_RE = re.compile(
        r"^(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<status>.+?)\s+\$(?P<amt>[\d,]+\.\d{2})$"
    )

    # "Amount $32,645.00 DR"
    PLAN_AMOUNT_RE = re.compile(r"^Amount\s+\$(?P<amt>[\d,]+\.\d{2})\s+(?P<side>DR|CR)$")

    # "Plan total, including estimated general interest charge" then next line "$35,936.92"
    PLAN_TOTAL_RE = re.compile(r"^\$(?P<amt>[\d,]+\.\d{2})$")

    # "Agent SPECTRUM ACCOUNTANTS"
    AGENT_RE = re.compile(r"^Agent\s+(?P<val>.+)$")

    # "Client PENINSULAR CAPITAL PTY LTD"
    CLIENT_RE = re.compile(r"^Client\s+(?P<val>.+)$")

    # "ABN 75 606 207 710"
    ABN_RE = re.compile(r"^ABN\s+(?P<val>[\d\s]+)$")

    # "Activity statement 002"
    ACTIVITY_RE = re.compile(r"^Activity statement\s+(?P<val>\S+)$")

    # "Date generated 26/08/2025"
    DATE_GEN_RE = re.compile(r"^Date generated\s+(?P<val>\d{2}/\d{2}/\d{4})$")

    # "Creation date 26/08/2025"
    CREATION_RE = re.compile(r"^Creation date\s+(?P<val>\d{2}/\d{2}/\d{4})$")

    # "Payment method Other payment options"
    PMETHOD_RE = re.compile(r"^Payment method\s+(?P<val>.+)$")

    # "Payment frequency Monthly"
    PFREQ_RE = re.compile(r"^Payment frequency\s+(?P<val>.+)$")

    # "Biller code 75556"
    BILLER_RE = re.compile(r"^Biller code\s+(?P<val>\S+)$")

    # "Ref 0027560..."
    REF_RE = re.compile(r"^Ref\s+(?P<val>\S+)$")

    # "Payment reference number" then next line "0027560..."
    PRN_LABEL_RE = re.compile(r"^Payment reference number$", re.IGNORECASE)
    PRN_VALUE_RE = re.compile(r"^(?P<val>\d{10,})$")

    # ---- parse header & rows ----
    instalment_rows: List[Dict[str, Any]] = []

    i = 0
    while i < len(lines):
        ln = lines[i]

        # schedule row
        m = ROW_RE.match(ln)
        if m:
            instalment_rows.append(
                {
                    "instalment_date": _parse_date_ddmmyyyy(m.group("date")),
                    "status": _clean(m.group("status")),
                    "instalment_amount": _money_to_decimal(m.group("amt")),
                }
            )
            i += 1
            continue

        # agent
        m = AGENT_RE.match(ln)
        if m:
            header["agent_name"] = _clean(m.group("val"))
            i += 1
            continue

        # client
        m = CLIENT_RE.match(ln)
        if m:
            header["company_name"] = _clean(m.group("val"))
            i += 1
            continue

        # abn
        m = ABN_RE.match(ln)
        if m:
            header["abn"] = _clean(m.group("val")).replace(" ", "")
            i += 1
            continue

        # activity statement
        m = ACTIVITY_RE.match(ln)
        if m:
            header["activity_statement_number"] = _clean(m.group("val"))
            i += 1
            continue

        # date generated
        m = DATE_GEN_RE.match(ln)
        if m:
            header["date_generated"] = _parse_date_ddmmyyyy(m.group("val"))
            i += 1
            continue

        # plan amount + side
        m = PLAN_AMOUNT_RE.match(ln)
        if m:
            header["plan_balance_amount"] = _money_to_decimal(m.group("amt"))
            header["plan_balance_side"] = _clean(m.group("side"))
            i += 1
            continue

        # payment method
        m = PMETHOD_RE.match(ln)
        if m:
            header["payment_method"] = _clean(m.group("val"))
            i += 1
            continue

        # payment frequency
        m = PFREQ_RE.match(ln)
        if m:
            header["payment_frequency"] = _clean(m.group("val"))
            i += 1
            continue

        # plan total line (label then amount on next line)
        if ln.lower().startswith("plan total") and "interest" in ln.lower():
            # scan forward for first "$xx.xx" line
            j = i + 1
            while j < len(lines):
                m2 = PLAN_TOTAL_RE.match(lines[j])
                if m2:
                    header["plan_total_including_estimated_gic"] = _money_to_decimal(m2.group("amt"))
                    break
                j += 1
            i = j + 1 if j < len(lines) else i + 1
            continue

        # creation date
        m = CREATION_RE.match(ln)
        if m:
            header["creation_date"] = _parse_date_ddmmyyyy(m.group("val"))
            i += 1
            continue

        # biller code
        m = BILLER_RE.match(ln)
        if m:
            header["biller_code"] = _clean(m.group("val"))
            i += 1
            continue

        # ref
        m = REF_RE.match(ln)
        if m:
            header["ref"] = _clean(m.group("val"))
            i += 1
            continue

        # payment reference number label + value on next line
        if PRN_LABEL_RE.match(ln):
            if i + 1 < len(lines):
                m2 = PRN_VALUE_RE.match(lines[i + 1])
                if m2:
                    header["payment_reference_number"] = _clean(m2.group("val"))
                    i += 2
                    continue
            i += 1
            continue

        i += 1

    # Final cleanup: ensure required shape
    header = {k: v for k, v in header.items() if v is not None}

    return header, instalment_rows


def parse_tax_return(file_bytes: bytes) -> Dict[str, Any]:
    """
    Parse an ATO Trust/Company tax return PDF into a snapshot dict for TaxReturn.
    Must return income_year at minimum.
    NO TFN stored (redacted from raw_payload).
    """

    # ---------- helpers ----------
    def pdf_text_from_bytes(b: bytes) -> str:
        with pdfplumber.open(BytesIO(b)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)

    def first_match(pattern: str, text: str, flags=0) -> Optional[re.Match]:
        return re.search(pattern, text, flags)

    def parse_date_loose(s: str) -> Optional[datetime.date]:
        s = (s or "").strip()
        if not s:
            return None
        # Try common ATO formats
        for fmt in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                pass
        return None

    def normalize_abn(s: str) -> str:
        return re.sub(r"\s+", "", (s or "").strip())

    # ---------- extract ----------
    text = pdf_text_from_bytes(file_bytes)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # ---------- detect company_type ----------
    # Your attached file is a Trust return; this will set TRUST if it sees the trust header.
    company_type = "OTHER"
    if re.search(r"\bTRUST\s+TAX\s+RETURN\b", text, re.I):
        company_type = "TRUST"
    elif re.search(r"\bCOMPANY\s+TAX\s+RETURN\b", text, re.I):
        company_type = "PTY_LTD"  # best-effort default for company PDFs

    # ---------- income_year (REQUIRED) ----------
    # Try: "Trust Tax Return 2024"
    income_year = None
    m = first_match(r"\bTax\s+Return\s+(20\d{2})\b", text, re.I)
    if m:
        income_year = int(m.group(1))

    # Try: "Trust Tax Return 2024" (with Trust prefix)
    if not income_year:
        m = first_match(r"\bTrust\s+Tax\s+Return\s+(20\d{2})\b", text, re.I)
        if m:
            income_year = int(m.group(1))

    # Try: "Year ... 2024"
    if not income_year:
        m = first_match(r"\bYear\b.*?\b(20\d{2})\b", text, re.I)
        if m:
            income_year = int(m.group(1))

    # Try: period end year (e.g. 30 Jun 2024 => income_year 2024)
    period_start = None
    period_end = None
    pm = first_match(
        r"(\d{1,2}\s+[A-Za-z]{3}\s+20\d{2})\s*[–—-]\s*(\d{1,2}\s+[A-Za-z]{3}\s+20\d{2})",
        text,
        re.I,
    )
    if pm:
        period_start = parse_date_loose(pm.group(1))
        period_end = parse_date_loose(pm.group(2))
        if not income_year and period_end:
            income_year = int(period_end.year)

    # ---------- trust_name / company_name ----------
    # Often appears as: "TRUST TAX RETURN  Diami Consulting Trust"
    trust_name = None
    if company_type == "TRUST":
        # look for the line after "TRUST TAX RETURN"
        for i, ln in enumerate(lines):
            if re.search(r"\bTRUST\s+TAX\s+RETURN\b", ln, re.I):
                # same line may contain the name
                tail = re.sub(r"(?i).*?\bTRUST\s+TAX\s+RETURN\b", "", ln).strip()
                if tail:
                    trust_name = tail
                    break
                # or next non-empty line
                if i + 1 < len(lines):
                    trust_name = lines[i + 1].strip()
                    break

    # company_name field in your model can reuse trust_name for trust returns
    company_name = trust_name

    # ---------- ABN ----------
    abn = None
    am = first_match(r"\bABN\s+([\d\s]{9,20})\b", text, re.I)
    if am:
        abn = normalize_abn(am.group(1))

    # ---------- optional: lodged/assessed dates (best-effort) ----------
    lodged_date = None
    assessed_date = None
    lm = first_match(r"\bLodg(?:ed|ment)\b.*?(\d{1,2}\s+[A-Za-z]{3}\s+20\d{2})", text, re.I)
    if lm:
        lodged_date = parse_date_loose(lm.group(1))
    am2 = first_match(r"\bAssess(?:ed|ment)\b.*?(\d{1,2}\s+[A-Za-z]{3}\s+20\d{2})", text, re.I)
    if am2:
        assessed_date = parse_date_loose(am2.group(1))

    # ---------- redact TFN from raw_payload ----------
    redacted_text = re.sub(r"(?i)(TFN\s*Recorded\s*)([0-9\s]+)", r"\1[REDACTED]", text)

    # ---------- build snapshot ----------
    snapshot: Dict[str, Any] = {
        "company_type": company_type,
        "income_year": income_year,              # REQUIRED
        "period_start": period_start,
        "period_end": period_end,
        "lodged_date": lodged_date,
        "assessed_date": assessed_date,

        "abn": abn,
        "company_name": company_name,
        "trust_name": trust_name,

        # keep the rest nullable for now (you can enrich later)
        "raw_payload": {
            "text": redacted_text,
        },
    }

    # If somehow still missing, force a fail early (better error than silent bad insert)
    if not snapshot.get("income_year"):
        raise ValueError("Could not determine income_year from PDF (no 'Tax Return YYYY' and no period end date).")

    return snapshot



def parse_bas(file_bytes: bytes) -> Dict[str, Any]:
    # returns single snapshot dict for BusinessActivityStatement
    return {}


import re
from io import BytesIO
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any

import pdfplumber

from datetime import date, datetime
from decimal import Decimal

def _json_safe(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v

def _json_safe_dict(d: dict):
    return {k: _json_safe(v) for k, v in (d or {}).items()}

# --------- small helpers ----------
_MONEY_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")
_DATE_DMY_RE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b")  # 25 Nov 2025
_RANGE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s*[—-]\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})")

def _clean(s: str, maxlen: int = 255) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s[:maxlen] if maxlen else s

def _money(s: str):
    if not s:
        return None
    m = _MONEY_RE.search(s)
    if not m:
        return None
    return Decimal(m.group(1).replace(",", ""))

def _parse_date_str(s: str):
    if not s:
        return None
    s = _clean(s, 64)
    # "25 Nov 2025"
    try:
        return datetime.strptime(s, "%d %b %Y").date()
    except Exception:
        return None

def _find_after(label: str, text: str, max_chars: int = 120) -> str:
    """
    Return substring after 'label' up to max_chars, same line-ish.
    """
    idx = text.find(label)
    if idx < 0:
        return ""
    tail = text[idx + len(label): idx + len(label) + max_chars]
    # stop at newline if present
    tail = tail.split("\n", 1)[0]
    return _clean(tail, max_chars)

def _extract_money_for_code(text: str, code: str):
    """
    Finds amounts near labels like "1A", "1B", "9", "G1", "W1"... from the BAS text.
    Works well for your screenshot layout.
    """
    # Look for "... <code> ... $X" on same line
    pattern = re.compile(rf"{re.escape(code)}\s*\$?\s*([0-9,]+\.[0-9]{{2}})")
    m = pattern.search(text)
    if m:
        return Decimal(m.group(1).replace(",", ""))

    # fallback: find line containing code then money
    for ln in text.splitlines():
        if code in ln:
            val = _money(ln)
            if val is not None:
                return val
    return None


def parse_bas(file_bytes: bytes) -> Dict[str, Any]:
    """
    Parses BAS PDF like your screenshots and returns a snapshot dict suitable for BusinessActivityStatement insertion.

    IMPORTANT:
    - Ignores redundant pages by only extracting pages that contain "Activity Statement" + key BAS section markers.
    - Extracts only the fields we care about (does NOT store TFN).
    - Truncates all strings to prevent varchar overflow.
    """
    # 1) Extract only relevant pages
    wanted_markers = [
        "Summary",
        "Goods and services tax (GST)",
        "PAYG tax withheld",
        "Payment Options",
        "DIRECT CREDIT",
        "BPAY",
    ]

    pages_text = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            if "Activity Statement" not in t:
                continue
            if not any(m in t for m in wanted_markers):
                # page says "Activity Statement" but doesn't look like the actual BAS content page -> skip
                continue
            pages_text.append(t)

    text = "\n".join(pages_text)
    if not text.strip():
        # fallback: if filtering was too strict, just use all pages that contain Activity Statement
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for p in pdf.pages:
                t = p.extract_text() or ""
                if "Activity Statement" in t:
                    pages_text.append(t)
        text = "\n".join(pages_text)

    # 2) Start building payload
    payload: Dict[str, Any] = {}

    # ---- Header fields (from first BAS page)
    # Company name appears top-right, also "Client name ..."
    # Prefer "Client name <name>"
    m_client = re.search(r"Client name\s+(.+?)\s+TFN\b", text)
    if m_client:
        payload["company_name"] = _clean(m_client.group(1), 255)
    else:
        # fallback: first line with "Pty" etc on top area
        m_top = re.search(r"\b([A-Za-z0-9&().,'\- ]+Pty Ltd)\b", text)
        if m_top:
            payload["company_name"] = _clean(m_top.group(1), 255)

    # year label like "2025" near top
    m_year = re.search(r"\b(20\d{2})\b", text)
    if m_year:
        payload["year_label"] = int(m_year.group(1))

    # period range "1 Jul 2025—30 Sep 2025"
    m_range = _RANGE_RE.search(text.replace("–", "—"))
    if m_range:
        payload["period_start"] = _parse_date_str(m_range.group(1))
        payload["period_end"] = _parse_date_str(m_range.group(2))

    # form type (BAS-F)
    m_form = re.search(r"Form type\s+([A-Z\-0-9]+)", text)
    if m_form:
        payload["form_type"] = _clean(m_form.group(1), 255)

    # ABN - IMPORTANT: DO NOT store TFN; ABN in screenshot is 11 digits
    m_abn = re.search(r"\bABN\s+([0-9 ]{9,20})\b", text)
    if m_abn:
        payload["abn"] = _clean(m_abn.group(1).replace(" ", ""), 255)

    # document id
    m_doc = re.search(r"Document ID\s+([0-9]{6,})", text)
    if m_doc:
        payload["document_id"] = _clean(m_doc.group(1), 255)

    # gst accounting method
    m_gst_method = re.search(r"GST accounting method\s+([A-Za-z ]+)", text)
    if m_gst_method:
        payload["gst_accounting_method"] = _clean(m_gst_method.group(1), 255)

    # due dates
    m_form_due = re.search(r"Form due on\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", text)
    if m_form_due:
        payload["form_due_on"] = _parse_date_str(m_form_due.group(1))

    m_pay_due = re.search(r"Payment due on\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", text)
    if m_pay_due:
        payload["payment_due_on"] = _parse_date_str(m_pay_due.group(1))

    # ---- Summary amounts
    payload["gst_on_sales_1a"] = _extract_money_for_code(text, "1A")
    payload["gst_on_purchases_1b"] = _extract_money_for_code(text, "1B")
    payload["payg_withheld_4"] = _extract_money_for_code(text, "4")
    payload["amount_you_owe_the_ato_8a"] = _extract_money_for_code(text, "8A")
    payload["your_payment_amount_9"] = _extract_money_for_code(text, "9")

    # ---- GST detail
    payload["total_sales_g1"] = _extract_money_for_code(text, "G1")
    # "Does the amount shown at G1 include GST? Yes"
    m_inc = re.search(r"include GST\?\s*(Yes|No)", text, re.IGNORECASE)
    if m_inc:
        payload["g1_includes_gst"] = (m_inc.group(1).strip().lower() == "yes")

    # ---- PAYG withheld detail (W1..W5)
    payload["total_salary_wages_w1"] = _extract_money_for_code(text, "W1")
    payload["amount_withheld_w2"] = _extract_money_for_code(text, "W2")
    payload["other_amounts_withheld_w3"] = _extract_money_for_code(text, "W3")
    payload["amount_withheld_no_abn_w4"] = _extract_money_for_code(text, "W4")
    payload["total_amounts_withheld_w5"] = _extract_money_for_code(text, "W5")

    # ---- Declaration (agent)
    # "I authorise Spectrum Accountants to give..."
    m_decl = re.search(r"I authorise\s+(.+?)\s+to give this activity statement", text, re.IGNORECASE)
    if m_decl:
        payload["declaring_agent"] = _clean(m_decl.group(1), 255)

    # ---- Payment Options (BPAY)
    m_ref = re.search(r"Reference Number:\s*([0-9 ]{6,})", text)
    if m_ref:
        payload["bpay_reference_number"] = _clean(m_ref.group(1).replace(" ", ""), 255)
        payload["direct_credit_reference_number"] = payload["bpay_reference_number"]

    m_biller = re.search(r"Biller Code:\s*([0-9 ]{3,})", text)
    if m_biller:
        payload["biller_code"] = _clean(m_biller.group(1).replace(" ", ""), 255)

    # Direct credit fields
    m_acc_name = re.search(r"Account Name:\s*(.+)", text)
    if m_acc_name:
        payload["direct_credit_account_name"] = _clean(m_acc_name.group(1), 255)

    m_bsb = re.search(r"BSB:\s*([0-9 ]+)", text)
    if m_bsb:
        payload["direct_credit_bsb"] = _clean(m_bsb.group(1).replace(" ", ""), 255)

    m_acc_no = re.search(r"Account Number:\s*([0-9 ]+)", text)
    if m_acc_no:
        payload["direct_credit_account_number"] = _clean(m_acc_no.group(1).replace(" ", ""), 255)

    m_inst = re.search(r"Institution Name:\s*(.+)", text)
    if m_inst:
        payload["direct_credit_institution_name"] = _clean(m_inst.group(1), 255)

    # ---- company type heuristic (optional)
    name = (payload.get("company_name") or "").lower()
    if "pty" in name:
        payload["company_type"] = "PTY_LTD"

    # ---- raw payload (DON'T dump whole PDF text; keep it safe)
    payload["raw_payload"] = {
        "extracted": _json_safe_dict({k: v for k, v in payload.items() if k != "raw_payload"}),
        "text_excerpt": _clean(text, 1500),
    }


    # Final truncation safety pass for every string field
    for k, v in list(payload.items()):
        if isinstance(v, str):
            payload[k] = _clean(v, 255)

    return payload





# ---------------- service ----------------
class TaxDocumentService:
    """
    Parse + insert only. No request.FILES, no request.POST, no file upload handling here.
    """

    PARSERS = {
        "tax_ita": "parse_integrated_tax_account",
        "tax_payment_plan": "parse_ato_payment_plan",
        "tax_return": "parse_tax_return",
        "tax_bas": "parse_bas",
    }

    @classmethod
    def parse_and_insert(
        cls,
        doc_type: str,
        file_bytes: bytes,
        source_file_name: str,
        ctx: Dict[str, Any],
    ) -> Dict[str, Any]:

        if doc_type not in cls.PARSERS:
            return {"ok": False, "error": f"Unsupported doc_type: {doc_type}", "status_code": 400}

        if not ctx.get("transaction_id"):
            return {"ok": False, "error": "transaction_id is required", "status_code": 400}

        try:
            with transaction.atomic():
                if doc_type == "tax_ita":
                    header, rows = parse_integrated_tax_account(file_bytes)
                    return cls._insert_tax_ita(header, rows, ctx, source_file_name)

                if doc_type == "tax_payment_plan":
                    header, rows = parse_ato_payment_plan(file_bytes)
                    return cls._insert_payment_plan(header, rows, ctx, source_file_name)

                if doc_type == "tax_return":
                    snapshot = parse_tax_return(file_bytes)
                    return cls._insert_tax_return(snapshot, ctx, source_file_name)

                if doc_type == "tax_bas":
                    snapshot = parse_bas(file_bytes)
                    return cls._insert_bas(snapshot, ctx, source_file_name)

        except Exception as e:
            return {"ok": False, "error": f"Parse/insert failed: {e}", "status_code": 400}

        return {"ok": False, "error": "Unhandled doc_type", "status_code": 400}

    # ---------- insert helpers ----------
    @staticmethod
    def _insert_tax_ita(
        header: Dict[str, Any],
        rows: List[Dict[str, Any]],
        ctx: Dict[str, Any],
        source_name: str,
    ) -> Dict[str, Any]:

        common = _attach_context(header, ctx, source_name)

        objs = []
        for r in (rows or []):
            payload = {**common, **(r or {})}
            objs.append(TaxAccountTransaction(**payload))
        if not objs:
            return {
                "ok": False,
                "error": "No rows parsed from document",
                "doc_type": "tax_ita",
                "inserted_rows": 0,
                "status_code": 400,
            }

        TaxAccountTransaction.objects.bulk_create(objs, batch_size=1000)
        return {"ok": True, "doc_type": "tax_ita", "inserted_rows": len(objs)}


    @staticmethod
    def _insert_payment_plan(
        header: Dict[str, Any],
        rows: List[Dict[str, Any]],
        ctx: Dict[str, Any],
        source_name: str,
    ) -> Dict[str, Any]:

        common = _attach_context(header, ctx, source_name)

        objs = []
        for r in (rows or []):
            payload = {**common, **(r or {})}
            objs.append(AtoPaymentPlanInstalment(**payload))

        if not objs:
            return {
                "ok": False,
                "error": "No rows parsed from document",
                "doc_type": "tax_payment_plan",
                "inserted_rows": 0,
                "status_code": 400,
            }

        AtoPaymentPlanInstalment.objects.bulk_create(objs, batch_size=1000)
        return {"ok": True, "doc_type": "tax_payment_plan", "inserted_rows": len(objs)}


    @staticmethod
    def _insert_tax_return(
        snapshot: Dict[str, Any],
        ctx: Dict[str, Any],
        source_name: str,
    ) -> Dict[str, Any]:

        payload = _attach_context(snapshot, ctx, source_name)

        if "raw_payload" in payload:
            payload["raw_payload"] = _redact_tfn(payload["raw_payload"])

        if not payload.get("income_year"):
            return {"ok": False, "error": "income_year missing from parsed return", "status_code": 400}

        obj = TaxReturn.objects.create(**payload)
        return {"ok": True, "doc_type": "tax_return", "inserted_rows": 1, "id": obj.id}

    @staticmethod
    def _insert_bas(
        snapshot: Dict[str, Any],
        ctx: Dict[str, Any],
        source_name: str,
    ) -> Dict[str, Any]:

        payload = _attach_context(snapshot, ctx, source_name)

        if "raw_payload" in payload:
            payload["raw_payload"] = _redact_tfn(payload["raw_payload"])

        if not (payload.get("period_start") and payload.get("period_end")):
            return {"ok": False, "error": "period_start/period_end missing from parsed BAS", "status_code": 400}

        obj = BusinessActivityStatement.objects.create(**payload)
        return {"ok": True, "doc_type": "tax_bas", "inserted_rows": 1, "id": obj.id}





#--------  ----------- ----------- -----------

# Fetch and displau TAX  statements logic 


#--------- ---------- ----------- -----------
from django.db.models import Q

def _safe_entity_filter(model, entity_id: str) -> Q:
    fields = {f.name for f in model._meta.get_fields()}
    q = Q()
    if "abn" in fields:
        q |= Q(abn=entity_id)
    if "acn" in fields:
        q |= Q(acn=entity_id)
    if "entity_id" in fields:
        q |= Q(entity_id=entity_id)
    return q

def _latest_ts_field(model) -> str:
    fields = {f.name for f in model._meta.get_fields()}
    # pick the best available timestamp field
    for candidate in ("created_at", "inserted_at", "timestamp", "declared_at", "processed_date", "effective_date", "id"):
        if candidate in fields:
            return candidate
    return "id"

from django.forms.models import model_to_dict
from datetime import date, datetime
from decimal import Decimal

def _serialize_instance(obj):
    """
    Convert a Django model instance into a JSON-safe dict.
    """
    if obj is None:
        return None

    data = model_to_dict(obj)

    # Ensure pk included (model_to_dict may omit)
    if "id" not in data and getattr(obj, "id", None) is not None:
        data["id"] = obj.id

    # JSON-safe conversions
    for k, v in list(data.items()):
        if isinstance(v, (date, datetime)):
            data[k] = v.isoformat()
        elif isinstance(v, Decimal):
            data[k] = float(v)

    return data


def _pp_group_key_field():
    """
    Decide which field to use to group instalments into a single plan.
    """
    fields = {f.name for f in AtoPaymentPlanInstalment._meta.get_fields()}
    for candidate in ("payment_reference_number", "ref", "activity_statement_number"):
        if candidate in fields:
            return candidate
    return None


# core/services/tax_document_service.py

# efs_data_financial/core/services.py

from django.db.models import F
from django.forms.models import model_to_dict

class StatutoryPacketService:
    @staticmethod
    def _model_to_dict(obj):
        """Safely convert a Django model instance to dict (no to_dict() dependency)."""
        if not obj:
            return None
        data = model_to_dict(obj)
        data["id"] = obj.pk
        return data

    @staticmethod
    def get_statutory_packet(entity_id: str):
        bas_q = _safe_entity_filter(BusinessActivityStatement, entity_id)
        latest_bas = (
            BusinessActivityStatement.objects
            .filter(bas_q)
            .order_by("-inserted_at")
            .first()
        )

        tr_q = _safe_entity_filter(TaxReturn, entity_id)
        latest_tr = (
            TaxReturn.objects
            .filter(tr_q)
            .order_by("-inserted_at")
            .first()
        )

        pp_q = _safe_entity_filter(AtoPaymentPlanInstalment, entity_id)
        latest_pp = (
            AtoPaymentPlanInstalment.objects
            .filter(pp_q)
            .order_by("-inserted_at")
            .values("payment_reference_number")
            .first()
        )

        pp_rows = []
        if latest_pp and latest_pp.get("payment_reference_number"):
            pp_rows = list(
                AtoPaymentPlanInstalment.objects
                .filter(payment_reference_number=latest_pp["payment_reference_number"])
                .order_by("instalment_date", "id")
                .values("instalment_date", "status", "instalment_amount")
            )

        ita_q = _safe_entity_filter(TaxAccountTransaction, entity_id)
        ita_rows = list(
            TaxAccountTransaction.objects
            .filter(ita_q)
            .annotate(
                debit=F("debit_amount"),
                credit=F("credit_amount"),
                balance=F("balance_amount"),
            )
            .order_by("-effective_date", "-processed_date", "-id")[:200]
            .values(
                "processed_date",
                "effective_date",
                "description",
                "debit",
                "credit",
                "balance",
                "balance_side",
            )
        )

        return {
            "statutory": {
                "bas_latest": StatutoryPacketService._model_to_dict(latest_bas),
                "tax_return_latest": StatutoryPacketService._model_to_dict(latest_tr),
                "payment_plan": {
                    "plan_id": (latest_pp.get("payment_reference_number") if latest_pp else None),
                    "instalments": pp_rows,
                },
                "ita": {"rows": ita_rows},
            }
        }
