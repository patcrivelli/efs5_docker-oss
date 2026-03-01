import logging
from .models import ApplicationData   # import your model
from .serializers import ApplicationDataSerializer

logger = logging.getLogger(__name__)

class InvoiceFinanceApplicationService:
    """Business logic for handling Invoice Finance application data."""

    @staticmethod
    def process_application_data(data: dict) -> dict:
        try:
            serializer = ApplicationDataSerializer(data=data)
            if serializer.is_valid():
                instance = ApplicationData.objects.create(**serializer.validated_data)
                logger.info(f"✅ Saved ApplicationData with transaction {instance.transaction_id}")
                return {"status": "success", "transaction_id": instance.transaction_id}
            else:
                logger.warning(f"❌ Validation failed: {serializer.errors}")
                return {"status": "error", "message": serializer.errors}
        except Exception as e:
            logger.error(f"❌ Failed to process application data: {e}")
            return {"status": "error", "message": str(e)}


import logging
from .models import TfApplicationData
from .serializers import TfApplicationDataSerializer

logger = logging.getLogger(__name__)

class TradeFinanceApplicationService:
    """Business logic for handling Trade Finance application data."""

    @staticmethod
    def process_application_data(data: dict) -> dict:
        try:
            serializer = TfApplicationDataSerializer(data=data)
            if serializer.is_valid():
                instance = TfApplicationData.objects.create(**serializer.validated_data)
                logger.info("✅ Saved TfApplicationData with transaction %s", instance.transaction_id)
                return {"status": "success", "transaction_id": instance.transaction_id}
            else:
                logger.warning("❌ TF validation failed: %s", serializer.errors)
                return {"status": "error", "message": serializer.errors}
        except Exception as e:
            logger.exception("❌ Failed to process TF application data")
            return {"status": "error", "message": str(e)}


# application_aggregate/aggregate/services.py
import logging
from .models import ScfApplicationData
from .serializers import ScfApplicationDataSerializer

logger = logging.getLogger(__name__)

class ScfApplicationService:
    """Business logic for handling SCF (Early Payments) application data."""

    @staticmethod
    def process_application_data(data: dict) -> dict:
        try:
            serializer = ScfApplicationDataSerializer(data=data)
            if serializer.is_valid():
                instance = ScfApplicationData.objects.create(**serializer.validated_data)
                logger.info("✅ Saved ScfApplicationData with transaction %s", instance.transaction_id)
                return {"status": "success", "transaction_id": instance.transaction_id}
            else:
                logger.warning("❌ SCF validation failed: %s", serializer.errors)
                return {"status": "error", "message": serializer.errors}
        except Exception as e:
            logger.exception("❌ Failed to process SCF application data")
            return {"status": "error", "message": str(e)}


