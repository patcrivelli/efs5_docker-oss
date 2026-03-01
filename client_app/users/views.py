# users/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

User = get_user_model()

@require_POST
@csrf_exempt  # ⚠️ only for testing; better to rely on your JS sending CSRF
def ajax_signup(request):
    email = request.POST.get("email")
    username = request.POST.get("username")
    password1 = request.POST.get("password1")
    password2 = request.POST.get("password2")

    # basic validation
    if not email or not username or not password1 or not password2:
        return JsonResponse({"error": "All fields are required."}, status=400)

    if password1 != password2:
        return JsonResponse({"error": "Passwords do not match."}, status=400)

    # create user
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
        )
        return JsonResponse({"success": True, "message": "Account created!"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

@require_POST
@csrf_exempt  # keep only for testing
def ajax_login(request):
    username = request.POST.get("username")
    password = request.POST.get("password")

    if not username or not password:
        return JsonResponse({"error": "Both fields required."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)  # ✅ attaches user to session
        return JsonResponse({"success": True, "username": user.username})
    else:
        return JsonResponse({"error": "Invalid username or password."}, status=401)
