# <project_module>/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("", include("core.urls")),   # ✅ expose the API endpoints
    path("admin/", admin.site.urls),
]
