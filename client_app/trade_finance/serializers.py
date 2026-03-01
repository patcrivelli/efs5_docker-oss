from rest_framework import serializers
from .models import TF_ApplicationData, TF_InvoiceData



class TFApplicationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TF_ApplicationData
        fields = '__all__'


class TFInvoiceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TF_InvoiceData
        fields = '__all__'
 