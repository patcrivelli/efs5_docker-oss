# efs_notifications/core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.notifications_home, name="home"),                                  # /
    path("notifications/", views.notifications_view, name="notifications"),           # ✅ unified view
    path("notifications/home/", views.notifications_home, name="notifications_home"), # optional landing page
    path("create-originator/", views.create_originator, name="create_originator"),
]
