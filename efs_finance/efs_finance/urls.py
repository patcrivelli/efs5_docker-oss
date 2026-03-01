# efs_finance/urls.py
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),                      # /
    path("finance/home/", views.finance_home, name="finance_home"),
    path("", include("core.urls")),                         # include app-level urls
]
