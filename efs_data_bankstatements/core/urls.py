# efs_data_bankstatements/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("ping/", views.ping, name="bank_ping"),
    path("modal/bank-statements/", views.bank_statements_modal, name="bank_statements_modal"),
    path("api/bankstatements/ingest-local/", views.ingest_local_bankstatements, name="ingest_local_bankstatements"),


    # 🔄 New endpoints used by efs_sales BFF proxy
    path("display_bank_account_data/<str:abn>/", views.display_bank_account_data, name="display_bank_account_data"),
    path("bankstatements/summary/<str:abn>/", views.bankstatements_summary, name="bankstatements_summary"),

    path("list-models/", views.list_models, name="list_models"),


    path("bankstatements/analyse-ai/<str:abn>/", views.bankstatements_analyse_and_ai, name="bankstatements_analyse_and_ai"),




]