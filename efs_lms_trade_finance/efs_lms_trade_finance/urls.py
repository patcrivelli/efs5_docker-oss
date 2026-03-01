from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # ✅ include core.urls and register the "trade_finance" namespace
    path("", include(("core.urls", "trade_finance"), namespace="trade_finance")),
]
