# efs_risk/urls.py
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("risk/home/", views.risk_home, name="risk_home"),
    path("", include("core.urls")),   # ✅ mount core urls at root
]
