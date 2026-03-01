# bank_statements/urls.py
from django.urls import path
from . import views

app_name = "bankstatements"


urlpatterns = [
    path("ping/", views.ping, name="bank_statements_ping"),
    path("", views.bank_statements_page, name="bankstatements_page"),  # <-- add this
    path("ingest/", views.ingest_bankstatements, name="bankstatements_ingest"),
    path("api/accounts-with-transactions", views.accounts_with_transactions, name="accounts_with_transactions"),


]
