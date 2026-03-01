# efs_finance/core/serializers.py
from rest_framework import serializers
from decimal import Decimal, InvalidOperation
from datetime import datetime

class IngestFromRiskSerializer(serializers.Serializer):
    transaction_id = serializers.CharField()

    application_time = serializers.DateTimeField(required=False, allow_null=True)
    contact_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    abn = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    acn = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    bankstatements_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    bureau_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    accounting_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ppsr_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    contact_email = serializers.EmailField(required=False, allow_null=True)
    contact_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    originator = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    state = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    amount_requested = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True
    )

    product = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    insurance_premiums = serializers.JSONField(required=False, allow_null=True)

    # ---------------------------
    # Custom validators
    # ---------------------------
    def validate_product(self, v):
        if not v:
            return None
        v = v.strip().lower()
        if v in {"invoice finance"}:
            return "invoice finance"
        if v in {"trade finance"}:
            return "trade finance"
        if v in {"supply chain finance", "scf"}:
            return "supply chain finance"
        if v in {"ipf", "insurance premium funding"}:
            return "insurance premium funding"
        return v

    def validate_amount_requested(self, v):
        if v in (None, "", "null"):
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            raise serializers.ValidationError("amount_requested must be decimal-like")

    def validate_application_time(self, v):
        if not v:
            return None
        # accept ISO8601 strings from risk (e.g. 2025-09-05T02:15:21Z)
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return v  # fallback to raw string if parsing fails
