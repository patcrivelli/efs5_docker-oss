from django.db import models
from django.utils import timezone
import uuid

class CreditScore(models.Model):
    abn = models.CharField(max_length=20, null=True)
    acn = models.CharField(max_length=20, null=True)
    current_credit_score = models.IntegerField(null=True)
    description = models.CharField(max_length=255, null=True)
    item_code = models.CharField(max_length=50, null=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the instance is created
    updated_at = models.DateTimeField(auto_now=True)      # Timestamp for when the instance is updated

    def __str__(self):
        return f"Credit Score for ABN {self.abn}, ACN {self.acn}"

class CreditScoreHistory(models.Model):
    abn = models.CharField(max_length=20, null=True)  # New field replacing ForeignKey
    date = models.DateField(null=True)
    score = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the instance is created
    updated_at = models.DateTimeField(auto_now=True)      # Timestamp for when the instance is updated

    def __str__(self):
        return f"History for ABN {self.abn} on {self.date}"


class CreditRatingHistory(models.Model):
    credit_score = models.ForeignKey(CreditScore, on_delete=models.CASCADE, related_name='rating_history', null=True)
    date = models.DateField(null=True)
    rating = models.CharField(max_length=10, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the instance is created
    updated_at = models.DateTimeField(auto_now=True)      # Timestamp for when the instance is updated

    def __str__(self):
        return f"Rating history for {self.credit_score} on {self.date}"

class PaymentPredictor(models.Model):
    credit_score = models.ForeignKey(CreditScore, on_delete=models.CASCADE, related_name='payment_predictor', null=True)
    expect_payment_range = models.CharField(max_length=50, null=True)
    predicted_days = models.CharField(max_length=10, null=True)
    average_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    average_overdue = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    highest_credit_exposure_single_supplier = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    highest_credit_exposure_combined_suppliers = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    highest_overdue_credit_exposure = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    number_of_trade_lines = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the instance is created
    updated_at = models.DateTimeField(auto_now=True)      # Timestamp for when the instance is updated

    def __str__(self):
        return f"Payment Predictor for {self.credit_score}"

class PaymentPredictorHistory(models.Model):
    payment_predictor = models.ForeignKey(PaymentPredictor, on_delete=models.CASCADE, related_name='history', null=True)
    time_series = models.CharField(max_length=10, null=True)
    overdue_days = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the instance is created
    updated_at = models.DateTimeField(auto_now=True)      # Timestamp for when the instance is updated

    def __str__(self):
        return f"Payment Predictor history for {self.payment_predictor} on {self.time_series}"

class CreditReport(models.Model):
    description = models.CharField(max_length=255)
    item_code = models.CharField(max_length=100)
    abn = models.CharField(max_length=20)
    acn = models.CharField(max_length=20)
    credit_enquiries = models.IntegerField()
    report = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the instance is created
    updated_at = models.DateTimeField(auto_now=True)      # Timestamp for when the instance is updated

    def __str__(self):
        return f"Credit Report for ABN: {self.abn}, ACN: {self.acn}"




class CompanySearch(models.Model):
    page = models.IntegerField(null=True, blank=True)
    results_per_page = models.IntegerField(null=True, blank=True)
    count = models.IntegerField(null=True, blank=True)
    number_of_pages = models.IntegerField(null=True, blank=True)
    results = models.JSONField(null=True, blank=True)  # Updated to use django.db.models.JSONField

    def __str__(self):
        return f"Company Search - Page {self.page} of {self.number_of_pages}"



class DataBlock(models.Model):
    snapshot_date = models.DateField(null=True, blank=True)
    segment = models.CharField(max_length=50, null=True, blank=True)
    riskscore = models.CharField(max_length=10, null=True, blank=True)
    alpha_rating = models.CharField(max_length=10, null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    pd = models.FloatField(null=True, blank=True)
    default_type = models.CharField(max_length=50, null=True, blank=True)
    georisk_index = models.FloatField(null=True, blank=True)
    georisk_rating = models.CharField(max_length=10, null=True, blank=True)
    text_category_broad = models.CharField(max_length=50, null=True, blank=True)
    payment_rating = models.CharField(max_length=50, null=True, blank=True)
    val_wtd_dpd_l12m = models.FloatField(null=True, blank=True)
    maximum_arrears_rating = models.CharField(max_length=10, null=True, blank=True)
    num_suppliers = models.IntegerField(null=True, blank=True)
    num_active_tradelines_invoices_l12m = models.IntegerField(null=True, blank=True)
    trade_activity_rating = models.CharField(max_length=10, null=True, blank=True)
    val_cw_defaults_l24m = models.FloatField(null=True, blank=True)
    val_cw_defaults_l24m_group = models.CharField(max_length=50, null=True, blank=True)
    pct_val_invc_on_time = models.FloatField(null=True, blank=True)
    pct_val_invc_on_time_group = models.CharField(max_length=50, null=True, blank=True)
    num_watched_l12m = models.IntegerField(null=True, blank=True)
    num_watched_l12m_group = models.CharField(max_length=50, null=True, blank=True)
    num_merc_enq_cw_l24m = models.IntegerField(null=True, blank=True)
    flg_merc_enq_cw_l24m = models.CharField(max_length=1, null=True, blank=True)
    cat_large = models.CharField(max_length=1, null=True, blank=True)
    flg_large = models.CharField(max_length=1, null=True, blank=True)
    flg_ato = models.CharField(max_length=1, null=True, blank=True)
    flg_asx_override = models.CharField(max_length=1, null=True, blank=True)
    flg_adverse_director = models.CharField(max_length=1, null=True, blank=True)
    num_adverse = models.IntegerField(null=True, blank=True)
    num_director = models.IntegerField(null=True, blank=True)
    num_director_group = models.CharField(max_length=50, null=True, blank=True)
    diff_num_director_l12m = models.CharField(max_length=10, null=True, blank=True)
    diff_num_director_l12m_group = models.CharField(max_length=50, null=True, blank=True)
    val_court_judgement_l24m = models.FloatField(null=True, blank=True)
    val_court_judgement_l24m_group = models.CharField(max_length=50, null=True, blank=True)
    flg_asic_pub_notice_l12m = models.CharField(max_length=1, null=True, blank=True)
    days_registered = models.IntegerField(null=True, blank=True)
    years_registered_group = models.CharField(max_length=50, null=True, blank=True)
    days_current_address = models.IntegerField(null=True, blank=True)
    years_current_address_group = models.CharField(max_length=50, null=True, blank=True)
    num_physical_address_l36m = models.IntegerField(null=True, blank=True)
    num_physical_address_l36m_group = models.CharField(max_length=50, null=True, blank=True)
    gst_current_flag = models.CharField(max_length=1, null=True, blank=True)
    def365 = models.IntegerField(null=True, blank=True)
    abn = models.CharField(max_length=20, null=True, blank=True)
    acn = models.CharField(max_length=20, null=True, blank=True)
    corporate_name = models.CharField(max_length=255, null=True, blank=True)
    flg_active = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"DataBlock - ABN: {self.abn}, Score: {self.score}"



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

