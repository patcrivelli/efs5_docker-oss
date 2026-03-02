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
