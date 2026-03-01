# efs_lms/urls.py (project-level)
from django.contrib import admin
from django.urls import path, include
from invoice_finance import views as inv_views   # 👈 import your app view


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("core.urls", "efs_lms"), namespace="efs_lms")),
    path("", include("invoice_finance.urls")),   # mounts /api/ingest_transaction/

]
