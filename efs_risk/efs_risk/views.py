# efs_risk/views.py
from django.shortcuts import render

def home(request):
    return render(request, "risk.html")

def risk_home(request):
    return render(request, "risk_home.html")
