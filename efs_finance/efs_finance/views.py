# efs_finance/views.py
from django.shortcuts import render

def home(request):
    return render(request, "finance.html")

def finance_home(request):
    return render(request, "finance_home.html")
