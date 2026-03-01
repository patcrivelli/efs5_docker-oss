from django.shortcuts import render

def home(request):
    return render(request, "home.html")  # or whatever you use as the landing page

def operations_page(request):
    return render(request, "operations.html")