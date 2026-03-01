# /Users/patrickcrivelligmail.com/Desktop/efs4_docker/efs_lms_invoice_finance/efs_lms_invoice_finance/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # ✅ include core.urls and register the "invoice_finance" namespace
    path("", include(("core.urls", "invoice_finance"), namespace="invoice_finance")),
]
