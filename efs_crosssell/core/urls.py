# efs_finance/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.finance_home, name="home"),                          # /
    path("finance/", views.finance_view, name="finance"),               # ✅ unified finance view
    path("finance/home/", views.finance_home, name="finance_home"),     # optional landing page
    path("create-originator/", views.create_originator, name="create_originator"),
    path("api/ingest_from_risk/", views.ingest_from_risk, name="ingest_from_risk"),
    path("api/update-transaction-state/", views.update_transaction_state, name="update_transaction_state"),

]
