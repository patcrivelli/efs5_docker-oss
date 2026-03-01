from rest_framework import serializers
from .models import (

    CreditRatingHistory,
    PaymentPredictor,
    PaymentPredictorHistory,
    CreditReport,
    CompanySearch,
    DataBlock,
    CreditScore,
    CreditScoreHistory,
)


class CreditRatingHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditRatingHistory
        fields = "__all__"


class PaymentPredictorSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentPredictor
        fields = "__all__"


class PaymentPredictorHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentPredictorHistory
        fields = "__all__"


class CreditReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditReport
        fields = "__all__"


class CompanySearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySearch
        fields = "__all__"


class DataBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataBlock
        fields = "__all__"





class CreditScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditScore
        fields = "__all__"


class CreditScoreHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditScoreHistory
        fields = "__all__"






