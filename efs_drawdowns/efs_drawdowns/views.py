# efs_drawdowns/views.py
from django.shortcuts import render

def home(request):
    return render(request, "drawdowns.html")

def drawdowns_home(request):
    return render(request, "drawdowns_home.html")
