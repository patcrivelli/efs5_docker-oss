from django.shortcuts import render
def index(request):
    return render(request, "insurance_premium_funding/index.html")



from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import IPF_ApplicationData
import uuid
from datetime import datetime

@api_view(['POST'])
def ipf_application_store(request):
    try:
        data = request.data

        ipf_app = IPF_ApplicationData.objects.create(
            transaction_id=uuid.uuid4(),
            application_time=datetime.now(),
            contact_name=data.get('contact_name'),
            abn=data.get('abn'),
            acn=data.get('abn')[2:] if data.get('abn') else None,  # derive ACN from ABN
            amount_requested=data.get('amount_requested'),
            product="Insurance Premium Funding",
            insurance_premiums=data.get('insurance_premiums'),

            # ✅ Insert tokens
            bureau_token=data.get('bureau_token'),
            accounting_token=data.get('accounting_token'),
            bankstatements_token=data.get('bankstatements_token'),
            ppsr_token=data.get('ppsr_token'),
            originator="Shift",  # ✅ Add this line

        )

        return Response({"success": True, "transaction_id": str(ipf_app.transaction_id)}, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# views.py (in IPF app)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import IPF_ApplicationData
from .serializers import IPFApplicationSerializer  # Make sure this exists

@api_view(['GET'])
def latest_ipf_application(request):
    latest = IPF_ApplicationData.objects.order_by('-application_time').first()
    if not latest:
        return Response({"error": "No applications found"}, status=404)

    serializer = IPFApplicationSerializer(latest)
    return Response(serializer.data, status=200)



import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import IPF_ApplicationData

# ✅ Define local and cloud API bases
LOCAL_API_BASE = "http://127.0.0.1:8000/efs_sales/api"
CLOUD_API_BASE = "https://efs3-docker-320779576692.australia-southeast1.run.app/efs_sales/api"

# ✅ Shared function to post to local and cloud
def post_to_all_targets(endpoint, payload):
    responses = []
    for base in [LOCAL_API_BASE, CLOUD_API_BASE]:
        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
            responses.append((url, response.status_code, response.text))
            print(f"📢 Posted to {url} → {response.status_code}")
        except Exception as e:
            responses.append((url, 500, str(e)))
            print(f"❌ Error posting to {url}: {e}")
    return responses

def send_ipf_application_data_to_efs2_docker(request):
    try:
        if request.method != "POST":
            return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

        latest = IPF_ApplicationData.objects.order_by('-application_time').first()
        if not latest:
            return JsonResponse({"success": False, "error": "No IPF applications found"}, status=404)

        payload = {
            "transaction_id": str(latest.transaction_id),
            "abn": latest.abn,
            "acn": latest.acn,
            "contact_name": latest.contact_name,
            "amount_requested": str(latest.amount_requested),
            "application_time": latest.application_time.isoformat() if latest.application_time else None,
            "bureau_token": latest.bureau_token,
            "bankstatements_token": latest.bankstatements_token,
            "accounting_token": latest.accounting_token,
            "ppsr_token": latest.ppsr_token,
            "originator": latest.originator,
            "product": latest.product,
            "insurance_premiums": latest.insurance_premiums,
        }

        print("📢 DEBUG: IPF Application Payload", json.dumps(payload, indent=2))
        responses = post_to_all_targets("receive-ipf-application/", payload)

        return JsonResponse({
            "success": True,
            "message": "IPF application data sent to both local and cloud",
            "responses": responses
        })

    except Exception as e:
        print(f"❌ Error sending IPF application data: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
