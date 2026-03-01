from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("liquidity/home/", views.liquidity_home, name="liquidity_home"),
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
]
