from django.db import models
from django.utils import timezone
from django.db.models import Q
import uuid

# Create your models here.




#--------------------------------------
    
    # Ledgers 

#--------------------------------------






class LedgerData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)  # Australian Business Number (ABN)
    acn = models.CharField(max_length=20, null=True, blank=True)
    transaction_id = models.UUIDField(unique=True, editable=False, null=True, blank=True)  # Unique transaction ID
    debtor = models.CharField(max_length=255, null=True, blank=True)  # Debtor name
    invoice_number = models.CharField(max_length=50, null=True, blank=True)  # Invoice number
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Amount due
    repayment_date = models.DateField(null=True, blank=True)  # Expected repayment date
    status = models.CharField(max_length=255, null=True, blank=True)  # Status of the ledger entry
    created_at = models.DateTimeField(default=timezone.now)  # Timestamp when entry was created

    class Meta:
        db_table = "efs_financial_ledgerdata"
        constraints = [
            models.UniqueConstraint(
                fields=["abn", "invoice_number"],
                condition=Q(abn__isnull=False) & ~Q(abn=""),
                name="uniq_ledger_by_abn_invnum",
            ),
            models.UniqueConstraint(
                fields=["acn", "invoice_number"],
                condition=Q(acn__isnull=False) & ~Q(acn=""),
                name="uniq_ledger_by_acn_invnum",
            ),
        ]

        def __str__(self):
            return f"Ledger {self.transaction_id} - {self.debtor} - {self.status}"



class UploadedLedgerData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)

    # not unique: multiple rows per deal/file upload
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False)

    debtor = models.CharField(max_length=255, null=True, blank=True)

    # Aged buckets (keeping as text because you're storing raw uploads)
    aged_receivables = models.CharField(max_length=50, null=True, blank=True)
    days_0_30 = models.CharField("0-30 days", max_length=50, null=True, blank=True)
    days_31_60 = models.CharField("31-60 days", max_length=50, null=True, blank=True)
    days_61_90 = models.CharField("61-90 days", max_length=50, null=True, blank=True)
    days_90_plus = models.CharField("90+ days", max_length=50, null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "uploaded_ledger_data"
        indexes = [
            models.Index(fields=["abn"]),
            models.Index(fields=["acn"]),             # <-- add this
            models.Index(fields=["transaction_id"]),  # <-- helpful for lookup per deal
        ]

    def __str__(self):
        # fall back to ACN if no ABN
        return f"{self.debtor} ({self.abn or self.acn})"


import uuid
from django.db import models

class UploadAPLedgerData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)

    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False)

    creditor = models.CharField(max_length=255, null=True, blank=True)

    aged_payables = models.CharField(max_length=50, null=True, blank=True)
    days_0_30 = models.CharField("0-30 days", max_length=50, null=True, blank=True)
    days_31_60 = models.CharField("31-60 days", max_length=50, null=True, blank=True)
    days_61_90 = models.CharField("61-90 days", max_length=50, null=True, blank=True)
    days_90_plus = models.CharField("90+ days", max_length=50, null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "uploaded_ap_ledger_data"
        indexes = [
            models.Index(fields=["abn"]),
            models.Index(fields=["acn"]),             # <-- new
            models.Index(fields=["transaction_id"]),  # <-- handy for pulling whole upload/deal
        ]

    def __str__(self):
        return f"{self.creditor} ({self.abn or self.acn})"




#--------------------------------------
    
    #Debtors_ credit reports 

#--------------------------------------



import uuid
from django.db import models


class DebtorsCreditReport(models.Model):
    transaction_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text="External/shared transaction identifier (UUID)."
    )
    description = models.CharField(max_length=255)
    item_code = models.CharField(max_length=100)
    abn = models.CharField(max_length=20)
    acn = models.CharField(max_length=20)
    credit_enquiries = models.IntegerField()
    report = models.JSONField()

    # Optional debtor fields
    debtor_name = models.CharField(max_length=255, null=True, blank=True)
    debtor_abn = models.CharField(max_length=20, null=True, blank=True)
    debtor_acn = models.CharField(max_length=20, null=True, blank=True)

    # ✅ New fields
    state = models.CharField(max_length=100, null=True, blank=True)
    debtor_start_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "debtors_credit reports"
        verbose_name_plural = "debtors_credit reports"

    def __str__(self):
        return f"Credit Report for ABN: {self.abn}, ACN: {self.acn}"


#--------------------------------------
    
    #Invoice data

#--------------------------------------





# models.py

class InvoiceData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    debtor = models.CharField(max_length=255, null=True, blank=True)

    date_funded = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    sif_batch = models.CharField(max_length=100, null=True, blank=True)
    inv_number = models.CharField(max_length=50, null=True, blank=True)

    # ✅ Add this
    approve_reject = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "efs_financial_invoicedata"
        constraints = [
            models.UniqueConstraint(
                fields=["abn", "inv_number"],
                condition=Q(abn__isnull=False) & ~Q(abn=""),
                name="uniq_invoice_by_abn",
            ),
            models.UniqueConstraint(
                fields=["acn", "inv_number"],
                condition=Q(acn__isnull=False) & ~Q(acn=""),
                name="uniq_invoice_by_acn",
            ),
        ]



from django.db import models
from django.db.models import Q
from django.utils import timezone


class InvoiceDataUploaded(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    debtor = models.CharField(max_length=255, null=True, blank=True)

    date_funded = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    invoice_state = models.CharField(max_length=100, null=True, blank=True)
    date_paid = models.DateField("Date Paid", null=True, blank=True)

    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    sif_batch = models.CharField(max_length=100, null=True, blank=True)
    inv_number = models.CharField(max_length=50, null=True, blank=True)

    approve_reject = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        # ✅ different table from the API model
        db_table = "efs_financial_invoicedata_uploaded"
        verbose_name = "InvoiceData-uploaded"
        verbose_name_plural = "InvoiceData-uploaded"

        # ✅ different constraint names from the API model
        constraints = [
            models.UniqueConstraint(
                fields=["abn", "inv_number"],
                condition=Q(abn__isnull=False) & ~Q(abn=""),
                name="uniq_uploaded_invoice_by_abn"
            ),
            models.UniqueConstraint(
                fields=["acn", "inv_number"],
                condition=Q(acn__isnull=False) & ~Q(acn=""),
                name="uniq_uploaded_invoice_by_acn"
            ),
        ]

    def __str__(self):
        return f"Uploaded Transaction {self.transaction_id} - {self.name}"




from django.db import models
from django.db.models import Q
from django.utils import timezone


class AP_InvoiceDataUploaded(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)

    # ✅ AP-specific counterparty field (replaces debtor)
    creditor = models.CharField(max_length=255, null=True, blank=True)

    date_funded = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    invoice_state = models.CharField(max_length=100, null=True, blank=True)
    date_paid = models.DateField("Date Paid", null=True, blank=True)

    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    sif_batch = models.CharField(max_length=100, null=True, blank=True)
    inv_number = models.CharField(max_length=50, null=True, blank=True)

    approve_reject = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        # ✅ separate table for AP uploaded invoices
        db_table = "efs_financial_ap_invoicedata_uploaded"
        verbose_name = "AP InvoiceData-uploaded"
        verbose_name_plural = "AP InvoiceData-uploaded"

        # ✅ unique constraint names must be unique across DB
        constraints = [
            models.UniqueConstraint(
                fields=["abn", "inv_number"],
                condition=Q(abn__isnull=False) & ~Q(abn=""),
                name="uniq_ap_uploaded_invoice_by_abn"
            ),
            models.UniqueConstraint(
                fields=["acn", "inv_number"],
                condition=Q(acn__isnull=False) & ~Q(acn=""),
                name="uniq_ap_uploaded_invoice_by_acn"
            ),
        ]

    def __str__(self):
        return f"AP Uploaded Transaction {self.transaction_id} - {self.name}"






# models.py

import uuid
from django.db import models
from django.utils import timezone

class FinancialStatementNotes(models.Model):
    """
    Free-form notes keyed to a transaction (deal) and an entity.
    Entity might be ABN or might only have ACN.
    """
    transaction_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text="External/shared transaction identifier (UUID)."
    )

    abn = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Australian Business Number (11 digits). Keep as text to preserve leading zeros."
    )

    acn = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        db_index=True,   # <-- add index here
    )

    financial_data_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="What these notes refer to (e.g. 'AR Ledger', 'Assets', 'Liabilities')."
    )

    notes = models.TextField(
        help_text="Free-text notes. Can be long / multi-line."
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "financial_statement_notes"
        # You can keep explicit indexes list OR just rely on db_index=True
        # Having both won't break anything, but it's a bit redundant.
        indexes = [
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["abn"]),
            models.Index(fields=["acn"]),                 # <-- new
            models.Index(fields=["financial_data_type"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        ident = self.abn or self.acn or "no-id"
        return f"Notes[{self.transaction_id}] • {ident} • {self.financial_data_type}"












class tf_InvoiceData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    debtor = models.CharField(max_length=255, null=True, blank=True)
    date_funded = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    sif_batch = models.CharField(max_length=100, null=True, blank=True)
    inv_number = models.CharField(max_length=50, null=True, blank=True)


    class Meta:
        db_table = "efs_financial_tf_invoicedata"
        constraints = [
            models.UniqueConstraint(
                fields=["abn", "inv_number"],
                condition=Q(abn__isnull=False) & ~Q(abn=""),
                name="uniq_tf_invoice_by_abn",
            ),
            models.UniqueConstraint(
                fields=["acn", "inv_number"],
                condition=Q(acn__isnull=False) & ~Q(acn=""),
                name="uniq_tf_invoice_by_acn",
            ),
        ]

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.name}"


from django.db import models
from django.utils import timezone

class scf_InvoiceData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    debtor = models.CharField(max_length=255, null=True, blank=True)
    date_funded = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    sif_batch = models.CharField(max_length=100, null=True, blank=True)
    inv_number = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = "efs_financial_scf_invoicedata"
        constraints = [
            models.UniqueConstraint(
                fields=["abn", "inv_number"],
                condition=Q(abn__isnull=False) & ~Q(abn=""),
                name="uniq_scf_invoice_by_abn",
            ),
            models.UniqueConstraint(
                fields=["acn", "inv_number"],
                condition=Q(acn__isnull=False) & ~Q(acn=""),
                name="uniq_scf_invoice_by_acn",
            ),
        ]

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.name}"



from django.db import models
import uuid
from django.utils import timezone

class FinancialData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(default=timezone.now, null=True, blank=True)  # Automatically store the timestamp
    abn = models.CharField(max_length=11, null=True, blank=True)  # Storing ABN as a string
    acn = models.CharField(max_length=20, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)  # Store company name
    year = models.IntegerField(null=True, blank=True)  # Store the financial year separately
    financials = models.JSONField(null=True, blank=True)  # Store all financial data in JSON format
    profit_loss = models.JSONField(null=True, blank=True)  # Store profit and loss as JSON
    balance_sheet = models.JSONField(null=True, blank=True)  # Store balance sheet as JSON
    cash_flow = models.JSONField(null=True, blank=True)  # Store cashflow as JSON
    financial_statement_notes = models.CharField(max_length=5000, null=True, blank=True)  
    subsidiaries = models.JSONField(default=list, blank=True, null=True)  # Store subsidiaries as a list of JSON objects
    raw = models.JSONField(null=True, blank=True)  # Store raw data as JSON
    
    def __str__(self):
        return f"{self.company_name or 'Unknown Company'} - {self.year or 'Unknown Year'}"


















#--------------------------------------
    
    #assets - vehicales

#--------------------------------------

import uuid
import re
from decimal import Decimal
from django.db import models
from django.utils import timezone

try:
    from django.db.models import JSONField  # Django 3.1+
except Exception:  # pragma: no cover
    from django.contrib.postgres.fields import JSONField

VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")

def validate_vin(value: str):
    v = (value or "").strip().upper()
    if v and not VIN_RE.match(v):
        raise models.ValidationError("VIN must be 17 chars (I,O,Q not allowed).")


class AssetScheduleRow(models.Model):
    """
    SINGLE TABLE capturing:
      - Source/batch info (was AssetSource)
      - Asset descriptors (was Asset)
      - Line item info (was AssetItem)
      - Valuations FMV/FSV/OLV (was AssetValuation)

    One row == one line of the uploaded schedule.
    """

    # Identity
    row_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ---- Source / batch (formerly AssetSource)
    provider_name      = models.CharField(max_length=200, default="Schedule Upload")
    schedule_title     = models.CharField(max_length=500, null=True, blank=True)
    source_as_of_date  = models.DateField(null=True, blank=True)
    original_filename  = models.CharField(max_length=500, null=True, blank=True)
    file_checksum      = models.CharField(max_length=128, null=True, blank=True)

    currency            = models.CharField(max_length=3, default="AUD")
    tax_label           = models.CharField(max_length=50, null=True, blank=True)
    amounts_include_tax = models.BooleanField(default=False)

    abn             = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    acn             = models.CharField(max_length=20, null=True, blank=True)
    transaction_id  = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    # ---- Asset descriptors (formerly Asset)
    make   = models.CharField(max_length=200, default="Unknown")
    model  = models.CharField(max_length=200, default="Unknown")
    type   = models.CharField(max_length=200, default="Asset")

    year_of_manufacture = models.IntegerField(null=True, blank=True)
    age_years           = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    serial_no       = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    vin             = models.CharField(max_length=17, null=True, blank=True, unique=False, validators=[validate_vin])
    registration_no = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    description = models.TextField(null=True, blank=True)
    attributes  = JSONField(default=dict, blank=True)  # extras like axle_configuration, odometer, etc.

    # ---- Line item (formerly AssetItem)
    line_number    = models.IntegerField(null=True, blank=True)
    quantity       = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("1"))
    location       = models.CharField(max_length=300, null=True, blank=True)
    condition_note = models.TextField(null=True, blank=True)

    row_raw = JSONField(default=dict, blank=True)   # original CSV row
    extras  = JSONField(default=dict, blank=True)   # fleet no, sighted flag, UI hints, etc.

    # ---- Valuations (formerly AssetValuation) — denormalised
    valuation_as_of_date = models.DateField(null=True, blank=True)
    fmv_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    fsv_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    olv_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    valuation_notes = models.TextField(null=True, blank=True)

    # ▼▼ NEW
    bv_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)         # Book Value
    lease_os_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)   # Lease Outstanding
    nbv_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)        # Net Book Value
    # ▲▲ NEW

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["abn"]),
            models.Index(fields=["acn"]),  # <-- add
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["source_as_of_date"]),
            models.Index(fields=["vin"]),
            models.Index(fields=["serial_no"]),
            models.Index(fields=["make", "model"]),
            models.Index(fields=["type"]),
        ]


    def __str__(self):
        base = f"{self.make} {self.model}".strip()
        if self.type:
            base += f" ({self.type})"
        return base



#--------------------------------------
    
    #assets - Plant & Machinery

#------------------------
    

# efs_data_financial/core/models.py
import uuid
from django.db import models


class PPEAsset(models.Model):
    """
    Single table for Plant/Property/Equipment asset rows.
    One row per asset line (from an uploaded file).
    """
    row_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Group all rows created by the same upload together
    upload_group = models.UUIDField(default=uuid.uuid4, db_index=True)

    # File context (stored on every row so the table is standalone)
    file = models.FileField(upload_to="uploads/asset_lists/", blank=True, null=True)
    original_filename = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Request/page context
    abn = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    acn = models.CharField(max_length=20, null=True, blank=True)

    transaction_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    originator = models.CharField(max_length=200, blank=True, null=True)

    # Requested/parsed columns
    asset_number = models.CharField(max_length=100, blank=True, null=True)
    asset = models.CharField(max_length=255, blank=True, null=True)
    make = models.CharField(max_length=255, blank=True, null=True)
    type = models.CharField(max_length=255, blank=True, null=True)
    serial_no = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    rego_no = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    year_of_manufacture = models.IntegerField(blank=True, null=True)
    fair_market_value_ex_gst = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    orderly_liquidation_value_ex_gst = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    

    # ▼▼ NEW
    bv_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)         # Book Value
    lease_os_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)   # Lease Outstanding
    nbv_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)        # Net Book Value
    # ▲▲ NEW

    class Meta:
        db_table = "ppe_assets"
        indexes = [
            models.Index(fields=["abn"]),
            models.Index(fields=["acn"]),  # <-- new
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["upload_group"]),
            models.Index(fields=["asset_number"]),
            models.Index(fields=["make"]),
            models.Index(fields=["serial_no"]),
            models.Index(fields=["rego_no"]),
        ]


    def __str__(self):
        parts = [self.asset_number or "", self.asset or "", self.make or "", self.type or ""]
        return " ".join(p for p in parts if p).strip()







# app: efs_sales (or wherever your sales endpoints live)
from django.db import models
from django.utils import timezone


class NetAssetValueSnapshot(models.Model):
    TAB_ASSETS      = "ASSETS"
    TAB_AR          = "AR"
    TAB_LIABILITIES = "LIABILITIES"  # NEW

    TAB_CHOICES = (
        (TAB_ASSETS, "Assets"),
        (TAB_AR, "Accounts Receivable"),
        (TAB_LIABILITIES, "Liabilities"),  # NEW
    )


    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    abn = models.CharField(
        max_length=32,
        db_index=True,
        null=True,         # <-- add this
        blank=True,        # <-- add this (helps admin/forms)
    )
    acn = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    transaction_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    # Which tab created this snapshot
    source_tab = models.CharField(max_length=16, choices=TAB_CHOICES)

    # Slider + totals at the time the user hit "Save"
    advance_rate_pct = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 60.00
    selected_total_amount = models.DecimalField(max_digits=16, decimal_places=2)  # raw nominated/selected sum
    available_funds_amount = models.DecimalField(max_digits=16, decimal_places=2)  # selected_total * advance_rate

    # Optional freeform context
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["abn", "transaction_id", "source_tab"]),
            models.Index(fields=["acn", "transaction_id", "source_tab"]),  # <-- new
        ]


class NAVAssetLine(models.Model):
    """Lines saved when source_tab == ASSETS; only for rows that were ticked."""
    snapshot = models.ForeignKey(
        NetAssetValueSnapshot,
        on_delete=models.CASCADE,
        related_name="asset_lines",
    )

    make = models.CharField(max_length=128, blank=True, default="")
    model = models.CharField(max_length=128, blank=True, default="")
    type = models.CharField(max_length=128, blank=True, default="")
    # keep text to avoid parsing issues
    year_of_manufacture = models.CharField(max_length=16, blank=True, default="")

    fmv_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    fsv_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    # ▼▼ NEW
    bv_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)       # Book Value
    lease_os_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True) # Lease Outstanding
    nbv_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)      # Net Book Value
    # ▲▲ NEW


class NAVPlantandequipmentLine(models.Model):
    """Lines saved for Plant & Equipment data, mirroring NAVAssetLine structure."""
    snapshot = models.ForeignKey(
        NetAssetValueSnapshot,
        on_delete=models.CASCADE,
        related_name="plant_equipment_lines",
    )

    make = models.CharField(max_length=128, blank=True, default="")
    model = models.CharField(max_length=128, blank=True, default="")
    type = models.CharField(max_length=128, blank=True, default="")
    # keep text to avoid parsing issues
    year_of_manufacture = models.CharField(max_length=16, blank=True, default="")

    fmv_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    fsv_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    # ▼▼ NEW
    bv_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)       # Book Value
    lease_os_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True) # Lease Outstanding
    nbv_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)      # Net Book Value
    # ▲▲ NEW



from django.db import models
from decimal import Decimal

class NAVARLine(models.Model):
    snapshot = models.ForeignKey(
        NetAssetValueSnapshot,
        on_delete=models.CASCADE,
        related_name="ar_lines"
    )

    debtor_name = models.CharField(max_length=256, blank=True, default="")

    # Raw aged buckets (as loaded)
    aged_current = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    d0_30        = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    d31_60       = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    d61_90       = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    d90_plus     = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))
    older        = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))  # you have a toggle for this

    # User choice
    nominated = models.BooleanField(default=True)

    # Bucket exclusion impact (per debtor)
    base_due        = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))  # before exclusions
    excluded_amount = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))  # base_due - due_adjusted
    due_adjusted    = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))  # after exclusions (drives EC)

    # Concentration controls and outcomes (per debtor)
    concentration_limit_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))
    conc_adj_manual         = models.BooleanField(default=False)

    # EC math trace (per debtor)
    advance_rate_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))  # the adv rate used
    base_ec          = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))  # due_adjusted * adv%
    adj_ec           = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))  # after concentration solve
    concentration_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0"))  # post-adjust conc %

    # Optional: full trace for weird edge cases / future widgets (safe escape hatch)
    trace = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)




# NEW ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
class NAVLiabilityLine(models.Model):
    """
    Liabilities rows captured manually in the Liabilities tab
    and included in NAV. Each row corresponds to one facility.
    """

    snapshot = models.ForeignKey(
        NetAssetValueSnapshot,
        on_delete=models.CASCADE,
        related_name="liability_lines",
    )

    # We'll store free-form text for lender/product/due_date,
    # and numeric for the money amounts.
    #
    # The UI currently has *two* "Loan Amount" headings.
    # We'll interpret:
    #   - first column "Loan Amount"  -> facility_limit_amount
    #   - fourth column "Loan amount" -> current_balance_amount
    #
    # If you want them identical instead of two concepts,
    # you can collapse these two DecimalFields into one.

    facility_limit_amount = models.DecimalField(  # "Loan Amount" (col 1)
        max_digits=16,
        decimal_places=2,
        default=0
    )

    lender = models.CharField(                    # "Lender"
        max_length=256,
        blank=True,
        default=""
    )

    product = models.CharField(                   # "Product"
        max_length=256,
        blank=True,
        default=""
    )

    current_balance_amount = models.DecimalField( # "Loan amount" (col 4)
        max_digits=16,
        decimal_places=2,
        default=0
    )

    due_date = models.CharField(                  # "Due date"
        max_length=64,
        blank=True,
        default=""
    )

    def __str__(self):
        return f"{self.lender} {self.product} {self.current_balance_amount}"



#--------------------------------------
    
    #Tax  models

#--------------------------------------






class TaxAccountTransaction(models.Model):
    """
    One row per transaction line item from the statement.
    - transaction_id: assigned during upload/insert; NOT unique (shared across many rows in the same upload batch)
    - Stores running balance to allow balance-over-time analysis.
    - Stores debit/credit amounts to compare inflows vs outflows trend.
    """

    # Set during file upload / insertion (can repeat across many rows)
    transaction_id = models.CharField(max_length=64, db_index=True)

    # Context / identifiers (no TFN)
    originator = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    abn = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    acn = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)

    account_label = models.CharField(max_length=100, null=True, blank=True)  # e.g. "Income tax 551"
    statement_generated_at = models.DateField(null=True, blank=True)

    # Core transaction fields
    processed_date = models.DateField(null=True, blank=True, db_index=True)
    effective_date = models.DateField(null=True, blank=True, db_index=True)
    description = models.TextField()

    # Money fields
    debit_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    credit_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    # Running balance + whether it is DR/CR
    balance_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    BALANCE_SIDE_CHOICES = (("DR", "Debit"), ("CR", "Credit"))
    balance_side = models.CharField(max_length=2, choices=BALANCE_SIDE_CHOICES, null=True, blank=True)

    # File / dedupe helpers
    source_file_name = models.CharField(max_length=255, null=True, blank=True)
    source_row_hash = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="Optional: hash of key fields to help detect duplicate inserts",
    )
    inserted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction_id", "effective_date"]),
            models.Index(fields=["originator", "effective_date"]),
            models.Index(fields=["abn", "effective_date"]),
            models.Index(fields=["acn", "effective_date"]),
        ]
        ordering = ["effective_date", "processed_date", "id"]

    def __str__(self):
        return f"{self.transaction_id} | {self.effective_date} | {self.description[:60]}"


class AtoPaymentPlanInstalment(models.Model):
    """
    One row per instalment line item in the payment plan schedule.
    Plan-level metadata is duplicated on each row (single-model constraint),
    which makes querying by transaction_id straightforward.
    """

    # Set during file upload / insertion (can repeat across many rows)
    transaction_id = models.CharField(max_length=64, db_index=True)

    # Context / identifiers (no TFN)
    originator = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    abn = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    acn = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)

    # Plan metadata (from the PDF)
    agent_name = models.CharField(max_length=255, null=True, blank=True)  # e.g. "SPECTRUM ACCOUNTANTS"
    activity_statement_number = models.CharField(max_length=64, null=True, blank=True)  # e.g. "002"
    date_generated = models.DateField(null=True, blank=True)  # e.g. 26/08/2025
    creation_date = models.DateField(null=True, blank=True)   # e.g. 26/08/2025

    # Amount shown on the plan summary line (e.g. "$32,645.00 DR")
    plan_balance_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    PLAN_BALANCE_SIDE_CHOICES = (("DR", "Debit"), ("CR", "Credit"))
    plan_balance_side = models.CharField(max_length=2, choices=PLAN_BALANCE_SIDE_CHOICES, null=True, blank=True)

    # Plan total incl. estimated GIC (interest)
    plan_total_including_estimated_gic = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    payment_method = models.CharField(max_length=100, null=True, blank=True)   # e.g. "Other payment options"
    payment_frequency = models.CharField(max_length=50, null=True, blank=True) # e.g. "Monthly"

    # Payment references (from the PDF)
    biller_code = models.CharField(max_length=32, null=True, blank=True)       # e.g. "75556"
    payment_reference_number = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    ref = models.CharField(max_length=64, null=True, blank=True)              # e.g. "0027560..."

    # Instalment schedule row (core line-item data)
    instalment_date = models.DateField(db_index=True)
    status = models.CharField(max_length=100, null=True, blank=True)           # e.g. "Amount to pay"
    instalment_amount = models.DecimalField(max_digits=14, decimal_places=2)

    # File traceability
    source_file_name = models.CharField(max_length=255, null=True, blank=True)
    inserted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction_id", "instalment_date"]),
            models.Index(fields=["abn", "instalment_date"]),
            models.Index(fields=["originator", "instalment_date"]),
        ]
        ordering = ["instalment_date", "id"]

    def __str__(self):
        return f"{self.company_name or 'Company'} | {self.instalment_date} | {self.instalment_amount}"



class TaxReturn(models.Model):
    """
    One row per lodged return (snapshot for a year).
    Trust-specific fields are nullable so the same model works for PTY LTD / sole trader / etc.
    NO TFN stored.
    """

    # Set during file upload / insertion (can repeat across many rows)
    transaction_id = models.CharField(max_length=64, db_index=True)

    # Context / identifiers (no TFN)
    originator = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    abn = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    acn = models.CharField(max_length=32, null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)

    # Entity type (Australian categories)
    COMPANY_TYPE_CHOICES = (
        ("TRUST", "Trust"),
        ("PTY_LTD", "Company (Pty Ltd)"),
        ("LTD", "Company (Public/Listed Ltd)"),
        ("SOLE_TRADER", "Sole trader"),
        ("PARTNERSHIP", "Partnership"),
        ("INC_ASSOC", "Incorporated association"),
        ("SMSF", "SMSF"),
        ("NON_PROFIT", "Not-for-profit"),
        ("GOV", "Government entity"),
        ("OTHER", "Other"),
    )
    company_type = models.CharField(
        max_length=20,
        choices=COMPANY_TYPE_CHOICES,
        default="OTHER",
        db_index=True,
        help_text="Entity category (e.g. TRUST, PTY_LTD, SOLE_TRADER).",
    )

    # Return metadata (common)
    income_year = models.PositiveIntegerField(db_index=True)  # e.g. 2024 :contentReference[oaicite:2]{index=2}
    period_start = models.DateField(null=True, blank=True)    # e.g. 1 Jul 2023 :contentReference[oaicite:3]{index=3}
    period_end = models.DateField(null=True, blank=True)      # e.g. 30 Jun 2024 :contentReference[oaicite:4]{index=4}
    lodged_date = models.DateField(null=True, blank=True)
    assessed_date = models.DateField(null=True, blank=True)

    # Financial rollups (works for any entity)
    total_income = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    total_deductions = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    taxable_income = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    tax_payable = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    refund_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    # ===== Trust-only fields (nullable; fill when company_type == TRUST) =====

    # Trust identity/details (optional)
    trust_name = models.CharField(max_length=255, null=True, blank=True)  # e.g. "Diami Consulting Trust" :contentReference[oaicite:5]{index=5}
    trustee_name = models.CharField(max_length=255, null=True, blank=True)  # e.g. non-individual trustee name :contentReference[oaicite:6]{index=6}

    # Screenshot 1: Trust information
    trust_type = models.CharField(
        max_length=160, null=True, blank=True,
        help_text="E.g. 'Discretionary trust – trading activities'."
    )  # :contentReference[oaicite:7]{index=7}
    is_tax_payable_by_trustee = models.BooleanField(null=True, blank=True)  # :contentReference[oaicite:8]{index=8}
    is_final_tax_return = models.BooleanField(null=True, blank=True)        # :contentReference[oaicite:9]{index=9}
    main_business_activity_code = models.CharField(max_length=10, null=True, blank=True)  # :contentReference[oaicite:10]{index=10}
    main_business_activity_desc = models.CharField(max_length=255, null=True, blank=True) # :contentReference[oaicite:11]{index=11}

    # Screenshot 2: Beneficiary not entitled
    beneficiary_under_legal_disability_entitled_from_another_trust = models.BooleanField(null=True, blank=True)  # :contentReference[oaicite:12]{index=12}
    is_non_resident_trust = models.BooleanField(null=True, blank=True)                                          # :contentReference[oaicite:13]{index=13}
    any_non_resident_beneficiary_presently_entitled = models.BooleanField(
        null=True, blank=True,
        help_text="Whether any beneficiary not resident at any time in the year was presently entitled."
    )  # :contentReference[oaicite:14]{index=14}

    # Full extracted content for future-proofing (excluding TFN)
    raw_payload = models.JSONField(
        null=True, blank=True,
        help_text="Structured extraction of the return (ensure TFN is excluded/redacted).",
    )

    source_file_name = models.CharField(max_length=255, null=True, blank=True)
    inserted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["transaction_id", "income_year"]),
            models.Index(fields=["originator", "income_year"]),
            models.Index(fields=["abn", "income_year"]),
            models.Index(fields=["acn", "income_year"]),
            models.Index(fields=["company_type", "income_year"]),
        ]
        ordering = ["-income_year", "-inserted_at", "id"]

    def __str__(self):
        return f"{self.company_name or self.trust_name or 'Entity'} | {self.income_year} | {self.transaction_id}"



class BusinessActivityStatement(models.Model):
    transaction_id = models.CharField(max_length=64, db_index=True)

    originator = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    abn = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    acn = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)

    COMPANY_TYPE_CHOICES = (
        ("PTY_LTD", "Company (Pty Ltd)"),
        ("LTD", "Company (Public/Listed Ltd)"),
        ("TRUST", "Trust"),
        ("SOLE_TRADER", "Sole trader"),
        ("PARTNERSHIP", "Partnership"),
        ("OTHER", "Other"),
    )
    company_type = models.CharField(max_length=20, choices=COMPANY_TYPE_CHOICES, default="OTHER", db_index=True)

    year_label = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    period_start = models.DateField(null=True, blank=True, db_index=True)
    period_end = models.DateField(null=True, blank=True, db_index=True)

    # ✅ remove 32-cap risks
    form_type = models.CharField(max_length=255, null=True, blank=True)
    document_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    gst_accounting_method = models.CharField(max_length=255, null=True, blank=True)

    form_due_on = models.DateField(null=True, blank=True)
    payment_due_on = models.DateField(null=True, blank=True)

    gst_on_sales_1a = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    gst_on_purchases_1b = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    payg_withheld_4 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    amount_you_owe_the_ato_8a = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    your_payment_amount_9 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    total_sales_g1 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    g1_includes_gst = models.BooleanField(null=True, blank=True)

    total_salary_wages_w1 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_withheld_w2 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_withheld_no_abn_w4 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    other_amounts_withheld_w3 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    total_amounts_withheld_w5 = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)

    declaring_agent = models.CharField(max_length=255, null=True, blank=True)
    declared_by_name = models.CharField(max_length=255, null=True, blank=True)
    declared_at = models.DateTimeField(null=True, blank=True)

    bpay_reference_number = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    biller_code = models.CharField(max_length=255, null=True, blank=True)

    direct_credit_account_name = models.CharField(max_length=255, null=True, blank=True)
    direct_credit_bsb = models.CharField(max_length=255, null=True, blank=True)
    direct_credit_account_number = models.CharField(max_length=255, null=True, blank=True)
    direct_credit_institution_name = models.CharField(max_length=255, null=True, blank=True)
    direct_credit_reference_number = models.CharField(max_length=255, null=True, blank=True)

    raw_payload = models.JSONField(null=True, blank=True)

    source_file_name = models.CharField(max_length=255, null=True, blank=True)
    inserted_at = models.DateTimeField(auto_now_add=True)






#--------------------------------------
    
    #PPSR registrations 

#------------------------

from django.db import models
import uuid
from django.utils import timezone

class Registration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.UUIDField(null=True, blank=True, db_index=True)
    abn = models.CharField(max_length=15, null=True, blank=True)  # ✅ Add this line
    acn = models.CharField(max_length=20, null=True, blank=True)

    search_date = models.DateField(null=True, blank=True) # Using DateField as it sounds like a date without time is sufficient

    # Main registration fields
    registration_number = models.CharField(max_length=20, null=True, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    change_number = models.CharField(max_length=20, null=True, blank=True)
    change_time = models.DateTimeField(null=True, blank=True)
    registration_kind = models.CharField(max_length=255, null=True, blank=True)
    is_migrated = models.BooleanField(null=True, blank=True)
    is_transitional = models.BooleanField(null=True, blank=True)
    
    # Grantor information
    grantor_organisation_identifier = models.CharField(max_length=255, null=True, blank=True)
    grantor_organisation_identifier_type = models.CharField(max_length=255, null=True, blank=True)
    grantor_organisation_name = models.CharField(max_length=255, null=True, blank=True)

    # Collateral information
    collateral_class_type = models.CharField(max_length=255, null=True, blank=True)
    collateral_type = models.CharField(max_length=255, null=True, blank=True)
    collateral_class_description = models.CharField(null=True, blank=True)
    are_proceeds_claimed = models.BooleanField(null=True, blank=True)
    proceeds_claimed_description = models.CharField(max_length=255, null=True, blank=True)
    is_security_interest_registration_kind = models.BooleanField(null=True, blank=True)
    are_assets_subject_to_control = models.BooleanField(null=True, blank=True)
    is_inventory = models.BooleanField(null=True, blank=True)
    is_pmsi = models.BooleanField(null=True, blank=True)
    is_subordinate = models.BooleanField(null=True, blank=True)
    giving_of_notice_identifier = models.CharField(max_length=255, null=True, blank=True)
    
    # JSON fields to store nested data
    security_party_groups = models.JSONField(null=True, blank=True)  # Store securityPartyGroups as a list of dictionaries (JSON)
    grantors = models.JSONField(null=True, blank=True)  # Store grantors as a list of dictionaries (JSON)
    address_for_service = models.JSONField(null=True, blank=True)  # Store addressForService as a dictionary (JSON)

    # Timestamp for when the record was created
    created_at = models.DateTimeField(default=timezone.now, null=True, blank=True)


    class Meta:
        indexes = [
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["abn"]),
            models.Index(fields=["acn"]),
            models.Index(fields=["registration_number"]),
        ]

    def __str__(self):
        return self.registration_number or str(self.id)







