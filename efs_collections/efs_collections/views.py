# efs_collections/views.py
from django.shortcuts import render

def home(request):
    return render(request, "collections.html")

def collections_home(request):
    return render(request, "collections_home.html")
