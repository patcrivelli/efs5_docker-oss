# efs_profile/core/views.py
import logging
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt

from .models import Originator
from .serializers import OriginatorSerializer
from .services import create_originator_service, check_internal_api_key

logger = logging.getLogger(__name__)

# ---- UI page ----
def profile_home(request):
    """Landing page for profiles."""
    originators = Originator.objects.all().order_by("originator")
    selected_originator = None
    selected_id = request.GET.get("originators")
    if selected_id:
        selected_originator = Originator.objects.filter(id=selected_id).first()

    ctx = {
        "originators": originators,
        "selected_originator": selected_originator,
    }
    return render(request, "profile.html", ctx)


from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods
from .models import Originator

@csrf_exempt
@require_http_methods(["POST"])
def create_originator(request):
    originator = request.POST.get("originator_name")
    if originator:
        Originator.objects.create(
            originator=originator,
            created_by=request.user.username if request.user.is_authenticated else "anonymous"
        )
    return redirect("profile_page")



class OriginatorList(APIView):
    """
    GET /api/originators/  ->  { "originators": [...] }
    (Open for reads so your sales UI can populate its dropdown without a key.)
    """
    def get(self, request, *args, **kwargs):
        qs = Originator.objects.all().order_by("originator")
        data = OriginatorSerializer(qs, many=True).data
        return Response({"originators": data}, status=status.HTTP_200_OK)

class OriginatorCreate(APIView):
    """
    POST /api/originators/create/
    Body JSON: { "originator": "...", "created_by": "..." }
    Requires X-API-Key.
    """
    def post(self, request, *args, **kwargs):
        if not check_internal_api_key(request):
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        result = create_originator_service(request.data)
        if result["ok"]:
            return Response(result["data"], status=status.HTTP_201_CREATED)
        return Response(result["errors"], status=status.HTTP_400_BAD_REQUEST)
