# early_payment_program/urls.py
from django.urls import path
from . import views

app_name = "early_payment_program"

urlpatterns = [
    # Page
    path("", views.index, name="index"),

    # Upload invoices
    path("api/upload/invoices/", views.upload_invoices, name="upload_invoices"),

    # Fetch invoices
    path("api/invoices/by-name/", views.fetch_scf_invoices_by_name, name="fetch_scf_invoices_by_name"),

    # Apply
    path("api/apply/", views.submit_scf_funding_application, name="submit_application"),

    # ✅ Send latest SCF application + invoices
    path("api/send/application/", views.send_scf_application_data, name="send_application"),
    path("api/send/invoices/", views.send_scf_invoice_data, name="send_invoices"),
]
