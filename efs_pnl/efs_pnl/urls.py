from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.home, name="home"),          # project root → pnl.html
    path("pnl/home/", views.pnl_home, name="pnl_home"),
    path("", include("core.urls")),             # delegate to core app
    path("admin/", admin.site.urls),
]
