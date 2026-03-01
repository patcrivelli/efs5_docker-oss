from rest_framework import serializers
from .models import ApplicationData

class ApplicationDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationData
        fields = "__all__"



from rest_framework import serializers
from .models import ApplicationData, TfApplicationData, ScfApplicationData, IpfApplicationData


class _BaseAppSerializer(serializers.ModelSerializer):
    app_type = serializers.CharField(read_only=True)

    class Meta:
        fields = [
            "app_type",
            "transaction_id",
            "application_time",
            "company_name",
            "abn",
            "acn",
            "originator",
            "state",
            "amount_requested",
            "product",
        ]


class ApplicationDataSerializer(_BaseAppSerializer):
    class Meta(_BaseAppSerializer.Meta):
        model = ApplicationData


class TfApplicationDataSerializer(_BaseAppSerializer):
    class Meta(_BaseAppSerializer.Meta):
        model = TfApplicationData


class ScfApplicationDataSerializer(_BaseAppSerializer):
    class Meta(_BaseAppSerializer.Meta):
        model = ScfApplicationData


class IpfApplicationDataSerializer(_BaseAppSerializer):
    class Meta(_BaseAppSerializer.Meta):
        model = IpfApplicationData





#---------#---------#---------#---------#---------
        

#--------- Save Deal conditions 
        

#---------#---------#---------#---------
        

from rest_framework import serializers
from .models import DealCondition

class DealConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DealCondition
        fields = [
            "id",
            "originator",
            "company_name",
            "product",
            "condition_type",
            "title",
            "description",
            "created_by",
            "assigned_to",
            "date_created",
            "transaction_id",
            "is_completed",
        ]
