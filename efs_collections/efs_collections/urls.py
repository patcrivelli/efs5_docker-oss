# efs_collections/urls.py
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),                         # /
    path("collections/home/", views.collections_home, name="collections_home"),
    path("", include("core.urls")),                            # include app-level routes
]
