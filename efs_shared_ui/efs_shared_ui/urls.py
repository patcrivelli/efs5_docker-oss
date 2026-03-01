# efs_shared_ui/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("create-originator/", views.create_originator, name="create_originator"),
]
