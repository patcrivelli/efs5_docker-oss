# efs_collections/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.collections_home, name="home"),                                # /
    path("collections/", views.collections_view, name="collections"),             # ✅ unified view
    path("collections/home/", views.collections_home, name="collections_home"),   # optional landing page
    path("create-originator/", views.create_originator, name="create_originator"),
]
