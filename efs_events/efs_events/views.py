from django.shortcuts import render
  # Optionally add efs_shared_ui to INSTALLED_APPS (after staticfiles)

def home(request):
    return render(request, "home.html")
