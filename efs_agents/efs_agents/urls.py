from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path("", views.home, name="home"),                # /
    path("agents/home/", views.agents_home, name="agents_home"),  # /agents/home/
    path("", include("core.urls")),                   # include core app routes
    path("admin/", admin.site.urls),
]
