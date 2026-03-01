from django.shortcuts import render

def overdraft_page(request):
    return render(request, "overdraft.html")
