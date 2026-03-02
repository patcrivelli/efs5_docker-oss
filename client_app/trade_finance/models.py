from django.db import models
from django.utils import timezone
import uuid

from django.db import models
from django.utils import timezone

class AccontsPayableLedgerData(models.Model):
    abn = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Australian Business Number (ABN)"
    )

    user_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Username captured from the Trade Finance UI"
    )

    supplier = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Creditor / supplier name"
    )

    invoice_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Invoice number"
    )

    amount_due = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount due"
    )

    repayment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected repayment date"
    )

    status = models.CharField(
        max_length=255,
        choices=[
            ("Open", "Open"),
            ("Paid", "Paid"),
            ("Draft", "Draft")
        ],
        default="Open"
    )

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"APLedger | ABN: {self.abn} | Supplier: {self.supplier} | Status: {self.status}"

from django.db import models
import uuid

class TF_ApplicationData(models.Model):
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)  # Unique auto-generated UUID
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
    amount_requested = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    product = models.CharField(max_length=2000, null=True, blank=True)  # New field for product name

    def __str__(self):
        return f"{self.contact_name} - {self.abn}"


from django.db import models
from django.utils import timezone

class TF_InvoiceData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)  # Australian Business Number (ABN)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)  # Name of the client or creditor
    transaction_id = models.CharField(max_length=50, null=True, blank=True)  # Transaction ID
    credit = models.CharField(max_length=255, null=True, blank=True)  # Name of the creditor
    date_funded = models.DateField(default=timezone.now, null=True, blank=True)  # Automatically set to current date on DB insertion
    due_date = models.DateField(null=True, blank=True)  # Due date for repayment
    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Amount funded
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Amount due
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Discount percentage
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  # Face value of the loan
    sif_batch = models.CharField(max_length=100, null=True, blank=True)  # SIF/Batch number
    inv_number = models.CharField(max_length=50, null=True, blank=True)  # Invoice number

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.name}"

