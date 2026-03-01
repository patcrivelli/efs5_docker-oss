from django.shortcuts import render
def index(request):
    return render(request, "asset_finance/index.html")
