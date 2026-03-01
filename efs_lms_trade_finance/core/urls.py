from django.urls import path
from . import views

app_name = "trade_finance"  # ✅ gives you namespaced reversing

urlpatterns = [
    # Main page (renders shared base + your trade finance template)
    path("", views.trade_finance_page, name="trade_finance_page"),

    # Healthcheck/API
    path("api/ping/", views.ping, name="ping"),
]
