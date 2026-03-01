# core/urls.py
from django.urls import path
from . import views

app_name = "efs_lms"   # 👈 REQUIRED for {% url 'efs_lms:...' %}

urlpatterns = [
    path("", views.lms_page, name="lms_page"),
    path("create-originator/", views.create_originator, name="create_originator"),
    path("invoice-finance/", views.invoice_finance_page, name="invoice_finance_page"),
    path("scf/", views.scf_page, name="scf_page"),
    path("trade-finance/", views.trade_finance_page, name="trade_finance_page"),
    path("term-loan/", views.term_loan_page, name="term_loan_page"),
    path("overdraft/", views.overdraft_page, name="overdraft_page"),
    path("asset-finance/", views.asset_finance_page, name="asset_finance_page"),
]
