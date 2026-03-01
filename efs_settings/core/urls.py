# efs_settings/core/urls.py  (app-level)
from django.urls import path
from . import views

urlpatterns = [
    path("", views.settings_home, name="home"),                                # /
    path("settings/", views.settings_view, name="settings_view"),
    path("settings/home/", views.settings_home, name="settings_home"),
    path("create-originator/", views.create_originator, name="create_originator"),
    path("save-settings/", views.save_settings, name="save_settings"),
    path("post-settings/", views.post_settings, name="post_settings"),         # used by your template

    # Optional API-style alias (safe to add)
    path("api/settings/post/", views.post_settings, name="post_settings_api"),
]
