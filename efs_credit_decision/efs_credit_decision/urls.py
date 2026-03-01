from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # mount the app's URLs under /credit-decision/
    path("credit-decision/", include("core.urls")),
]
