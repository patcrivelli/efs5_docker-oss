from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # ✅ include core.urls and register the "scf" namespace
    path("", include(("core.urls", "scf"), namespace="scf")),
]
