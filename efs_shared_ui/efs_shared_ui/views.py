


import os
import requests
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages

def create_originator(request):
    if request.method != "POST":
        messages.error(request, "Invalid request.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # match your form field names
    username = request.POST.get("username") or (
        request.user.username if request.user.is_authenticated else "anonymous"
    )
    originator = request.POST.get("originator_name")

    if not originator:
        messages.error(request, "Please enter an originator name.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    # Where the profile API lives (fallback for dev)
    base = getattr(settings, "EFS_PROFILE_BASE_URL", None) or "http://localhost:8002"
    api_url = f"{base.rstrip('/')}/api/originators/"

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("INTERNAL_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    try:
        resp = requests.post(
            api_url,
            json={"originator": originator, "created_by": username},
            headers=headers,
            timeout=8,
        )
    except requests.RequestException as e:
        messages.error(request, f"Profile service unavailable: {e}")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if resp.status_code in (200, 201):
        messages.success(request, f"Originator “{originator}” created.")
    else:
        # show whatever the API returned
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        messages.error(request, f"Failed to create originator: {detail}")

    return redirect(request.META.get("HTTP_REFERER", "/"))



