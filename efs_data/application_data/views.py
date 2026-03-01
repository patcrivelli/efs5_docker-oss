# application_data/views.py
import logging
import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView
from .models import ApplicationData
from .services import InvoiceFinanceApplicationService

logger = logging.getLogger(__name__)

# -------------------------
# 📋 Class-based List View
# -------------------------
class ApplicationListView(ListView):
    model = ApplicationData
    template_name = "application_data/application_list.html"
    context_object_name = "applications"


# -------------------------
# 📩 API Receiver Endpoint
# -------------------------
from django.db import IntegrityError

@csrf_exempt
def receive_application_data(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            transaction_id = data.get("transaction_id")

            obj, created = ApplicationData.objects.update_or_create(
                transaction_id=transaction_id,
                defaults=data
            )

            return JsonResponse(
                {"status": "success", "created": created, "transaction_id": str(obj.transaction_id)},
                status=201 if created else 200
            )
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
