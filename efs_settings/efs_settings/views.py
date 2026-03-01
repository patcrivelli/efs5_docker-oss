# efs_settings/views.py
from django.shortcuts import render

def home(request):
    return render(request, "settings.html")

def settings_home(request):
    return render(request, "settings_home.html")
