from django.shortcuts import render
def index(request):
    return render(request, "term_loan/index.html")
