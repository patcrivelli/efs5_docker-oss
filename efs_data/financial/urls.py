# financial/urls.py
from django.urls import path
from . import views

app_name = "financial"

urlpatterns = [
    path("proxy/", views.proxy_view, name="financial_proxy"),
    path("receive-invoice-data/", views.receive_invoice_data, name="receive_invoice_data"),
    path("receive-ledger-data/", views.receive_ledger_data, name="receive_ledger_data"),
    path("store_ppsr_data/", views.store_ppsr_data, name="store_ppsr_data"),  # aligned
    path("store-accounting-data/", views.store_accounting_data, name="store_accounting_data"),
    path("", views.financial_page, name="financial_page"),  # <-- add this
    path("summary", views.get_financials_summary, name="financials_summary"),
    path("api/ppsr/registrations", views.get_ppsr_registrations, name="get_ppsr_registrations"),
    path("invoices/", views.invoices_by_transaction, name="invoices_by_transaction"),


]
