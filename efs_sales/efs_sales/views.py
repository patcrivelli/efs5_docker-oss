from django.shortcuts import render

def home(request):
    return render(request, "sales.html")

def sales_home(request):
    return render(request, "sales_home.html")