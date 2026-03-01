# efs_data_bankstatements/efs_data_bankstatements/urls.py
from django.contrib import admin
from django.urls import path, include
from core import views as core_views



urlpatterns = [
    path("admin/", admin.site.urls),

  
    # Optional extras (ping, future routes)
    path("", include("core.urls")),
]
