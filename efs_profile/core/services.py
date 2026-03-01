from django.conf import settings
from .models import Originator
from .serializers import OriginatorSerializer

def check_internal_api_key(request) -> bool:
    """
    Accepts 'X-API-Key' header. Compare with settings.INTERNAL_API_KEY.
    """
    expected = getattr(settings, "INTERNAL_API_KEY", None)
    supplied = request.headers.get("X-API-Key")
    return bool(expected) and supplied == expected

def create_originator_service(payload: dict) -> dict:
    """
    Business logic wrapper. Validates and creates an Originator.
    Input keys expected: 'originator', optional 'created_by'.
    """
    data = {
        "originator": (payload.get("originator") or "").strip(),
        "created_by": (payload.get("created_by") or "").strip() or "anonymous",
    }
    ser = OriginatorSerializer(data=data)
    if not ser.is_valid():
        return {"ok": False, "errors": ser.errors}

    instance = ser.save()
    return {"ok": True, "data": OriginatorSerializer(instance).data}
