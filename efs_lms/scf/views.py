from django.shortcuts import render

def scf_page(request):
    return render(request, "scf.html")