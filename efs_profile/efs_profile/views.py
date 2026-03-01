# efs_profile/efs_profile/views.py
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import Originator  # assuming you have an Originator model


# efs_profile/efs_profile/views.py
@require_http_methods(["POST"])
def create_originator(request):
    originator = request.POST.get("originator")  # match input name in base.html
    if originator:
        Originator.objects.create(
            originator=originator,
            created_by=request.user.username if request.user.is_authenticated else "anonymous"
        )
    return redirect(request.META.get("HTTP_REFERER", "sales_home"))

# Optional: an API endpoint (if you need JSON response for async calls)
@require_http_methods(["GET"])
def list_originators(request):
    """
    Return all originators as JSON (to feed side panel, etc.)
    """
    data = list(Originator.objects.values("id", "originator"))
    return JsonResponse({"originators": data})
