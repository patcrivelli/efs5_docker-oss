# efs_apis/core/serializers.py
import re
from rest_framework import serializers

# keep this here to avoid circular imports
def _normalize_bearer_token(raw: str) -> str:
    if not raw:
        return ""
    t = raw.strip()
    if t.lower().startswith("bearer "):
        t = t[7:].lstrip()
    t = (
        t.replace("\u2014", "-")   # em dash —
         .replace("\u2013", "-")   # en dash –
         .replace("\u2212", "-")   # minus sign −
    )
    t = t.strip('\'"')
    t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)   # zero-width
    t = re.sub(r"[^\x20-\x7E]", "", t)            # ASCII visible only
    return t

class FetchBureauRequestSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    abn            = serializers.CharField(required=False, allow_blank=True)
    acn            = serializers.CharField(required=False, allow_blank=True)
    bureau_token   = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    product        = serializers.CharField(required=False, allow_blank=True)
    originator     = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        tx    = (attrs.get("transaction_id") or "").strip()
        abn   = (attrs.get("abn") or "").strip()
        token = (attrs.get("bureau_token") or "").strip()

        # must have either (abn & token) or tx (for fallback lookup)
        if not ((abn and token) or tx):
            raise serializers.ValidationError(
                "Provide either (abn and bureau_token) or transaction_id."
            )

        if abn:
            digits = re.sub(r"\D", "", abn)
            if len(digits) != 11:
                raise serializers.ValidationError("ABN must be 11 digits.")
            attrs["abn"] = digits

        if token:
            attrs["bureau_token"] = _normalize_bearer_token(token)

        return attrs


# efs_apis/core/serializers.py
from rest_framework import serializers
import re

def _normalize_bearer_token(raw: str) -> str:
    # (reuse your existing version)
    if not raw:
        return ""
    t = raw.strip()
    if t.lower().startswith("bearer "):
        t = t[7:].lstrip()
    t = (t.replace("\u2014","-").replace("\u2013","-").replace("\u2212","-"))
    t = t.strip('\'"')
    t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)
    t = re.sub(r"[^\x20-\x7E]", "", t)
    return t

class FetchAccountingRequestSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    abn            = serializers.CharField(required=False, allow_blank=True)
    acn            = serializers.CharField(required=False, allow_blank=True)
    bureau_token   = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
    product        = serializers.CharField(required=False, allow_blank=True)
    originator     = serializers.CharField(required=False, allow_blank=True)
    year           = serializers.IntegerField(required=False)

    def validate(self, attrs):
        tx    = (attrs.get("transaction_id") or "").strip()
        abn   = (attrs.get("abn") or "").strip()
        token = (attrs.get("bureau_token") or "").strip()

        if not ((abn and token) or tx):
            raise serializers.ValidationError("Provide either (abn and bureau_token) or transaction_id.")

        if abn:
            digits = re.sub(r"\D", "", abn)
            if len(digits) != 11:
                raise serializers.ValidationError("ABN must be 11 digits.")
            attrs["abn"] = digits

        if token:
            attrs["bureau_token"] = _normalize_bearer_token(token)
        return attrs
