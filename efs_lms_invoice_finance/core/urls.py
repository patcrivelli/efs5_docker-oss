from django.urls import path
from . import views

app_name = "invoice_finance"

urlpatterns = [
    # Base page
    path("", views.invoice_finance_page, name="invoice_finance_page"),

    # Ingestion endpoint (finance → LMS)
    path("api/ingest_transaction/", views.ingest_transaction, name="ingest_transaction"),

    # JSON endpoints used by the page JS
    path("fetch-invoice-data/<str:transaction_id>/", views.fetch_invoice_data, name="fetch_invoice_data"),
    path("fetch-invoice-repayments/<str:transaction_id>/", views.fetch_invoice_repayments, name="fetch_invoice_repayments"),
    path("allocate_payment/", views.allocate_payment, name="allocate_payment"),
    path("close-invoice-transaction/<str:trans_id>/", views.close_transaction, name="close_invoice_transaction"),
    path("allocate_drawdown/", views.allocate_drawdown_view, name="allocate_drawdown"),

    # Optional — keeps Upload button harmless
    path("handle_file_upload/", views.handle_file_upload, name="handle_file_upload"),

#drawdown endpoint urls 
    path("pay_drawdown/", views.pay_drawdown, name="pay_drawdown"),


#upload new invoices

    path("upload_invoices_csv/", views.upload_invoices_csv, name="upload_invoices_csv"),

#new drawdowns 
    path("create_drawdown_request/", views.create_drawdown_request, name="create_drawdown_request"),




]
