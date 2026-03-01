# invoice_finance/urls.py
from django.urls import path
from . import views

app_name = "invoice_finance"

urlpatterns = [
    path("", views.index, name="index"),

    # File upload
    path("upload-ledger-csv/", views.upload_ledger_csv, name="upload_ledger_csv"),

    # API endpoints
    path("api/fetch-ledger-data/", views.fetch_ledger_data, name="fetch_ledger_data"),
    path("api/submit-application/", views.submit_application, name="submit_application"),
    path("api/get-latest-transaction-id/", views.get_latest_transaction_id, name="get_latest_transaction_id"),

    # 🔹 Add these senders
    path("api/send-application-data/", views.send_application_data, name="send_application_data"),
    path("api/send-invoice-data/", views.send_invoice_data, name="send_invoice_data"),
    path("api/send-ledger-data/", views.send_ledger_data, name="send_ledger_data"),  # 👈 this was missing
]


