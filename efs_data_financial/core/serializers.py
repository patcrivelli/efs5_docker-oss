from rest_framework import serializers
from .models import InvoiceData, LedgerData, tf_InvoiceData, scf_InvoiceData

class InvoiceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceData
        fields = "__all__"

class LedgerDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerData
        fields = "__all__"






class TFInvoiceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = tf_InvoiceData
        fields = '__all__'
      




class SCFInvoiceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = scf_InvoiceData
        fields = '__all__'







from rest_framework import serializers
import re

def _norm_abn(v: str) -> str:
    digits = re.sub(r"\D", "", v or "")
    return digits

class FinancialRecordSerializer(serializers.Serializer):
    abn           = serializers.CharField(required=True, allow_blank=False, max_length=32)
    acn           = serializers.CharField(required=False, allow_blank=True, max_length=32)
    company_name  = serializers.CharField(required=False, allow_blank=True, max_length=255)
    year          = serializers.IntegerField(required=False, allow_null=True)
    financials    = serializers.JSONField(required=False, allow_null=True)
    profit_loss   = serializers.JSONField(required=False, allow_null=True)
    balance_sheet = serializers.JSONField(required=False, allow_null=True)
    subsidiaries  = serializers.ListField(child=serializers.DictField(), required=False, allow_empty=True)
    raw           = serializers.JSONField(required=False, allow_null=True)

    def validate_abn(self, v):
        vv = _norm_abn(v)
        if len(vv) != 11:
            raise serializers.ValidationError("ABN must contain 11 digits.")
        return vv

    def validate_year(self, v):
        if v is None:
            return v
        if not (1900 <= int(v) <= 2100):
            raise serializers.ValidationError("Year must be in a reasonable range.")
        return int(v)

class FinancialStoreSerializer(serializers.Serializer):
    record  = FinancialRecordSerializer(required=False)
    records = FinancialRecordSerializer(many=True, required=False)

    def validate(self, attrs):
        rec  = attrs.get("record")
        recs = attrs.get("records")
        if not rec and not recs:
            raise serializers.ValidationError("Provide either 'record' or 'records'.")
        # normalize to a list for the view/service
        attrs["as_list"] = recs if recs else [rec]
        return attrs


from rest_framework import serializers
from .models import Registration


class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = '__all__'





        