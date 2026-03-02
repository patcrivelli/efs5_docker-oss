from django.db import models

# Updated Model for storing Products settings
class ProductsGlobalSettings(models.Model):
    originator = models.CharField(max_length=255, null=True, blank=True)  # String field for originator
    term_loan_switch = models.BooleanField(default=False, null=True, blank=True)
    term_loan_duration_years = models.IntegerField(null=True, blank=True)
    term_loan_duration_months = models.IntegerField(null=True, blank=True)
    overdraft_switch = models.BooleanField(default=False, null=True, blank=True)
    overdraft_duration_years = models.IntegerField(null=True, blank=True)
    overdraft_duration_months = models.IntegerField(null=True, blank=True)
    credit_card_switch = models.BooleanField(default=False, null=True, blank=True)
    credit_card_duration_years = models.IntegerField(null=True, blank=True)
    credit_card_duration_months = models.IntegerField(null=True, blank=True)
    bulk_invoice_finance_switch = models.BooleanField(default=False, null=True, blank=True)
    single_invoice_finance_switch = models.BooleanField(default=False, null=True, blank=True)

    # Trade Finance
    trade_finance_switch = models.BooleanField(default=False, null=True, blank=True)
    trade_finance_installments = models.JSONField(null=True, blank=True)  # Added
    trade_finance_installment_frequency = models.JSONField(null=True, blank=True)  # Added

    # Insurance Premium Funding
    insurance_premium_funding_switch = models.BooleanField(default=False, null=True, blank=True)
    insurance_premium_funding_installments = models.JSONField(null=True, blank=True)  # Added
    insurance_premium_funding_installment_frequency = models.JSONField(null=True, blank=True)  # Added

    timestamp = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"Products Settings (Originator: {self.originator}, ID: {self.id})"

    class Meta:
        ordering = ['-timestamp']

