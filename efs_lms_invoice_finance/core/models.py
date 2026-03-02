from django.db import models
import uuid


# -------------------------
# Abstract bases (local only)
# -------------------------
class BaseTransactionLedger(models.Model):
    trans_id = models.CharField(max_length=255, unique=True)
    abn = models.CharField(max_length=20, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)  # ✅ ADD THIS
    originator = models.CharField(max_length=2000, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_repaid = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    state = models.CharField(max_length=255, null=True, blank=True)
    product = models.CharField(max_length=2000, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"Transaction {self.trans_id} - {self.name}"


class BaseTransactionDetails(models.Model):
    trans_id = models.CharField(max_length=255)
    originator = models.CharField(max_length=2000, null=True, blank=True)
    debtor = models.CharField(max_length=255, null=True, blank=True)
    due = models.DateField(null=True, blank=True)
    amount_funded = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_repaid = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    amount_due = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    face_value = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    date_funded = models.DateField(null=True, blank=True)
    invoice_number = models.CharField(max_length=255, null=True, blank=True)
    abn = models.CharField(max_length=20, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)  # ✅ ADD THIS
    product = models.CharField(max_length=2000, null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"Details for Transaction {self.trans_id} - Invoice {self.invoice_number}"


class BaseInvoiceRepayments(models.Model):
    trans_id = models.CharField(max_length=255, null=True, blank=True)
    originator = models.CharField(max_length=2000, null=True, blank=True)
    invoice_number = models.CharField(max_length=255, null=True, blank=True)
    amount_repaid = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    date_repaid = models.DateField(null=True, blank=True)
    allocation_id = models.CharField(max_length=255, null=True, blank=True)
    abn = models.CharField(max_length=20, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)  # ✅ ADD THIS
    product = models.CharField(max_length=2000, null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"Repayment for Invoice {self.invoice_number} - {self.amount_repaid}"


class BaseDrawdownData(models.Model):
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    originator = models.CharField(max_length=2000, null=True, blank=True)
    drawdown_time = models.DateTimeField(null=True, blank=True)
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
    insurance_premiums = models.JSONField(null=True, blank=True)

    class Meta:
        abstract = True


class BaseDrawdown(models.Model):
    trans_id = models.CharField(max_length=255, null=True, blank=True)
    originator = models.CharField(max_length=2000, null=True, blank=True)
    invoice_number = models.CharField(max_length=255, null=True, blank=True)
    amount_drawndown = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    date_drawndown = models.DateField(null=True, blank=True)
    allocation_id = models.CharField(max_length=255, null=True, blank=True)
    abn = models.CharField(max_length=20, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)  # ✅ ADD THIS
    product = models.CharField(max_length=2000, null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self):
        return f"Drawdown for Invoice {self.invoice_number} - {self.amount_drawndown}"


# -------------------------
# Concrete models (Invoice Finance)
# -------------------------
class TransactionLedger(BaseTransactionLedger):
    class Meta:
        db_table = "efs_lms_transactionledger"


class TransactionDetails(BaseTransactionDetails):
    class Meta:
        db_table = "efs_lms_transactiondetails"


class InvoiceRepayments(BaseInvoiceRepayments):
    class Meta:
        db_table = "efs_lms_invoicerepayments"


class DrawdownData(BaseDrawdownData):
    class Meta:
        db_table = "efs_lms_drawdowndata"


class Drawdown(BaseDrawdown):
    class Meta:
        db_table = "efs_lms_drawdown"
