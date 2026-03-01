# efs_sales/core/serializers.py
from rest_framework import serializers

class ApproveApplicationRequestSerializer(serializers.Serializer):
    transaction_id = serializers.CharField()
    new_state = serializers.CharField()
    product = serializers.CharField()

    def validate_product(self, value):
        v = (value or "").strip().lower()
        if v in {"ipf", "insurance premium funding"}:
            return "insurance premium funding"
        if v in {"scf", "supply chain finance"}:
            return "supply chain finance"
        if v in {"invoice finance"}:
            return "invoice finance"
        if v in {"trade finance"}:
            return "trade finance"
        raise serializers.ValidationError("Unknown product")
