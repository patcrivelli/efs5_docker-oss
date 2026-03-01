from rest_framework import serializers
from .models import ApplicationData, InvoiceData, LedgerData


class ApplicationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationData
        fields = "__all__"
        read_only_fields = ["transaction_id"]


class InvoiceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceData
        fields = "__all__"
        read_only_fields = ["transaction_id"]


class LedgerDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerData
        fields = "__all__"
