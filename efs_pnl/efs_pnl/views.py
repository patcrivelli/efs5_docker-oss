from django.shortcuts import render

def home(request):
    # Landing page (default /)
    return render(request, "pnl.html")

def pnl_home(request):
    # Optional secondary landing page (/pnl/home/)
    return render(request, "pnl_home.html")
