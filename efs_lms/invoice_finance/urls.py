from django.urls import path
from . import views

app_name = "invoice_finance"   # ✅ this matches {% url 'invoice_finance:invoice_finance_page' %}

urlpatterns = [
    path("", views.invoice_finance_page, name="invoice_finance_page"),
    path("api/ingest_transaction/", views.ingest_transaction, name="ingest_transaction"),
    path("fetch-invoice-data/<str:trans_id>/", views.fetch_invoice_data, name="fetch_invoice_data"),

]
