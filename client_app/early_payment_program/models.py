
from django.db import models
from django.utils import timezone
import uuid

class scf_ApplicationData(models.Model):
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)  # Unique transaction ID
    application_time = models.DateTimeField(null=True, blank=True)
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    abn = models.CharField(max_length=20, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    bankstatements_token = models.CharField(max_length=2000, null=True, blank=True)
    bureau_token = models.CharField(max_length=2000, null=True, blank=True)
    accounting_token = models.CharField(max_length=2000, null=True, blank=True)
    ppsr_token = models.CharField(max_length=2000, null=True, blank=True)  # PPSR token
    contact_email = models.EmailField(null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    originator = models.CharField(max_length=2000, null=True, blank=True)
    amount_requested = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    product = models.CharField(max_length=2000, null=True, blank=True)

    def __str__(self):
        return f"{self.contact_name} - {self.abn}"
    

from django.db import models
from django.utils import timezone
import uuid


class scf_ApplicationInvoiceData(models.Model):
    """
    Denormalised invoice table linked to SCF applications
    via shared transaction_id (UUID).

    IMPORTANT:
    - transaction_id is NOT unique here
    - multiple invoices can share the same transaction_id
    """

    # 🔗 Shared with scf_ApplicationData.transaction_id
    transaction_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True  # ✅ index for fast lookups
    )

    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    debtor = models.CharField(max_length=255, null=True, blank=True)

    date_funded = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)

    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)

    sif_batch = models.CharField(max_length=100, null=True, blank=True)
    inv_number = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Application {self.transaction_id} – Invoice {self.inv_number}"




class scf_InvoiceData(models.Model):
    abn = models.CharField(max_length=15, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    transaction_id = models.CharField(max_length=50, null=True, blank=True)
    debtor = models.CharField(max_length=255, null=True, blank=True)
    date_funded = models.DateField(default=timezone.now, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    sif_batch = models.CharField(max_length=100, null=True, blank=True)
    inv_number = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.name}"