from django.urls import path
from .views import modal_apis, application_details, fetch_bureau_data, fetch_bank_statements, fetch_accounting_data, fetch_ppsr_data

urlpatterns = [
    path("modal/apis", modal_apis),
    path("apis/application-details", application_details),
    path("application-details", application_details),   # 👈 extra alias
    path("apis/fetch-bureau-data/", fetch_bureau_data),
    path("apis/fetch-bank-statements/", fetch_bank_statements, name="apis_fetch_bank_statements"),
    path("apis/fetch-accounting-data/", fetch_accounting_data, name="fetch_accounting_data"),
    path("apis/fetch-accounting_data/", fetch_accounting_data),
    path("apis/fetch-ppsr-data/", fetch_ppsr_data, name="fetch_ppsr_data"),  # 👈 FIXED

]