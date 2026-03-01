from django.http import JsonResponse
from django.shortcuts import render

def ping(request):
    return JsonResponse({"status": "ok", "app": "aggregate"})

def aggregate_page(request):
    return render(request, "aggregate.html")