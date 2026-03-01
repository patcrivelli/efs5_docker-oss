# efs_sales/efs_sales/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sales/", include("core.urls")),

    # APIs used by the modal/buttons

    # Other APIs you already had
    path("api/credit-decision/", include("credit_decision.urls")),
    path("api/credit-decision/", include("credit_decision.urls")),  # <- used below from JS


    path("", include("core.urls")),  # 👈 adds /upload-financials/ (no /sales prefix)


]

