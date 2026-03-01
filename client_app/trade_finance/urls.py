# trade_finance/urls.py
from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = "trade_finance"

urlpatterns = [
    # Landing page
    path("", TemplateView.as_view(template_name="trade_finance.html"), name="index"),

    # Existing APIs
    path("api/upload-ap-ledger/", views.upload_ap_ledger, name="upload_ap_ledger"),
    path("api/fetch-accounts-payable-ledger/", views.fetch_accounts_payable_ledger, name="fetch_accounts_payable_ledger"),

    path("api/apply/", views.TF_application_store, name="tf_application_store"),
    path("api/invoices/", views.tf_get_invoices, name="tf_get_invoices"),
    path("api/invoice/store/", views.TF_invoice_store, name="tf_invoice_store"),
    path("api/transaction/latest/", views.tf_get_latest_transaction_id, name="tf_get_latest_txid"),

    # ✅ Forward to other services (NEW functions)
    path("api/send/application/", views.send_tf_application_data, name="send_tf_application_data"),
    path("api/send/invoices/", views.send_tf_invoice_data, name="send_tf_invoice_data"),
]
