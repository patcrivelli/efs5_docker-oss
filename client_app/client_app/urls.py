"""
URL configuration for client_app project.
"""
# client_app/urls.py
"""
URL configuration for client_app project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # root
    path("", include(("home.urls", "home"), namespace="home")),

    path("users/", include("users.urls")),   # 👈 add this
    path("accounts/", include("allauth.urls")),

    path("invoice_finance/", include("invoice_finance.urls")),
    path("trade_finance/", include(("trade_finance.urls", "trade_finance"), namespace="trade_finance")),
    path("insurance_premium_funding/", include(("insurance_premium_funding.urls", "insurance_premium_funding"), namespace="insurance_premium_funding")),
    path("sif/", include(("sif.urls", "sif"), namespace="sif")),
    path("term_loan/", include(("term_loan.urls", "term_loan"), namespace="term_loan")),
    path("asset_finance/", include(("asset_finance.urls", "asset_finance"), namespace="asset_finance")),
    path("early_payment_program/", include(("early_payment_program.urls", "early_payment_program"), namespace="early_payment_program")),
]

