from django.urls import path
from . import views

app_name = "bureau"

urlpatterns = [
    # Bureau APIs
    path("", views.bureau_page, name="bureau_page"),
    path('store-credit-report-data/', views.store_credit_report_data, name='store-credit-report-data'),
    path('store-datablock-data/', views.store_datablock_data, name='store-datablock-data'),
    path('store-company-search-data/', views.store_company_search_data, name='store-company-search-data'),
    # Optional: debug proxy
    path("proxy/", views.proxy_view, name="proxy_view"),
    path("api/bureau/credit-report", views.get_credit_report),
    path("api/bureau/credit-score", views.get_credit_score),
    path("api/bureau/credit-score-history", views.get_credit_score_history),

]
