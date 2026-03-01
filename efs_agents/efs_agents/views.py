from django.shortcuts import render

def home(request):
    # default landing page (when you hit service root)
    return render(request, "agents.html")

def agents_home(request):
    # secondary landing page
    return render(request, "agents_home.html")
