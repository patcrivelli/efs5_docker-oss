from django.urls import path
from . import views

urlpatterns = [
    path("", views.trade_finance_page, name="trade_finance"),
]