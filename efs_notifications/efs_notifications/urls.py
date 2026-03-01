# efs_notifications/urls.py
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),                                # /
    path("notifications/home/", views.notifications_home, name="notifications_home"),
    path("", include("core.urls")),                                   # include app-level routes
]
