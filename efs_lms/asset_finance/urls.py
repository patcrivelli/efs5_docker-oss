from django.urls import path
from . import views

urlpatterns = [
    path("", views.asset_finance_page, name="asset_finance"),
]
