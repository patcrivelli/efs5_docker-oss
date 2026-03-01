# efs_notifications/views.py
from django.shortcuts import render

def home(request):
    return render(request, "notifications.html")

def notifications_home(request):
    return render(request, "notifications_home.html")
