from django.db import models
from django.utils import timezone

# Create your models here.


class InvoiceData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)  # Australian Business Number (ABN)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)  # Name of the client or debtor
    transaction_id = models.CharField(max_length=100, null=True, blank=True)  # ✅ Removed `unique=True`
    debtor = models.CharField(max_length=255, null=True, blank=True)  # Name of the debtor
    date_funded = models.DateField(default=timezone.now, null=True, blank=True)  # Automatically set to current date on DB insertion
    due_date = models.DateField(null=True, blank=True)  # Due date for repayment
    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Amount funded
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Amount due
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Discount percentage
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Face value of the loan
    sif_batch = models.CharField(max_length=100, null=True, blank=True)  # SIF/Batch number
    inv_number = models.CharField(max_length=50, null=True, blank=True)  # Invoice number

    class Meta:
        db_table = "efs_financial_invoicedata"  # Explicitly define table name
        unique_together = ('abn', 'inv_number')  # ✅ Ensure uniqueness

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.name}"


class LedgerData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)  # Australian Business Number (ABN)
    transaction_id = models.UUIDField(unique=True, editable=False, null=True, blank=True)  # Unique transaction ID
    debtor = models.CharField(max_length=255, null=True, blank=True)  # Debtor name
    invoice_number = models.CharField(max_length=50, null=True, blank=True)  # Invoice number
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Amount due
    repayment_date = models.DateField(null=True, blank=True)  # Expected repayment date
    status = models.CharField(max_length=255, null=True, blank=True)  # Status of the ledger entry
    created_at = models.DateTimeField(default=timezone.now)  # Timestamp when entry was created

    class Meta:
        db_table = "efs_financial_ledgerdata"  # Explicitly define table name
        unique_together = ('abn', 'invoice_number')  # ✅ Ensure uniqueness

    def __str__(self):
        return f"Ledger {self.transaction_id} - {self.debtor} - {self.status}"


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
        db_table = "efs_financial_tf_invoicedata"  # Updated to reflect efs_sales naming
        unique_together = ('abn', 'inv_number')  # ✅ Ensure uniqueness

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
        db_table = "efs_financial_scf_invoicedata"  # Reflects efs_sales naming
        unique_together = ('abn', 'inv_number')  # ✅ Ensure uniqueness

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
    subsidiaries = models.JSONField(default=list, blank=True, null=True)  # Store subsidiaries as a list of JSON objects
    raw = models.JSONField(null=True, blank=True)  # Store raw data as JSON
    
    def __str__(self):
        return f"{self.company_name or 'Unknown Company'} - {self.year or 'Unknown Year'}"




from django.db import models
import uuid
from django.utils import timezone

class Registration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    abn = models.CharField(max_length=15, null=True, blank=True)  # ✅ Add this line
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

    def __str__(self):
        return self.registration_number or str(self.id)

