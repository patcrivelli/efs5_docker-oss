# efs_drawdowns/urls.py
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),                      # /
    path("drawdowns/home/", views.drawdowns_home, name="drawdowns_home"),
    path("", include("core.urls")),                         # include app-level routes
]
