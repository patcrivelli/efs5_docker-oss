from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("", include("core.urls")),   # all routes from core
    path("admin/", admin.site.urls),
    # if you later have apis for ops, add: path("apis/", include("apis.urls")),
]
