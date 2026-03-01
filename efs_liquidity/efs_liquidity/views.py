from django.shortcuts import render

def home(request):
    return render(request, "liquidity.html")

def liquidity_home(request):
    return render(request, "liquidity_home.html")
