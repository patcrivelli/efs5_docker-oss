from django.db import models

class BaseApplicationData(models.Model):
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    application_time = models.DateTimeField(null=True, blank=True)
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    abn = models.CharField(max_length=20, null=True, blank=True)
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
    insurance_premiums = models.JSONField(null=True, blank=True)  # New field to store insurance premiums as JSON

    class Meta:
        abstract = True

class ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "efs_risk_applicationdata"

class tf_ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "efs_risk_tf_applicationdata"

class scf_ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "efs_risk_scf_applicationdata"

class IPF_ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "efs_risk_ipf_applicationdata"

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

