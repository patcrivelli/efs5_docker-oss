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
        db_table = "efs_application_data_applicationdata"

class tf_ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "efs_application_data_tf_applicationdata"

class scf_ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "efs_application_data_scf_applicationdata"

class IPF_ApplicationData(BaseApplicationData):
    class Meta:
        db_table = "efs_application_data_ipf_applicationdata"
