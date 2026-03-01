from rest_framework import serializers
from .models import InvoiceData, LedgerData, FinancialData, Registration

class InvoiceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceData
        fields = "__all__"

class LedgerDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerData
        fields = "__all__"


class FinancialDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialData
        fields = '__all__'

class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = '__all__'