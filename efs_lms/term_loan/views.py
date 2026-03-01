from django.shortcuts import render

def term_loan_page(request):
    return render(request, "term_loan.html")
