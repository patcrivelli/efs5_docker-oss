# application_data/services.py
import logging
from .serializers import ApplicationDataSerializer

logger = logging.getLogger(__name__)

class InvoiceFinanceApplicationService:
    @staticmethod
    def process_application_data(data):
        """
        Store Invoice Finance ApplicationData into the DB.
        This service is dedicated to handling Invoice Finance applications.
        """
        serializer = ApplicationDataSerializer(data=data)
        if serializer.is_valid():
            instance = serializer.save()
            logger.info(
                f"✅ Invoice Finance ApplicationData saved "
                f"(ABN: {data.get('abn')}, Transaction ID: {getattr(instance, 'transaction_id', None)})"
            )
            return {
                'status': 'success',
                'message': 'ApplicationData saved successfully',
                'transaction_id': str(getattr(instance, 'transaction_id', None)),
            }
        else:
            logger.error(f"❌ Validation failed: {serializer.errors}")
            return {
                'status': 'error',
                'message': 'ApplicationData validation failed',
                'errors': serializer.errors,
            }
