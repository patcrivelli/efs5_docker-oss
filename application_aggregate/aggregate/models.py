from django.db import models
from django.core.exceptions import ValidationError

def _digits_only(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())

def _classify_id_type(digits: str) -> str:
    """
    Return "abn" if 11 digits, "acn" if 9 digits, else "" (invalid).
    """
    if len(digits) == 11:
        return "abn"
    if len(digits) == 9:
        return "acn"
    return ""


class BaseApplicationData(models.Model):
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    application_time = models.DateTimeField(null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    abn = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    bankstatements_token = models.CharField(max_length=2000, null=True, blank=True)
    bureau_token = models.CharField(max_length=2000, null=True, blank=True)
    accounting_token = models.CharField(max_length=2000, null=True, blank=True)
    ppsr_token = models.CharField(max_length=2000, null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    originator = models.CharField(max_length=2000, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    amount_requested = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    product = models.CharField(max_length=2000, null=True, blank=True)
    insurance_premiums = models.JSONField(null=True, blank=True)

    # links is now a list of objects:
    #   { "id": "11111111111", "type": "abn" }
    #   { "id": "080772096",   "type": "acn" }
    #
    # NOTE: we'll gracefully accept legacy lists like ["11111111111", "080772096"]
    # and convert them on clean().
    links = models.JSONField(default=list, blank=True)

    # Human readable notes about relationships (multi-line string)
    link_description = models.TextField(blank=True, default="")

    class Meta:
        abstract = True

    def clean(self):
        """
        - Ensure `links` is always a list of dicts:
            { "id": "<digits>", "type": "abn"|"acn" }
        - Auto-upgrade legacy data (list of strings).
        - Dedupe entries (same id+type).
        - Validate each id is either 11-digit ABN or 9-digit ACN.
        - Normalize link_description stays as-is (no validation here).
        """
        super().clean()

        raw_links = self.links

        # Treat None as []
        if raw_links is None:
            raw_links = []

        if not isinstance(raw_links, list):
            raise ValidationError({
                "links": "Must be a list of ABN/ACN link objects."
            })

        normalized_links = []
        bad_values = []

        for entry in raw_links:
            # Case 1: legacy string "53004085616"
            if isinstance(entry, str):
                digits = _digits_only(entry)
                link_type = _classify_id_type(digits)
                if digits and link_type:
                    normalized_links.append({"id": digits, "type": link_type})
                else:
                    bad_values.append(entry)
                continue

            # Case 2: new style dict {"id": "...", "type": "..."}
            if isinstance(entry, dict):
                digits = _digits_only(entry.get("id", ""))
                link_type = (entry.get("type") or "").strip().lower()
                # if "type" is missing or wrong, infer from length:
                if link_type not in ("abn", "acn"):
                    link_type = _classify_id_type(digits)

                if digits and link_type in ("abn","acn") and _classify_id_type(digits) == link_type:
                    normalized_links.append({"id": digits, "type": link_type})
                else:
                    bad_values.append(entry)
                continue

            # Anything else is junk
            bad_values.append(entry)

        if bad_values:
            raise ValidationError({
                "links": [
                    "Invalid link entries (must be ABN=11 digits or ACN=9 digits): "
                    + ", ".join(str(v) for v in bad_values)
                ]
            })

        # Dedupe by (id,type)
        dedup = {}
        for l in normalized_links:
            dedup[(l["id"], l["type"])] = l
        self.links = list(dedup.values())


class ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "aggregate_applicationdata"


class TfApplicationData(BaseApplicationData):
    class Meta:
        db_table = "aggregate_tf_applicationdata"


class ScfApplicationData(BaseApplicationData):
    class Meta:
        db_table = "aggregate_scf_applicationdata"


class IpfApplicationData(BaseApplicationData):
    class Meta:
        db_table = "aggregate_ipf_applicationdata"





from django.db import models
from django.utils import timezone
import uuid


from django.db import models
import uuid

class SalesOverride(models.Model):
    ABN = models.CharField(max_length=100, null=True, blank=True)
    transactionID = models.UUIDField(default=uuid.uuid4, null=True, blank=True)  # Assuming this is a UUID for transactions
    Insolvencies = models.BooleanField(default=False, null=True, blank=True)  # True if Insolvencies exist
    Insolvencies_state = models.CharField(max_length=100, choices=[('open', 'Open'), ('closed', 'Closed')], default='open', null=True, blank=True)
    Payment_Defaults = models.BooleanField(default=False, null=True, blank=True)  # True if Payment Defaults exist
    Payment_Defaults_state = models.CharField(max_length=100, choices=[('open', 'Open'), ('closed', 'Closed')], default='open', null=True, blank=True)
    Mercantile_Enquiries = models.BooleanField(default=False, null=True, blank=True)  # True if Mercantile Enquiries exist
    Mercantile_Enquiries_state = models.CharField(max_length=100, choices=[('open', 'Open'), ('closed', 'Closed')], default='open', null=True, blank=True)
    Court_Judgements = models.BooleanField(default=False, null=True, blank=True)  # True if Court Judgements exist
    Court_Judgements_state = models.CharField(max_length=100, choices=[('open', 'Open'), ('closed', 'Closed')], default='open', null=True, blank=True)
    ATO_Tax_Default = models.BooleanField(default=False, null=True, blank=True)  # True if ATO Tax Default exists
    ATO_Tax_Default_state = models.CharField(max_length=100, choices=[('open', 'Open'), ('closed', 'Closed')], default='open', null=True, blank=True)
    Loans = models.BooleanField(default=False, null=True, blank=True)  # True if Loans exist
    Loans_state = models.CharField(max_length=100, choices=[('open', 'Open'), ('closed', 'Closed')], default='open', null=True, blank=True)
    ANZSIC = models.BooleanField(default=False, null=True, blank=True)  # True if ANZSIC exists
    ANZSIC_state = models.CharField(max_length=100, choices=[('open', 'Open'), ('closed', 'Closed')], default='open', null=True, blank=True)
    Credit_score_threshold = models.CharField(max_length=100, null=True, blank=True)
    Credit_score_threshold_state = models.CharField(max_length=100, choices=[('below', 'Below Threshold'), ('above', 'Above Threshold')], default='above', null=True, blank=True)
    Sales_notes = models.TextField(blank=True, null=True)
    
    # ✅ Field added to timestamp the insertion
    created_at = models.DateTimeField(auto_now_add=True)  # Automatically set the timestamp on insert

    def __str__(self):
        return f"Sales Override for ABN {self.ABN}, Transaction {self.transactionID}"



from django.db import models

# Create your models here.
from django.db import models
from django.utils import timezone # Import for datestamp default/auto_now_add

# Removed: from efs_profile.models import Originator (no longer needed if no ForeignKey)

class InvoiceFinanceTerms(models.Model):
    """
    Data model to store terms and conditions for Invoice Finance.
    """
    # --- Updated Fields (No ForeignKey) ---
    originator = models.CharField( # Changed from ForeignKey to CharField
        max_length=255, # Sufficient length for a name
        blank=True,
        null=True,
        help_text="Name of the originator associated with these terms."
    )
    abn = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        help_text="Australian Business Number (ABN) associated with these terms."
    )
    acn = models.CharField(
        max_length=11,
        blank=True,
        null=True,
        help_text="Australian Company Number (ACN) associated with these terms."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        help_text="Date and time when these terms were created."
    )
    # --- End Updated Fields ---

    facility_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=10000,
        help_text="Facility Limit in AUD ($)"
    )
    legal_fees = models.DecimalField(
        max_digits=10, decimal_places=2, default=850,
        help_text="Legal Fees in AUD ($)"
    )
    establishment_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=5000,
        help_text="Establishment Fee in AUD ($)"
    )
    advanced_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=80,
        help_text="Advanced Rate (%)"
    )
    minimum_term = models.IntegerField(
        default=36,
        help_text="Minimum Term (months)"
    )
    notice_period = models.IntegerField(
        default=9,
        help_text="Notice Period (months)"
    )
    recourse_period = models.IntegerField(
        default=90,
        help_text="Recourse Period (days)"
    )

    # Service Fee
    service_fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=1000,
        help_text="Service Fee Amount (Higher of) in AUD ($)"
    )
    service_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.25,
        help_text="Service Fee Percent (Higher of) (%)"
    )

    # Default Max Concentration
    concentration_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=50000,
        help_text="Default Max Concentration Amount Limit (Lower of) in AUD ($)"
    )
    concentration_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=50,
        help_text="Default Max Concentration Percentage Limit (Lower of) (%)"
    )

    # Interest Rate Charge
    base_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=6.59,
        help_text="Interest Rate Charge Base Rate (%)"
    )
    charge_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.41,
        help_text="Interest Rate Charge Rate (%)"
    )

    # Upfront Discount
    discount_per_invoice = models.DecimalField(
        max_digits=5, decimal_places=2, default=1,
        help_text="Upfront Discount Per Invoice (%)"
    )

    class Meta:
        verbose_name = "Invoice Finance Terms"
        verbose_name_plural = "Invoice Finance Terms"

    def __str__(self):
        # Updated __str__ to use the CharField 'originator' or 'abn'
        return f"Invoice Finance Terms for {self.originator or self.abn or 'N/A'} - ID: {self.id}"


class TradeFinanceTerms(models.Model):
    """
    Data model to store terms and conditions for Trade Finance.
    """
    # --- Updated Fields (No ForeignKey) ---
    originator = models.CharField(max_length=255, blank=True, null=True, help_text="Name of the originator.")
    abn = models.CharField(max_length=11, blank=True, null=True, help_text="Australian Business Number (ABN)")
    acn = models.CharField(max_length=11, blank=True, null=True, help_text="Australian Company Number (ACN)")
    timestamp = models.DateTimeField(auto_now_add=True, null=True, blank=True, help_text="Date and time when these terms were created.")
    # --- End Updated Fields ---

    facility_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=25000,
        help_text="Trade Facility Limit in AUD ($)"
    )
    legal_fees = models.DecimalField(
        max_digits=10, decimal_places=2, default=1000,
        help_text="Trade Legal Fees in AUD ($)"
    )
    establishment_fee = models.DecimalField(
        max_digits=12, decimal_places=2, default=6000,
        help_text="Trade Establishment Fee in AUD ($)"
    )
    advanced_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=75,
        help_text="Trade Advance Rate (%)"
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=15,
        help_text="Trade Interest Rate (%)"
    )
    minimum_term = models.IntegerField(
        default=24,
        help_text="Trade Minimum Term (months)"
    )
    notice_period = models.IntegerField(
        default=6,
        help_text="Trade Notice Period (months)"
    )
    payment_term = models.IntegerField(
        default=120,
        help_text="Trade Payment Term (days)"
    )
    num_installments = models.IntegerField(
        default=4,
        help_text="Number of Installments"
    )
    installment_period = models.IntegerField(
        default=30,
        help_text="Installment Period (days)"
    )

    # Service Fee
    service_fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=1200,
        help_text="Trade Service Fee Amount (Higher of) in AUD ($)"
    )
    service_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.5,
        help_text="Trade Service Fee Percent (Higher of) (%)"
    )

    # Discount Charge
    base_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=7.0,
        help_text="Trade Discount Charge Base Rate (%)"
    )
    charge_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.6,
        help_text="Trade Discount Charge Rate (%)"
    )

    class Meta:
        verbose_name = "Trade Finance Terms"
        verbose_name_plural = "Trade Finance Terms"

    def __str__(self):
        return f"Trade Finance Terms for {self.originator or self.abn or 'N/A'} - Limit: ${self.facility_limit}"


class SupplyChainFinanceTerms(models.Model):
    """
    Data model to store terms and conditions for Supply Chain Finance.
    """
    # --- Updated Fields (No ForeignKey) ---
    originator = models.CharField(max_length=255, blank=True, null=True, help_text="Name of the originator.")
    abn = models.CharField(max_length=11, blank=True, null=True, help_text="Australian Business Number (ABN)")
    acn = models.CharField(max_length=11, blank=True, null=True, help_text="Australian Company Number (ACN)")
    timestamp = models.DateTimeField(auto_now_add=True, null=True, blank=True, help_text="Date and time when these terms were created.")
    # --- End Updated Fields ---

    scf_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=100000,
        help_text="SCF Limit in AUD ($)"
    )
    scf_setup_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=1000,
        help_text="SCF Setup Fee in AUD ($)"
    )
    scf_discount_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.5,
        help_text="SCF Discount Rate (%)"
    )
    scf_payment_terms = models.IntegerField(
        default=60,
        help_text="SCF Payment Terms (days)"
    )
    scf_min_invoice = models.DecimalField(
        max_digits=10, decimal_places=2, default=500,
        help_text="SCF Minimum Invoice in AUD ($)"
    )

    # Service Charge
    scf_rate_per_invoice = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.25,
        help_text="SCF Service Charge Rate per Invoice (%)"
    )

    class Meta:
        verbose_name = "Supply Chain Finance Terms"
        verbose_name_plural = "Supply Chain Finance Terms"

    def __str__(self):
        return f"SCF Terms for {self.originator or self.abn or 'N/A'} - Limit: ${self.scf_limit}"
    



class InsurancePremiumFundingTerms(models.Model):
    """
    Data model to store terms and conditions for Insurance Premium Funding.
    """
    # --- Updated Fields (No ForeignKey) ---
    originator = models.CharField(max_length=255, blank=True, null=True, help_text="Name of the originator.")
    abn = models.CharField(max_length=11, blank=True, null=True, help_text="Australian Business Number (ABN)")
    acn = models.CharField(max_length=11, blank=True, null=True, help_text="Australian Company Number (ACN)")
    timestamp = models.DateTimeField(auto_now_add=True, null=True, blank=True, help_text="Date and time when these terms were created.")
    # --- End Updated Fields ---

    funding_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=5000,
        help_text="Funding Limit in AUD ($)"
    )
    admin_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=100,
        help_text="Admin Fee in AUD ($)"
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=9,
        help_text="Interest Rate (%)"
    )
    term = models.IntegerField(
        default=12,
        help_text="Term (months)"
    )
    late_payment_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=50,
        help_text="Late Payment Fee in AUD ($)"
    )
    num_installments = models.IntegerField(
        default=4,
        help_text="Number of Installments"
    )
    installment_period = models.IntegerField(
        default=30,
        help_text="Installment Period (days)"
    )

    # Service Fee
    service_fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=50,
        help_text="IPF Service Fee Amount in AUD ($)"
    )

    class Meta:
        verbose_name = "Insurance Premium Funding Terms"
        verbose_name_plural = "Insurance Premium Funding Terms"

    def __str__(self):
        return f"IPF Terms for {self.originator or self.abn or 'N/A'} - Limit: ${self.funding_limit}"





class DealCondition(models.Model):
    class ConditionType(models.TextChoices):
        PRE = "pre", "PRE-Settlement"
        POST = "post", "POST-Settlement"

    # Core “context” fields
    originator = models.CharField(max_length=2000, null=True, blank=True, db_index=True)
    company_name = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    product = models.CharField(max_length=2000, null=True, blank=True, db_index=True)

    # The condition itself
    condition_type = models.CharField(
        max_length=10,
        choices=ConditionType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")

    # Assignment / audit fields (store as strings to keep services decoupled)
    created_by = models.CharField(max_length=255)
    assigned_to = models.CharField(max_length=255, null=True, blank=True)

    # Dates
    date_created = models.DateTimeField(auto_now_add=True)

    # Optional but very useful for joining back to a deal (if you have it)
    transaction_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Optional state (if you later want the green tick to mean something persisted)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "deal_conditions"
        ordering = ["-date_created"]
        indexes = [
            models.Index(fields=["originator", "company_name"]),
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["condition_type", "date_created"]),
        ]

    def __str__(self):
        return f"{self.get_condition_type_display()} | {self.company_name or ''} | {self.title}"
