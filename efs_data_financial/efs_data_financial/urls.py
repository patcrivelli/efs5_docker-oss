# efs_data_financial/efs_data_financial/urls.py
from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),  
    path("api/financial/", include(("core.urls", "data_financial"), namespace="data_financial")),

    ]


