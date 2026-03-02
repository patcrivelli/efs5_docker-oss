from django.db import models

# Updated Model for storing Credit Decision Parameters
class CreditDecisionParametersGlobalSettings(models.Model):
    originator = models.CharField(max_length=255, null=True, blank=True)  # String field for originator
    credit_score_threshold = models.IntegerField(default=500, null=True, blank=True)
    credit_score_switch = models.BooleanField(default=False, null=True, blank=True)
    credit_enquiries_switch = models.BooleanField(default=False, null=True, blank=True)
    court_actions_current_switch = models.BooleanField(default=False, null=True, blank=True)
    court_actions_resolved_switch = models.BooleanField(default=False, null=True, blank=True)
    payment_defaults_current_switch = models.BooleanField(default=False, null=True, blank=True)
    payment_defaults_resolved_switch = models.BooleanField(default=False, null=True, blank=True)
    insolvencies_switch = models.BooleanField(default=False, null=True, blank=True)
    ato_tax_default_switch = models.BooleanField(default=False, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"Credit Decision Parameters (Originator: {self.originator}, ID: {self.id})"

    class Meta:
        ordering = ['-timestamp']


# Updated Model for storing Bank Statements settings
class BankStatementsGlobalSettings(models.Model):
    originator = models.CharField(max_length=255, null=True, blank=True)  # String field for originator
    debt_serviceability_coverage = models.FloatField(default=2.5, null=True, blank=True)
    debt_serviceability_switch = models.BooleanField(default=False, null=True, blank=True)
    inflow_outflow_ratio = models.FloatField(default=2.5, null=True, blank=True)
    inflow_outflow_switch = models.BooleanField(default=False, null=True, blank=True)
    expense_category_1 = models.IntegerField(default=1, null=True, blank=True)
    expense_category_1_switch = models.BooleanField(default=False, null=True, blank=True)
    expense_category_2 = models.IntegerField(default=1, null=True, blank=True)
    expense_category_2_switch = models.BooleanField(default=False, null=True, blank=True)
    expense_category_3 = models.IntegerField(default=1, null=True, blank=True)
    expense_category_3_switch = models.BooleanField(default=False, null=True, blank=True)
    expense_category_4 = models.IntegerField(default=1, null=True, blank=True)
    expense_category_4_switch = models.BooleanField(default=False, null=True, blank=True)
    expense_category_5 = models.IntegerField(default=1, null=True, blank=True)
    expense_category_5_switch = models.BooleanField(default=False, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"Bank Statements Settings (Originator: {self.originator}, ID: {self.id})"

    class Meta:
        ordering = ['-timestamp']


# Updated Model for storing Financials settings
class FinancialsGlobalSettings(models.Model):
    originator = models.CharField(max_length=255, null=True, blank=True)  # String field for originator
    ebitda_margin = models.FloatField(default=0.5, null=True, blank=True)
    ebitda_margin_switch = models.BooleanField(default=False, null=True, blank=True)
    debt_to_equity_ratio = models.FloatField(default=2.5, null=True, blank=True)
    debt_to_equity_ratio_switch = models.BooleanField(default=False, null=True, blank=True)
    liquidity_ratio = models.FloatField(default=2.5, null=True, blank=True)
    liquidity_ratio_switch = models.BooleanField(default=False, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"Financials Settings (Originator: {self.originator}, ID: {self.id})"

    class Meta:
        ordering = ['-timestamp']


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
