from rest_framework import serializers
from .models import Originator

class OriginatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Originator
        fields = ["id", "originator", "created_by", "date_created"]

    def validate_originator(self, value):
        v = (value or "").strip()
        if not v:
            raise serializers.ValidationError("originator is required.")
        return v
