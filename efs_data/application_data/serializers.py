# application_data/serializers.py
from rest_framework import serializers
from .models import ApplicationData

class ApplicationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationData
        fields = "__all__"
