# efs_risk/core/serializers.py
from rest_framework import serializers

class IngestApplicationSerializer(serializers.Serializer):
    transaction_id = serializers.CharField()
    product = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    application_time = serializers.DateTimeField(required=False, allow_null=True)
    contact_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    abn = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    acn = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bankstatements_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bureau_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    accounting_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ppsr_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    contact_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    originator = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    state = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    amount_requested = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    insurance_premiums = serializers.JSONField(required=False, allow_null=True)

    def validate_product(self, value):
        if not value:
            return "invoice finance"
        v = value.strip().lower()
        if v in {"ipf", "insurance premium funding"}:
            return "insurance premium funding"
        if v in {"scf", "supply chain finance"}:
            return "supply chain finance"
        if v in {"trade finance"}:
            return "trade finance"
        if v in {"invoice finance"}:
            return "invoice finance"
        # default to invoice finance to avoid dropping payloads
        return "invoice finance"


from rest_framework import serializers

class ApproveTransactionSerializer(serializers.Serializer):
    transaction_id = serializers.CharField()
    decision = serializers.ChoiceField(choices=["approve", "reject"])


