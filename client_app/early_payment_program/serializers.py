from rest_framework import serializers
from .models import scf_ApplicationData, scf_InvoiceData



 
class SCFApplicationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = scf_ApplicationData
        fields = '__all__'

class SCFInvoiceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = scf_InvoiceData
        fields = '__all__'
